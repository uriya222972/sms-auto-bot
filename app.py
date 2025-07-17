from flask import Flask, request, redirect, url_for, render_template, jsonify, session, flash
from functools import wraps
import requests
import csv
from io import TextIOWrapper
from datetime import datetime
import random
import hashlib
from storage import save_data, load_data

app = Flask(__name__)
app.secret_key = 'שנה_את_זה_לסוד_אמיתי'

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

users = {
    'admin': hashlib.sha256('1234'.encode()).hexdigest(),
    '22uriya22': hashlib.sha256('972uriya'.encode()).hexdigest()
}

def load_user_data():
    user = session.get('user', 'default')
    return load_data().get(user, {})

def save_user_data(data):
    user = session.get('user', 'default')
    full_data = load_data()
    full_data[user] = data
    save_data(full_data)

def get_user_variables():
    saved = load_user_data()
    return {
        "rows": saved.get("rows", []),
        "sent_indices": set(saved.get("sent_indices", [])),
        "phone_map": saved.get("phone_map", {}),
        "responses": saved.get("responses", {}),
        "send_log": saved.get("send_log", {}),
        "scheduled_retries": saved.get("scheduled_retries", {}),
        "custom_template": saved.get("custom_template", "המספר הבא הוא {next}."),
        "response_map": saved.get("response_map", {
            "1": {"label": "תרם", "callback_required": False, "hours": 0, "followups": []},
            "2": {"label": "לא תרם", "callback_required": False, "hours": 0, "followups": []},
            "3": {"label": "לא ענה", "callback_required": True, "hours": 5, "followups": []},
            "4": {"label": "לחזור בעוד 5 שעות", "callback_required": True, "hours": 5, "followups": []},
            "5": {"label": "לחזור בעוד 8 שעות", "callback_required": True, "hours": 8, "followups": []},
            "6": {"label": "הבטיח לתרום", "callback_required": True, "hours": 2, "followups": []},
            "7": {"label": "שיחה חוזרת בערב", "callback_required": True, "hours": 6, "followups": []},
            "8": {"label": "מספר שגוי", "callback_required": False, "hours": 0, "followups": []},
            "9": {"label": "סיים לדבר", "callback_required": False, "hours": 0, "followups": []}
        }),
        "encouragements": saved.get("encouragements", {
            "1": ["יישר כח! אלוף! {next}"],
            "2": ["לא נורא, כנראה לא הסתדר לו – בטלפון הבא בע"ה. {next}"],
            "3": ["לא ענה – ממשיכים לטלפון הבא. {next}"],
            "4": ["נחזור אליו בעוד כמה שעות – בינתיים קדימה! {next}"],
            "5": ["נחזור בעוד 8 שעות, אל תתייאש! {next}"],
            "6": ["מצוין, מחכים שיתרום – לטלפון הבא! {next}"],
            "7": ["בערב נתקשר שוב – עכשיו ממשיכים. {next}"],
            "8": ["מספר שגוי – לא נורא, קדימה. {next}"],
            "9": ["סיים לדבר – כל הכבוד! {next}"]
        }),
        "activation_word": saved.get("activation_word", "התחל"),
        "end_word": saved.get("end_word", "סיום"),
        "end_message": saved.get("end_message", "תודה רבה! ביצעת {count} שיחות. כל הכבוד!"),
        "filename": saved.get("filename", ""),
        "target_goal": saved.get("target_goal", 100),
        "bonus_goal": saved.get("bonus_goal", 0),
        "bonus_active": saved.get("bonus_active", False),
        "name_map": saved.get("name_map", {}),
        "greeting_template": saved.get("greeting_template", "שלום! נא לשלוח את שמך כדי להתחיל."),
        "pending_names": saved.get("pending_names", {})
    }


@app.route("/admin")
def admin_panel():
    return render_template("admin.html")


@app.route("/save", methods=["POST"])
@login_required
def auto_save():
    data = request.get_json()
    if not data or "key" not in data or "value" not in data:
        return "Invalid request", 400
    key = data["key"]
    value = data["value"]
    vars = get_user_variables()
    if key in vars:
        vars[key] = value
        save_user_data(vars)
        return "Saved"
    return "Unknown key", 400


@app.route("/", methods=["GET", "POST"])
def root():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        phone = data.get("Phone")
        text = data.get("Message")
        if phone and text:
            session["user"] = "default"
            return index()
        else:
            return "Unauthorized", 401

    # בקשת GET רגילה: נטען את הדשבורד כברירת מחדל
    session["user"] = "default"
    return index()



@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            error = "נא להזין שם משתמש וסיסמה"
        else:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            if users.get(username) == hashed:
                session["user"] = username
                if username == '22uriya22':
                    return redirect(url_for("admin_panel"))
                return redirect(url_for("index"))
            else:
                error = "שם משתמש או סיסמה שגויים"
    return render_template("login.html", error=error)

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def index():
    vars = get_user_variables()
    rows = vars["rows"]
    sent_indices = vars["sent_indices"]
    phone_map = vars["phone_map"]
    responses = vars["responses"]
    send_log = vars["send_log"]
    scheduled_retries = vars["scheduled_retries"]
    custom_template = vars["custom_template"]
    response_map = vars["response_map"]
    encouragements = vars["encouragements"]
    activation_word = vars["activation_word"]
    filename = vars["filename"]
    target_goal = vars["target_goal"]
    bonus_goal = vars["bonus_goal"]
    bonus_active = vars["bonus_active"]
    name_map = vars["name_map"]
    greeting_template = vars["greeting_template"]
    pending_names = vars["pending_names"]

    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        phone = data.get("Phone")
        text = data.get("Message")

        if not phone or not text:
            return "Missing parameters", 400

        if phone in pending_names:
            name = text.strip()
            name_map[phone] = name
            del pending_names[phone]
            for i in range(len(rows)):
                if i not in sent_indices:
                    sent_indices.add(i)
                    send_log[i] = {"to": phone, "phone": phone, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message": "נשלח לפי שם"}
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

        for digit in response_map:
            if text.strip().endswith(digit) and text.strip()[:-1].strip().isdigit():
                num = text.strip()[:-1].strip()
                for i, val in enumerate(rows):
                    if val == num:
                        label = response_map[digit]["label"]
                        responses[i] = {
                            "message": digit,
                            "label": label,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        messages = encouragements.get(digit, [])
                        next_number = next((rows[j] for j in range(len(rows)) if j not in sent_indices), None)
                        if messages and next_number:
                            msg = random.choice(messages).replace("{next}", next_number)
                            send_sms(phone, msg)
                        save_all()
                        return "OK"

        return "הודעה לא זוהתה"

    stats = {}
    for r in responses.values():
        label = r.get("label", "לא ידוע")
        stats[label] = stats.get(label, 0) + 1

    percentage = round((len(sent_indices) / target_goal) * 100, 2) if target_goal else 0

    return render_template("index.html", rows=rows, responses=responses, send_log=send_log, total_sent=len(sent_indices), template=custom_template, response_map=response_map, activation_word=activation_word, filename=filename, target_goal=target_goal, bonus_goal=bonus_goal, bonus_active=bonus_active, stats=stats, encouragements=encouragements, name_map=name_map, greeting_template=greeting_template, percentage=percentage)

@app.route("/view")
@login_required
def view_stats():
    vars = get_user_variables()
    responses = vars["responses"]
    target_goal = vars["target_goal"]
    sent_count = len(vars["sent_indices"])

    stats = {}
    for r in responses.values():
        label = r.get("label", "לא ידוע")
        stats[label] = stats.get(label, 0) + 1

    percentage = round((sent_count / target_goal) * 100, 2) if target_goal else 0

    return render_template("view.html", stats=stats, percentage=percentage, target_goal=target_goal, sent_count=sent_count)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    vars = get_user_variables()
    rows = vars["rows"]
    file = request.files.get("file")
    if not file:
        return "לא נבחר קובץ", 400

    try:
        filename = file.filename
        stream = TextIOWrapper(file.stream, encoding="utf-8-sig")
        csv_input = csv.reader(stream)
        new_numbers = [row[0].strip() for row in csv_input if row and len(row) > 0 and row[0].strip()]
        rows.extend(new_numbers)
        vars["filename"] = filename
        vars["sent_indices"] = list(vars.get("sent_indices", set()))
        save_user_data(vars)
        return redirect(url_for("index"))
    except Exception as e:
        return f"שגיאה בהעלאת הקובץ: {e}", 500

@app.route("/reset", methods=["POST"])
@login_required
def reset():
    vars = get_user_variables()
    vars["rows"].clear()
    vars["sent_indices"].clear()
    vars["phone_map"].clear()
    vars["responses"].clear()
    vars["send_log"].clear()
    vars["scheduled_retries"].clear()
    vars["name_map"].clear()
    vars["pending_names"].clear()
    save_user_data(vars)
    return redirect(url_for("index"))

@app.route("/telephony")
@login_required
def telephony():
    vars = get_user_variables()
    return render_template("telephony.html", response_map=vars["response_map"])

def send_sms(phone, text):
    payload = {"Data": {"Phones": phone, "Sender": SENDER, "Message": text}}
    headers = {"Authorization": AUTH_HEADER, "Content-Type": "application/json"}
    try:
        requests.post(API_URL, headers=headers, json=payload)
    except Exception as e:
        print("שגיאה בשליחת SMS:", e)


