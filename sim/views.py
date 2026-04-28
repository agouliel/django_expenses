import os
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from django.http import JsonResponse
from google_auth_oauthlib.flow import Flow # google-auth-oauthlib
import json
from .gcal import get_service as gcal_get_service
from .models import User
import uuid
from .expenses import insert_to_db
from django.shortcuts import render, get_object_or_404
from collections import defaultdict
from .models import Expense
from calendar import month_abbr


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

    #user, created = User.objects.get_or_create(
        #email=user_data['email'],
        #defaults={'id':uuid.uuid4(), 'google_calendar_token':creds.to_json()}
    #)

    try:
        user = User.objects.get(email=user_data['email'])
        user.google_calendar_token = creds.to_json()
        user.save()
    except User.DoesNotExist:
        user = User(email=user_data['email'], id=uuid.uuid4(), google_calendar_token=creds.to_json())
        user.save()

    # Add any other logic, such as setting a http-only auth cookie as needed here.
    #return HttpResponse(status=200)

    request.session['user_data'] = user_data
    #print(user_data)
    
    #print(creds.to_json())

    service = gcal_get_service(user.email)
    insert_to_db(service, user.id)
    
    #return JsonResponse({'status': 'success'})
    return redirect('expenses')


def sign_out(request):
    del request.session['user_data']
    return redirect('sign_in')


def serialize_expense(e):
    return {
        "id": e.id,
        "summary": e.summary,
        "amount": e.amount,
        "url": e.url,
    }


def expenses_view(request):
    # https://chatgpt.com/c/69ef68dc-8920-8332-aca8-efc06fde66b2
    
    email = request.session['user_data']['email']
    user = User.objects.get(email=email)
    user_id = user.id
    year = request.GET.get("year")

    expenses = Expense.objects.filter(user_id=user_id)

    # Filter by year (since date_start is text, we assume format "YYYY-MM-DD")
    if year:
        expenses = expenses.filter(date_start__startswith=year)

    # Build pivot: {category: {month: total}}
    pivot = defaultdict(lambda: {m: 0 for m in range(1, 13)})
    expense_map = defaultdict(list)

    for exp in expenses:
        if not exp.date_start:
            continue

        try:
            month = int(exp.date_start[5:7])
        except:
            continue

        category = exp.hashtag or "Uncategorized"

        pivot[category][month] += exp.amount or 0
        expense_map[(category, month)].append(exp)
    
    expense_map_serialized = {
        f"{category}|{month}": [serialize_expense(e) for e in expenses]
        for (category, month), expenses in expense_map.items()
    }

    # Totals
    totals_by_month = {m: 0 for m in range(1, 13)}
    totals_by_category = {}

    for category, months in pivot.items():
        totals_by_category[category] = sum(months.values())
        for m, val in months.items():
            totals_by_month[m] += val

    MONTHS = [(i, month_abbr[i]) for i in range(1, 13)]
    
    context = {
        "pivot": dict(pivot),
        "expense_map": dict(expense_map),
        "totals_by_month": totals_by_month,
        "totals_by_category": totals_by_category,
        "year": year,
        "years": sorted(
            set(
                e.date_start[:4]
                for e in Expense.objects.exclude(date_start__isnull=True)
            )
        ),
        "months": MONTHS,
        "expense_map_json": json.dumps(expense_map_serialized),
    }

    return render(request, "expenses.html", context)
