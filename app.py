import requests

# טוקן בסיסי מ־Inforu
basic_token = "Basic MjJ1cml5YTIyOjRkYzYyZTBhLTRkNzAtNDZiMC05ZmZkLTIyZmM5ZDBmYzViMQ=="

# פרטי ההודעה
recipient = "0585906040"  # החלף במספר אמיתי לבדיקה
message = "שלום! זו הודעת בדיקה דרך Inforu API V2"
sender = "0001"  # מזהה שולח מאושר

# גוף הבקשה
payload = {
    "data": {
        "Message": {
            "Sender": sender,
            "Content": message,
            "Recipients": [
                {"Phone": recipient}
            ]
        }
    }
}

# שליחת הבקשה
response = requests.post(
    url="https://capi.inforu.co.il/api/v2/SMS/SendSms",
    headers={
        "Authorization": basic_token,
        "Content-Type": "application/json"
    },
    json=payload
)

# תוצאות
print("Status Code:", response.status_code)
print("Response:")
print(response.text)
