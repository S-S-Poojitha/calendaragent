import os
import datetime
import uuid
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import json
import warnings
import google.auth.transport.requests
import requests

warnings.filterwarnings("ignore")
SERVICE_ACCOUNTS_DIR = 'service_accounts'
SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.readonly"]
ORG_CALENDAR_ID = 'poojithasarvamangala@gmail.com'
DEFAULT_SLOT_DURATION = 60  # Default slot duration in minutes
slot_durations_file = 'slot_durations.json'

# Static password for the organization email (for demonstration purposes)
ORG_PASSWORD = 'org'  # This should be securely stored and managed in practice
st.title('Google Calendar Events Viewer & Scheduler')

def authenticate(user_email):
    creds = None
    token_path = os.path.join(SERVICE_ACCOUNTS_DIR, f'{user_email}_token.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Initialize OAuth flow
            flow = Flow.from_client_secrets_file('credentials.json', SCOPES)
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.write('Please go to this URL and authorize access:')
            st.write(auth_url)

            code = st.text_input('Enter the authorization code here:')
            if code:
                flow.fetch_token(code=code)
                creds = flow.credentials
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

    return creds

def initiate_google_sign_in():
    flow = Flow.from_client_secrets_file(
        'credentials.json',  # Path to your OAuth client ID JSON file
        scopes=['openid', 'https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/userinfo.profile' ,'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/calendar']
    )
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
    auth_url, _ = flow.authorization_url(prompt='consent')
    st.write('Please go to this URL and authorize access:')
    st.write(auth_url)

    code = st.text_input('Enter the authorization code here:')
    if code:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        return credentials

def fetch_organization_calendar_events(credentials, calendar_id, selected_date):
    try:
        service = build('calendar', 'v3', credentials=credentials)
        start_of_day = datetime.datetime.combine(selected_date, datetime.time.min)
        end_of_day = datetime.datetime.combine(selected_date, datetime.time.max)

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_of_day.isoformat() + 'Z',
            timeMax=end_of_day.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        return events
    except HttpError as error:
        st.error(f"An error occurred: {error}")
        return []

# Other functions remain unchanged...

def main():
    o = []
    c = 0
    credentials = initiate_google_sign_in()
    if credentials:
        user_email = credentials.id_token['email']
        st.write(';')
        if credentials:
            user_creds = authenticate(user_email)
            if user_creds:
                st.success('Authenticated successfully.')

            selected_date = datetime.date.today() + datetime.timedelta(days=2)
            while len(o) < 3:
                user_events = fetch_organization_calendar_events(user_creds, 'primary', selected_date)
                org_events = fetch_organization_calendar_events(user_creds, ORG_CALENDAR_ID, selected_date)
                free_slots = calculate_free_slots(user_events, org_events, selected_date, 60)
                if len(free_slots) > 0:
                    for i in free_slots:
                        o.append(i)
                        if len(o) == 3:
                            break
                selected_date += datetime.timedelta(days=1)
            if len(o) > 0:
                selected_slot = display_slots(o)
                if selected_slot:
                    message_placeholder = st.empty()
                    org_creds = authenticate('poojithasarvamangala@gmail.com')
                    try:
                        start_time, end_time = selected_slot
                        org_event = add_event_to_calendar(org_creds, ORG_CALENDAR_ID, start_time, end_time, 'Interview')
                        if org_event:
                            meeting_link = org_event.get('hangoutLink')
                            st.success(f"Event created in organization's calendar. Google Meet Link: {meeting_link}")
                            st.write(f"Google Meet Link: {meeting_link}")
                            send_email('Interview', start_time, end_time, meeting_link, user_email)
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
            else:
                st.write("No free slots available for scheduling.")

if __name__ == "__main__":
    if not os.path.exists(SERVICE_ACCOUNTS_DIR):
        os.makedirs(SERVICE_ACCOUNTS_DIR)
    main()
