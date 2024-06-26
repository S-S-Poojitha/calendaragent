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

warnings.filterwarnings("ignore")

SERVICE_ACCOUNTS_DIR = 'service_accounts'
SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.readonly"]
ORG_CALENDAR_ID = 'poojithasarvamangala@gmail.com'
DEFAULT_SLOT_DURATION = 60  # Default slot duration in minutes
slot_durations_file = 'slot_durations.json'

# Static password for the organization email (for demonstration purposes)
ORG_PASSWORD = 'org'  # This should be securely stored and managed in practice

st.title('Google Calendar Events Viewer & Scheduler')
user_email = st.text_input("Enter your email address:")

def authenticate(user_email):
    creds = None
    token_path = os.path.join(SERVICE_ACCOUNTS_DIR, f'{user_email}_token.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    else:
        st.write(f"No token found for {user_email}. Please authorize access.")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                st.error(f"Failed to refresh credentials: {e}")
                logging.error(f"Failed to refresh credentials for {user_email}: {e}")
                return None
        else:
            flow = Flow.from_client_secrets_file('credentials.json', SCOPES)
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.write('Please go to this URL and authorize access:')
            st.write(auth_url)

            code = st.text_input('Enter the authorization code here:')
            if code:
                try:
                    flow.fetch_token(code=code)
                    creds = flow.credentials
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    st.error(f"Failed to fetch token: {e}")
                    logging.error(f"Failed to fetch token for {user_email}: {e}")

    return creds

def fetch_calendar_events(credentials, calendar_id, selected_date):
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

def calculate_free_slots(user_events, org_events, selected_date, slot_duration, timezone_str='Asia/Kolkata'):
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
        while start_time + datetime.timedelta(minutes=slot_duration) <= end_time and start_time + datetime.timedelta(minutes=slot_duration) <= working_hours_end:
            if start_time > datetime.datetime.now(tz):
                filtered_free_slots.append((start_time, start_time + datetime.timedelta(minutes=slot_duration)))
            start_time += datetime.timedelta(minutes=slot_duration)

    return filtered_free_slots

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
            'attendees': [
                {'email': user_email},  # Add the email of the user to invite
            ],
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

        if hangout_link:
            event['conferenceData']['entryPoints'] = [{
                'entryPointType': 'video',
                'uri': hangout_link,
                'label': 'Google Meet'
            }]

        event = service.events().insert(calendarId=calendar_id, body=event, conferenceDataVersion=1).execute()
        return event
    except HttpError as error:
        st.error(f"An error occurred: {error}")
        return None


def send_email(event_summary, start_time, end_time, meeting_link, recipient_email, password=None):
    # Set up SMTP server
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587  # For SSL: 465, For TLS: 587

    # Sender and receiver email addresses
    sender_email = 'poojithasarvamangala@gmail.com'  # Change this to your email address
    receiver_email = recipient_email

    # Email content
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = 'Event Details'

    body = f"Event: {event_summary}\nTime: {start_time} - {end_time}\nGoogle Meet Link: {meeting_link}"
    if password:
        body += f"\nPassword for organization email confirmation: {password}"

    # Add event invitation details
    event_invite = f"\n\nPlease respond with Yes/No/Maybe directly from Google Calendar"
    body += event_invite

    message.attach(MIMEText(body, 'plain'))

    # Connect to SMTP server and send email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Enable TLS encryption
            server.login(sender_email, 'ferm bqim epzj xdlc')  # Change this to your password
            server.sendmail(sender_email, receiver_email, message.as_string())
        st.success('Email sent successfully!')
    except Exception as e:
        st.error(f"Failed to send email: {e}")


def save_default_slot_duration(duration):
    try:
        with open(slot_durations_file, 'r+') as file:
            data = json.load(file)  # Load existing data
            data["default_slot_duration"] = duration  # Update the default slot duration
            file.seek(0)  # Move the file pointer to the beginning
            json.dump(data, file, indent=4)  # Write the updated data back to the file
            file.truncate()  # Remove any remaining content (in case the new content is shorter)
        st.success(f"Default slot duration updated to {duration} minutes.")
    except Exception as e:
        st.error(f"Failed to save default slot duration: {e}")

        
def load_default_slot_duration():
    if os.path.exists(slot_durations_file):
        with open(slot_durations_file, 'r') as file:
            slot_durations = json.load(file)
        return slot_durations.get("default_slot_duration", DEFAULT_SLOT_DURATION)
    return DEFAULT_SLOT_DURATION


def display_slots(free_slots):
    st.write("Available time slots:")
    selected_slot = None
    for i, (start, end) in enumerate(free_slots):
        slot_str = f"{start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%Y-%m-%d %H:%M')}"
        if st.button(slot_str, key=f'slot_{i}'):
            selected_slot = (start, end)
    return selected_slot


def main():
    if user_email=='poojithasarvamangala@gmail.com':
            org_password = st.text_input("Enter organization password:", type="password")
            if org_password == ORG_PASSWORD:
                st.success("Password correct! You can now change the slot duration.")
                new_duration = st.number_input("Enter new slot duration (in minutes):", min_value=1, step=1)
                if st.button("Save Slot Duration"):
                   # selected_date = st.date_input('Select a date', value=datetime.date.today() + datetime.timedelta(days=2), min_value=datetime.date.today() + datetime.timedelta(days=2))  # Change this to adjust the number of days to check
                    save_default_slot_duration(new_duration)
                    st.success(f"Slot duration updated to {new_duration} minutes.")
            elif org_password:
                st.error("Incorrect password. Please try again.")
    else:
        user_creds = authenticate(user_email)
        if user_creds:
            st.success('Authenticated successfully.')
            selected_date = st.date_input('Select a date', value=datetime.date.today() + datetime.timedelta(days=2), min_value=datetime.date.today() + datetime.timedelta(days=2))  # Change this to adjust the number of days to check
            slot_duration = load_default_slot_duration()
            st.write(f"Current slot duration: {slot_duration} minutes")
            user_events = fetch_calendar_events(user_creds, 'primary', selected_date)
            org_events = fetch_calendar_events(user_creds, ORG_CALENDAR_ID, selected_date)
            free_slots = calculate_free_slots(user_events, org_events, selected_date, slot_duration)

            if st.button('Fetch Events'):
                events = fetch_calendar_events(user_creds, 'primary', selected_date)
                if events:
                    st.write('Events for selected date:')
                    for event in events:
                        event_start_time = event.get('start', {}).get('dateTime')
                        event_end_time = event.get('end', {}).get('dateTime')
                        if event_start_time and event_end_time:
                            start_time = datetime.datetime.strptime(event_start_time[:-6], '%Y-%m-%dT%H:%M:%S')
                            end_time = datetime.datetime.strptime(event_end_time[:-6], '%Y-%m-%dT%H:%M:%S')
                            st.write(f"- {event.get('summary', 'No summary available')} (Time: {start_time.time()} - {end_time.time()})")

            if free_slots:
                selected_slot = display_slots(free_slots)
                if selected_slot:
                    message_placeholder = st.empty()
                    org_creds = authenticate(ORG_CALENDAR_ID)
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
