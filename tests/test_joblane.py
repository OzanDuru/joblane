import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from werkzeug.security import generate_password_hash
from pypdf import PdfReader
from joblane.server import create_app
from joblane.store import Store, DEFAULT_SETTINGS
from joblane.policy import normalize_url, within_window, validate_settings, digest, matches_preferences
from joblane.browser import field_value, Handoff
from joblane.cv import generate, tailor

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def profile():
    return json.loads((ROOT/'starter-profile.json').read_text())


@pytest.fixture
def env(tmp_path,profile):
    app=create_app(tmp_path,start_worker=False)
    app.config['TESTING']=True
    store=app.extensions['store']
    store.set('password_hash',generate_password_hash('private-test-password'))
    store.set('profile',profile)
    client=app.test_client()
    res=client.post('/api/login',json={'password':'private-test-password'},headers={'Origin':'http://127.0.0.1:8765'})
    headers={'Origin':'http://127.0.0.1:8765','X-CSRF-Token':res.json['csrf']}
    return app,store,client,headers


def add(client,headers,**extra):
    data={'url':'https://example.com/careers/123','company':'Example','title':'Software Engineer','description':'Python SQL REST APIs. Full-time. Istanbul.','track':'software',**extra}
    return client.post('/api/jobs',json=data,headers=headers)


def test_auth_required(env):
    app,*_=env
    c=app.test_client()
    assert c.get('/api/state').status_code==401
    assert c.get('/').status_code==200


