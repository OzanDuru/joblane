import json
import pytest
from test_codex_agent import enabled, result
from test_joblane import env, profile
from joblane.workflow import validate_search, SEARCH_DEFAULTS, search_instruction
from joblane.form_plan import validate_plan,signature
from joblane.telegram import ReplyListener


def test_filters_validate_and_reach_prompt(env):
    a,s,c,h,j=enabled(env)
    bad=c.put('/api/ai/config',json={'search_filters':{**SEARCH_DEFAULTS,'sources':[]}},headers=h)
    assert bad.status_code==400
    good=c.put('/api/ai/config',json={'search_filters':{**SEARCH_DEFAULTS,'geography':'turkey'}},headers=h)
    assert good.status_code==200
    run=a.enqueue(kind='discover')
    prompt=a.prompt(a.get_run(run))
    assert 'Only jobs explicitly located in Türkiye' in prompt
    for query in ('site:kariyer.net/is-ilani','site:linkedin.com/jobs/view'):assert query in prompt


def test_answer_is_scoped_and_resumes_one_task(env):
    a,s,c,h,j=enabled(env)
    from datetime import datetime,timezone
    s.set(f'source_check:{j}',{'posting_status':'open','checked_at':datetime.now(timezone.utc).isoformat()})
    task=a.enqueue(j);r=result(s.get('profile'));r['questions']=['ABD çalışma iznin var mı?']
    a.update(task,status='completed',result=json.dumps(r))
    response=c.post(f'/api/jobs/{j}/answers',json={'text':'Hayır, sponsor gerekiyor.','question_run':task},headers=h)
    assert response.status_code==200 and response.json['queued']
    inputs=json.loads(a.get_run(response.json['run_id'])['inputs'])
    assert 'ABD çalışma' in inputs['answers'][-1]['text']
    assert 'sponsor gerekiyor' in inputs['shared_answers'][-1]['text']
    assert 'sponsor gerekiyor' not in s.get('profile').get('verified_notes','')
    assert c.post(f'/api/jobs/{j}/answers',json={'text':'Ek açıklama'},headers=h).json['saved']
    assert j in s.get('pending_answers')


def test_stale_answer_and_submitted_application_are_rejected(env):
    a,s,c,h,j=enabled(env)
    assert c.post(f'/api/jobs/{j}/answers',json={'text':'Hayır','question_run':900},headers=h).status_code==400
    assert not s.get(f'answers:{j}')
    s.update(j,status='submitted')
    assert c.post(f'/api/jobs/{j}/answers',json={'text':'Hayır'},headers=h).status_code==400
    assert not s.get(f'answers:{j}')


def test_paused_answer_saved_without_starting(env):
    a,s,c,h,j=enabled(env);a.browser_worker.paused.set()
    response=a.answer(j,'Gerektiğinde taşınabilirim.')
    assert response['saved'] and not response['queued'] and not a.runs()


def test_clear_analysis_can_queue_fill_but_never_marks_submitted(env):
    a,s,c,h,j=enabled(env)
    s.set('ai_config',{**a.config(),'auto_prepare':True,'auto_fill':True})
    task=a.enqueue(j);r=result(s.get('profile'));r['requires_review']=False
    a.update(task,status='completed',result=json.dumps(r));a.advance_analysis(task,r)
    assert s.job(j)['status']=='queued' and s.job(j)['authorized']==1
    assert not s.get('attempt:'+str(j))


def test_form_plan_rejects_fabricated_choice_and_legal_field():
    field={'index':2,'label':'Work permit','kind':'select-one','required':True,'options':[{'value':'no','label':'No'}]}
    plan={'answers':[{'index':2,'label':'Work permit','value':'no','fact_ids':['answers.0']}],'questions':[],'requires_review':False}
    assert validate_plan(plan,[field],{'answers.0':'No permit'})==plan
    plan['answers'][0]['value']='yes'
    with pytest.raises(ValueError):validate_plan(plan,[field],{'answers.0':'No permit'})
    plan['answers'][0].update(label='I agree to terms',value='yes');field.update(label='I agree to terms',kind='text')
    with pytest.raises(ValueError):validate_plan(plan,[field],{'answers.0':'yes'})


def test_form_plan_only_queues_and_is_tied_to_actual_fields(env):
    a,s,c,h,j=enabled(env);s.update(j,authorized=1)
    field={'index':2,'label':'Current city','kind':'text','required':True,'options':None}
    s.set(f'observation:{j}',{'fields':[field]})
    task=a.enqueue(j,kind='form');r={'answers':[{'index':2,'label':'Current city','value':'Istanbul','fact_ids':['location']}],'questions':[],'requires_review':False}
    a.update(task,status='completed',result=json.dumps(r));a.advance_form(task,r)
    assert s.job(j)['status']=='queued'
    assert s.get(f'form_plan:{j}')['signature']==signature([field])
    assert not s.get('attempt:'+str(j))


