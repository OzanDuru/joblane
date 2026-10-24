"""Outlook via delegated Microsoft Graph Mail.Send; no mailbox reading."""
import base64
import hashlib
import json
import re
import threading
import urllib.request
import urllib.error
from email.message import EmailMessage
from email.policy import SMTP
from .policy import digest

SCOPES=['https://graph.microsoft.com/Mail.Send']
AUTHORITY='https://login.microsoftonline.com/common'
_LOCK=threading.RLock()


def secure_keyring():
    import keyring
    backend=keyring.get_keyring()
    if not type(backend).__module__.startswith(('keyring.backends.macOS','keyring.backends.Windows','keyring.backends.SecretService')):
        raise ValueError('A native OS credential store is required; plaintext token storage is disabled.')
    return keyring


def cache_service(directory):
    return 'Joblane-Outlook-'+hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:16]


def client(directory,client_id):
    import msal
    ring=secure_keyring();service=cache_service(directory)
    cache=msal.SerializableTokenCache()
    saved=ring.get_password(service,'oauth-cache')
    if saved:cache.deserialize(saved)
    app=msal.PublicClientApplication(client_id,authority=AUTHORITY,token_cache=cache)
    return app,cache,ring,service


def access_token(store):
    config=store.get('outlook',{})
    if not config.get('client_id') or not config.get('account_id'):raise ValueError('Connect Outlook locally with connect-outlook.py first.')
    with _LOCK:
        app,cache,ring,service=client(store.directory,config['client_id'])
        accounts=[a for a in app.get_accounts() if a['home_account_id']==config['account_id']]
        if len(accounts)!=1:raise ValueError('Outlook needs sign-in again. Run connect-outlook.py.')
        result=app.acquire_token_silent(SCOPES,account=accounts[0])
        if cache.has_state_changed:ring.set_password(service,'oauth-cache',cache.serialize())
        if not result or 'access_token' not in result:raise ValueError('Outlook sign-in expired or requires attention. Run connect-outlook.py.')
        return result['access_token']


def email_address(value):
    if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',value):
        raise ValueError('Enter one valid recipient email address from the employer’s published contact details.')
    return value


def mime_message(delivery,attachment,sender=''):
    msg=EmailMessage(policy=SMTP)
    if sender:msg['From']=email_address(sender)
    msg['To']=email_address(delivery['destination']);msg['Subject']=delivery['subject']
    msg['X-Unsent']='1'
    msg.set_content(delivery['body'])
    msg.add_attachment(attachment,maintype='application',subtype='pdf',filename=f'CV-application-{delivery["job_id"]}.pdf')
    return msg.as_bytes()


class Outlook:
    def __init__(self,store,worker):self.store=store;self.worker=worker;self.history=worker.history

    def status(self):
        config=self.store.get('outlook',{})
        return {'configured':bool(config.get('account_id')),'account':config.get('username',''),'provider':'Microsoft Graph','permission':'Mail.Send'}

    def draft(self,job_id,recipient,subject,body):
        with self.store.lock:
            job=self.store.job(job_id)
            if job['status'] in ('running','submitting','submitted','skipped','queued') or self.worker.current==job_id or self.store.get(f'attempt:{job_id}'):
                raise ValueError('This application is active or may already have been sent.')
            recipient=email_address(recipient.strip())
            if not isinstance(subject,str) or not subject.strip() or len(subject)>250 or '\r' in subject or '\n' in subject:raise ValueError('Use a single-line subject under 250 characters.')
            if not isinstance(body,str) or not 20<=len(body)<=10000:raise ValueError('Email body must contain 20–10,000 characters.')
            if digest(self.store.get('profile'),job)!=job['approval_digest']:raise ValueError('Rebuild or reanalyze the CV after your profile changes.')
            version=self.history.archive_cv(job_id,'Email attachment')
            ident=self.history.create(job_id,'outlook',recipient,'draft',version,subject.strip(),body.strip(),'Saved locally. Not sent.')
            self.store.set(f'email-sender:{ident}',self.status()['account'])
            self.store.set(f'email-digest:{ident}',job['approval_digest'])
            self.store.event(job_id,'Outlook email draft and exact CV attachment saved locally.')
            return ident

    def send(self,delivery_id,reviewed):
        if reviewed is not True:raise ValueError('Review the recipient, text and attached CV before sending.')
        with self.store.lock:
            d=self.history.delivery(delivery_id);job=self.store.job(d['job_id'])
            if d['channel']!='outlook' or d['status']!='draft':raise ValueError('Only an unsent email draft can be sent.')
            if job['demo']:raise ValueError('Practice jobs cannot send real emails.')
            if self.worker.paused.is_set():raise ValueError('Resume Joblane first.')
            if self.worker.current==job['id'] or job['status'] in ('running','submitting','submitted','queued','skipped') or self.store.get(f'attempt:{job["id"]}'):
                raise ValueError('This job is active, sent or has an uncertain previous submission.')
            if digest(self.store.get('profile'),job)!=self.store.get(f'email-digest:{delivery_id}'):
                raise ValueError('Profile or job changed. Prepare and review a new email draft.')
            token=access_token(self.store)
            sender=self.status()['account']
            previous_sender=self.store.get(f'email-sender:{delivery_id}','')
            if previous_sender and previous_sender!=sender:raise ValueError('Outlook account changed. Prepare a new draft for the connected sender.')
            self.store.set(f'email-sender:{delivery_id}',sender)
            attachment=self.history.cv_bytes(d['cv_version_id'])
            if len(attachment)>2_500_000:raise ValueError('Use a PDF under 2.5 MB for this email adapter.')
            payload={'message':{'subject':d['subject'],'body':{'contentType':'Text','content':d['body']},'toRecipients':[{'emailAddress':{'address':d['destination']}}],'attachments':[{'@odata.type':'#microsoft.graph.fileAttachment','name':f'CV-application-{job["id"]}.pdf','contentType':'application/pdf','contentBytes':base64.b64encode(attachment).decode()}]},'saveToSentItems':True}
            request=urllib.request.Request('https://graph.microsoft.com/v1.0/me/sendMail',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
            self.history.update(delivery_id,'sending','Sending through Outlook.')
            self.store.set(f'attempt:{job["id"]}',True)
            self.store.update(job['id'],status='submitting',reason='Sending reviewed Outlook email.')
        # Never retry this request automatically: a timeout can occur after acceptance.
        try:
            with urllib.request.urlopen(request,timeout=40) as response:
                if response.status!=202:raise ValueError('Unexpected delivery status')
        except Exception:
            self.history.update(delivery_id,'uncertain','Outlook result is uncertain. Check Sent Items before any retry.')
            self.store.update(job['id'],status='needs_attention',reason='Email result uncertain. Check Outlook Sent Items; no automatic resend.')
            self.worker.notify(job['id'])
            return 'uncertain'
        self.history.update(delivery_id,'accepted','Microsoft accepted the send request (202). This is not proof of recipient delivery. Check Outlook Sent Items.')
        self.store.update(job['id'],status='needs_attention',reason='Outlook accepted the email. Check Sent Items and record confirmation; employer receipt is not verified.')
        self.store.event(job['id'],'Outlook accepted the email request. Exact text and CV are archived; no automatic resend.')
        return 'accepted'
