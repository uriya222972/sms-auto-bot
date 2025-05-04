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
    if not clean_phone.isdigit() or len(clean_phone) != 10:
        print("❌ מספר טלפון לא חוקי לשליחה:", clean_phone)
        return None

    payload = f'''<Inforu>
<User>
<Username>{user_data["inforu_username"]}</Username>
<Password>{user_data["inforu_password"]}</Password>
</User>
<Content Type="sms">
<Message><![CDATA[{message}]]></Message>
</Content>
<Recipients>
<PhoneNumber>{clean_phone}</PhoneNumber>
</Recipients>
<Settings>
<Sender>{user_data["sender"]}</Sender>
</Settings>
</Inforu>'''

    headers = {'Content-Type': 'application/xml'}
    print("== PAYLOAD ================\n" + payload + "\n============================")
    response = requests.post("https://api.inforu.co.il/SendMessageXml.ashx", data=payload.encode('utf-8'), headers=headers)
    print("== תשובת Inforu ================\n" + response.text + "\n=================================")
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
    error = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            flask_session['admin'] = username
            return redirect(url_for('admin_panel'))
        error = "שם משתמש או סיסמה שגויים."
    return render_template_string('''
        <form method="post">
            <input name="username" placeholder="שם משתמש">
            <input name="password" type="password" placeholder="סיסמה">
            <button type="submit">התחבר</button>
        </form>
        <p style="color:red">{{ error }}</p>
        <a href="{{ url_for('forgot_password') }}">שכחתי סיסמה</a>
    ''', error=error)

@app.route('/logout')
def logout():
    flask_session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_panel():
    if 'admin' not in flask_session:
        return redirect(url_for('login'))
    return render_template_string("""
        <h2>דף ניהול</h2>
        <p>ברוך הבא {{ flask_session['admin'] }}</p>
        <a href="{{ url_for('view_inbound_log') }}">יומן הודעות נכנסות</a><br>
        <a href="{{ url_for('logout') }}">התנתק</a>
    """)

@app.route('/inbound', methods=['POST'])
def inbound_sms():
    xml_data = request.data.decode('utf-8')
    
    with open("inbound_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"[קלט גולמי]\n{xml_data}\n")

    try:
        root = ET.fromstring(xml_data)
        phone = root.findtext('PhoneNumber')
        message = root.findtext('Message')
        with open("inbound_log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(f"מספר: {phone}\nהודעה: {message}\n---\n")
    except Exception as e:
        with open("inbound_log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(f"שגיאה בקריאת XML: {str(e)}\n---\n")
    
    return Response("<Inforu>OK</Inforu>", mimetype='application/xml')

@app.route('/inbound-log')
def view_inbound_log():
    if not os.path.exists("inbound_log.txt"):
        return "לא התקבלו הודעות עדיין."
    with open("inbound_log.txt", "r", encoding="utf-8") as f:
        content = f.read()
    return render_template_string("""
        <h2>יומן הודעות נכנסות</h2>
        <pre style='direction: rtl; background-color: #f4f4f4; padding: 15px; border-radius: 8px;'>{{ content }}</pre>
        <a href='{{ url_for("index") }}'>חזרה</a>
    """, content=content)

if __name__ == '__main__':
    app.run(debug=True)
