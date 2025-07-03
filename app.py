from flask import Flask, request, render_template_string
import requests
import json  # נוספה כדי להמיר תשובה למחרוזת JSON

app = Flask(__name__)

API_URL = "https://capi.inforu.co.il/api/v2/SMS/SendSms"
AUTH_HEADER = "Basic MjJ1cml5YTIyOjE1ZDFmNmI1LTFhZGYtNGY2YS1iYTY1LSAyOTE3YTA3Y2QzNjg"  # הטוקן שלך
SENDER = "0001"  # מזהה השולח המאושר

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
        <pre>{{ response }}</pre>
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
            response = json.dumps(res.json(), ensure_ascii=False, indent=2)  # המרנו מ־dict למחרוזת
        except Exception as e:
            response = json.dumps({"error": str(e)}, ensure_ascii=False)

    return render_template_string(HTML, response=response)

if __name__ == "__main__":
    app.run(debug=True)