def test_csrf_and_origin(env):
    app,store,client,headers=env
    assert client.post('/api/jobs',json={}).status_code==403
    assert client.post('/api/jobs',json={},headers={**headers,'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/jobs',json={},headers={'Origin':headers['Origin']}).status_code==403
    assert client.get('/api/state',headers={'Host':'evil.example'}).status_code==400


def test_logout_invalidates_session(env):
    _,_,c,h=env
    assert c.post('/api/logout',json={},headers=h).status_code==200
    assert c.get('/api/state').status_code==401


@pytest.mark.parametrize('url',['http://example.com','https://localhost/test','https://127.0.0.1','https://192.168.1.1','https://100.64.0.1','https://user:password@example.com','https://example.com:8765','file:///etc/passwd','https://device.tailnet.ts.net'])
def test_rejects_unsafe_job_destinations(url):
    with pytest.raises(ValueError):normalize_url(url)


def test_duplicate_tracking_urls(env):
    _,store,c,h=env
    assert add(c,h,url='https://example.com/careers/123/?utm_source=foo#apply').status_code==201
    res=add(c,h,url='https://example.com/careers/123?utm_source=bar')
    assert res.status_code==400
    assert len(store.jobs())==1


def test_schedule_boundaries_and_timezone():
    s=DEFAULT_SETTINGS.copy()
    assert within_window(s,datetime(2026,10,24,12,0,tzinfo=timezone.utc))
    assert not within_window(s,datetime(2026,10,24,11,59,tzinfo=timezone.utc))
    assert not within_window(s,datetime(2026,10,24,17,0,tzinfo=timezone.utc))
    s['days']=[0]
    assert not within_window(s,datetime(2026,10,24,12,0,tzinfo=timezone.utc))


def test_invalid_schedule_and_board_authorization():
    for extra in ({'start':'25:00'},{'end':'14:00'},{'days':[]},{'daily_limit':0},{'allowed_domains':['www.linkedin.com']}):
        with pytest.raises(ValueError):validate_settings({**DEFAULT_SETTINGS,**extra})


def test_filters_are_optional():
    j={'title':'Any role','description':'Anywhere'}
    assert matches_preferences(j,DEFAULT_SETTINGS)[0]
    assert not matches_preferences(j,{**DEFAULT_SETTINGS,'roles':'Python, SQL'})[0]


def test_cv_tailoring_preserves_facts_and_unicode(profile,tmp_path):
    job={'title':'Cybersecurity Python','description':'Phishing detection Python','track':'security'}
    result=tailor(profile,job)
    assert result['projects'][0]['title']=='Phishing URL Detection'
    assert sorted(p['text'] for p in result['projects'])==sorted(p['text'] for p in profile['projects'])
    out=tmp_path/'cv.pdf'
    generate(profile,job,out)
    text='\n'.join(p.extract_text() for p in PdfReader(out).pages)
    assert 'Ozan Duru' in text and 'TÜBİTAK' in text
    assert 'Phishing URL Detection' in text and 'penetration testing' not in text.lower()


def test_profile_change_invalidates_approval(env,profile):
    _,store,c,h=env
    job_id=add(c,h).json['id']
    assert c.post(f'/api/jobs/{job_id}/action',json={'action':'queue','authorize':True},headers=h).status_code==200
    profile['phone']='01234567890'
    assert c.put('/api/profile',json=profile,headers=h).status_code==200
    assert store.job(job_id)['authorized']==0
    assert store.job(job_id)['status']=='needs_attention'
    assert c.post(f'/api/jobs/{job_id}/action',json={'action':'fill','authorize':True},headers=h).status_code==400


def test_per_destination_authorization(env):
    _,store,c,h=env
    job_id=add(c,h).json['id']
    assert c.post(f'/api/jobs/{job_id}/action',json={'action':'fill'},headers=h).status_code==400
    assert store.job(job_id)['status']=='draft'
    assert c.post(f'/api/jobs/{job_id}/action',json={'action':'submit','reviewed':True},headers=h).status_code==400


def test_persistent_restart_stops_uncertain_submission(env):
    _,store,c,h=env
    job_id=add(c,h).json['id']
    store.update(job_id,status='submitting')
    again=Store(store.directory)
    assert again.job(job_id)['status']=='needs_attention'
    assert 'restarted' in again.job(job_id)['reason']


def test_demo_endpoints_removed(env):
    _,store,c,h=env
    assert c.post('/api/practice',json={},headers=h).status_code==404
    assert c.get('/practice/1?key=old-token').status_code==404
    assert c.get('/practice/style.css').status_code==404
    assert store.jobs()==[]


def test_manual_record_does_not_qualify_domain(env):
    _,store,c,h=env
    job_id=add(c,h).json['id']
    res=c.post(f'/api/jobs/{job_id}/action',json={'action':'manual','note':'Received employer receipt ABC-123.'},headers=h)
    assert res.status_code==200
    assert store.reviewed_count('example.com')==0


def test_state_omits_internal_paths_and_password(env):
    _,_,c,h=env
    add(c,h)
    data=c.get('/api/state').json
    assert 'cv_path' not in data['jobs'][0]
    assert 'snapshot' not in data['jobs'][0]
    assert 'password_hash' not in json.dumps(data)
    assert c.get('/api/jobs/1/cv').status_code==200


def test_csv_formula_injection_prevented(env):
    _,_,c,h=env
    add(c,h,company='=HYPERLINK("bad")')
    assert "'=HYPERLINK" in c.get('/api/export').text


def test_automatic_domain_changes_require_scope(env):
    _,_,c,h=env
    data={**DEFAULT_SETTINGS,'mode':'automatic','allowed_domains':['example.com']}
    assert c.put('/api/settings',json=data,headers=h).status_code==400
    assert c.put('/api/settings',json={**data,'authorize_domains':True},headers=h).status_code==200


def test_known_fields_only(profile):
    assert field_value('Expected salary','text','',profile) is None
    assert field_value('Work authorization','text','',profile) is None
    assert field_value('Full name','text','',profile)=='Ozan Duru'
    assert field_value('Email','email','',profile)==profile['email']


class FakeBrowser:
    def __init__(self):self.pages={};self.submits=0;self.uncertain=False;self.fills=0
    def page(self,job):self.pages[job['id']]='page';return 'page'
    def open_application_form(self,page):pass
    def fill(self,*args,**kwargs):self.fills+=1;return 'fingerprint'
    def confirmation(self,page):return None
    def submit(self,page,signature,mark_submitting):
        mark_submitting();self.submits+=1
        if self.uncertain:raise Handoff('Submission result is uncertain.')
        return 'your application has been submitted'


def test_review_then_submit_only_once(env,monkeypatch):
    app,store,c,h=env
    job_id=add(c,h).json['id']
    w=app.extensions['worker'];fake=FakeBrowser();w.browser=fake
    monkeypatch.setattr('joblane.worker.public_host',lambda x:True)
    store.update(job_id,authorized=1)
    w.run(job_id,'prepare')
    assert store.job(job_id)['status']=='ready_review' and fake.submits==0
    store.update(job_id,reviewed=1)
    w.run(job_id,'submit');w.run(job_id,'submit')
    assert store.job(job_id)['status']=='submitted' and fake.submits==1


def test_uncertain_submission_cannot_be_requeued(env,monkeypatch):
    app,store,c,h=env
    job_id=add(c,h).json['id']
    w=app.extensions['worker'];fake=FakeBrowser();fake.uncertain=True;w.browser=fake
    monkeypatch.setattr('joblane.worker.public_host',lambda x:True)
    store.update(job_id,authorized=1)
    w.run(job_id,'prepare');store.update(job_id,reviewed=1)
    with pytest.raises(Handoff):w.run(job_id,'submit')
    w.attention(job_id,'Submission result is uncertain.')
    for action in ('fill','queue','resume','rebuild'):
        assert c.post(f'/api/jobs/{job_id}/action',json={'action':action,'authorize':True},headers=h).status_code==400
    assert fake.submits==1


def test_pause_prevents_browser_actions(env):
    app,_,c,h=env
    job_id=add(c,h).json['id']
    w=app.extensions['worker'];w.paused.set()
    with pytest.raises(Handoff):w.run(job_id,'prepare')


def test_board_stays_manual(env):
    app,store,c,h=env
    job_id=add(c,h,url='https://www.linkedin.com/jobs/view/123').json['id']
    with pytest.raises(Handoff,match='manual application'):app.extensions['worker'].run(job_id,'prepare')


def test_auto_queue_requires_five_reviewed_confirmations(env):
    app,store,c,h=env
    store.set('settings',{**DEFAULT_SETTINGS,'mode':'automatic','allowed_domains':['example.com']})
    first=add(c,h,url='https://example.com/jobs/first').json['id']
    assert store.job(first)['status']=='draft'
    for i in range(5):
        job_id=add(c,h,url=f'https://example.com/jobs/{i}').json['id']
        store.update(job_id,status='submitted',reviewed=1)
    last=add(c,h,url='https://example.com/jobs/last').json['id']
    assert store.job(last)['status']=='queued'


def test_changed_form_does_not_mark_submitting():
    from joblane.browser import FormBrowser
    b=FormBrowser(Path('.'),lambda:None)
    b.signature=lambda page:'new values'
    markers=[]
    with pytest.raises(Handoff,match='changed'):
        b.submit(object(),'approved values',lambda:markers.append(True))
    assert markers==[]
