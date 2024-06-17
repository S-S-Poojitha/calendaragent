import requests
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
import 

app = Flask(__name__)

# Constants
CALENDLY_API_TOKEN = 'eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzE4NjAwNjU1LCJqdGkiOiI5YjEwY2RmOC0xYjc3LTQ0Y2QtYWNlZi02NTRiN2U5YWRhM2MiLCJ1c2VyX3V1aWQiOiI0Yjc3MzljYy0wMmUwLTRlNzEtYWRhOS02ZGVkZDE0MjNhOWUifQ.r7BmZgF3IomyAkALMMzk29K361AxTzzUQkz4IHIg5wYDiU9_OtirKPoUmEGb4OplQ3nkVdaVZlkYVI41v-2y4A'
SMTP_SERVER = 'smtp.example.com'
SMTP_PORT = 587
SMTP_USERNAME = 'poojithasarvamangala@gmail.com'
SMTP_PASSWORD = 'ferm bqim epzj xdlc'
FROM_EMAIL = 'poojithasarvamangala@gmail.com'
CALENDLY_EVENT_TYPE_LINK = 'https://calendly.com/poojithasarvamangala/interview'  # e.g., https://calendly.com/your-username/interview

# Sample selected candidates
user_email=st.text_input("enter gmail address")

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())

@app.route('/webhook', methods=['POST'])
def calendly_webhook():
    data = request.json
    if data['event'] == 'invitee.created':
        invitee_email = data['payload']['invitee']['email']
        invitee_name = data['payload']['invitee']['name']
        send_confirmation_email(invitee_email, invitee_name)
    return jsonify({'status': 'success'})

def send_confirmation_email(candidate_email, candidate_name):
    subject = "Interview Confirmation"
    body = f"Dear {candidate_name},\n\nYour interview has been successfully scheduled. We look forward to speaking with you.\n\nBest regards,\nYour Company"
    send_email(candidate_email, subject, body)


def main():
    for candidate in selected_candidates:
        candidate_email = candidate['email']
        candidate_name = candidate['name']
        subject = "Book Your Interview Slot"
        body = f"Dear {candidate_name},\n\nPlease book your preferred interview slot by clicking the link below:\n{CALENDLY_EVENT_TYPE_LINK}\n\nBest regards,\nYour Company"
        send_email(candidate_email, subject, body)

if __name__ == '__main__':
    main()
    app.run(port=5000)
