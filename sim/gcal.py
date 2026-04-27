from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import User

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_service(user_email):
    user = User.objects.get(email=user_email)

    token_file = 'token.json'
    with open(token_file, 'w') as token:
        token.write(user.google_calendar_token)

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service