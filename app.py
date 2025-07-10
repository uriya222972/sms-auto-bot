from flask import Flask, request, redirect, url_for, render_template, Response, jsonify
import requests
import csv
from io import TextIOWrapper, StringIO
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from storage import save_data, load_data
import random

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
response_map = saved.get("response_map", {
    str(i): {
        "label": f"הגדרה {i}",
        "callback_required": False,
        "hours": 0,
        "followups": []
    } for i in range(1, 10)
})
encouragements = saved.get("encouragements", {})
activation_word = saved.get("activation_word", "התחל")
filename = saved.get("filename", "")
target_goal = saved.get("target_goal", 100)
bonus_goal = saved.get("bonus_goal", 0)
bonus_active = saved.get("bonus_active", False)
name_map = saved.get("name_map", {})
greeting_template = saved.get("greeting_template", "שלום! נא לשלוח את שמך כדי להתחיל.")

@app.route("/")
def index():
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
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, name_map
    rows.clear()
    sent_indices.clear()
    phone_map.clear()
    responses.clear()
    send_log.clear()
    scheduled_retries.clear()
    name_map.clear()
    save_all()
    return redirect(url_for("index"))

@app.route("/telephony")
def telephony():
    return render_template("telephony.html", response_map=response_map)

@app.route("/response-options")
def response_options():
    return jsonify([{"value": k, "label": v["label"]} for k, v in response_map.items()])

@app.route("/next-number")
def next_number():
    agent = request.args.get("agent")
    if not agent:
        return "Missing agent", 400
    name_map[agent] = agent
    for i in range(len(rows)):
        if i not in sent_indices:
            phone_map.setdefault(agent, []).append(i)
            sent_indices.add(i)
            send_log[i] = {
                "to": agent,
                "phone": agent,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "נמסר לטלפן"
            }
            save_all()
            return rows[i]
    return ""

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
            # Send encouragement if available
            next_number = ""
            for j in range(len(rows)):
                if j not in sent_indices:
                    next_number = rows[j]
                    break
            messages = encouragements.get(response, [])
            if messages and next_number:
                text = random.choice(messages).replace("{next}", next_number)
                send_sms(agent, text)
            save_all()
            return "OK"
    return "לא נמצא", 400

@app.route("/manual-update", methods=["POST"])
def manual_update():
    data = request.get_json()
    phone = data.get("phone")
    response = data.get("response")
    if not phone or not response:
        return "Missing data", 400
    for i in range(len(rows)):
        if rows[i] == phone:
            responses[i] = {
                "message": response,
                "label": response_map.get(response, {}).get("label", "לא ידוע"),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            send_log[i] = {
                "to": "עודכן ידנית",
                "phone": phone,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "עדכון ידני"
            }
            sent_indices.add(i)
            save_all()
            return "OK"
    return "לא נמצא", 404

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
        "encouragements": encouragements
    })
