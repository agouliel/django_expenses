import os, datetime, sqlite3, psycopg2
from django.conf import settings

def insert_to_db(service, user_id):
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    month_start = datetime.datetime.today().date().replace(day=1).isoformat() + 'T00:00:00.000000Z'
    month_end = now

    events_result = service.events().list(calendarId='primary',
                                            timeMin=month_start,
                                            timeMax=month_end,
                                            singleEvents=True,
                                            orderBy='startTime').execute()

    events = events_result.get('items', [])

    events_with_expenses = []

    for event in events:
        parts = event.get("summary", "").split()
        
        # Check if we have enough parts and if the first part is numeric
        if parts:
            first_word = parts[0]
            
            # This check handles both integers and decimals
            if first_word.replace('.', '', 1).isdigit():
                amount = float(first_word)
                hashtag = parts[-1]

                event_with_expense = (
                    event.get('id'),
                    user_id,
                    event['start']['dateTime'][:10],
                    hashtag[1:],
                    ' '.join(parts[1:-1]), # summary
                    amount,
                    event.get('htmlLink')
                )
                events_with_expenses.append(event_with_expense)

    # we should use the models here
    db_path = settings.DATABASES['default']['NAME']
    with sqlite3.connect(db_path) as conn:
        conn.executemany('''
            INSERT OR REPLACE INTO tbl_expenses(id, user_id, date_start, hashtag, summary, amount, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            events_with_expenses
        )
        conn.commit()
    print(f'Saved to {db_path}')

    pg_host = os.environ.get('PGHOST')
    if pg_host:
        pg_conn = psycopg2.connect(
            host=pg_host,
            port=os.environ.get('PGPORT', 5432),
            dbname=os.environ.get('PGDATABASE', 'expenses'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
        )
        with pg_conn:
            with pg_conn.cursor() as cur:
                cur.executemany('''
                    INSERT INTO tbl_expenses(id, user_id, date_start, hashtag, summary, amount, url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET (date_start, hashtag, summary, amount, url) =
                    (EXCLUDED.date_start, EXCLUDED.hashtag, EXCLUDED.summary, EXCLUDED.amount, EXCLUDED.url)
                    ''',
                    events_with_expenses
                )
