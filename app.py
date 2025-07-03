from flask import Flask, request, render_template_string
import requests
import json

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic a2F2aGFyYXY6ZDFkNWQ3NWQtM2ViMi00ZWNmLWFIMTQtOTg4NTg2OTI1MWQ0"
SENDER = "0537038545"  # מספר מאושר על ידי Inforu

HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>שליחת SMS</title>
</head>
<body>
    <h1>שליחת SMS דרך Inforu</h1>
    <form method="post">
        <label>מספר טלפון:</label><br>
        <input type="text" name="phone" required><br><br>

        <label>תוכן ההודעה:</label><br>
        <textarea name="message" rows="6" cols="50" required></textarea><br><br>

        <input type="submit" value="שלח">
    </form>

    {% if response %}
        <h2>תשובת Inforu:</h2>
        <pre>{{ response | tojson(indent=2, ensure_ascii=False) }}</pre>
    {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    response = None

    if request.method == "POST":
        phone = request.form["phone"]
        message = request.form["message"]

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": AUTH_HEADER
        }

        data = {
            "Sender": SENDER,
            "Message": message,
            "Recipients": [
                {"Phone": phone}
            ]
        }

        try:
            res = requests.post(API_URL, headers=headers, json=data)
            response = res.json()
        except Exception as e:
            response = {"error": str(e)}

    return render_template_string(HTML, response=response)

if __name__ == "__main__":
    app.run(debug=True)