def test_telegram_reply_requires_paired_user_context_and_deduplicates(env):
    _,s,_,_=env;s.set('telegram',{'chat_id':42,'bot_id':12});s.set('telegram_message:99',{'job_id':7,'run_id':3})
    calls=[]
    listener=ReplyListener(s,lambda *a,**kw:(calls.append((a,kw)) or {'detail':'Kaydedildi'}))
    update={'update_id':123,'message':{'text':'Hayır','chat':{'id':42,'type':'private'},'from':{'id':42,'is_bot':False},'reply_to_message':{'message_id':99}}}
    assert 'Kaydedildi' in listener.handle(update)
    assert listener.handle(update) is None and len(calls)==1
    assert calls[0][1]['question_run']==3
    update['update_id']=124;update['message']['from']['id']=43
    assert listener.handle(update) is None and len(calls)==1


def test_start_now_uses_saved_scope_and_deduplicates(env,monkeypatch):
    a,s,c,h,j=enabled(env)
    monkeypatch.setattr(a,'check',lambda:{'auth':'ChatGPT'})
    body={'confirmed':True,'immediate':True,'auto_fill':True,'search_filters':SEARCH_DEFAULTS}
    assert c.post('/api/automation/start',json=body,headers=h).status_code==200
    assert c.post('/api/automation/start',json=body,headers=h).status_code==200
    assert len([r for r in a.runs() if r['kind']=='discover'])==1
    assert s.get('last_discovery') and a.config()['auto_fill']


def test_frontend_bundle_is_served_and_contains_single_question_flow(env):
    _,_,c,_=env
    html=c.get('/').text
    assert 'src="./static/workflow-ui.js"' in html
    js=c.get('/static/workflow-ui.js')
    assert js.status_code==200 and 'function searchFilterForm' in js.text
    assert 'questions.slice(0,1)' in js.text


def test_auto_fill_waits_for_missing_information(env,monkeypatch):
    a,s,c,h,j=enabled(env);monkeypatch.setattr(a.browser_worker,'notify',lambda *args:None)
    s.set('ai_config',{**a.config(),'auto_prepare':True,'auto_fill':True})
    task=a.enqueue(j);r=result(s.get('profile'));r['questions']=['Çalışma iznin var mı?']
    a.update(task,status='completed',result=json.dumps(r));a.advance_analysis(task,r)
    assert s.job(j)['status']=='needs_attention' and not s.job(j)['authorized']


def test_auto_fill_preference_is_acknowledged_and_persists(env):
    a,s,c,h,j=enabled(env)
    for desired in (True,False):
        response=c.put('/api/ai/config',json={'auto_fill':desired},headers=h)
        assert response.status_code==200 and response.json['config']['auto_fill'] is desired
        assert c.get('/api/state').json['ai']['config']['auto_fill'] is desired
        assert s.get('ai_config')['auto_fill'] is desired
    assert not a.runs() and s.job(j)['status']=='draft'


def test_source_verification_has_no_candidate_facts_or_prior_session(env):
    from joblane.codex_agent import command_for
    a,s,c,h,j=enabled(env)
    s.set(f'answers:{j}',[{'text':'private answer'}])
    task=a.enqueue(j,kind='verify');inputs=json.loads(a.get_run(task)['inputs'])
    assert set(inputs)=={'job'} and set(inputs['job'])=={'url','title','company'}
    assert 'private answer' not in a.prompt(a.get_run(task))
    assert 'web_search="live"' in command_for('/fake/codex',s.directory,'verify')


def test_verified_employment_updates_evidence_and_reanalyzes(env):
    a,s,c,h,j=enabled(env);task=a.enqueue(j,kind='verify');a.update(task,status='completed')
    a.advance_verification(task,{'employment':'Full-time','source_url':s.job(j)['url'],'evidence':'Employment type: Full time','limitation':''})
    assert s.get(f'source_check:{j}')['employment']=='Full-time'
    assert 'verified on source' in s.job(j)['description']
    assert a.runs()[0]['kind']=='analyze' and a.runs()[0]['status']=='queued'
    assert not s.job(j)['authorized']


def test_unavailable_employment_source_does_not_guess_or_retry(env,monkeypatch):
    a,s,c,h,j=enabled(env);monkeypatch.setattr(a.browser_worker,'notify',lambda *args:None)
    task=a.enqueue(j,kind='verify');a.update(task,status='completed')
    a.advance_verification(task,{'employment':'Unknown','source_url':s.job(j)['url'],'evidence':'','limitation':'Kaynak erişilemiyor.'})
    assert s.job(j)['status']=='needs_attention' and len(a.runs())==1
    assert 'Kaynak erişilemiyor' in s.job(j)['reason']


