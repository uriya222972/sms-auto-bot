from flask import Flask, request, redirect, url_for, render_template_string, Response, jsonify
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

@app.route("/", methods=["GET", "POST"])
def home():
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, custom_template, response_map, activation_word, filename

    now = datetime.now()
    retry_indices = [i for i, t in scheduled_retries.items() if t <= now and i not in sent_indices]
    if retry_indices:
        retry_index = min(retry_indices)
        scheduled_retries.pop(retry_index)
        sent_indices.discard(retry_index)

    if request.method == "POST":
        if request.form.get("IncomingXML"):
            try:
                raw_xml = request.form.get("IncomingXML")
                root = ET.fromstring(raw_xml)
                sender = root.findtext("PhoneNumber")
                message = root.findtext("Message")

                if not activation_word:
                    return "Activation word is required", 400

                if sender not in phone_map and message.strip() != activation_word:
                    return "Ignored: Activation word not received yet", 200

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
                            if r["callback_required"]:
                                hours = r["hours"]
                                if last_index is not None:
                                    scheduled_retries[last_index] = datetime.now() + timedelta(hours=hours)

                next_index = 0
                while next_index < len(rows) and next_index in sent_indices:
                    next_index += 1
                if next_index < len(rows):
                    next_message = rows[next_index]
                    personalized_message = custom_template.replace("{next}", next_message)
                    headers = {
                        "Content-Type": "application/json; charset=utf-8",
                        "Authorization": AUTH_HEADER
                    }
                    payload = {
                        "Sender": SENDER,
                        "Message": personalized_message,
                        "Recipients": [{"Phone": sender}]
                    }
                    res = requests.post(API_URL, headers=headers, json=payload)
                    res.raise_for_status()
                    send_log[next_index] = {
                        "to": sender,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "message": personalized_message
                    }
                    phone_map[sender].append(next_index)
                    sent_indices.add(next_index)

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
                    "filename": filename
                })

                return "OK"
            except Exception as e:
                return str(e), 400

        # שאר הטפסים לניהול...
        if "upload_csv" in request.form and "csv_file" in request.files:
            file = request.files["csv_file"]
            if file.filename.endswith(".csv"):
                decoded = TextIOWrapper(file, encoding='utf-8')
                reader = csv.reader(decoded)
                rows = [row[0] for row in reader if row]
                filename = file.filename
                sent_indices.clear()
                phone_map.clear()
                responses.clear()
                send_log.clear()
                scheduled_retries.clear()

        if "update_activation_word" in request.form:
            activation_word = request.form.get("activation_word", activation_word)

        if "update_template" in request.form:
            custom_template = request.form.get("template", custom_template)

        if "update_response_map" in request.form:
            for key in response_map:
                label = request.form.get(f"label_{key}", response_map[key]["label"])
                callback = request.form.get(f"callback_{key}") == "on"
                hours = int(request.form.get(f"hours_{key}", response_map[key]["hours"]))
                response_map[key] = {"label": label, "callback_required": callback, "hours": hours}

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
            "filename": filename
        })

    total_sent = len(sent_indices)
    stats = {r["label"]: 0 for r in response_map.values()}
    for r in responses.values():
        if "label" in r:
            stats[r["label"]] = stats.get(r["label"], 0) + 1

    html = '''...'''  # (השארת תבנית html כמו קודם)
    return render_template_string(html, rows=rows, total_sent=total_sent, stats=stats, template=custom_template, filename=filename, activation_word=activation_word, response_map=response_map)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
