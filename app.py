from flask import Flask, request, redirect, url_for, render_template, jsonify
import requests
import csv
from io import TextIOWrapper
from datetime import datetime
import random
from storage import save_data, load_data

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

# טענת נתונים
saved = load_data()
rows = saved.get("rows", [])
sent_indices = set(saved.get("sent_indices", []))
phone_map = saved.get("phone_map", {})
responses = saved.get("responses", {})
send_log = saved.get("send_log", {})
scheduled_retries = saved.get("scheduled_retries", {})
custom_template = saved.get("custom_template", "יישר כח {name}! המספר הבא הוא {next}.")
response_map = saved.get("response_map", {str(i): {"label": f"הגדרה {i}", "callback_required": False, "hours": 0, "followups": []} for i in range(1, 10)})
encouragements = saved.get("encouragements", {})
activation_word = saved.get("activation_word", "התחל")
filename = saved.get("filename", "")
target_goal = saved.get("target_goal", 100)
bonus_goal = saved.get("bonus_goal", 0)
bonus_active = saved.get("bonus_active", False)
name_map = saved.get("name_map", {})
greeting_template = saved.get("greeting_template", "שלום! נא לשלוח את שמך כדי להתחיל.")
pending_names = saved.get("pending_names", {})  # טלפונים שממתינים לשם

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        phone = request.form.get("Phone") or request.json.get("Phone")
        text = request.form.get("Message") or request.json.get("Message")
        if not phone or not text:
            return "Missing parameters", 400

        if phone in pending_names:
            # קיבלנו שם, שולחים מספר להתקשרות
            name = text.strip()
            name_map[phone] = name
            del pending_names[phone]
            for i in range(len(rows)):
                if i not in sent_indices:
                    sent_indices.add(i)
                    send_log[i] = {
                        "to": phone,
                        "phone": phone,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "message": "נשלח לפי שם"
                    }
                    msg = custom_template.replace("{next}", rows[i]).replace("{name}", name)
                    send_sms(phone, msg)
                    save_all()
                    return "שם נקלט ונשלחה הודעה"
            return "אין מספרים זמינים"

        if text.strip() == activation_word:
            pending_names[phone] = True
            send_sms(phone, greeting_template)
            save_all()
            return "הודעת התחלה נקלטה"

        return "הודעה לא זוהתה"

    # GET רגיל מחזיר ממשק ניהול
    stats = {}
    for r in responses.values():
        label = r.get("label", "לא ידוע")
        stats[label] = stats.get(label, 0) + 1
    return render_template("index.html",
        rows=rows,
        responses=responses,
        send_log=send_log,
        total_sent=len(sent_indices),
        template=custom_template,
        response_map=response_map,
        activation_word=activation_word,
        filename=filename,
        target_goal=target_goal,
        bonus_goal=bonus_goal,
        bonus_active=bonus_active,
        stats=stats,
        encouragements=encouragements,
        name_map=name_map,
        greeting_template=greeting_template
    )

@app.route("/upload", methods=["POST"])
def upload():
    global rows, filename
    file = request.files.get("file")
    if not file:
        return "לא נבחר קובץ", 400
    filename = file.filename
    stream = TextIOWrapper(file.stream, encoding="utf-8-sig")
    csv_input = csv.reader(stream)
    new_numbers = [row[0] for row in csv_input if row]
    rows.extend(new_numbers)
    save_all()
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset():
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, name_map, pending_names
    rows.clear()
    sent_indices.clear()
    phone_map.clear()
    responses.clear()
    send_log.clear()
    scheduled_retries.clear()
    name_map.clear()
    pending_names.clear()
    save_all()
    return redirect(url_for("index"))

@app.route("/telephony")
def telephony():
    return render_template("telephony.html", response_map=response_map)

@app.route("/submit-response", methods=["POST"])
def submit_response():
    data = request.get_json()
    agent = data.get("agent")
    response = data.get("response")
    if not agent or not response:
        return "Missing data", 400

    for i in reversed(phone_map.get(agent, [])):
        if i in send_log:
            label = response_map.get(response, {}).get("label", "לא ידוע")
            responses[i] = {
                "message": response,
                "label": label,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            # עידוד
            next_number = next((rows[j] for j in range(len(rows)) if j not in sent_indices), None)
            messages = encouragements.get(response, [])
            if messages and next_number:
                text = random.choice(messages).replace("{next}", next_number)
                send_sms(agent, text)
            save_all()
            return "OK"
    return "לא נמצא", 400

def send_sms(phone, text):
    payload = {
        "Data": {
            "Phones": phone,
            "Sender": SENDER,
            "Message": text
        }
    }
    headers = {
        "Authorization": AUTH_HEADER,
        "Content-Type": "application/json"
    }
    try:
        requests.post(API_URL, headers=headers, json=payload)
    except Exception as e:
        print("שגיאה בשליחת SMS:", e)

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
        "bonus_active": bonus_active,
        "name_map": name_map,
        "greeting_template": greeting_template,
        "encouragements": encouragements,
        "pending_names": pending_names
    })
