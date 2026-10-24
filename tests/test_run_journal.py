import json
import threading
from test_joblane import env,profile
from test_codex_agent import enabled


def test_cancel_does_not_notify_but_failure_does(env,monkeypatch):
    a,s,c,h,j=enabled(env);calls=[]
    monkeypatch.setattr(a.browser_worker,'notify',lambda job:calls.append(job))
    task=a.enqueue(j);a.active=task;a.update(task,status='running')
    a.cancel(task);a.finish_error(task,ValueError('Stopped by you.'))
    assert calls==[] and a.get_run(task)['error'] is None
    assert a.get_run(task)['status']=='cancelled'
    assert len([e for e in a.runs()[0]['journal'] if e['state']=='cancelled'])==1
    task2=a.enqueue(j);a.finish_error(task2,ValueError('Connection failed'))
    assert calls==[j] and a.get_run(task2)['status']=='failed'


def test_global_pause_and_resume_are_separate_from_task_cancel(env,monkeypatch):
    a,s,c,h,j=enabled(env);task=a.enqueue(j);a.active=task
    monkeypatch.setattr(a.browser_worker,'notify',lambda *args:(_ for _ in ()).throw(AssertionError('unexpected notification')))
    assert c.post('/api/worker',json={'action':'pause'},headers=h).status_code==200
    assert c.get('/api/state').json['worker']['paused'] is True
    a.finish_error(task,ValueError('Stopped'))
    assert c.post('/api/worker',json={'action':'resume'},headers=h).status_code==200
    assert c.get('/api/state').json['worker']['paused'] is False
    task2=a.enqueue(j);a.cancel(task2)
    assert c.get('/api/state').json['worker']['paused'] is False


def test_live_journal_incremental_partial_lines_and_allowlist(env,tmp_path):
    a,s,c,h,j=enabled(env);task=a.enqueue(j);p=tmp_path/'events.jsonl'
    events=[{'type':'item.completed','item':{'type':'reasoning','text':'PRIVATE THOUGHT'}},
            {'type':'item.completed','item':{'type':'agent_message','text':'PRIVATE RESPONSE'}},
            {'type':'item.completed','item':{'type':'web_search','action':{'type':'search','queries':['Python remote','token=secretvalue']},'results':[{'secret':'RAW RESULT'}]}},
            {'type':'item.completed','item':{'type':'web_search','action':{'type':'open_page','url':'https://example.com/jobs?token=private#secret'}}}]
    raw='\n'.join(json.dumps(e) for e in events)+'\n';p.write_text(raw[:-8])
    offset=a.journal.ingest(task,p);p.write_text(raw);a.journal.ingest(task,p,offset);a.journal.ingest(task,p)
    journal=a.journal.for_runs([task])[task];text=json.dumps(journal)
    assert len(journal)==4
    for secret in ['PRIVATE THOUGHT','PRIVATE RESPONSE','RAW RESULT','secretvalue','?token=private']:assert secret not in text
    assert 'Python remote' in text and 'https://example.com/jobs' in text
    assert 'inputs' not in c.get('/api/state').json['ai']['runs'][0]


def test_watcher_records_before_process_completion(env,tmp_path):
    a,s,c,h,j=enabled(env);task=a.enqueue(j);p=tmp_path/'events.jsonl';p.write_text('{"type":"turn.started"}\n')
    done=threading.Event();seen=threading.Event();original=a.journal.normalize
    def normalize(*args,**kwargs):original(*args,**kwargs);seen.set()
    a.journal.normalize=normalize
    t=threading.Thread(target=a.watch_events,args=(task,p,done));t.start()
    try:
        assert seen.wait(3)
        assert a.journal.for_runs([task])[task][-1]['title']=='AI görevi işleniyor'
    finally:done.set();t.join(3)


def test_search_sources_are_allowlisted_and_existing_records_can_be_enriched(env):
    a,s,c,h,j=enabled(env);task=a.enqueue(j)
    a.journal.record(task,'cli:0','search','completed','Old summary',archived=True)
    before=a.journal.for_runs([task])[task][-1]['created']
    e={'type':'item.completed','item':{'type':'web_search','action':{'type':'search','queries':['junior Python remote']},'results':[{'title':'Role A','url':'https://example.com/jobs/7?token=secret','snippet':'RAW SECRET'},{'title':'Bad','url':'javascript:alert(1)'}]}}
    a.journal.normalize(task,e,'cli:0',True)
    row=a.journal.for_runs([task])[task][-1]
    assert row['created']==before and row['archived']==1
    assert row['data']['queries']==['junior Python remote']
    assert row['data']['source_count']==2
    assert row['data']['sources']==[{'title':'Role A','url':'https://example.com/jobs/7'}]
    assert 'RAW SECRET' not in json.dumps(row) and 'token=secret' not in json.dumps(row)


def test_discovery_schedule_explains_interval_and_pause(env,monkeypatch):
    from datetime import datetime
    a,s,c,h,j=enabled(env)
    stamp=datetime.fromisoformat('2026-10-25T01:15:00+03:00').timestamp()
    monkeypatch.setattr('joblane.codex_agent.time.time',lambda:stamp)
    s.set('settings',{**s.get('settings'),'enabled':True,'start':'00:00','end':'20:00','days':list(range(7))})
    s.set('ai_config',{**a.config(),'discovery_enabled':True,'discovery_interval':120})
    s.set('last_discovery',stamp-60*60)
    schedule=a.discovery_schedule()
    assert schedule['next_at']==stamp+60*60
    assert schedule['server_now']==stamp
    a.browser_worker.paused.set()
    schedule=a.discovery_schedule()
    assert schedule['reason']=='paused' and schedule['next_at'] is None
    monkeypatch.undo()
    assert c.get('/api/state').json['ai']['schedule']['reason']=='paused'


def test_discovery_schedule_moves_due_time_into_working_day(env,monkeypatch):
    from datetime import datetime
    a,s,c,h,j=enabled(env)
    stamp=datetime.fromisoformat('2026-10-25T19:30:00+03:00').timestamp()
    monkeypatch.setattr('joblane.codex_agent.time.time',lambda:stamp)
    s.set('settings',{**s.get('settings'),'enabled':True,'start':'15:00','end':'20:00','days':[0]})
    s.set('ai_config',{**a.config(),'discovery_enabled':True,'discovery_interval':120})
    s.set('last_discovery',stamp)
    assert a.discovery_schedule()['next_at']==datetime.fromisoformat('2026-10-26T15:00:00+03:00').timestamp()
    s.set('ai_config',{**a.config(),'discovery_enabled':False})
    assert a.discovery_schedule()['next_at'] is None
