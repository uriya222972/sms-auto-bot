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

@app.route("/update_goals", methods=["POST"])
def update_goals():
    global target_goal, bonus_goal, bonus_active
    target_goal = int(request.form.get("target_goal", 100))
    bonus_goal = int(request.form.get("bonus_goal", 0))
    bonus_active = request.form.get("bonus_active") == "on"
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

@app.route("/upload", methods=["POST"])
def upload():
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, filename
    file = request.files.get("file")
    if not file:
        return "לא נבחר קובץ", 400
    try:
        stream = TextIOWrapper(file.stream, encoding="utf-8")
        reader = csv.reader(stream)
        rows = [row[0].strip() for row in reader if row and row[0].strip()]
        sent_indices = set()
        phone_map = {}
        responses = {}
        send_log = {}
        scheduled_retries = {}
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
    except Exception as e:
        return f"שגיאה בקריאת הקובץ: {str(e)}", 500

@app.route("/reset", methods=["POST"])
def reset():
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, filename
    rows = []
    sent_indices = set()
    phone_map = {}
    responses = {}
    send_log = {}
    scheduled_retries = {}
    filename = ""
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

@app.route("/download")
def download():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Index", "Target Number", "To", "Send Time", "Response Label", "Response Time"])
    for i in range(len(rows)):
        row = [
            i + 1,
            rows[i],
            send_log.get(i, {}).get("to", ""),
            send_log.get(i, {}).get("time", ""),
            responses.get(i, {}).get("label", ""),
            responses.get(i, {}).get("time", "")
        ]
        writer.writerow(row)
    return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=data.csv"})

@app.route("/")
def home():
    now = datetime.now()
    retry_indices = [i for i, t in scheduled_retries.items() if t <= now and i not in sent_indices]
    if retry_indices:
        retry_index = min(retry_indices)
        scheduled_retries.pop(retry_index)
        sent_indices.discard(retry_index)

    stats = {r["label"]: 0 for r in response_map.values()}
    for r in responses.values():
        if "label" in r:
            stats[r["label"]] = stats.get(r["label"], 0) + 1

    retry_times = {}
    for i, dt in scheduled_retries.items():
        delta = dt - now
        if delta.total_seconds() > 0:
            retry_times[i] = str(delta).split('.')[0]

    total_sent = len(sent_indices)
    return render_template("index.html",
                           rows=rows,
                           responses=responses,
                           send_log=send_log,
                           response_map=response_map,
                           total_sent=total_sent,
                           template=custom_template,
                           activation_word=activation_word,
                           filename=filename,
                           stats=stats,
                           retry_times=retry_times,
                           target_goal=target_goal,
                           bonus_goal=bonus_goal,
                           bonus_active=bonus_active)
