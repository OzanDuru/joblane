import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
import pytest
from test_joblane import env, profile, add
from joblane.outlook import Outlook, mime_message
from joblane.codex_agent import validate_email


def draft(env):
    app,s,c,h=env
    job=add(c,h).json['id']
    r=c.post(f'/api/jobs/{job}/email',json={'recipient':'careers@example.com','subject':'Software Engineer application','body':'Hello, I would like to apply for this role. My CV is attached.'},headers=h)
    assert r.status_code==201
    return app,s,c,h,job,r.json['id']


def test_archive_is_exact_and_survives_current_cv_changes(env):
    app,s,c,h,j,d=draft(env);history=app.extensions['worker'].history
    version=history.delivery(d)['cv_version_id'];before=history.cv_bytes(version)
    Path(s.job(j)['cv_path']).write_bytes(b'new working draft')
    assert history.cv_bytes(version)==before
    r=c.get(f'/api/history/cvs/{version}')
    assert r.status_code==200 and r.data==before
    assert app.test_client().get(f'/api/history/cvs/{version}').status_code==401


def test_eml_keeps_subject_body_and_exact_attachment(env):
    app,s,c,h,j,d=draft(env)
    raw=c.get(f'/api/history/emails/{d}').data
    msg=BytesParser(policy=policy.default).parsebytes(raw)
    assert msg['To']=='careers@example.com' and msg['Subject']=='Software Engineer application'
    assert 'would like to apply' in msg.get_body().get_content()
    attachment=list(msg.iter_attachments())[0]
    history=app.extensions['worker'].history
    assert attachment.get_payload(decode=True)==history.cv_bytes(history.delivery(d)['cv_version_id'])


def test_recipient_and_subject_injection_rejected(env):
    app,s,c,h=env;j=add(c,h).json['id']
    for recipient,subject in [('a@example.com,b@example.com','Hello'),('a@example.com','Hi\r\nBcc: x@example.com')]:
        assert c.post(f'/api/jobs/{j}/email',json={'recipient':recipient,'subject':subject,'body':'A sufficiently long test email body.'},headers=h).status_code==400


def test_send_needs_review_and_connection(env,monkeypatch):
    app,s,c,h,j,d=draft(env)
    assert c.post(f'/api/history/emails/{d}/send',json={'reviewed':False},headers=h).status_code==400
    assert c.post(f'/api/history/emails/{d}/send',json={'reviewed':True},headers=h).status_code==400
    assert not s.get(f'attempt:{j}')


def test_outlook_acceptance_archived_without_claiming_delivery(env,monkeypatch):
    app,s,c,h,j,d=draft(env)
    monkeypatch.setattr('joblane.outlook.access_token',lambda store:'fake-test-token')
    requests=[]
    class Response:
        status=202
        def __enter__(self):return self
        def __exit__(self,*args):pass
    def accept(request,**kwargs):requests.append(request);return Response()
    monkeypatch.setattr('joblane.outlook.urllib.request.urlopen',accept)
    r=c.post(f'/api/history/emails/{d}/send',json={'reviewed':True},headers=h)
    assert r.json['status']=='accepted' and s.job(j)['status']=='needs_attention'
    payload=json.loads(requests[0].data)
    assert payload['saveToSentItems'] is True and len(payload['message']['attachments'])==1
    assert c.post(f'/api/history/emails/{d}/send',json={'reviewed':True},headers=h).status_code==400
    assert len(requests)==1


def test_timeout_never_retries(env,monkeypatch):
    app,s,c,h,j,d=draft(env)
    monkeypatch.setattr('joblane.outlook.access_token',lambda store:'fake-test-token')
    count=[]
    def timeout(*args,**kwargs):count.append(1);raise TimeoutError()
    monkeypatch.setattr('joblane.outlook.urllib.request.urlopen',timeout)
    assert c.post(f'/api/history/emails/{d}/send',json={'reviewed':True},headers=h).json['status']=='uncertain'
    assert c.post(f'/api/history/emails/{d}/send',json={'reviewed':True},headers=h).status_code==400
    assert len(count)==1 and s.get(f'attempt:{j}')


def test_stale_email_draft_cannot_send(env):
    app,s,c,h,j,d=draft(env);p=s.get('profile');p['headline']='Updated';s.set('profile',p)
    r=c.post(f'/api/history/emails/{d}/send',json={'reviewed':True},headers=h)
    assert r.status_code==400 and 'changed' in r.json['error']


def test_email_schema_and_cv_apply_separated(env):
    app,s,c,h=env;a=app.extensions['agent'];a.binary='fake';s.set('ai_config',{**a.config(),'enabled':True,'auto_prepare':False})
    j=add(c,h).json['id']
    run=a.enqueue(j,kind='email',message='Turkish speculative application.')
    result={'subject':'Yazılım geliştirme fırsatları','body':'Merhaba, yazılım geliştirme fırsatları için iletişime geçiyorum.','fact_ids':['skills'],'questions':[]}
    validate_email(result,s.get('profile'));a.update(run,status='completed',result=json.dumps(result))
    with pytest.raises(ValueError):a.apply(run)
    assert 'speculative applications' in a.prompt(a.get_run(run))
