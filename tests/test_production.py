import json
import sqlite3
from pathlib import Path
import pytest
from test_joblane import env, profile, add
from joblane.maintenance import remove_demo_data


def test_password_transition_revokes_old_sessions(env):
    app,s,c,h=env
    other=app.test_client()
    other.post('/api/login',json={'password':'private-test-password'},headers={'Origin':h['Origin']})
    s.set('password_change_required',True)
    assert add(c,h).status_code==403
    assert c.post('/api/password',json={'current':'wrong','new':'my-private-password'},headers=h).status_code==400
    result=c.post('/api/password',json={'current':'private-test-password','new':'my-private-password'},headers=h)
    assert result.status_code==200
    assert other.get('/api/state').status_code==401
    assert c.get('/api/state').json['security']['password_change_required'] is False
    assert add(c,{**h,'X-CSRF-Token':result.json['csrf']}).status_code==201


def test_cleanup_preserves_real_history_and_has_backup(env,tmp_path):
    app,s,c,h=env
    real=add(c,h).json['id']
    demo=add(c,h,url='https://example.com/jobs/demo').json['id']
    history=app.extensions['worker'].history
    version=history.archive_cv(demo,'Legacy demo')
    real_path=Path(s.job(real)['cv_path']);real_bytes=real_path.read_bytes()
    path=Path(s.job(demo)['cv_path'])
    run_dir=s.directory/'ai'/'run-77';run_dir.mkdir(parents=True);(run_dir/'result.json').write_text('{}')
    with s.connect() as db:
        db.execute('UPDATE jobs SET demo=1 WHERE id=?',(demo,))
        db.execute("INSERT INTO ai_runs(id,job_id,kind,message,status,inputs,created,updated) VALUES (77,?,'analyze','','completed','{}','','')",(demo,))
        db.execute('INSERT INTO ai_sessions VALUES (?,?)',(demo,'old-session'))
    d=history.create(demo,'practice','practice://old','confirmed',version)
    s.set(f'email-digest:{d}','old');s.set(f'cv_variant:{demo}',{})
    # Ensure prefix matching never deletes application-20 when demo ID is 2.
    neighbor=s.directory/'cvs'/f'application-{demo}0.pdf';neighbor.write_bytes(b'keep')
    result=remove_demo_data(s.directory,tmp_path.parent/'backups')
    assert result['removed_jobs']==[demo]
    assert [j['id'] for j in s.jobs()]==[real]
    assert real_path.read_bytes()==real_bytes and neighbor.exists()
    assert not path.exists() and not run_dir.exists()
    assert s.get(f'email-digest:{d}') is None and s.get(f'cv_variant:{demo}') is None
    assert history.data()['deliveries']==[]
    assert all(v['job_id']==real for v in history.data()['versions'])
    with sqlite3.connect(Path(result['backup'])/'data'/'joblane.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==2
    assert remove_demo_data(s.directory,tmp_path.parent/'backups')['removed_jobs']==[]


def test_cleanup_refuses_external_artifact_paths(env,tmp_path):
    _,s,c,h=env
    j=add(c,h).json['id'];external=tmp_path.parent/'keep-me.pdf';external.write_bytes(b'private')
    with s.connect() as db:db.execute('UPDATE jobs SET demo=1,cv_path=? WHERE id=?',(str(external),j))
    with pytest.raises(ValueError,match='Unexpected artifact'):
        remove_demo_data(s.directory,tmp_path.parent/'backups')
    assert s.job(j)['demo']==1 and external.read_bytes()==b'private'


def test_start_flow_requires_confirmation_and_login(env,monkeypatch):
    app,s,c,h=env
    monkeypatch.setattr(app.extensions['agent'],'check',lambda:{'auth':'not signed in'})
    assert c.post('/api/automation/start',json={'confirmed':True},headers=h).status_code==400
    monkeypatch.setattr(app.extensions['agent'],'check',lambda:{'auth':'ChatGPT'})
    assert c.post('/api/automation/start',json={},headers=h).status_code==400
    assert c.post('/api/automation/start',json={'confirmed':True},headers=h).status_code==200
    assert s.get('settings')['enabled'] and s.get('settings')['mode']=='review'
    assert s.get('ai_config')['discovery_enabled'] and s.get('profile_confirmed')
    assert not s.jobs()


def test_auto_prepare_creates_cv_but_does_not_send(env,monkeypatch):
    from test_codex_agent import result
    app,s,c,h=env;j=add(c,h).json['id'];a=app.extensions['agent'];a.binary='fake'
    s.set('ai_config',{**a.config(),'enabled':True,'auto_prepare':True})
    run=a.enqueue(j);analysis=result(s.get('profile'));analysis['questions']=['When can you start?']
    a.update(run,status='completed',result=json.dumps(analysis))
    notices=[];monkeypatch.setattr(app.extensions['worker'],'notify',lambda job_id:notices.append(job_id))
    a.advance_analysis(run,analysis)
    assert a.get_run(run)['applied']==1
    assert s.job(j)['status']=='needs_attention' and s.job(j)['authorized']==0
    assert notices==[j] and app.extensions['worker'].history.data()['deliveries']==[]


def test_test_notification_requires_configuration(env,monkeypatch):
    _,_,c,h=env
    for k in ['PUSHOVER_APP_TOKEN','PUSHOVER_USER_KEY','PUSHOVER_DEVICE']:monkeypatch.delenv(k,raising=False)
    assert c.post('/api/notifications/test',json={},headers=h).status_code==400


@pytest.mark.parametrize('devices,expected_calls',[(['ozans-phone'],2),(['another-phone'],1)])
def test_push_verifies_exact_device_before_sending(env,monkeypatch,devices,expected_calls):
    import io
    app,s,_,_=env
    for key,value in [('PUSHOVER_APP_TOKEN','private-token'),('PUSHOVER_USER_KEY','private-user'),('PUSHOVER_DEVICE','ozans-phone')]:monkeypatch.setenv(key,value)
    calls=[]
    def respond(request,**kwargs):
        calls.append(request.full_url)
        return io.BytesIO(json.dumps({'status':1,'devices':devices}).encode())
    monkeypatch.setattr('joblane.worker.urllib.request.urlopen',respond)
    app.extensions['worker'].notify(None,test=True)
    assert len(calls)==expected_calls
    with s.connect() as db:state=db.execute('SELECT state FROM notifications').fetchone()[0]
    assert state==('sent' if expected_calls==2 else 'failed')


def test_first_clear_application_still_notifies_for_review(env,monkeypatch):
    from test_codex_agent import result
    app,s,c,h=env;j=add(c,h).json['id'];a=app.extensions['agent'];a.binary='fake'
    s.set('ai_config',{**a.config(),'enabled':True,'auto_prepare':True})
    run=a.enqueue(j);analysis=result(s.get('profile'));analysis['requires_review']=False
    a.update(run,status='completed',result=json.dumps(analysis))
    notices=[];monkeypatch.setattr(app.extensions['worker'],'notify',lambda job_id:notices.append(job_id))
    a.advance_analysis(run,analysis)
    assert s.job(j)['status']=='needs_attention' and notices==[j]
    assert app.extensions['worker'].history.data()['deliveries']==[]
