from flask import Flask, request, render_template_string, redirect, url_for
import requests
import csv
import json
from io import TextIOWrapper

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="  # הטוקן שלך
SENDER = "0001"  # מזהה השולח המאושר

rows = []
current_index = 0
recipient_number = ""  # מספר המקבל אליו תישלח כל שורה

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
    <p><strong>תוכן השורה:</strong> {{ row }}</p>
    <form method=\"post\">
        <input type=\"submit\" value=\"שלח שורה הבאה\">
    </form>
    {% if response %}
        <h2>תשובת Inforu:</h2>
        <pre>{{ response }}</pre>
    {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload():
    global rows, current_index, recipient_number
    if request.method == "POST":
        file = request.files["file"]
        recipient_number = request.form.get("recipient", "")
        if file and recipient_number:
            wrapper = TextIOWrapper(file, encoding='utf-8')
            reader = csv.reader(wrapper)
            rows = [", ".join(r).strip() for r in reader if any(r)]
            current_index = 0
            return redirect(url_for("send_next"))
    return HTML_FORM

@app.route("/send", methods=["GET", "POST"])
def send_next():
    global rows, current_index, recipient_number
    response = None

    if current_index >= len(rows):
        return "סיימנו לשלוח את כל השורות."

    if request.method == "POST":
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
        response = json.dumps(res.json(), ensure_ascii=False, indent=2)
    except Exception as e:
        response = json.dumps({"error": str(e)}, ensure_ascii=False)

    return render_template_string(HTML_SENT, phone=phone, row=row, response=response)

if __name__ == "__main__":
    app.run(debug=True)
