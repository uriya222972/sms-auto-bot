from flask import Flask, request, render_template_string, redirect, url_for, send_file
import requests
import csv
import json
from io import TextIOWrapper, StringIO

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

rows = []
sent_indices = set()
current_index = 0
recipient_number = ""
responses = {}

HTML_FORM = """
<!DOCTYPE html>
<html lang=\"he\" dir=\"rtl\">
<head>
    <meta charset=\"UTF-8\">
    <title>שליחת SMS לפי קובץ</title>
</head>
<body>
    <h1>העלאת קובץ CSV ושליחת שורות למספר</h1>
    <form method=\"post\" enctype=\"multipart/form-data\">
        <label>בחר קובץ CSV (שורה לכל הודעה):</label><br>
        <input type=\"file\" name=\"file\" accept=\".csv\" required><br><br>

        <label>מספר טלפון שאליו תישלח כל שורה:</label><br>
        <input type=\"text\" name=\"recipient\" required><br><br>

        <input type=\"submit\" value=\"העלה ושלח ראשון\">
    </form>
</body>
</html>
"""

HTML_SENT = """
<!DOCTYPE html>
<html lang=\"he\" dir=\"rtl\">
<head>
    <meta charset=\"UTF-8\">
    <title>הודעה נשלחה</title>
</head>
<body>
    <h1>ההודעה נשלחה למספר {{ phone }}</h1>
    <p><strong>תוכן ההודעה:</strong> {{ row }}</p>
    <form method=\"post\">
        <label>הזן תשובה מהמשתמש (ספרה):</label><br>
        <input type=\"text\" name=\"response_digit\" maxlength=\"1\" required><br><br>
        <input type=\"submit\" value=\"שלח שורה הבאה\">
    </form>
    {% if inforu_response %}
        <h2>תשובת Inforu:</h2>
        <pre>{{ inforu_response }}</pre>
    {% endif %}
    <br><br>
    <form action=\"/download\" method=\"get\">
        <button type=\"submit\">הורד קובץ תגובות</button>
    </form>
    <h2>סטטוס השאלון:</h2>
    <table border=\"1\" cellpadding=\"5\" cellspacing=\"0\">
        <tr>
            <th>שורה</th>
            <th>תוכן ההודעה</th>
            <th>האם נשלח</th>
            <th>תגובה</th>
        </tr>
        {% for i in range(all_rows|length) %}
        <tr>
            <td>{{ i + 1 }}</td>
            <td>{{ all_rows[i] }}</td>
            <td>{{ '✓' if i in sent_indices else '' }}</td>
            <td>{{ responses.get(i, '') }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload():
    global rows, current_index, recipient_number, responses, sent_indices
    if request.method == "POST":
        file = request.files["file"]
        recipient_number = request.form.get("recipient", "")
        if file and recipient_number:
            wrapper = TextIOWrapper(file, encoding='utf-8')
            reader = csv.reader(wrapper)
            rows = [", ".join(r).strip() for r in reader if any(r)]
            current_index = 0
            responses = {}
            sent_indices = set()
            return redirect(url_for("send_next"))
    return HTML_FORM

@app.route("/send", methods=["GET", "POST"])
def send_next():
    global rows, current_index, recipient_number, responses, sent_indices
    inforu_response = None

    while current_index < len(rows) and current_index in sent_indices:
        current_index += 1

    if current_index >= len(rows):
        return "סיימנו לשלוח את כל השורות. <a href='/download'>הורד קובץ תגובות</a>"

    if request.method == "POST":
        digit = request.form.get("response_digit")
        if digit and digit.isdigit():
            responses[current_index] = digit
            current_index += 1
            return redirect(url_for("send_next"))

    row = rows[current_index]
    phone = recipient_number

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": AUTH_HEADER
    }

    data = {
        "Sender": SENDER,
        "Message": row,
        "Recipients": [
            {"Phone": phone}
        ]
    }

    try:
        res = requests.post(API_URL, headers=headers, json=data)
        inforu_response = json.dumps(res.json(), ensure_ascii=False, indent=2)
        sent_indices.add(current_index)
    except Exception as e:
        inforu_response = json.dumps({"error": str(e)}, ensure_ascii=False)

    return render_template_string(HTML_SENT, phone=phone, row=row, inforu_response=inforu_response,
                                  all_rows=rows, responses=responses, sent_indices=sent_indices)

@app.route("/download")
def download():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["שורה", "תוכן ההודעה", "תגובה"])
    for i, row in enumerate(rows):
        writer.writerow([i + 1, row, responses.get(i, "")])
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name="sms_responses.csv")

if __name__ == "__main__":
    app.run(debug=True)
