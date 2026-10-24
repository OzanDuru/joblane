import csv
import io
import json
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, jsonify, request, session, send_file, send_from_directory, Response
from werkzeug.security import check_password_hash, generate_password_hash
from .store import Store, now
from .policy import normalize_url, validate_settings, validate_profile, digest, within_window
from .cv import generate
from .worker import Worker
from .codex_agent import CodexAgent, AI_DEFAULTS
from .outlook import Outlook, mime_message
from .workflow import validate_search
from .telegram import ReplyListener

def create_app(directory,port=8765,start_worker=True):
    app=Flask(__name__,static_folder='static')
    store=Store(directory)
    secret=store.get('secret')
    if not secret:
        secret=secrets.token_hex(32)
        store.set('secret',secret)
    public=os.getenv('JOBLANE_PUBLIC_URL','').rstrip('/')
    if public and (urlsplit(public).scheme!='https' or not urlsplit(public).hostname):
        raise ValueError('JOBLANE_PUBLIC_URL must be your HTTPS Tailscale Serve address.')
    app.config.update(SECRET_KEY=secret,MAX_CONTENT_LENGTH=8*1024*1024,
        SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=bool(public),PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        TRUSTED_HOSTS=['127.0.0.1','localhost']+([urlsplit(public).hostname] if public else []))
    worker=Worker(store,port)
    agent=CodexAgent(store,worker)
    outlook=Outlook(store,worker)
    replies=ReplyListener(store,agent.answer)
    app.extensions.update(store=store,worker=worker,agent=agent,replies=replies)
    def analyze_problem(job_id):
        if not agent.config()['enabled']:return False
        observation=store.get(f'observation:{job_id}',{})
        if not observation.get('fields'):return False
        from .form_plan import signature
        key=signature(observation['fields'])
        if store.get(f'form_attempt:{job_id}')==key:return False
        try:
            agent.enqueue(job_id,kind='form',message='Resolve the actual form fields using known facts; ask only essential missing information.')
            store.set(f'form_attempt:{job_id}',key)
            return True
        except ValueError:return False
    worker.on_attention=analyze_problem
    attempts={'count':0,'until':0}
    allowed_origins={f'http://127.0.0.1:{port}',f'http://localhost:{port}'}
    if public: allowed_origins.add(public)

    @app.before_request
    def protect():
        if urlsplit('http://'+request.host).hostname not in app.config['TRUSTED_HOSTS']:
            return jsonify(error='Untrusted host'),400
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('Origin') not in allowed_origins:
                return jsonify(error='Untrusted request origin'),403
            if request.path!='/api/login':
                if not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
                    return jsonify(error='Session expired. Sign in again.'),403
        if request.path.startswith('/api/') and request.path not in ('/api/login','/api/session') and not session.get('signed_in'):
            return jsonify(error='Sign in to your private workspace.'),401
        if request.method not in ('GET','HEAD','OPTIONS') and store.get('password_change_required',False) and request.path not in ('/api/login','/api/logout','/api/password','/api/worker'):
            return jsonify(error='Set your private workspace password in Schedule & settings before starting live work.'),403

    @app.after_request
    def headers(response):
        response.headers.update({
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'",
        })
        return response

    @app.errorhandler(ValueError)
    def value_error(error): return jsonify(error=str(error)),400

    @app.errorhandler(413)
    def too_large(error): return jsonify(error='File too large. Maximum size is 8 MB.'),413

    @app.errorhandler(500)
    def internal(error): return jsonify(error='The operation failed. No automatic retry was made. Check the local service console.'),500

    @app.get('/')
    def index(): return send_from_directory(app.static_folder,'index.html')

    @app.get('/app.js')
    @app.get('/ai-ui.js')
    @app.get('/history-ui.js')
    @app.get('/home-ui.js')
    @app.get('/style.css')
    @app.get('/design.css')
    @app.get('/workflow-ui.js')
    @app.get('/theme.js')
    def frontend_asset():
        return send_from_directory(app.static_folder,request.path.lstrip('/'))

    @app.get('/api/session')
    def current_session():
        return jsonify(app='joblane',signed_in=bool(session.get('signed_in')),csrf=session.get('csrf'),initialized=bool(store.get('password_hash')))

    @app.post('/api/login')
    def login():
        if time.monotonic()<attempts['until']:
            return jsonify(error='Too many attempts. Try again in 30 seconds.'),429
        password=(request.get_json(silent=True) or {}).get('password','')
        hashed=store.get('password_hash')
        if not hashed: return jsonify(error='Run the local setup script on your laptop first.'),403
        if not isinstance(password,str) or not check_password_hash(hashed,password):
            attempts['count']+=1
            if attempts['count']>=5:
                attempts.update(count=0,until=time.monotonic()+30)
            return jsonify(error='Incorrect password.'),401
        attempts.update(count=0,until=0)
        session.clear()
        session.update(signed_in=True,csrf=secrets.token_hex(24))
        session.permanent=True
        return jsonify(csrf=session['csrf'])

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.post('/api/password')
    def change_password():
        if time.monotonic()<attempts['until']:
            return jsonify(error='Too many attempts. Try again in 30 seconds.'),429
        data=request.get_json() or {}
        old,new=data.get('current',''),data.get('new','')
        if not isinstance(old,str) or len(old)>1024 or not check_password_hash(store.get('password_hash',''),old):
            attempts['count']+=1
            if attempts['count']>=5:attempts.update(count=0,until=time.monotonic()+30)
            raise ValueError('Current password is incorrect.')
        if not isinstance(new,str) or not 12<=len(new)<=1024 or new==old:
            raise ValueError('Choose a different password containing at least 12 characters.')
        secret=secrets.token_hex(32)
        with store.lock,store.connect() as db:
            for key,value in [('password_hash',generate_password_hash(new)),('secret',secret),('password_change_required',False)]:
                db.execute('INSERT OR REPLACE INTO config VALUES (?,?)',(key,json.dumps(value)))
        app.config['SECRET_KEY']=secret
        attempts.update(count=0,until=0)
        session.clear()
        session.update(signed_in=True,csrf=secrets.token_hex(24))
        session.permanent=True
        return jsonify(csrf=session['csrf'])

    @app.get('/api/state')
    def state():
        jobs=store.jobs()
        settings=store.get('settings')
        for job in jobs:
            job['discovery']=store.get(f'discovery:{job["id"]}')
            job['answers']=store.get(f'answers:{job["id"]}',[])
            job['observation']=store.get(f'observation:{job["id"]}',{})
            for key in ('snapshot','cv_path','approval_digest','evidence'):
                job['has_'+key]=bool(job.pop(key,None))
        domains={j['domain']:store.reviewed_count(j['domain']) for j in jobs if not j['demo']}
        with store.connect() as db:
            notifications=[dict(r) for r in db.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 10')]
        return jsonify(setup={'profile_confirmed':store.get('profile_confirmed',False)},security={'password_change_required':store.get('password_change_required',False)},jobs=jobs,events=store.events(),settings=settings,profile=store.get('profile',{}),
            worker={'paused':worker.paused.is_set(),'active_job':worker.current,'within_window':within_window(settings),
                    'browser_connected':bool(worker.browser.context),'running':bool(worker.thread and worker.thread.is_alive())},
            site_sessions=worker.login_status(),connection={'private_url':public,'notifications':worker.notification_status()['configured'],'notification_provider':worker.notification_status()['provider'],'telegram_bot':worker.notification_status()['bot_username'],'telegram_replies':store.get('telegram_reply_status','not_started')},
            reviewed_by_domain=domains,notifications=notifications,
            ai={'config':agent.config(),'runtime':agent.runtime_status,'active':agent.active,'runs':agent.runs(),'schedule':agent.discovery_schedule()},
            history=worker.history.data(),outlook=outlook.status())

    @app.post('/api/site-sessions/<site>')
    def site_session(site):
        if site not in ('linkedin','kariyer'):raise ValueError('Bilinmeyen site.')
        action=(request.get_json() or {}).get('action')
        if action=='open':worker.open_login(site)
        elif action in ('confirm','check'):worker.check_login(site)
        else:raise ValueError('Bilinmeyen oturum işlemi.')
        return jsonify(ok=True)

    @app.post('/api/automation/start')
    def start_automation():
        data=request.get_json() or {}
        if data.get('confirmed') is not True:
            raise ValueError('Confirm your profile and Codex use before starting.')
        filters=validate_search(data.get('search_filters',agent.config()['search_filters']))
        if type(data.get('auto_fill',agent.config()['auto_fill'])) is not bool:raise ValueError('Form tercihi geçersiz.')
        profile=validate_profile(store.get('profile',{}))
        if not profile.get('skills','').strip() and not profile.get('projects') and not profile.get('experience'):
            raise ValueError('Complete your CV facts before starting discovery.')
        status=agent.check()
        if status['auth'] not in ('ChatGPT','API key'):
            raise ValueError('Codex needs sign-in. Open AI & discovery and check the connection.')
        with agent.lock,store.lock:
            store.set('profile_confirmed',True)
            store.set('ai_config',{**agent.config(),'enabled':True,'auto_prepare':True,'discovery_enabled':True,'search_filters':filters,'auto_fill':data.get('auto_fill',agent.config()['auto_fill'])})
            store.set('settings',{**store.get('settings'),'enabled':True})
            store.set('paused',False)
            worker.paused.clear()
            store.event(None,'Otomasyon arama tercihleriyle açıldı; gönderim inceleme kuralları korundu.')
            if data.get('immediate') is True:
                with store.connect() as db:busy=db.execute("SELECT id FROM ai_runs WHERE kind='discover' AND status IN ('queued','running')").fetchone()
                if not busy:
                    agent.enqueue(kind='discover')
                    store.set('last_discovery',time.time())
        return jsonify(ok=True)

    @app.post('/api/notifications/test')
    def test_notification():
        if not worker.notification_status()['configured']:
            raise ValueError('Configure your private phone notifications first.')
        result=worker.notify(None,test=True)
        return jsonify(ok=result['state']=='sent',**result)

    @app.get('/api/history/cvs/<int:version_id>')
    def archived_cv(version_id):
        return send_file(io.BytesIO(worker.history.cv_bytes(version_id)),mimetype='application/pdf',as_attachment=True,download_name=f'Joblane-CV-version-{version_id}.pdf')

    @app.post('/api/jobs/<int:job_id>/email')
    def email_draft(job_id):
        data=request.get_json() or {}
        return jsonify(id=outlook.draft(job_id,data.get('recipient',''),data.get('subject',''),data.get('body',''))),201

    @app.post('/api/jobs/<int:job_id>/email/ai')
    def email_ai(job_id):
        data=request.get_json() or {}
        return jsonify(id=agent.enqueue(job_id,kind='email',message=data.get('message','Write a concise application. Choose Turkish for a Turkish-language posting and English for an English-language posting; if unclear ask. Use the role-specific CV.'))),202

    @app.get('/api/history/emails/<int:delivery_id>')
    def email_file(delivery_id):
        d=worker.history.delivery(delivery_id)
        if d['channel']!='outlook':raise ValueError('Not an email draft.')
        content=mime_message(d,worker.history.cv_bytes(d['cv_version_id']),store.get(f'email-sender:{delivery_id}',''))
        return send_file(io.BytesIO(content),mimetype='message/rfc822',as_attachment=True,download_name=f'Joblane-email-{delivery_id}.eml')

    @app.post('/api/history/emails/<int:delivery_id>/send')
    def email_send(delivery_id):
        return jsonify(status=outlook.send(delivery_id,(request.get_json() or {}).get('reviewed')))

    @app.post('/api/ai/check')
    def check_ai():return jsonify(agent.check())

    @app.put('/api/ai/config')
    def save_ai_config():
        data=request.get_json() or {}
        config={**agent.config(),**{k:v for k,v in data.items() if k in AI_DEFAULTS}}
        for key in ('enabled','auto_prepare','auto_fill','discovery_enabled'):
            if type(config[key]) is not bool:raise ValueError('Invalid AI preference.')
        if not isinstance(config['discovery_query'],str) or not 10<=len(config['discovery_query'])<=4000:raise ValueError('Describe the job search in 10–4,000 characters.')
        if type(config['discovery_interval']) is not int or not 30<=config['discovery_interval']<=1440:raise ValueError('Discovery interval must be 30–1,440 minutes.')
        config['search_filters']=validate_search(config['search_filters'])
        store.set('ai_config',config)
        store.event(None,'Codex connection and discovery preferences updated.')
        return jsonify(ok=True,config=config)

    @app.post('/api/ai/discover')
    def discover_jobs():
        message=(request.get_json() or {}).get('message','')
        return jsonify(id=agent.enqueue(kind='discover',message=message)),202

    @app.post('/api/jobs/<int:job_id>/answers')
    def answer_job(job_id):
        data=request.get_json() or {}
        if type(data.get('remember',False)) is not bool:raise ValueError('Ortak yanıt tercihi geçersiz.')
        return jsonify(agent.answer(job_id,data.get('text',''),remember=data.get('remember',False),question_run=data.get('question_run')))

    @app.post('/api/jobs/<int:job_id>/ai')
    def analyze_job(job_id):
        data=request.get_json() or {}
        return jsonify(id=agent.enqueue(job_id,message=data.get('message',''),kind='analyze')),202

    @app.post('/api/ai/runs/<int:run_id>/action')
    def ai_action(run_id):
        action=(request.get_json() or {}).get('action')
        if action=='apply':agent.apply(run_id)
        elif action=='cancel':agent.cancel(run_id)
        elif action=='retry':
            run=agent.get_run(run_id)
            if run['status'] not in ('failed','cancelled','interrupted'):raise ValueError('Only a stopped or failed run can retry.')
            return jsonify(id=agent.enqueue(run['job_id'],message=run['message'],kind=run['kind'])),202
        else:raise ValueError('Unknown AI action.')
        return jsonify(ok=True)

    @app.put('/api/profile')
    def save_profile():
        profile=validate_profile(request.get_json())
        with store.lock:
            if worker.current: raise ValueError('Wait for the active browser action to finish before changing your profile.')
            store.set('profile',profile)
            store.set('profile_confirmed',False)
            for job in store.jobs():
                if job['status'] not in ('submitted','skipped','draft'):
                    store.update(job['id'],status='needs_attention',authorized=0,reviewed=0,reason='Profile updated. Rebuild and review this CV before applying.')
            store.event(None,'Master profile updated. Existing applications keep their original CV snapshots.')
        return jsonify(ok=True)

    @app.post('/api/import-cv')
    def import_cv():
        file=request.files.get('file')
        if not file or not file.filename.lower().endswith('.pdf'): raise ValueError('Choose a PDF CV.')
        from pypdf import PdfReader
        try:
            reader=PdfReader(file.stream)
            if len(reader.pages)>10: raise ValueError()
            extracted='\n\n'.join(page.extract_text() or '' for page in reader.pages)
        except Exception:
            raise ValueError('Could not read this PDF. Use an unlocked, text-based CV with at most 10 pages.')
        if not extracted.strip(): raise ValueError('This PDF has no readable text. Use a text-based export.')
        store.set('imported_cv_text',extracted[:50000])
        return jsonify(text=extracted[:50000])

    def build_cv(job_id):
        job=store.job(job_id)
        if job['status'] in ('submitted','submitting','running') or store.get('attempt:'+str(job_id)):
            raise ValueError('Cannot rebuild an application that was submitted or has an uncertain submission.')
        profile=validate_profile(store.get('profile',{}))
        path=store.directory/'cvs'/f'application-{job_id}.pdf'
        generate(profile,job,path)
        store.update(job_id,cv_path=str(path),snapshot=json.dumps(profile),approval_digest=digest(profile,job),
            status='draft',authorized=0,reviewed=0,reason='CV prepared from verified profile facts. Review before sharing.')
        store.event(job_id,'Role-specific CV prepared; no claims were invented.')
        worker.history.archive_cv(job_id,'Profile-based CV')

    @app.post('/api/jobs')
    def create_job():
        data=request.get_json()
        if not isinstance(data,dict): raise ValueError('Invalid application.')
        for key in ('company','title','description'):
            if not isinstance(data.get(key),str) or not data[key].strip() or len(data[key])>30000:
                raise ValueError('Provide a company, title and job description.')
        if data.get('track') not in ('software','security','ml'): raise ValueError('Choose a CV focus.')
        url,domain=normalize_url(data.get('url',''))
        job_id=store.add(url=url,domain=domain,company=data['company'].strip(),title=data['title'].strip(),description=data['description'].strip(),track=data['track'],demo=0)
        build_cv(job_id)
        settings=store.get('settings')
        if agent.config()['enabled'] and agent.config()['auto_prepare']:
            try:agent.enqueue(job_id)
            except ValueError as exc:store.event(job_id,'AI preparation needs attention: '+str(exc))
        elif settings['mode']=='automatic' and domain in settings['allowed_domains'] and store.reviewed_count(domain)>=5:
            store.update(job_id,status='queued',reason='Queued under your authorization for this company domain.')
        return jsonify(id=job_id),201

    @app.post('/api/jobs/<int:job_id>/action')
    def job_action(job_id):
        data=request.get_json() or {}
        action=data.get('action')
        with store.lock:
            job=store.job(job_id)
            if worker.current==job_id or job['status'] in ('running','submitting'):
                raise ValueError('This application already has a browser action in progress.')
            if action=='rebuild': build_cv(job_id)
            elif action in ('fill','queue'):
                if job['status'] not in ('draft','needs_attention','ready_review'): raise ValueError('This application cannot be started from its current state.')
                if data.get('authorize') is not True: raise ValueError('Authorize sharing your profile and CV with this destination.')
                if digest(store.get('profile'),job)!=job['approval_digest']: raise ValueError('Rebuild the CV after profile changes.')
                if store.get('attempt:'+str(job_id)): raise ValueError('Check the previous submission result before doing anything else.')
                store.update(job_id,authorized=1,reviewed=0,status='queued',reason='Waiting for the execution window.' if action=='queue' else 'Waiting for the browser worker.')
                if action=='fill': worker.enqueue(job_id,'prepare')
            elif action=='submit':
                if job['status']!='ready_review' or data.get('reviewed') is not True:
                    raise ValueError('Review the prepared form before submitting.')
                store.update(job_id,reviewed=1,status='queued',reason='Reviewed; submission requested.')
                worker.enqueue(job_id,'submit')
            elif action=='resume':
                if job['status']!='needs_attention': raise ValueError('Only a paused application can resume.')
                if store.get('attempt:'+str(job_id)): raise ValueError('Use Check confirmation for an uncertain submission.')
                store.update(job_id,status='queued',reason='Resume requested.')
                worker.enqueue(job_id,'resume')
            elif action=='check':
                if job['status'] not in ('needs_attention','ready_review'): raise ValueError('Nothing to check in this state.')
                worker.enqueue(job_id,'check')
            elif action=='manual':
                note=str(data.get('note','')).strip()
                if len(note)<12: raise ValueError('Record how you verified submission (confirmation text or receipt reference).')
                if job['status'] in ('submitted','skipped'): raise ValueError('Application is already finished.')
                store.update(job_id,status='submitted',submitted=now(),reviewed=0,reason='Recorded by you: '+note[:2000])
                store.event(job_id,'Manual submission recorded by you; excluded from automatic-mode qualification.')
            elif action=='skip':
                if job['status']=='submitted': raise ValueError('A submitted application cannot be skipped.')
                store.update(job_id,status='skipped',reason='Skipped by you.')
            else: raise ValueError('Unknown action.')
        return jsonify(ok=True)

    @app.get('/api/jobs/<int:job_id>/<kind>')
    def download(job_id,kind):
        job=store.job(job_id)
        key={'cv':'cv_path','screenshot':'evidence'}.get(kind)
        if not key or not job[key] or not Path(job[key]).exists(): raise ValueError('File not available yet.')
        return send_file(job[key],as_attachment=kind=='cv',download_name=f'CV-{job_id}.pdf' if kind=='cv' else None)

    @app.put('/api/settings')
    def settings():
        data=request.get_json() or {}
        values={k:data.get(k,v) for k,v in store.get('settings').items()}
        validated=validate_settings(values)
        previous=store.get('settings')
        if (validated['mode']=='automatic' and previous['mode']!='automatic') or set(validated['allowed_domains'])-set(previous['allowed_domains']):
            if data.get('authorize_domains') is not True:
                raise ValueError('Authorize profile and CV sharing with the exact company domains listed.')
        store.set('settings',validated)
        store.event(None,'Schedule and application preferences updated.')
        return jsonify(ok=True)

    @app.post('/api/worker')
    def control():
        action=(request.get_json() or {}).get('action')
        if action=='pause':
            worker.paused.set(); store.set('paused',True)
            if agent.active:
                try:agent.cancel(agent.active)
                except ValueError:pass
            store.event(None,'All browser actions paused. An already-sent request may still complete.')
        elif action=='resume':
            worker.paused.clear(); store.set('paused',False)
            store.event(None,'Worker resumed.')
        else: raise ValueError('Unknown worker action.')
        return jsonify(ok=True)

    @app.get('/api/export')
    def export():
        text=io.StringIO()
        writer=csv.writer(text)
        keys=['company','title','url','status','track','created','submitted','reason']
        writer.writerow(keys)
        for job in store.jobs():
            values=[]
            for k in keys:
                value=str(job[k] or '')
                if value.startswith(('=','+','-','@','\t','\r')): value="'"+value
                values.append(value)
            writer.writerow(values)
        return Response(text.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=joblane-applications.csv'})

    if start_worker:
        worker.start()
        agent.start()
        replies.start()
    return app
