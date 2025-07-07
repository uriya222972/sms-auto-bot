from flask import Flask, request, redirect, url_for, render_template_string, Response, jsonify
import requests
import csv
from io import TextIOWrapper, StringIO
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from storage import save_data, load_data

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

saved = load_data()
rows = saved.get("rows", [])
sent_indices = set(saved.get("sent_indices", []))
phone_map = saved.get("phone_map", {})
responses = saved.get("responses", {})
send_log = saved.get("send_log", {})
scheduled_retries = saved.get("scheduled_retries", {})
custom_template = saved.get("custom_template", "יישר כח! המספר הבא אליו צריך להתקשר הוא {next}. תודה!")
response_map = saved.get("response_map", {str(i): {"label": f"הגדרה {i}", "callback_required": False, "hours": 0} for i in range(1, 10)})
activation_word = saved.get("activation_word", "התחל")
filename = saved.get("filename", "")

@app.route("/")
def home():
    now = datetime.now()
    retry_indices = [i for i, t in scheduled_retries.items() if t <= now and i not in sent_indices]
    if retry_indices:
        retry_index = min(retry_indices)
        scheduled_retries.pop(retry_index)
        sent_indices.discard(retry_index)

    total_sent = len(sent_indices)
    stats = {r["label"]: 0 for r in response_map.values()}
    for r in responses.values():
        if "label" in r:
            stats[r["label"]] = stats.get(r["label"], 0) + 1

    html = '''
    <!DOCTYPE html>
    <html lang="he">
    <head>
        <meta charset="UTF-8">
        <title>מערכת טלפונים</title>
    </head>
    <body style="font-family:Arial; direction:rtl; padding:20px;">
        <h1>מערכת טלפונים</h1>
        <form method="post" enctype="multipart/form-data">
            <label>העלה קובץ CSV של מספרים:</label>
            <input type="file" name="csv_file">
            <button type="submit" name="upload_csv">טען</button>
        </form>
        <h2>מספרים בקובץ:</h2>
        <ul>
            {% for row in rows %}
                <li>{{ row }}</li>
            {% endfor %}
        </ul>
        <h2>מספר הודעות שנשלחו: {{ total_sent }}</h2>
        <h2>סטטיסטיקות:</h2>
        <ul>
            {% for label, count in stats.items() %}
                <li>{{ label }}: {{ count }}</li>
            {% endfor %}
        </ul>
        <p><strong>תבנית הודעה:</strong> {{ template }}</p>
        <p><strong>קובץ נוכחי:</strong> {{ filename }}</p>
    </body>
    </html>
    '''
    return render_template_string(html, rows=rows, total_sent=total_sent, stats=stats, template=custom_template, filename=filename)

@app.route("/", methods=["POST"])
def upload():
    global rows, sent_indices, phone_map, responses, send_log, scheduled_retries, filename
    if "upload_csv" in request.form and "csv_file" in request.files:
        file = request.files["csv_file"]
        if file.filename.endswith(".csv"):
            decoded = TextIOWrapper(file, encoding='utf-8')
            reader = csv.reader(decoded)
            rows = [row[0] for row in reader if row]
            filename = file.filename
            sent_indices.clear()
            phone_map.clear()
            responses.clear()
            send_log.clear()
            scheduled_retries.clear()
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
                "filename": filename
            })
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
