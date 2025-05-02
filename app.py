from flask import Flask, request, Response, render_template_string, redirect, url_for, session as flask_session
import requests
import xml.etree.ElementTree as ET
import json
import os

app = Flask(__name__)
app.secret_key = "verysecretkey"

USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

if not users:
    users = {
        "22uriya22": {
            "password": "222972uriya",
            "phone": "0585906040",
            "inforu_username": "22uriya22",
            "inforu_password": "222972Uriya!",
            "token": "4a549e05-8668-448f-b3a7-5ee7816ee0ad",
            "sender": "0537038545"
        }
    }
    save_users()

session = {
    'last_message': {},
    'waiting_for_group_choice': {}
}

@app.route('/')
def index():
    return redirect(url_for('login'))

def get_user_by_phone(phone):
    for username, data in users.items():
        if data["phone"] == phone:
            return username, data
    return None, None

def send_sms(phone, message, user_data):
    clean_phone = phone.strip().replace('-', '').replace(' ', '')
    payload = f"""
    <Inforu>
      <User>
        <Username>{user_data['inforu_username']}</Username>
        <Password>{user_data['inforu_password']}</Password>
      </User>
      <Content Type=\"sms\">
        <Message>{message}</Message>
      </Content>
      <Recipients>
        <PhoneNumber>{clean_phone}</PhoneNumber>
      </Recipients>
      <Settings>
        <Sender>{user_data['sender']}</Sender>
      </Settings>
    </Inforu>
    """
    headers = {'Content-Type': 'application/xml'}
    print("== PAYLOAD ================")
    print(payload)
    print("============================")
    response = requests.post("https://api.inforu.co.il/SendMessageXml.ashx", data=payload.encode('utf-8'), headers=headers)
    print("== תשובת Inforu ================")
    print(response.text)
    print("=================================")
    return response

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    message = ""
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        username, user_data = get_user_by_phone(phone)
        if user_data:
            msg = f"שם משתמש: {username}\nסיסמה: {user_data['password']}"
            temp_user_data = user_data.copy()
            temp_user_data["sender"] = "0001"
            send_sms(phone, msg, temp_user_data)
            message = "הסיסמה נשלחה בהודעת SMS."
        else:
            message = "מספר לא נמצא."
    return render_template_string('''
        <h2>שחזור סיסמה</h2>
        <form method="post">
            <input name="phone" placeholder="מספר טלפון">
            <button type="submit">שלח לי סיסמה</button>
        </form>
        <p>{{ message }}</p>
        <a href="{{ url_for('login') }}">חזרה להתחברות</a>
    ''', message=message)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            flask_session['admin'] = username
            return redirect(url_for('admin_panel'))
        return "שגיאת התחברות"
    return render_template_string('''
        <form method="post">
            <input name="username" placeholder="שם משתמש">
            <input name="password" type="password" placeholder="סיסמה">
            <button type="submit">התחבר</button>
        </form>
        <a href="{{ url_for('forgot_password') }}">שכחתי סיסמה</a>
    ''')

@app.route('/logout')
def logout():
    flask_session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
