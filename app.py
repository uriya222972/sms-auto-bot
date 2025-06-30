from flask import Flask, request, render_template_string
import requests
import json

app = Flask(__name__)

HTML_FORM = '''
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>שליחת SMS</title></head>
<body>
  <h2>שליחת SMS דרך Inforu</h2>
  <form method="POST">
    מספר טלפון: <input type="text" name="recipient" required><br>
    טקסט ההודעה: <input type="text" name="text" required><br>
    <button type="submit">שלח</button>
  </form>
  {% if response %}
    <h3>תגובה מ־Inforu:</h3>
    <pre>{{ response }}</pre>
  {% endif %}
</body>
</html>
'''

# כאן הטוקן הבסיסי שלך (החלף אם צריך)
AUTH_TOKEN = "Basic MjJ1cml5YTIyOjRkYzYyZTBhLTRkNzAtNDZiMC05ZmZkLTIyZmM5ZDBmYzViMQ=="

@app.route("/", methods=["GET", "POST"])
def send_sms():
    response_text = ""
    if request.method == "POST":
        recipient = request.form.get("recipient", "").strip()
        message = request.form.get("text", "").strip()

        if not recipient or not message:
            response_text = "נדרש גם מספר טלפון וגם תוכן הודעה"
        else:
            url = "https://api.inforu.co.il/api/v2/SMS/SendSms"
            headers = {
                "Authorization": AUTH_TOKEN,
                "Content-Type": "application/json"
            }
            payload = {
                "Data": {
                    "Message": {
                        "Sender": "0001",  # שם השולח שלך
                        "Content": message,
                        "Recipients": [{"Phone": recipient}]
                    }
                }
            }

            try:
                res = requests.post(url, headers=headers, json=payload)
                response_text = res.text
            except Exception as e:
                response_text = f"שגיאה בשליחה: {e}"

    return render_template_string(HTML_FORM, response=response_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
