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

SERVICE_ACCOUNTS_DIR = 'service_accounts'
SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.readonly"]
ORG_CALENDAR_ID = 'REPLACE_WITH_COMPANY_MAIL'

def authenticate(user_email):
    creds = None
    token_path = os.path.join(SERVICE_ACCOUNTS_DIR, f'{user_email}_token.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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

def calculate_free_slots(user_events, org_events, selected_date, timezone_str='Asia/Kolkata'):
    events = user_events + org_events

    tz = pytz.timezone(timezone_str)
    working_hours_start = tz.localize(datetime.datetime.combine(selected_date, datetime.time(9, 0)))
    working_hours_end = tz.localize(datetime.datetime.combine(selected_date, datetime.time(17, 0)))
    current_system_time = datetime.datetime.now(tz)

    if selected_date != current_system_time.date():
        current_system_time = working_hours_start

    occupied_slots = []
    for event in events:
        start_time = event.get('start', {}).get('dateTime')
        end_time = event.get('end', {}).get('dateTime')
        if start_time and end_time:
            try:
                event_start = datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S%z')
                event_end = datetime.datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S%z')
                occupied_slots.append((event_start.astimezone(tz), event_end.astimezone(tz)))
            except ValueError as e:
                st.error(f"Error parsing event times: {e}")

    occupied_slots.sort()
    free_slots = []
    current_time = max(current_system_time, working_hours_start)

    for event_start, event_end in occupied_slots:
        if event_start > current_time:
            free_slots.append((current_time, event_start))
        current_time = max(current_time, event_end)

    if current_time < working_hours_end:
        free_slots.append((current_time, working_hours_end))

    filtered_free_slots = []
    for start_time, end_time in free_slots:
        while start_time + datetime.timedelta(hours=1) <= end_time and start_time + datetime.timedelta(hours=1) <= working_hours_end :
            if start_time > datetime.datetime.now(tz):
                filtered_free_slots.append((start_time, start_time + datetime.timedelta(hours=1)))
            start_time += datetime.timedelta(hours=1)

    return filtered_free_slots

def display_free_slots(free_slots):
    st.write("Available time slots:")
    selected_slot = None
    for i, (start, end) in enumerate(free_slots):
        slot_str = f"{start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%Y-%m-%d %H:%M')}"
        if st.button(slot_str, key=f'slot_{i}'):
            selected_slot = (start, end)
    return selected_slot

def add_event_to_calendar(credentials, calendar_id, start_time, end_time, event_summary, hangout_link=None):
    try:
        service = build('calendar', 'v3', credentials=credentials)
        event = {
            'summary': event_summary,
            'location': 'Office',
            'description': 'A meeting',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': str(uuid.uuid4()),
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            } if not hangout_link else {
                'createRequest': {
                    'requestId': str(uuid.uuid4()),
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    },
                    'conferenceSolution': {
                        'conferenceId': hangout_link
                    }
                }
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        event = service.events().insert(calendarId=calendar_id, body=event, conferenceDataVersion=1).execute()
        return event
    except HttpError as error:
        st.error(f"An error occurred: {error}")
        return None

# Function to send email
def send_email(event_summary, start_time, end_time, meeting_link, recipient_email):
    # Set up SMTP server
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587  # For SSL: 465, For TLS: 587

    # Sender and receiver email addresses
    sender_email = 'REPLACE_WITH_COMPANY_MAIL'  # Change this to your email address
    receiver_email = recipient_email

    # Email content
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = 'Event Details'

    body = f"Event: {event_summary}\nTime: {start_time} - {end_time}\nGoogle Meet Link: {meeting_link}"
    message.attach(MIMEText(body, 'plain'))

    # Connect to SMTP server and send email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Enable TLS encryption
            server.login(sender_email, 'REPLACE_YOUR_PASSWORD')  # Change this to your password
            server.sendmail(sender_email, receiver_email, message.as_string())
        st.success('Email sent successfully!')
    except Exception as e:
        st.error(f"Failed to send email: {e}")

def main():
    st.title('Google Calendar Events Viewer & Scheduler')
    user_email = st.text_input("Enter your email address:")
    if user_email:
        user_creds = authenticate(user_email)

        if user_creds:
            st.success('Authenticated successfully.')
            selected_date = st.date_input('Select a date', value=datetime.date.today(), min_value=datetime.date.today())

            user_events = fetch_organization_calendar_events(user_creds, 'primary', selected_date)
            org_events = fetch_organization_calendar_events(user_creds, ORG_CALENDAR_ID, selected_date)

            if st.button('Fetch My Events'):
                events = user_events + org_events
                if events:
                    st.write('Events for selected date:')
                    for event in user_events:
                        event_start_time = event.get('start', {}).get('dateTime')
                        event_end_time = event.get('end', {}).get('dateTime')
                        if event_start_time and event_end_time:
                            start_time = datetime.datetime.strptime(event_start_time[:-6], '%Y-%m-%dT%H:%M:%S')
                            end_time = datetime.datetime.strptime(event_end_time[:-6], '%Y-%m-%dT%H:%M:%S')
                            st.write(f"- {event.get('summary', 'No summary available')} (Time: {start_time.time()} - {end_time.time()})")
                        else:
                            st.write(f"- {event.get('summary', 'No summary available')}")

            user_events = fetch_organization_calendar_events(user_creds, 'primary', selected_date)
            org_events = fetch_organization_calendar_events(user_creds, ORG_CALENDAR_ID, selected_date)
            free_slots = calculate_free_slots(user_events, org_events, selected_date)
            event_summary = st.text_input("Enter event summary:")
            e = event_summary
            selected_slot = display_free_slots(free_slots)

            if selected_slot is not None:
                start_time, end_time = selected_slot
                st.write(selected_slot)
                #add_event_button = st.button('Add Event')

                message_placeholder = st.empty()
                message_placeholder.write("Proceeding to create event...")

                org_creds = authenticate('poojithasarvamangala@gmail.com')
                org_event = add_event_to_calendar(org_creds, ORG_CALENDAR_ID, start_time, end_time, e)

                if org_event:
                    meeting_link = org_event.get('hangoutLink')
                    st.success(f"Event created in organization's calendar. Google Meet Link: {meeting_link}")
                    st.write(f"Google Meet Link: {meeting_link}")

                    # Create event in user's calendar with the same Google Meet link
                    user_event = add_event_to_calendar(user_creds, 'primary', start_time, end_time, e, hangout_link=meeting_link)

                    # Send email with event details
                    recipient_email = user_email  # You can change this to any email address
                    send_email(e, start_time, end_time, meeting_link, recipient_email)
                else:
                    st.warning('Failed to create event in organization\'s calendar. Please try again.')

if __name__ == "__main__":
    if not os.path.exists(SERVICE_ACCOUNTS_DIR):
        os.makedirs(SERVICE_ACCOUNTS_DIR)
    main()
