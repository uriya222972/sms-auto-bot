from flask import Flask, request, render_template_string, redirect, url_for, send_file, Response
import requests
import csv
import json
from io import TextIOWrapper, StringIO
from datetime import datetime

app = Flask(__name__)

# הגדרות API של Inforu
API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

# משתנים גלובליים לשמירת נתונים
rows = []  # רשימת ההודעות בקובץ
sent_indices = set()  # אינדקסים של הודעות שנשלחו
phone_map = {}  # מיפוי בין מספרים לשליחות: מספר -> [אינדקסים שנשלחו אליו]
responses = {}  # תגובות: אינדקס -> {"message": ..., "time": ...}
send_log = {}  # יומן שליחה: אינדקס -> {"to": ..., "time": ...}

# תבנית HTML כולל טבלה והודעת סטטוס
HTML_PAGE = """
<!DOCTYPE html>
<html lang=\"he\" dir=\"rtl\">
<head>
    <meta charset=\"UTF-8\">
    <title>שליחת SMS לפי קובץ</title>
</head>
<body>
    <h1>מערכת שליחת SMS</h1>

    <form method=\"post\" enctype=\"multipart/form-data\" action=\"/upload\">
        <label>בחר קובץ CSV (שורה לכל הודעה):</label><br>
        <input type=\"file\" name=\"file\" accept=\".csv\" required>
        <input type=\"submit\" value=\"העלה קובץ\">
    </form>

    <form method=\"post\" action=\"/reset\">
        <button type=\"submit\">מחק קובץ</button>
    </form>

    <form action=\"/download\" method=\"get\">
        <button type=\"submit\">הורד קובץ תגובות</button>
    </form>

    {% if rows %}
        <h2 style='color: green;'>קובץ נטען. המערכת מחכה להודעות SMS.</h2>
    {% endif %}

    <h2>סטטוס הודעות</h2>
    <table border=\"1\">
        <tr>
            <th>#</th>
            <th>תוכן ההודעה</th>
            <th>נשלח למספר</th>
            <th>זמן שליחה</th>
            <th>תגובה</th>
            <th>זמן תגובה</th>
        </tr>
        {% for i, row in enumerate(rows) %}
        <tr>
            <td>{{ i + 1 }}</td>
            <td>{{ row }}</td>
            <td>{{ send_log.get(i, {}).get("to", "") }}</td>
            <td>{{ send_log.get(i, {}).get("time", "") }}</td>
            <td>{{ responses.get(i, {}).get("message", "") }}</td>
            <td>{{ responses.get(i, {}).get("time", "") }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_PAGE, rows=rows, responses=responses, send_log=send_log)

@app.route("/upload", methods=["POST"])
def upload():
    global rows
    file = request.files["file"]
    if file:
        wrapper = TextIOWrapper(file, encoding='utf-8')
        reader = csv.reader(wrapper)
        rows = [", ".join(r).strip() for r in reader if any(r)]
    return redirect(url_for("home"))

@app.route("/reset", methods=["POST"])
def reset():
    global rows, sent_indices, phone_map, send_log
    rows = []
    sent_indices.clear()
    phone_map.clear()
    send_log.clear()
    return redirect(url_for("home"))

@app.route("/incoming", methods=["POST"])
def incoming_sms():
    global rows, responses, phone_map, sent_indices, send_log
    try:
        data = request.get_json(force=True)
        message = data.get("Message")
        sender = data.get("Phone")

        last_index = None
        if sender in phone_map and phone_map[sender]:
            last_index = phone_map[sender][-1]
            previous = responses.get(last_index, {}).get("message")
            if previous != message:
                responses[last_index] = {
                    "message": message,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

        next_index = 0
        while next_index < len(rows) and next_index in sent_indices:
            next_index += 1

        if next_index < len(rows):
            row = rows[next_index]
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": AUTH_HEADER
            }
            data = {
                "Sender": SENDER,
                "Message": row + "\nהשב ספרה אחת להמשך",
                "Recipients": [
                    {"Phone": sender}
                ]
            }
            res = requests.post(API_URL, headers=headers, json=data)
            res.raise_for_status()
            sent_indices.add(next_index)
            send_log[next_index] = {
                "to": sender,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            phone_map.setdefault(sender, []).append(next_index)

        return "OK"
    except Exception as e:
        return str(e), 400

@app.route("/download")
def download():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["שורה", "תוכן ההודעה", "נשלח למספר", "זמן שליחה", "תגובה", "זמן תגובה"])
    for i, row in enumerate(rows):
        sent = send_log.get(i, {})
        sent_to = sent.get("to", "")
        sent_time = sent.get("time", "")
        resp = responses.get(i, {})
        resp_msg = resp.get("message", "")
        resp_time = resp.get("time", "")
        writer.writerow([i + 1, row, sent_to, sent_time, resp_msg, resp_time])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=sms_responses.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True)
