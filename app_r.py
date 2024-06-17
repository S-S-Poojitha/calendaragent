import streamlit as st
import requests

CALENDLY_API_TOKEN = 'eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzE4NjAwNjU1LCJqdGkiOiI5YjEwY2RmOC0xYjc3LTQ0Y2QtYWNlZi02NTRiN2U5YWRhM2MiLCJ1c2VyX3V1aWQiOiI0Yjc3MzljYy0wMmUwLTRlNzEtYWRhOS02ZGVkZDE0MjNhOWUifQ.r7BmZgF3IomyAkALMMzk29K361AxTzzUQkz4IHIg5wYDiU9_OtirKPoUmEGb4OplQ3nkVdaVZlkYVI41v-2y4A'
CALENDLY_EVENT_TYPE_LINK = 'https://calendly.com/poojithasarvamangala/interview'  # e.g., https://calendly.com/your-username/interview

def get_available_slots():
    url = f'https://api.calendly.com/scheduled_events/{CALENDLY_EVENT_TYPE_LINK}/available_times'
    headers = {
        'Authorization': f'Bearer {CALENDLY_API_TOKEN}',
    }
    response = requests.get(url, headers=headers)
    return response.json()

def main():
    st.title("Interview Slot Selection")
    st.write("Please select your preferred interview slot from the available options below:")

    email = st.text_input("Enter your email:")
    if email:
        slots = get_available_slots()
        if slots:
            slot = st.selectbox("Available Slots", [slot['start_time'] for slot in slots['data']])
            if st.button("Submit"):
                st.success(f"Your interview slot {slot} has been booked. Please check your email for confirmation.")
                # You can handle booking logic here or through Calendly's web interface

if __name__ == '__main__':
    main()
