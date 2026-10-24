import io
import json
import urllib.error
import pytest
from test_joblane import env,profile
from joblane import telegram

TOKEN='12345:'+'x'*32
CONFIG={'bot_id':12345,'bot_username':'ozan_test_bot','chat_id':42,'credential':'test-slot'}


def test_pair_requires_fresh_exact_nonce_and_private_sender():
    msg={'chat':{'id':42,'type':'private'},'from':{'id':42,'is_bot':False},'text':'/start joblane_nonce','date':100}
    assert telegram.paired_chat([{'message':msg}],'joblane_nonce',100)['id']==42
    for change in [{'date':99},{'text':'/start'},{'chat':{'id':42,'type':'group'}},{'from':{'id':43,'is_bot':False}}]:
        assert telegram.paired_chat([{'message':{**msg,**change}}],'joblane_nonce',100) is None


def test_multiple_pairing_senders_rejected():
    msgs=[{'message':{'chat':{'id':i,'type':'private'},'from':{'id':i,'is_bot':False},'text':'/start nonce','date':1}} for i in (1,2)]
    with pytest.raises(telegram.TelegramError):telegram.paired_chat(msgs,'nonce',1)


class Ring:
    def __init__(self):self.values={}
    def get_password(self,service,key):return self.values.get((service,key))
    def set_password(self,service,key,value):self.values[(service,key)]=value
    def delete_password(self,service,key):self.values.pop((service,key),None)


def test_pair_token_only_in_native_keyring(env,monkeypatch):
    _,s,c,_=env;ring=Ring();monkeypatch.setattr(telegram,'secure_keyring',lambda:ring)
    telegram.save_pair(s.directory,TOKEN,{'id':12345,'username':'test_bot'},{'type':'private','id':42})
    assert TOKEN not in json.dumps(s.get('telegram'))
    assert list(ring.values.values())==[TOKEN]
    public=c.get('/api/state').json['connection']
    assert public['notification_provider']=='telegram' and TOKEN not in json.dumps(public)
    assert 'credential' not in json.dumps(public)


@pytest.mark.parametrize('chat',[{'id':43,'type':'private'},{'id':42,'type':'group'}])
def test_no_send_to_unverified_chat(env,monkeypatch,chat):
    _,s,_,_=env;s.set('telegram',CONFIG);ring=Ring();ring.set_password(telegram.service(s.directory),'test-slot',TOKEN)
    monkeypatch.setattr(telegram,'secure_keyring',lambda:ring)
    calls=[]
    def api(token,method,payload):calls.append(method);return chat
    monkeypatch.setattr(telegram,'api',api)
    with pytest.raises(telegram.TelegramError):telegram.send(s)
    assert calls==['getChat']


def test_send_private_generic_message(env,monkeypatch):
    _,s,_,_=env;s.set('telegram',CONFIG);ring=Ring();ring.set_password(telegram.service(s.directory),'test-slot',TOKEN)
    monkeypatch.setattr(telegram,'secure_keyring',lambda:ring)
    calls=[]
    def api(token,method,payload):
        calls.append((method,payload))
        return {'id':42,'type':'private'} if method=='getChat' else {'message_id':7,'chat':{'id':42}}
    monkeypatch.setattr(telegram,'api',api)
    telegram.send(s)
    payload=calls[-1][1]
    assert payload['chat_id']==42 and payload['protect_content'] is True
    assert s.get('profile')['email'] not in payload['text']


def test_test_route_failure_does_not_claim_success_or_fallback(env,monkeypatch):
    app,s,c,h=env;s.set('telegram',CONFIG)
    calls=[]
    def fail(*args,**kwargs):calls.append(1);raise RuntimeError('secret-token')
    monkeypatch.setattr(telegram,'send',fail)
    r=c.post('/api/notifications/test',json={},headers=h)
    assert r.status_code==200 and r.json['ok'] is False and r.json['state']=='failed'
    assert len(calls)==1 and 'secret-token' not in json.dumps(r.json)
    with s.connect() as db:assert db.execute('select count(*) from notifications').fetchone()[0]==1


def test_api_errors_do_not_expose_token_or_retry(monkeypatch):
    calls=[]
    def fail(req,**kwargs):
        calls.append(req)
        raise urllib.error.HTTPError(req.full_url,401,'URL contains token',{},io.BytesIO(b'bad'))
    monkeypatch.setattr(telegram.urllib.request,'urlopen',fail)
    with pytest.raises(telegram.TelegramError) as exc:telegram.api(TOKEN,'getMe')
    assert TOKEN not in str(exc.value) and 'api.telegram.org' not in str(exc.value)
    assert len(calls)==1
