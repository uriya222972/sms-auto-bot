from flask import Flask, request, redirect, url_for, render_template, jsonify, session
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

# משתמשים לדוגמה
users = {
    'admin': hashlib.sha256('1234'.encode()).hexdigest()
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user') != 'admin':
            return "גישה חסומה", 403
        return f(*args, **kwargs)
    return decorated_function

def load_user_data():
    user = session.get('user', 'default')
    return load_data().get(user, {})

def save_user_data(data):
    user = session.get('user', 'default')
    full_data = load_data()
    full_data[user] = data
    save_data(full_data)

saved = load_user_data()
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
pending_names = saved.get("pending_names", {})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = hashlib.sha256(request.form["password"].encode()).hexdigest()
        if username in users and users[username] == password:
            session['user'] = username
            return redirect(url_for('index'))
        return "שם משתמש או סיסמה שגויים", 401
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def manage_users():
    if request.method == "POST":
        if 'delete_user' in request.form:
            user_to_delete = request.form["delete_user"]
            if user_to_delete in users:
                users.pop(user_to_delete)
                data = load_data()
                if user_to_delete in data:
                    del data[user_to_delete]
                    save_data(data)
        else:
            new_user = request.form["new_user"]
            new_pass = hashlib.sha256(request.form["new_pass"].encode()).hexdigest()
            users[new_user] = new_pass
    return render_template("manage_users.html", users=users)

@app.route("/", methods=["GET", "POST"])
def root():
    if request.method == "POST":
        return index()
    return redirect(url_for('login'))

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def index():
    print("POST request received")
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        print("Received data:", data)
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

    return render_template("index.html", rows=rows, responses=responses, send_log=send_log, total_sent=len(sent_indices), template=custom_template, response_map=response_map, activation_word=activation_word, filename=filename, target_goal=target_goal, bonus_goal=bonus_goal, bonus_active=bonus_active, stats=stats, encouragements=encouragements, name_map=name_map, greeting_template=greeting_template)

@app.route("/upload", methods=["POST"])
@login_required
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
@login_required
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
@login_required
def telephony():
    return render_template("telephony.html", response_map=response_map)

def send_sms(phone, text):
    payload = {"Data": {"Phones": phone, "Sender": SENDER, "Message": text}}
    headers = {"Authorization": AUTH_HEADER, "Content-Type": "application/json"}
    try:
        requests.post(API_URL, headers=headers, json=payload)
    except Exception as e:
        print("שגיאה בשליחת SMS:", e)

def save_all():
    save_user_data({
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

# override previous save_all
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
