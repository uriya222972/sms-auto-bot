from flask import Flask, request, render_template_string
import requests

app = Flask(__name__)  # 🔴 חובה לשים את זה

BASIC_TOKEN = "Basic MjJ1cml5YTIyOjRkYzYyZTBhLTRkNzAtNDZiMC05ZmZkLTIyZmM5ZDBmYzViMQ=="
SENDER_NAME = "0001"

HTML_FORM = """
<!doctype html>
<html>
  <head><title>שליחת SMS</title></head>
  <body style="direction:rtl; font-family:Arial; padding:20px;">
    <h2>שליחת SMS דרך Inforu</h2>
    <form method="post">
      <label>מספר טלפון:</label><br>
      <input type="text" name="recipient" required><br><br>
      <label>תוכן ההודעה:</label><br>
      <textarea name="message" rows="5" cols="50" required></textarea><br><br>
      <button type="submit">שלח</button>
    </form>
    {% if response %}
      <h3>תשובת Inforu:</h3>
      <pre>{{ response }}</pre>
    {% endif %}
  </body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def send_sms():
    response_text = ""
    if request.method == "POST":
        recipient = request.form.get("recipient", "").strip()
        message = request.form.get("message", "").strip()

        if not recipient or not message:
            response_text = "שגיאה: חסר מספר או טקסט"
        else:
            payload = {
                "data": {
                    "Message": {
                        "Sender": SENDER_NAME,
                        "Content": message,
                        "Recipients": [{"Phone": recipient}]
                    }
                }
            }

            r = requests.post(
                "https://capi.inforu.co.il/api/v2/SMS/SendSms",
                headers={
                    "Authorization": BASIC_TOKEN,
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response_text = r.text

    return render_template_string(HTML_FORM, response=response_text)
