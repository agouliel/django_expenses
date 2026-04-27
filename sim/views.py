import os
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from django.http import JsonResponse
from google_auth_oauthlib.flow import Flow # google-auth-oauthlib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json

def sign_in(request):
    return render(request, 'sign_in.html')


@csrf_exempt
def auth_receiver(request):
    """
    Google calls this URL after the user has signed in with their Google account.
    """
    #token = request.POST['credential']
    #print(token)
    data = json.loads(request.body)
    auth_code = data.get('code')

    # Exchange Code for Calendar Access Tokens
    # use the file you downloaded from Google Console
    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, 'cred.json'),
        scopes=[
            'openid', 
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/calendar.readonly'
        ],
        redirect_uri='postmessage' # Standard for code exchange from JS
    )
    
    # This exchanges the temporary code for permanent tokens
    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    try:
        user_data = id_token.verify_oauth2_token(
            creds.id_token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']
        )
    except ValueError:
        return HttpResponse(status=403)

    # save any new user here to the database.
    # You could also authenticate the user here using the details from Google
    # https://docs.djangoproject.com/en/4.2/topics/auth/default/#how-to-log-a-user-in

    #email = user_data["email"]
    #user, created = models.User.objects.get_or_create(
        #email=email, defaults={"username": email, "sign_up_method": "google", "first_name": user_data.get("given_name"),}
    #)

    # Add any other logic, such as setting a http-only auth cookie as needed here.
    #return HttpResponse(status=200)

    request.session['user_data'] = user_data
    #print(user_data)

    # Save to Database
    # You should save creds.to_json() tied to your Django User model
    # user_profile.google_calendar_token = creds.to_json()
    # user_profile.save()
    
    #print(creds.to_json())

    token_file = 'token.json'
    with open(token_file, 'w') as token:
        token.write(creds.to_json())
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    service = build('calendar', 'v3', credentials=creds)

    month_start = '2026-04-01T00:00:00.000000Z'
    #month_start = datetime.datetime.today().date().replace(day=1).isoformat() + 'T00:00:00.000000Z'
    month_end = '2026-04-25T00:00:00.000000Z'

    events_result = service.events().list(calendarId='primary',
                                        timeMin=month_start,
                                        timeMax=month_end,
                                        singleEvents=True,
                                        orderBy='startTime').execute()

    events = events_result.get('items', [])
    print(events)

    return JsonResponse({'status': 'success'})

    return redirect('sign_in')


def sign_out(request):
    del request.session['user_data']
    return redirect('sign_in')
