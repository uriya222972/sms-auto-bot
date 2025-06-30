from flask import Flask, request, render_template_string
import requests

app = Flask(__name__)

USERNAME = "22uriya22"
API_TOKEN = "15d1f6b5-1adf-4f6a-ba65-2917a07cd368"
SENDER_NAME = "0001"

HTML_FORM = """
<!doctype html>
<html>
  <head><title>שלח SMS</title></head>
  <body style="font-family:Arial;direction:rtl;text-align:right;">
    <h2>שליחת הודעת SMS</h2>
    <form method="post">
      <label>מספר נמען:</label><br>
      <input type="text" name="recipient" required><br><br>
      <label>תוכן הודעה:</label><br>
      <textarea name="message" rows="5" cols="40" required></textarea><br><br>
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
        recipient = request.form["recipient"]
        message = request.form["message"]

        xml_data = f"""<?xml version="1.0" encoding="utf-8"?>
        <Inforu>
          <User>
            <Username>{USERNAME}</Username>
            <ApiToken>{API_TOKEN}</ApiToken>
          </User>
          <Content>
            <Message>{message}</Message>
          </Content>
          <Recipients>
            <PhoneNumber>{recipient}</PhoneNumber>
          </Recipients>
          <Settings>
            <Sender>{SENDER_NAME}</Sender>
          </Settings>
        </Inforu>"""

        res = requests.post(
            url="https://api.inforu.co.il/SendMessageXml.ashx",
            data=xml_data.encode('utf-8'),
            headers={'Content-Type': 'application/xml'}
        )
        response_text = res.text

    return render_template_string(HTML_FORM, response=response_text)

if __name__ == "__main__":
    app.run()
