# app.py
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)
messages = []  # שמירת ההודעות בזיכרון – אפשר להחליף לקובץ/DB

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.form.to_dict() or request.json
    msg = {
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'from': data.get('Msisdn'),
        'text': data.get('Message'),
        'raw': data
    }
    messages.append(msg)
    print("📩 הודעה חדשה:", msg)
    return 'OK', 200

@app.route('/messages')
def get_messages():
    return jsonify(messages[::-1])  # להחזיר לפי סדר יורד

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
