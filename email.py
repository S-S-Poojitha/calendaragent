import os
import sqlite3
import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

SERVICE_ACCOUNTS_DIR = 'service_accounts'
SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.readonly"]

def send_email(event_summary, recipient_email):
    # Set up SMTP server
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587  # For SSL: 465, For TLS: 587

    # Sender and receiver email addresses
    sender_email = 'poojithasarvamangala@gmail.com'  # Change this to your email address

    # Email content
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = recipient_email
    message['Subject'] = 'Proposed Event'  # Corrected typo in 'Subject'
    body = event_summary
    message.attach(MIMEText(body, 'plain'))

    # Connect to SMTP server and send email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Enable TLS encryption
            server.login(sender_email, 'ferm bqim epzj xdlc')  # Change this to your password
            server.sendmail(sender_email, recipient_email, message.as_string())
        st.success('Email sent successfully!')
    except Exception as e:
        st.error(f"Failed to send email: {e}")

def save_user_email(email):
    # Connect to SQLite database or create it if it doesn't exist
    conn = sqlite3.connect('user_emails.db')
    c = conn.cursor()

    # Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS emails (email TEXT)''')

    # Insert user's email into the table
    c.execute("INSERT INTO emails (email) VALUES (?)", (email,))
    conn.commit()

    # Close the connection
    conn.close()
    
def commit_and_push_changes():
    repo = git.Repo(search_parent_directories=True)
    repo.git.add(update=True)
    repo.index.commit("Deleted user email from database")
    origin = repo.remote(name="origin")
    origin.push()

def main():
    user_email = st.text_input("Enter recipient's email address")
    if st.button('Send Email'):
        if user_email:
            # Save user's email to SQLite database
            save_user_email(user_email)
            commit_and_push_changes()
            # Send email
            event_summary = 'https://calendaragent-o72w6artpmcejn99oyzjl2.streamlit.app/'
            send_email(event_summary, user_email)
        else:
            st.error('Please enter a recipient email address.')

if __name__ == "__main__":
    main()
