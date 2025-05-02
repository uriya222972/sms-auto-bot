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

def get_groups(token):
    url = "https://api.inforu.co.il/Contact/GetGroups"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    groups = res.json().get('Groups', [])
    return [(i+1, g['GroupName'], g['GroupId']) for i, g in enumerate(groups)]

def get_group_contacts(group_id, token):
    url = f"https://api.inforu.co.il/Contact/GetGroupContacts?groupId={group_id}"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    contacts = res.json().get('Contacts', [])
    return [c['Phone'] for c in contacts]

def send_sms(phone, message, user_data):
    payload = f"""
    <Inforu>
      <User>
        <Username>{user_data['inforu_username']}</Username>
        <Password>{user_data['inforu_password']}</Password>
      </User>
      <Content Type="sms">
        <Message>{message}</Message>
      </Content>
      <Recipients>
        <PhoneNumber>{phone}</PhoneNumber>
      </Recipients>
      <Settings>
        <Sender>{user_data['sender']}</Sender>
      </Settings>
    </Inforu>
    """
    headers = {'Content-Type': 'application/xml'}
    return requests.post("https://api.inforu.co.il/SendMessageXml.ashx", data=payload.encode('utf-8'), headers=headers)

@app.route('/inbound', methods=['POST'])
def inbound_sms():
    xml_data = request.data.decode('utf-8')
    root = ET.fromstring(xml_data)
    phone = root.findtext('PhoneNumber')
    message = root.findtext('Message')

    username, user_data = get_user_by_phone(phone)
    if not user_data:
        return Response("<Inforu>OK</Inforu>", mimetype='application/xml')

    if not session['waiting_for_group_choice'].get(phone):
        session['last_message'][phone] = message
        groups = get_groups(user_data['token'])
        session['group_map'] = {str(i): gid for i, name, gid in groups}
        session['waiting_for_group_choice'][phone] = True

        group_list = "\n".join([f"{i}. {name}" for i, name, gid in groups])
        reply = f"למי לשלוח את ההודעה הבאה?\n\"{message}\"\nענה עם מספר קבוצה:\n{group_list}"
        send_sms(phone, reply, user_data)
    else:
        group_choice = message.strip()
        group_id = session['group_map'].get(group_choice)
        if group_id:
            contacts = get_group_contacts(group_id, user_data['token'])
            for number in contacts:
                send_sms(number, session['last_message'][phone], user_data)
            send_sms(phone, "ההודעה נשלחה לקבוצה בהצלחה.", user_data)
        else:
            send_sms(phone, "מספר קבוצה לא חוקי. נסה שוב.", user_data)
        session['waiting_for_group_choice'][phone] = False
        session['last_message'][phone] = None

    return Response("<Inforu>OK</Inforu>", mimetype='application/xml')

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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    message = ""
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        username, user_data = get_user_by_phone(phone)
        if user_data:
            msg = f"שם משתמש: {username}\nסיסמה: {user_data['password']}"
            send_sms(phone, msg, user_data)
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

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'admin' not in flask_session:
        return redirect(url_for('login'))

    message = ""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            username = request.form['username'].strip()
            if username and username not in users:
                users[username] = {
                    "password": request.form['password'].strip(),
                    "phone": request.form['phone'].strip(),
                    "inforu_username": request.form['inforu_username'].strip(),
                    "inforu_password": request.form['inforu_password'].strip(),
                    "token": request.form['token'].strip(),
                    "sender": request.form['sender'].strip()
                }
                save_users()
                message = f"נוסף משתמש {username}"
        elif action == 'delete':
            del_user = request.form['delete_username'].strip()
            if del_user in users:
                users.pop(del_user)
                save_users()
                message = f"נמחק משתמש {del_user}"

    return render_template_string('''
        <h2>ניהול משתמשים</h2>
        <p>{{ message }}</p>
        <ul>
        {% for u in users %}
            <li>{{ u }} ({{ users[u]['phone'] }})
                <form method="post" style="display:inline">
                    <input type="hidden" name="delete_username" value="{{ u }}">
                    <button name="action" value="delete" type="submit">מחק</button>
                </form>
            </li>
        {% endfor %}
        </ul>
        <h3>הוסף משתמש חדש</h3>
        <form method="post">
            <input name="username" placeholder="שם משתמש">
            <input name="password" placeholder="סיסמה">
            <input name="phone" placeholder="טלפון">
            <input name="inforu_username" placeholder="Inforu Username">
            <input name="inforu_password" placeholder="Inforu Password">
            <input name="token" placeholder="Token">
            <input name="sender" placeholder="Sender">
            <button name="action" value="add" type="submit">הוסף</button>
        </form>
        <a href="{{ url_for('logout') }}">התנתק</a>
    ''', users=users, message=message)

@app.route('/logout')
def logout():
    flask_session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
