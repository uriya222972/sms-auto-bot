from flask import Flask, request, redirect, url_for, render_template, Response, jsonify
import requests
import csv
from io import TextIOWrapper, StringIO
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from storage import save_data, load_data

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

saved = load_data()
rows = saved.get("rows", [])
sent_indices = set(saved.get("sent_indices", []))
phone_map = saved.get("phone_map", {})
responses = saved.get("responses", {})
send_log = saved.get("send_log", {})
scheduled_retries = saved.get("scheduled_retries", {})
custom_template = saved.get("custom_template", "יישר כח! המספר הבא אליו צריך להתקשר הוא {next}. תודה!")
response_map = saved.get("response_map", {str(i): {"label": f"הגדרה {i}", "callback_required": False, "hours": 0} for i in range(1, 10)})
activation_word = saved.get("activation_word", "התחל")
filename = saved.get("filename", "")
target_goal = saved.get("target_goal", 100)
bonus_goal = saved.get("bonus_goal", 0)
bonus_active = saved.get("bonus_active", False)

@app.route("/upload", methods=["POST"])
def upload():
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, filename
    file = request.files.get("file")
    if file and file.filename.endswith(".csv"):
        stream = TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.reader(stream)
        rows = [row[0] for row in reader if row]
        sent_indices.clear()
        phone_map.clear()
        responses.clear()
        send_log.clear()
        scheduled_retries.clear()
        filename = file.filename
        save_all()
        return redirect(url_for("home"))
    return "Invalid file", 400

@app.route("/telephony", methods=["GET", "POST"])
def telephony():
    global responses, sent_indices
    message = ""
    selected_digit = None
    current_index = None
    next_number = None

    if request.method == "POST":
        if "mark_manual" in request.form:
            phone = request.form.get("manual_number", "").strip()
            digit = request.form.get("manual_digit", "").strip()
            label = response_map.get(digit, {}).get("label", "")
            for idx, log in send_log.items():
                if log.get("to") == phone:
                    responses[idx] = {
                        "message": digit,
                        "label": label,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    message = f"עודכן: {phone} ← {label}"
                    save_all()
                    break
            else:
                message = "לא נמצא מספר כזה ביומן השליחות."

        elif "telephony_submit" in request.form:
            selected_digit = request.form.get("digit")
            current_index = int(request.form.get("current_index"))
            label = response_map.get(selected_digit, {}).get("label", "")
            responses[current_index] = {
                "message": selected_digit,
                "label": label,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            sent_indices.add(current_index)
            message = f"הוגדר: {rows[current_index]} ← {label}"
            save_all()

    i = 0
    while i < len(rows) and i in sent_indices:
        i += 1
    if i < len(rows):
        next_number = rows[i]
        current_index = i

    return render_template("telephony.html",
                           number=next_number,
                           index=current_index,
                           response_map=response_map,
                           message=message)

@app.route("/", methods=["GET", "POST"])
def home():
    global activation_word, custom_template, response_map

    if request.method == "POST":
        if "update_activation_word" in request.form:
            activation_word = request.form.get("activation_word", activation_word)
        if "update_template" in request.form:
            custom_template = request.form.get("template", custom_template)
        if "update_response_map" in request.form:
            for key in response_map:
                label = request.form.get(f"label_{key}", f"הגדרה {key}")
                callback = request.form.get(f"callback_{key}") == "on"
                hours = int(request.form.get(f"hours_{key}", 0)) if callback else 0
                response_map[key] = {
                    "label": label,
                    "callback_required": callback,
                    "hours": hours
                }
        save_all()
        return redirect(url_for("home"))

    stats = {r["label"]: 0 for r in response_map.values()}
    for r in responses.values():
        if "label" in r:
            stats[r["label"]] = stats.get(r["label"], 0) + 1

    return render_template("index.html",
                           rows=rows,
                           responses=responses,
                           send_log=send_log,
                           response_map=response_map,
                           total_sent=len(sent_indices),
                           template=custom_template,
                           activation_word=activation_word,
                           filename=filename,
                           stats=stats,
                           retry_times={},
                           target_goal=target_goal,
                           bonus_goal=bonus_goal,
                           bonus_active=bonus_active)

@app.route("/sms", methods=["POST"])
def sms():
    global phone_map, responses, send_log, scheduled_retries, sent_indices
    try:
        raw_xml = request.form.get("IncomingXML")
        root = ET.fromstring(raw_xml)
        sender = root.findtext("PhoneNumber")
        message = root.findtext("Message")

        if not sender or not message:
            return "Missing data", 400

        message = message.strip()

        if not activation_word:
            return "Missing activation word", 400

        if sender not in phone_map and message != activation_word:
            return "Ignored", 200

        if sender not in phone_map:
            phone_map[sender] = []

        last_index = None
        if phone_map[sender]:
            last_index = phone_map[sender][-1]
            previous = responses.get(last_index, {}).get("message")
            if previous != message:
                label = response_map.get(message, {}).get("label", "")
                responses[last_index] = {
                    "message": message,
                    "label": label,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                if message in response_map:
                    r = response_map[message]
                    if r["callback_required"] and last_index is not None:
                        scheduled_retries[last_index] = datetime.now() + timedelta(hours=r["hours"])

        next_index = 0
        while next_index < len(rows) and next_index in sent_indices:
            next_index += 1
        if next_index < len(rows):
            next_message = rows[next_index]
            personalized = custom_template.replace("{next}", next_message)
            headers = {"Content-Type": "application/json", "Authorization": AUTH_HEADER}
            payload = {"Sender": SENDER, "Message": personalized, "Recipients": [{"Phone": sender}]}
            res = requests.post(API_URL, headers=headers, json=payload)
            res.raise_for_status()
            send_log[next_index] = {
                "to": sender,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": personalized
            }
            phone_map[sender].append(next_index)
            sent_indices.add(next_index)

        save_all()
        return "OK"
    except Exception as e:
        return str(e), 400

def save_all():
    save_data({
        "rows": rows,
        "sent_indices": list(sent_indices),
        "phone_map": phone_map,
        "responses": responses,
        "send_log": send_log,
        "scheduled_retries": scheduled_retries,
        "custom_template": custom_template,
        "response_map": response_map,
        "activation_word": activation_word,
        "filename": filename,
        "target_goal": target_goal,
        "bonus_goal": bonus_goal,
        "bonus_active": bonus_active
    })
