from flask import Flask, request, Response
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

USERNAME = "22uriya22"
PASSWORD = "222972Uriya!"
SENDER = "0537038545"
TOKEN = "4a549e05-8668-448f-b3a7-5ee7816ee0ad"
USER_PHONE = "0585906040"

session = {
    'last_message': None,
    'waiting_for_group_choice': False
}

def get_groups():
    url = "https://api.inforu.co.il/Contact/GetGroups"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    res = requests.get(url, headers=headers)
    groups = res.json().get('Groups', [])
    return [(i+1, g['GroupName'], g['GroupId']) for i, g in enumerate(groups)]

def get_group_contacts(group_id):
    url = f"https://api.inforu.co.il/Contact/GetGroupContacts?groupId={group_id}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    res = requests.get(url, headers=headers)
    contacts = res.json().get('Contacts', [])
    return [c['Phone'] for c in contacts]

def send_sms(phone, message):
    payload = f"""
    <Inforu>
      <User>
        <Username>{USERNAME}</Username>
        <Password>{PASSWORD}</Password>
      </User>
      <Content Type=\"sms\">
        <Message>{message}</Message>
      </Content>
      <Recipients>
        <PhoneNumber>{phone}</PhoneNumber>
      </Recipients>
      <Settings>
        <Sender>{SENDER}</Sender>
      </Settings>
    </Inforu>
    """
    headers = {'Content-Type': 'application/xml'}
    response = requests.post("https://api.inforu.co.il/SendMessageXml.ashx", data=payload.encode('utf-8'), headers=headers)
    return response.text

@app.route('/inbound', methods=['POST'])
def inbound_sms():
    xml_data = request.data.decode('utf-8')
    root = ET.fromstring(xml_data)
    phone = root.findtext('PhoneNumber')
    message = root.findtext('Message')

    if phone != USER_PHONE:
        return Response("<Inforu>OK</Inforu>", mimetype='application/xml')

    if not session['waiting_for_group_choice']:
        session['last_message'] = message
        groups = get_groups()
        session['group_map'] = {str(i): gid for i, name, gid in groups}
        session['waiting_for_group_choice'] = True

        group_list = "\n".join([f"{i}. {name}" for i, name, gid in groups])
        reply = f"לאיזה קבוצה לשלוח את ההודעה הבאה?\n\"{message}\"\nענה במספר קבוצה:\n{group_list}"
        send_sms(USER_PHONE, reply)
    else:
        group_choice = message.strip()
        group_id = session['group_map'].get(group_choice)
        if group_id:
            contacts = get_group_contacts(group_id)
            for number in contacts:
                send_sms(number, session['last_message'])
            send_sms(USER_PHONE, "ההודעה נשלחה לקבוצה בהצלחה.")
        else:
            send_sms(USER_PHONE, "מספר קבוצה לא חוקי. נסה שוב.")
        session['waiting_for_group_choice'] = False
        session['last_message'] = None
        session['group_map'] = {}

    return Response("<Inforu>OK</Inforu>", mimetype='application/xml')

if __name__ == '__main__':
    app.run()