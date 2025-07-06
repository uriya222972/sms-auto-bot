from flask import Flask, request, render_template, redirect, url_for, send_file, Response
import requests
import csv
from io import TextIOWrapper, StringIO
from datetime import datetime
import xml.etree.ElementTree as ET

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjRkNTFjZGU5LTBkZmQtNGYwYi1iOTY4LWQ5MTA0NjdjZmM4MQ=="
SENDER = "0001"

rows = []
sent_indices = set()
phone_map = {}
responses = {}
send_log = {}

@app.route("/", methods=["GET", "POST"])
def home():
    global rows, responses, phone_map, sent_indices, send_log

    if request.method == "POST":
        try:
            print("== POST / התקבל ==")
            print("Headers:", dict(request.headers))
            print("Body:", request.get_data(as_text=True))

            # חילוץ XML מתוך השדה IncomingXML
            raw_xml = request.form.get("IncomingXML")
            if not raw_xml:
                print("❌ לא נמצא IncomingXML")
                return "Missing IncomingXML", 400

            print("📥 קיבלנו XML:")
            print(raw_xml)
            root = ET.fromstring(raw_xml)
            sender = root.findtext("PhoneNumber")
            message = root.findtext("Message")

            print("📞 Sender:", sender)
            print("💬 Message:", message)

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
                payload = {
                    "Sender": SENDER,
                    "Message": row + "\nהשב ספרה אחת להמשך",
                    "Recipients": [{"Phone": sender}]
                }
                print("➡️ שולח:", payload)
                res = requests.post(API_URL, headers=headers, json=payload)
                print("↩️ תשובת Inforu:", res.status_code, res.text)
                res.raise_for_status()

                sent_indices.add(next_index)
                send_log[next_index] = {
                    "to": sender,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                phone_map.setdefault(sender, []).append(next_index)

            return "OK"
        except Exception as e:
            print("❌ שגיאה ב־POST /:", e)
            return str(e), 400

    return render_template("index.html", rows=rows, responses=responses, send_log=send_log)

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
    global rows, sent_indices, phone_map, send_log, responses
    rows = []
    sent_indices.clear()
    phone_map.clear()
    send_log.clear()
    responses.clear()
    return redirect(url_for("home"))

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
