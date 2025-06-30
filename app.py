import requests

# פרטי התחברות שלך
USERNAME = "22uriya22"
API_TOKEN = "15d1f6b5-1adf-4f6a-ba65-2917a07cd368"
SENDER_NAME = "0001"

# קלט מהמשתמש
recipient = input("הכנס מספר טלפון (למשל 0501234567): ").strip()
message = input("הכנס את תוכן ההודעה שברצונך לשלוח: ").strip()

# הרכבת XML פשוט בלי הזחות מיותרות
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

# שליחה ל־Inforu
response = requests.post(
    url="https://api.inforu.co.il/SendMessageXml.ashx",
    data=xml_data.encode('utf-8'),
    headers={'Content-Type': 'application/xml; charset=utf-8'}
)

# פלט התוצאה
print("\nתשובת Inforu:")
print(response.text)
