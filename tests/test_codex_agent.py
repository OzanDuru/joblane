import copy
import json
from pathlib import Path
import pytest
from test_joblane import env, profile, add
from joblane.codex_agent import command_for, profile_facts, validate_analysis
from joblane.policy import digest


def result(profile):
    return {'assessment':'Fits the supplied role.', 'fit':'possible',
            'summary':profile['summaries']['software'],'summary_fact_ids':['skills'],
            'project_edits':[{'index':0,'text':profile['projects'][0]['text'], 'fact_ids':['projects.0'],'reason':'Relevant project'}],
            'questions':[], 'gaps':[], 'next_step':'Review the PDF.', 'requires_review':True}


def enabled(env):
    app,s,c,h=env
    a=app.extensions['agent'];a.binary='/fake/codex'
    s.set('ai_config',{**a.config(),'enabled':True,'auto_prepare':False})
    job=add(c,h).json['id']
    return a,s,c,h,job


def completed(env):
    a,s,c,h,j=enabled(env);run=a.enqueue(j)
    a.update(run,status='completed',result=json.dumps(result(s.get('profile'))))
    return a,s,c,h,j,run


def test_exact_session_and_restricted_command(tmp_path):
    session='12345678-1234-1234-1234-123456789abc'
    args=command_for('/path with spaces/codex',tmp_path,'analyze',session,'selected-model')
    assert args[:4]==['/path with spaces/codex','exec','resume',session]
    assert '--last' not in args and '--ignore-user-config' in args
    assert 'sandbox_mode="read-only"' in args and 'web_search="disabled"' in args
    assert '--model' in args and 'selected-model' in args
    assert args[-1]=='-'
    with pytest.raises(ValueError):command_for('codex',tmp_path,'analyze','--last')


def test_fact_prompt_omits_contact_data(profile):
    facts=profile_facts(profile)
    assert not {'name','email','phone','links'} & facts.keys()
    assert 'projects.0' in facts
    good=result(profile)
    validate_analysis(good,profile)
    good['summary_fact_ids']=['invented-employer']
    with pytest.raises(ValueError):validate_analysis(good,profile)


def test_project_must_reference_its_original_fact(profile):
    bad=result(profile);bad['project_edits'][0]['fact_ids']=['skills']
    with pytest.raises(ValueError):validate_analysis(bad,profile)


def test_queue_deduplicates_and_cancels(env):
    a,s,c,h,j=enabled(env)
    first=c.post(f'/api/jobs/{j}/ai',json={'message':'Focus on Python.'},headers=h)
    assert first.status_code==202
    assert c.post(f'/api/jobs/{j}/ai',json={},headers=h).status_code==400
    run=first.json['id']
    assert c.post(f'/api/ai/runs/{run}/action',json={'action':'cancel'},headers=h).status_code==200
    assert a.get_run(run)['status']=='cancelled'
    assert c.post(f'/api/ai/runs/{run}/action',json={'action':'retry'},headers=h).status_code==202
    assert 'inputs' not in c.get('/api/state').json['ai']['runs'][0]


def test_apply_preserves_master_and_requires_fresh_authorization(env):
    a,s,c,h,j,run=completed(env);before=copy.deepcopy(s.get('profile'))
    s.update(j,authorized=1,reviewed=1)
    a.apply(run)
    job=s.job(j)
    assert s.get('profile')==before
    assert Path(job['cv_path']).exists() and f'-ai-{run}' in job['cv_path']
    assert job['authorized']==0 and job['reviewed']==0 and job['status']=='draft'
    assert json.loads(job['snapshot'])==before
    assert a.get_run(run)['applied']==1


@pytest.mark.parametrize('blocked',['stale','submitted','uncertain','active'])
def test_apply_rejects_changed_or_active_application(env,blocked):
    a,s,c,h,j,run=completed(env)
    if blocked=='stale':
        p=s.get('profile');p['headline']='Changed';s.set('profile',p)
    elif blocked=='submitted':s.update(j,status='submitted')
    elif blocked=='uncertain':s.set(f'attempt:{j}',True)
    else:a.browser_worker.current=j
    with pytest.raises(ValueError):a.apply(run)


def test_discovery_import_deduplicates_and_preserves_source(env):
    a,s,c,h,j=enabled(env)
    s.set('ai_config',{**a.config(),'auto_prepare':False})
    item={'url':'https://example.com/jobs/123','source_url':'https://example.com/jobs/123',
          'company':'Example','title':'Software Engineer','description':'Python and SQL.',
          'track':'software','evidence':'Requirements visible on the original page.'}
    found={'jobs':[item], 'search_summary':'One listing','limitations':[]}
    first=a.import_discovery(found)
    assert len(first['imported_ids'])==1
    job=first['imported_ids'][0]
    assert s.job(job)['status']=='draft' and s.get(f'discovery:{job}')['source_url']==item['source_url']
    second=a.import_discovery(found)
    assert not second['imported_ids'] and second['skipped']


def test_ai_config_validation_and_pause(env):
    a,s,c,h,j=enabled(env)
    assert c.put('/api/ai/config',json={'discovery_interval':0},headers=h).status_code==400
    assert c.put('/api/ai/config',json={'enabled':'yes'},headers=h).status_code==400
    a.browser_worker.paused.set()
    assert c.post(f'/api/jobs/{j}/ai',json={},headers=h).status_code==400


def test_saved_skill_answers_are_reused_as_facts(env):
    a,s,c,h,j=enabled(env)
    p=s.get('profile');p['verified_notes']='Docker: basic project exposure, no production operations.'
    assert c.put('/api/profile',json=p,headers=h).status_code==200
    run=a.enqueue(j)
    saved=a.get_run(run)
    assert json.loads(saved['inputs'])['facts']['verified_notes']==p['verified_notes']
    assert 'distinguish hands-on experience, project-level exposure and basic knowledge' in a.prompt(saved)
