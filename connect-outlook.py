"""Interactive local OAuth setup. Never accepts a password or client secret."""
import json
import os
import re
import sqlite3
from pathlib import Path
from joblane.outlook import client, SCOPES

root=Path(__file__).resolve().parent
directory=Path(os.getenv('JOBLANE_DATA_DIR',str(root/'data'))).resolve()
if not (directory/'joblane.sqlite3').exists():raise SystemExit('Initialize Joblane first.')
print('Use your own Microsoft Entra app registration (public desktop client).')
print('Account type: organizational + personal Microsoft accounts. Redirect URI: http://localhost')
print('Delegated permission: Microsoft Graph / Mail.Send. No client secret is needed.')
client_id=input('Application (client) ID: ').strip()
if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',client_id):raise SystemExit('Invalid client ID.')
app,cache,ring,service=client(directory,client_id)
print('Complete Microsoft sign-in and consent in your browser. No email is sent by setup.')
result=app.acquire_token_interactive(scopes=SCOPES,prompt='select_account',timeout=300)
if 'access_token' not in result:raise SystemExit('Sign-in did not complete. Check the app registration and retry.')
claims=result.get('id_token_claims',{})
accounts=app.get_accounts(username=claims.get('preferred_username'))
if len(accounts)!=1:raise SystemExit('Could not select exactly one signed-in account. Reconnect with one account.')
account=accounts[0]
ring.set_password(service,'oauth-cache',cache.serialize())
config={'client_id':client_id,'account_id':account['home_account_id'],'username':account.get('username','')}
with sqlite3.connect(directory/'joblane.sqlite3') as db:
    db.execute('INSERT OR REPLACE INTO config VALUES (?,?)',('outlook',json.dumps(config)))
print('Outlook connected. Tokens are in your OS credential store. Refresh Joblane to see the account.')
