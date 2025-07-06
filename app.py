from flask import Flask, request, redirect, url_for, render_template, Response
import requests
import csv
from io import TextIOWrapper, StringIO
from datetime import datetime, timedelta
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
scheduled_retries = {}

response_map = {str(i): {"label": f"הגדרה {i}", "callback_required": False, "hours": 0} for i in range(1, 10)}
custom_template = "שלום {phone}, זו הודעה לדוגמה."

@app.route("/", methods=["GET", "POST"])
def home():
    global rows, responses, phone_map, sent_indices, send_log, scheduled_retries, response_map, custom_template

    if request.method == "POST":
        if request.form.get("IncomingXML"):
            try:
                raw_xml = request.form.get("IncomingXML")
                root = ET.fromstring(raw_xml)
                sender = root.findtext("PhoneNumber")
                message = root.findtext("Message")

                last_index = None
                if sender in phone_map and phone_map[sender]:
                    last_index = phone_map[sender][-1]
                    previous = responses.get(last_index, {}).get("message")
                    if previous != message:
                        label = response_map.get(message, {}).get("label", "")
                        responses[last_index] = {
                            "message": message,
                            "label": label,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if message in response_map:
                            r = response_map[message]
                            if r["callback_required"]:
                                hours = r["hours"]
                                if last_index is not None:
                                    scheduled_retries[last_index] = datetime.now() + timedelta(hours=hours)
                return "OK"
            except Exception as e:
                return str(e), 400

        if "update_response_map" in request.form:
            for key in response_map:
                label = request.form.get(f"label_{key}", f"ספרה {key}")
                callback = request.form.get(f"callback_{key}") == "on"
                hours = int(request.form.get(f"hours_{key}", 0)) if callback else 0
                response_map[key] = {
                    "label": label,
                    "callback_required": callback,
                    "hours": hours
                }
            return redirect(url_for("home"))

        if "update_template" in request.form:
            custom_template = request.form.get("template", custom_template)
            return redirect(url_for("home"))

        sender = request.form.get("phone")
        message = request.form.get("message")

        if request.form.get("send_to_all") == "yes" and custom_template:
            unique_phones = list(phone_map.keys())
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": AUTH_HEADER
            }
            for phone in unique_phones:
                personalized_message = custom_template.replace("{phone}", phone)
                payload = {
                    "Sender": SENDER,
                    "Message": personalized_message,
                    "Recipients": [{"Phone": phone}]
                }
                res = requests.post(API_URL, headers=headers, json=payload)
            return redirect(url_for("home"))

        if sender and message:
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": AUTH_HEADER
            }
            payload = {
                "Sender": SENDER,
                "Message": message,
                "Recipients": [{"Phone": sender}]
            }
            res = requests.post(API_URL, headers=headers, json=payload)
            res.raise_for_status()

            send_log[len(rows)] = {
                "to": sender,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": message
            }
            rows.append(message)
            sent_indices.add(len(rows) - 1)

            return redirect(url_for("home"))

    now = datetime.now()
    retry_indices = [i for i, t in scheduled_retries.items() if t <= now and i not in sent_indices]
    if retry_indices:
        retry_index = min(retry_indices)
        scheduled_retries.pop(retry_index)
        sent_indices.discard(retry_index)

    total_sent = len(sent_indices)
    return render_template("index.html", rows=rows, responses=responses, send_log=send_log, response_map=response_map, total_sent=total_sent, template=custom_template)

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
    global rows, sent_indices, phone_map, send_log, responses, scheduled_retries
    rows = []
    sent_indices.clear()
    phone_map.clear()
    send_log.clear()
    responses.clear()
    scheduled_retries.clear()
    return redirect(url_for("home"))

@app.route("/download")
def download():
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "מספר שורה",
        "תוכן ההודעה שנשלחה",
        "נשלח למספר",
        "זמן שליחה",
        "תוכן תגובה שהתקבלה",
        "פירוש תגובה",
        "זמן תגובה"
    ])
    for i, row in enumerate(rows):
        sent = send_log.get(i, {})
        sent_to = sent.get("to", "")
        sent_time = sent.get("time", "")
        sent_msg = sent.get("message", row)
        resp = responses.get(i, {})
        resp_msg = resp.get("message", "")
        resp_label = resp.get("label", "")
        resp_time = resp.get("time", "")
        writer.writerow([i + 1, sent_msg, sent_to, sent_time, resp_msg, resp_label, resp_time])
    output.seek(0)
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=תגובות_סמס.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True)
