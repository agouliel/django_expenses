from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import User
import ast

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_service(user_email):
    user = User.objects.get(email=user_email)
    creds = Credentials.from_authorized_user_info(ast.literal_eval(user.google_calendar_token), SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service