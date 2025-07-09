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
            manual_input = request.form.get("manual_response", "").strip()
            parts = manual_input.split()
            if len(parts) == 2:
                phone, digit = parts
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

@app.route("/")
def home():
    # אפשרות תצוגה ראשית או שליחת נתונים
    return render_template("index.html",
                           rows=rows,
                           responses=responses,
                           send_log=send_log,
                           response_map=response_map,
                           total_sent=len(sent_indices),
                           template=custom_template,
                           activation_word=activation_word,
                           filename=filename,
                           stats={r["label"]: list(responses.values()).count(r) for r in response_map.values()},
                           retry_times={},
                           target_goal=target_goal,
                           bonus_goal=bonus_goal,
                           bonus_active=bonus_active)

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