def test_employment_filter_recognizes_turkish_and_spacing():
    from joblane.policy import matches_preferences
    for label in ('Full time','Full-time','Tam zamanlı'):
        assert matches_preferences({'title':'Engineer','description':label},{'employment':'Full-time'})[0]
    assert not matches_preferences({'title':'Engineer','description':'Internship'},{'employment':'Full-time'})[0]


def test_waiting_question_does_not_block_other_scheduled_application(env):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from test_joblane import add
    a,s,c,h,j=enabled(env)
    other=add(c,h,url='https://example.com/careers/another').json['id']
    s.update(j,status='needs_attention',reason='Aday yanıtı bekleniyor.')
    s.update(other,status='queued')
    dt=datetime.now(ZoneInfo('Europe/Istanbul'))
    s.set('settings',{**s.get('settings'),'enabled':True,'start':'00:00','end':'23:59','days':list(range(7))})
    # Test the queue independently of the actual minute of execution.
    from unittest.mock import patch
    with patch('joblane.worker.within_window',return_value=True):assert a.browser_worker.scheduled_job()==other
    assert not a.browser_worker.paused.is_set()
    task=a.enqueue(kind='discover')
    assert a.get_run(task)['status']=='queued' and s.job(j)['status']=='needs_attention'


def test_deadline_expiry_is_conservative_and_source_dates_require_evidence():
    from datetime import datetime,timezone
    from joblane.job_health import deadline_passed,validate_source_dates
    assert deadline_passed('2026-10-22',datetime(2026,10,25,tzinfo=timezone.utc))
    assert not deadline_passed('2026-10-25',datetime(2026,10,25,23,tzinfo=timezone.utc))
    assert not deadline_passed('')
    with pytest.raises(ValueError):validate_source_dates({'posting_status':'open','deadline':'2026-10-25','opens_on':'','status_evidence':''})


def test_reply_after_deadline_cannot_restart_application(env):
    a,s,c,h,j=enabled(env)
    s.set(f'source_check:{j}',{'deadline':'2000-01-01','posting_status':'open'})
    response=c.post(f'/api/jobs/{j}/answers',json={'text':'Evet, uygunum.'},headers=h)
    assert response.status_code==400 and s.job(j)['status']=='skipped'
    assert not a.runs()


def test_waiting_job_metadata_refresh_is_independent_of_candidate_answers(env,monkeypatch):
    a,s,c,h,j=enabled(env)
    s.update(j,status='needs_attention')
    s.set('settings',{**s.get('settings'),'enabled':True})
    monkeypatch.setattr('joblane.codex_agent.within_window',lambda *args:True)
    a.schedule_source_refresh()
    assert a.runs()[0]['kind']=='verify' and s.job(j)['status']=='needs_attention'


def test_answer_during_running_ai_is_saved_and_old_result_is_not_applied(env):
    a,s,c,h,j=enabled(env);task=a.enqueue(j);a.update(task,status='running')
    before=a.get_run(task)
    reply=a.answer(j,'Bu ülke için sponsorluğa ihtiyacım var.')
    assert reply['saved'] and reply['queued'] and j in s.get('pending_answers')
    assert a.superseded(before)
    assert a.get_run(task)['status']=='superseded'
    assert not s.get('attempt:'+str(j))
    fresh=a.enqueue(j)
    assert not a.superseded(a.get_run(fresh)) and j not in s.get('pending_answers')


def test_notifications_suppress_repeated_question_and_pending_ai(env,monkeypatch):
    a,s,c,h,j=enabled(env);w=a.browser_worker
    s.set('telegram',{'chat_id':42,'bot_id':7})
    monkeypatch.setattr('joblane.worker.telegram.send',lambda *args,**kwargs:'ok')
    s.update(j,status='needs_attention',reason='A question')
    assert w.notify(j)['state']=='sent'
    assert w.notify(j)['state']=='suppressed'
    a.enqueue(j);s.update(j,reason='New question')
    assert w.notify(j)['state']=='suppressed'


def test_saved_question_answer_is_reused_in_another_job_context(env):
    from test_joblane import add
    a,s,c,h,j=enabled(env)
    prior=a.enqueue(j);r=result(s.get('profile'));r['questions']=['Cisco Packet Tracer kullandın mı?']
    a.update(prior,status='completed',result=json.dumps(r))
    a.answer(j,'Evet, laboratuvar denemelerinde kullandım.',question_run=prior)
    remembered=s.get('shared_answers')[-1]
    assert remembered['question']==r['questions'][0] and remembered['answer'].startswith('Evet')
    other=add(c,h,url='https://example.com/jobs/network').json['id'];run=a.enqueue(other)
    inputs=json.loads(a.get_run(run)['inputs'])
    assert remembered in inputs['shared_answers']
    assert 'semantically' in a.prompt(a.get_run(run))
