from flask import Flask, request, render_template_string, redirect, url_for, send_file, Response
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
    <h1>העלאת קובץ CSV</h1>
    <form method=\"post\" enctype=\"multipart/form-data\" action=\"/upload\">
        <label>בחר קובץ CSV (שורה לכל הודעה):</label><br>
        <input type=\"file\" name=\"file\" accept=\".csv\" required><br><br>

        <label>מספר טלפון שאליו תישלח כל שורה:</label><br>
        <input type=\"text\" name=\"recipient\" required><br><br>

        <input type=\"submit\" value=\"אשר קובץ\">
    </form>

    <form method=\"post\" action=\"/reset\">
        <button type=\"submit\">מחק קובץ</button>
    </form>

    <form method=\"get\" action=\"/send\">
        <button type=\"submit\">שלח שורה ראשונה</button>
    </form>

    <form action=\"/download\" method=\"get\">
        <button type=\"submit\">הורד קובץ תגובות</button>
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
        <input type=\"hidden\" name=\"index\" value=\"{{ current_index }}\">
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
            <th>נשלח למספר</th>
            <th>תגובה</th>
        </tr>
        {% for i in range(all_rows|length) %}
        <tr>
            <td>{{ i + 1 }}</td>
            <td>{{ all_rows[i] }}</td>
            <td>{{ recipient if i in sent_indices else '' }}</td>
            <td>{{ responses.get(i, '') }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    return HTML_FORM

@app.route("/upload", methods=["POST"])
def upload():
    global rows, current_index, recipient_number, responses, sent_indices
    file = request.files["file"]
    recipient_number = request.form.get("recipient", "")
    if file and recipient_number:
        wrapper = TextIOWrapper(file, encoding='utf-8')
        reader = csv.reader(wrapper)
        rows = [", ".join(r).strip() for r in reader if any(r)]
        current_index = 0
        responses = {}
        sent_indices = set()
    return redirect(url_for("home"))

@app.route("/reset", methods=["POST"])
def reset():
    global rows, current_index, recipient_number, responses, sent_indices
    rows = []
    current_index = 0
    recipient_number = ""
    responses = {}
    sent_indices = set()
    return redirect(url_for("home"))

@app.route("/send", methods=["GET", "POST"])
def send_next():
    global rows, current_index, recipient_number, responses, sent_indices
    inforu_response = None

    if request.method == "POST":
        digit = request.form.get("response_digit")
        index = int(request.form.get("index"))
        if digit and digit.isdigit():
            responses[index] = digit
            current_index += 1
            return redirect(url_for("send_next"))

    while current_index < len(rows) and current_index in sent_indices:
        current_index += 1

    if current_index >= len(rows):
        return "סיימנו לשלוח את כל השורות. <a href='/download'>הורד קובץ תגובות</a>"

    row = rows[current_index]
    phone = recipient_number

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": AUTH_HEADER
    }

    data = {
        "Sender": SENDER,
        "Message": row + "\nהשב ספרה אחת להמשך",
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
                                  all_rows=rows, responses=responses, sent_indices=sent_indices,
                                  current_index=current_index, recipient=recipient_number)

@app.route("/download")
def download():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["שורה", "תוכן ההודעה", "נשלח למספר", "תגובה"])
    for i, row in enumerate(rows):
        sent_to = recipient_number if i in sent_indices else ""
        response = responses.get(i, "")
        writer.writerow([i + 1, row, sent_to, response])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=sms_responses.csv"}
    )

@app.route("/incoming", methods=["POST"])
def incoming_sms():
    global current_index, responses
    try:
        data = request.get_json(force=True)
        message = data.get("Message")
        sender = data.get("Phone")

        if current_index in sent_indices and current_index not in responses:
            responses[current_index] = message
            current_index += 1
        return "OK"
    except Exception as e:
        return str(e), 400

if __name__ == "__main__":
    app.run(debug=True)
