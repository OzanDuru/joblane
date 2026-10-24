import json
import os
import queue
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from .browser import FormBrowser, Handoff
from .policy import within_window, board_requires_handoff, digest, matches_preferences, public_host
from .store import now
from .history import History
from . import telegram
from .form_plan import descriptors


class Worker:
    def __init__(self,store,port):
        self.store=store
        self.history=History(store)
        self.port=port
        self.commands=queue.Queue()
        self.stop_event=threading.Event()
        self.paused=threading.Event()
        self.paused.set() if store.get('paused',False) else None
        self.thread=None
        self.current=None
        self.browser=FormBrowser(store.directory,self.guard)
        self.signatures={}
        self.scheduled_action=False
        self.on_attention=None
        for site in ('linkedin','kariyer'):
            prior=store.get('site_session:'+site,{})
            if site=='kariyer' and 'session_present' in prior:
                prior['session_present']=None
                store.set('site_session:'+site,prior)
            if prior.get('status') in ('opening','login_open','manual_login_open','checking','verified'):
                store.set('site_session:'+site,{'status':'reopen_required','updated':now(),'last_verified_at':prior.get('last_verified_at')})

    def start(self):
        self.thread=threading.Thread(target=self.loop,daemon=True,name='joblane-worker')
        self.thread.start()

    def guard(self):
        if self.store.get('password_change_required',False): raise Handoff('Set your private workspace password before live work.')
        if self.paused.is_set(): raise Handoff('All browser actions are paused. Resume when you are ready.')
        if self.scheduled_action:
            settings=self.store.get('settings')
            if not settings['enabled'] or not within_window(settings):
                raise Handoff('The scheduled window ended or the scheduler was disabled. Resume during the next window.')

    def enqueue(self,job_id,action):
        if self.paused.is_set(): raise ValueError('Resume the worker before starting an application.')
        self.commands.put((job_id,action,False))

    def login_status(self):
        return {site:self.store.get('site_session:'+site,{'status':'not_configured'}) for site in ('linkedin','kariyer')}

    def open_login(self,site):
        if site not in ('linkedin','kariyer'):raise ValueError('Bilinmeyen site.')
        if self.current:raise ValueError('Aktif başvuru işlemi bitene kadar bekle.')
        previous=self.store.get('site_session:'+site,{})
        if previous.get('status')=='opening':return
        self.store.set('site_session:'+site,{'status':'opening','updated':now()})
        self.commands.put((None,'login:'+site,False))

    def check_login(self,site):
        if site not in ('linkedin','kariyer'):raise ValueError('Bilinmeyen site.')
        if self.current:raise ValueError('Aktif başvuru işlemi bitene kadar bekle.')
        previous=self.store.get('site_session:'+site,{})
        if previous.get('status')=='checking':return
        if previous.get('status') in (None,'not_configured','opening'):
            raise ValueError('Önce Joblane tarayıcısında giriş sayfasını aç.')
        self.store.set('site_session:'+site,{**previous,'status':'checking','updated':now()})
        self.commands.put((None,'check-login:'+site,False))

    def verify_login(self,site):
        try:result=self.browser.check_login(site)
        except Exception:result={'status':'error','detail':'Oturum kontrolü tamamlanamadı. Tarayıcıyı ve bağlantıyı kontrol edip tekrar dene.','session_present':None}
        if result['status']=='verified':
            try:
                self.browser.close_verified_login(site)
                result['detail']+=' Giriş sekmesi kapatıldı; oturum kaydı korunuyor.'
            except Exception:
                result['detail']+=' Giriş sekmesi otomatik kapatılamadı; elle kapatabilirsin.'
        checked=now();previous=self.store.get('site_session:'+site,{})
        result.update(checked_at=checked,updated=checked,storage='browser_profile',last_verified_at=checked if result['status']=='verified' else previous.get('last_verified_at'))
        self.store.set('site_session:'+site,result)
        self.store.event(None,site+' oturum kontrolü: '+result['status'])

    def notification_status(self):
        tg=telegram.status(self.store)
        pushover=all(os.getenv(k) for k in ('PUSHOVER_APP_TOKEN','PUSHOVER_USER_KEY','PUSHOVER_DEVICE'))
        return {'configured':tg['configured'] or pushover,
                'provider':'telegram' if tg['configured'] else 'pushover' if pushover else None,
                'bot_username':tg['bot_username']}

    def notify(self,job_id,test=False):
        if telegram.status(self.store)['configured']:
            state='sent'
            try:detail=telegram.send(self.store,test=test,job_id=job_id)
            except Exception:
                state,detail='failed','Telegram bildirimi doğrulanamadı. Bot bağlantısını, engelleme durumunu ve interneti kontrol et. Otomatik tekrar veya başka kanala gönderim yapılmadı.'
            with self.store.connect() as db:
                db.execute('INSERT INTO notifications(job_id,state,detail,created) VALUES (?,?,?,?)',(job_id,state,detail,now()))
            return {'state':state,'detail':detail}
        token=os.getenv('PUSHOVER_APP_TOKEN')
        user=os.getenv('PUSHOVER_USER_KEY')
        device=os.getenv('PUSHOVER_DEVICE')
        if not (token and user and device): return
        payload=urllib.parse.urlencode({'token':token,'user':user,'device':device,'title':'Joblane connection test' if test else 'Joblane needs you','message':'Your private Joblane notification connection is working.' if test else 'An application needs your attention. Open your private Joblane dashboard.'}).encode()
        state,detail='sent','Notification queued for your configured device.'
        try:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,25}',device) or ',' in user:
                raise ValueError('Use one private user and device.')
            validation=urllib.parse.urlencode({'token':token,'user':user,'device':device}).encode()
            with urllib.request.urlopen(urllib.request.Request('https://api.pushover.net/1/users/validate.json',data=validation),timeout=10) as response:
                checked=json.load(response)
            if checked.get('status')!=1 or device not in checked.get('devices',[]):
                raise ValueError('The exact private device could not be verified.')
            with urllib.request.urlopen(urllib.request.Request('https://api.pushover.net/1/messages.json',data=payload),timeout=10) as response:
                if json.load(response).get('status')!=1: raise ValueError()
        except Exception:
            state,detail='failed','Push validation or delivery failed. Check the exact private device and credentials; the issue remains in the dashboard.'
        with self.store.connect() as db:
            db.execute('INSERT INTO notifications(job_id,state,detail,created) VALUES (?,?,?,?)',(job_id,state,detail,now()))
        return {'state':state,'detail':detail}

    def attention(self,job_id,reason):
        record=self.store.get(f'delivery:{job_id}')
        if record and self.history.delivery(record)['status']=='sending':self.history.update(record,'uncertain',reason)
        self.store.update(job_id,status='needs_attention',reason=reason)
        self.store.event(job_id,reason)
        observation={'reason':reason,'fields':[]}
        page=self.browser.pages.get(job_id)
        if page:
            try:
                _,fields=self.browser.inspect(page)
                observation['fields']=descriptors(fields)
            except Exception:pass
        self.store.set(f'observation:{job_id}',observation)
        handling=self.on_attention(job_id) if self.on_attention else False
        if not handling:self.notify(job_id)

    def scheduled_job(self):
        settings=self.store.get('settings')
        if self.store.get('password_change_required',False) or self.paused.is_set() or not settings['enabled'] or not within_window(settings): return None
        today=datetime.now(ZoneInfo(settings['timezone'])).date()
        used=sum(1 for j in self.store.jobs() if not j['demo'] and j['attempt_started'] and datetime.fromisoformat(j['attempt_started']).astimezone(ZoneInfo(settings['timezone'])).date()==today)
        if used>=settings['daily_limit']: return None
        for job in reversed(self.store.jobs()):
            if job['status']=='queued': return job['id']
        return None

    def loop(self):
        while not self.stop_event.is_set():
            # Routing callbacks are delivered only during Playwright calls.
            # Keep login, MFA and review tabs responsive even when paused/idle.
            self.browser.pump()
            try:
                item=self.commands.get(timeout=.25)
            except queue.Empty:
                job_id=self.scheduled_job()
                if job_id is None: continue
                item=(job_id,'prepare',True)
            job_id,action,scheduled=item
            if action.startswith('check-login:'):
                self.verify_login(action.split(':',1)[1])
                continue
            if action.startswith('login:'):
                site=action.split(':',1)[1]
                try:
                    if site=='kariyer':self.browser.open_manual_kariyer()
                    else:self.browser.open_login(site)
                    self.store.set('site_session:'+site,{'status':'manual_login_open' if site=='kariyer' else 'login_open','updated':now()})
                except Exception:
                    self.store.set('site_session:'+site,{'status':'error','updated':now(),'detail':'Kariyer.net için Google Chrome açılamadı. Bu bilgisayarda Google Chrome kurulu olmalı.' if site=='kariyer' else 'Giriş tarayıcısı açılamadı. Bilgisayarı ve Playwright kurulumunu kontrol et.'})
                continue
            self.current=job_id
            self.scheduled_action=scheduled
            try:
                self.run(job_id,action)
            except Handoff as exc:
                self.attention(job_id,str(exc))
            except Exception as exc:
                # Do not expose cookies, query strings, or secrets in browser stack traces.
                reason='Browser could not complete this step ('+type(exc).__name__+'). Check the laptop browser, internet connection and browser installation. No automatic retry was made.'
                self.attention(job_id,reason)
            finally:
                page=self.browser.pages.get(job_id)
                if page:
                    try:
                        path=self.store.directory / 'evidence' / f'{job_id}.png'
                        path.parent.mkdir(exist_ok=True)
                        self.browser.screenshot(page,path)
                        self.store.update(job_id,evidence=str(path))
                    except Exception: pass
                self.current=None
                self.scheduled_action=False
        self.browser.close()

    def run(self,job_id,action):
        self.guard()
        job=self.store.job(job_id)
        if job['demo']: raise Handoff('Legacy demo data must be removed before use.')
        if job['status'] in ('submitted','skipped'): return
        settings=self.store.get('settings')
        if action=='check':
            page=self.browser.pages.get(job_id)
            if not page: raise Handoff('No live tab exists in this process. Check the employer history manually; do not retry an uncertain submission.')
            result=self.browser.confirmation(page)
            if not result: raise Handoff('No submission confirmation is visible yet. Check the existing application in the browser.')
            self.complete(job_id,result)
            return
        if not job['demo'] and board_requires_handoff(job['domain']):
            raise Handoff('This job board uses manual application in this build. Use its employer application link when available, or apply yourself and record the result.')
        if not job['snapshot']: raise Handoff('Prepare a CV before filling the application.')
        profile=json.loads(job['snapshot'])
        current_profile=self.store.get('profile')
        if digest(current_profile,job)!=job['approval_digest']:
            raise Handoff('Your profile changed. Prepare a new CV and authorize it before continuing.')
        automatic=(settings['mode']=='automatic' and job['domain'] in settings['allowed_domains'] and self.store.reviewed_count(job['domain'])>=5 and not job['demo'])
        if not job['authorized'] and not automatic:
            raise Handoff('Authorize sharing this profile and CV with the application destination first.')
        match,reason=matches_preferences(job,settings)
        if not match and not job['demo']: raise Handoff(reason)
        if not job['demo'] and not public_host(job['domain']):
            raise Handoff('The destination is unavailable or resolves to a private network address.')
        if action=='submit':
            page=self.browser.pages.get(job_id)
            signature=self.signatures.get(job_id)
            if not page or not signature: raise Handoff('The prepared tab is no longer available. Resume to prepare it again.')
            # A fresh human review is required for a manually requested submission.
            if not job['reviewed']: raise Handoff('Review the prepared form before submitting.')
        else:
            # Never fill or submit again after a possibly transmitted request.
            if job['status']=='needs_attention' and job['attempt_started'] and self.store.get('attempt:'+str(job_id)):
                raise Handoff('An earlier submission may have reached the employer. Check confirmation or record the result manually.')
            self.store.update(job_id,status='running',reason='',attempt_started=job['attempt_started'] or now())
            page=self.browser.page(job)
            if self.browser.confirmation(page):
                raise Handoff('A confirmation-like page is already visible. Check the existing submission before doing anything else.')
            self.browser.open_application_form(page)
            plan=self.store.get(f'form_plan:{job_id}')
            self.signatures[job_id]=self.browser.fill(page,profile,job['cv_path'],acknowledge_unknown=action=='resume' or bool(plan),plan=plan)
            self.store.update(job_id,status='ready_review',reason='Form filled. Inspect the CV and browser screenshot before submitting.')
            self.store.event(job_id,'Form filled; ready for review.' if not automatic else 'Known form filled under domain authorization.')
            if not automatic: return
            signature=self.signatures[job_id]
        def mark_submitting():
            version=self.history.archive_cv(job_id,'CV used for browser submission')
            record=self.history.create(job_id,'browser',job['url'],'sending',version,details='Submission attempt started; confirmation pending.')
            self.store.set(f'delivery:{job_id}',record)
            self.store.set('attempt:'+str(job_id),True)
            self.store.update(job_id,status='submitting',reason='Waiting for employer confirmation.')
        result=self.browser.submit(page,signature,mark_submitting)
        self.complete(job_id,result)

    def complete(self,job_id,result):
        if not result:raise Handoff('No reliable submission confirmation is visible. Check the existing application.')
        record=self.store.get(f'delivery:{job_id}')
        if record:self.history.update(record,'confirmed','Verified on page: '+str(result))
        self.store.update(job_id,status='submitted',reason='Verified on page: '+str(result),submitted=now())
        self.store.event(job_id,'Application submission confirmed.')
