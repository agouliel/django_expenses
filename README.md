## Auth Flow: Step by Step                                                       
                                                                            
1. Frontend — Authorization Code Request (`sign_in.html`)   
When the user clicks "Sign in with Google", `startAuthFlow()` calls `client.requestCode()` on the Google Identity Services (GIS) OAuth2 client, which was initialized with:
- `client_id`: the app's Google OAuth client ID
- `scope: openid email profile calendar.readonly`
- `ux_mode: 'popup'`: opens a Google consent popup                              
- `redirect_uri: 'postmessage'`: tells Google to return the auth code directly to the JavaScript callback (not via a URL redirect)                           
                
Google shows the consent screen. On approval, the GIS library calls the callback with `response.code` — a short-lived authorization code (not a token yet).

2. Frontend -> Backend — Code POSTed to Django (`sign_in.html`)   
The JS immediately POSTs the code to the backend:
```
POST /auth-receiver
Body: { "code": "<authorization_code>" }
```

After the fetch resolves, the browser redirects to `/expenses`. This redirect happens client-side before the server's redirect response is processed.

3. Backend — Token Exchange (`views.py`)   
`auth_receiver` parses the JSON body to get the code, then uses `google_auth_oauthlib.flow.Flow` to exchange it for tokens:
```
flow = Flow.from_client_secrets_file(                                         
    'cred.json',   # downloaded from Google Cloud Console                     
    scopes=[...],                                                             
    redirect_uri='postmessage'  # must match what the JS client sent          
)                                                                             
flow.fetch_token(code=auth_code)
creds = flow.credentials                                                      
```
`flow.fetch_token()` makes a server-to-server POST to https://oauth2.googleapis.com/token. Google returns:
- `access_token` — short-lived, used to call Google APIs                        
- `refresh_token` — long-lived, used to get new access tokens silently          
- `id_token` — a JWT containing the user's identity claims (email, sub, name, picture, etc.)
                                                                            
All of this is bundled into `creds` (a `google.oauth2.credentials.Credentials` object).  

4. Backend — Identity Verification (`views.py`)   
The `id_token` JWT is verified cryptographically:
```
user_data = id_token.verify_oauth2_token(
    creds.id_token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']  
)                                                                             
```
This checks:                                                                  
- The JWT signature (against Google's public keys)
- The aud claim matches GOOGLE_OAUTH_CLIENT_ID                           
- The token is not expired                         
                                                                            
On failure, returns HTTP 403. On success, `user_data` is a dict with email, sub, name, picture, etc.

5. Backend — User Upsert (`views.py`)   
The token is persisted to the `User` model (keyed by `email`)
```
user = User.objects.get(email=user_data['email'])                             
user.google_calendar_token = creds.to_json()  # overwrites on re-login
# ...or on first login:                                                       
user = User(email=user_data['email'], id=uuid.uuid4(),                        
google_calendar_token=creds.to_json())                                        
user.save()                                                                   
```
`creds.to_json()` serializes the entire credentials object — access token, refresh token, expiry, scopes — as a JSON string stored in the `google_calendar_token` TextField.   
                
Note: id is set to a random uuid4(), not to the Google sub ID.

6. Backend — Session Set + Calendar Sync (`views.py`)
```
request.session['user_data'] = user_data  # stores Google profile in Django session
service = gcal_get_service(user.email)
insert_to_db(service, user.id)                                                
return redirect('expenses')                                                   
```
The Django session cookie is set on the response. All subsequent requests are identified by this session.

7. Calendar API Usage (`gcal.py`)   
On any subsequent request requiring calendar access:
```
creds = Credentials.from_authorized_user_info(
    ast.literal_eval(user.google_calendar_token), SCOPES                      
)                                                                             
service = build('calendar', 'v3', credentials=creds)
```
The stored JSON token is deserialized back into a Credentials object. The Google client library automatically refreshes the access token using the stored refresh token when it's expired — but the refreshed token is not written back to the database, so after the first expiry the stored access token becomes stale (though the refresh token keeps it working at runtime).
