from test_joblane import env,profile


def test_site_sessions_require_auth_and_allowlisted_site(env):
    app,s,c,h=env
    assert app.test_client().post('/api/site-sessions/linkedin',json={'action':'open'}).status_code in (401,403)
    assert c.post('/api/site-sessions/unknown',json={'action':'open'},headers=h).status_code==400
    assert c.post('/api/site-sessions/linkedin',json={'action':'confirm'},headers=h).status_code==400
    assert c.post('/api/site-sessions/linkedin',json={'action':'open'},headers=h).status_code==200
    assert app.extensions['worker'].commands.get_nowait()==(None,'login:linkedin',False)
    assert c.get('/api/state').json['site_sessions']['linkedin']['status']=='opening'
    s.set('site_session:linkedin',{'status':'login_open'})
    assert c.post('/api/site-sessions/linkedin',json={'action':'confirm'},headers=h).status_code==200
    status=c.get('/api/state').json['site_sessions']['linkedin']
    assert status['status']=='checking'
    assert app.extensions['worker'].commands.get_nowait()==(None,'check-login:linkedin',False)
    assert not {'cookies','token','password'} & status.keys()


def test_theme_assets_load_without_login(env):
    app,*_=env;c=app.test_client()
    for path in ('/theme.js','/design.css'):
        r=c.get(path);assert r.status_code==200
        assert 'no-store' in r.headers['Cache-Control']


def test_login_open_rejected_during_application(env):
    app,s,c,h=env;app.extensions['worker'].current=42
    assert c.post('/api/site-sessions/linkedin',json={'action':'open'},headers=h).status_code==400


def test_idle_paused_worker_keeps_browser_requests_moving(env,monkeypatch):
    import queue
    app,s,c,h=env;worker=app.extensions['worker'];worker.paused.set()
    pending=['stylesheet','login-script','login-request'];delivered=[]
    def pump():
        if pending:delivered.append(pending.pop(0))
        else:worker.stop_event.set()
    class IdleQueue:
        def get(self,timeout):raise queue.Empty()
    worker.commands=IdleQueue()
    monkeypatch.setattr(worker.browser,'pump',pump)
    monkeypatch.setattr(worker.browser,'close',lambda:None)
    worker.loop()
    assert delivered==['stylesheet','login-script','login-request']


def test_closed_browser_can_be_reopened(env):
    from playwright.sync_api import Error
    app,*_=env;browser=app.extensions['worker'].browser
    class Page:
        def wait_for_timeout(self,ms):raise Error('closed')
    class Context:
        pages=[Page()]
        def close(self):raise Error('already closed')
    class Runtime:
        def stop(self):pass
    browser.context=Context();browser.runtime=Runtime();browser.login_pages={'linkedin':Page()}
    browser.pump()
    assert browser.context is None and browser.runtime is None and browser.login_pages=={}


def test_verification_result_is_visible_without_cookie_values(env,monkeypatch):
    app,s,c,h=env;worker=app.extensions['worker']
    s.set('site_session:linkedin',{'status':'login_open'})
    monkeypatch.setattr(worker.browser,'check_login',lambda site:{'status':'verified','session_present':True,'detail':'Account UI verified'})
    assert c.post('/api/site-sessions/linkedin',json={'action':'check'},headers=h).status_code==200
    worker.verify_login('linkedin')
    status=c.get('/api/state').json['site_sessions']['linkedin']
    assert status['status']=='verified' and status['session_present'] is True
    assert status['checked_at']==status['last_verified_at']
    assert set(status)<= {'status','session_present','detail','checked_at','updated','storage','last_verified_at'}


def test_linkedin_verification_requires_session_and_account_ui(env):
    app,*_=env;b=app.extensions['worker'].browser
    class Locator:
        def __init__(self,n=0):self.n=n
        def count(self):return self.n
        def inner_text(self,timeout):return 'Account page'
    class Page:
        url='https://www.linkedin.com/feed/'
        marker=False
        password=False
        def is_closed(self):return False
        def reload(self,**kwargs):pass
        def wait_for_function(self,*args,**kwargs):pass
        def locator(self,selector):
            if selector=='input[type="password"]:visible':return Locator(int(self.password))
            return Locator(int(self.marker and selector.startswith('.global-nav__me')))
    class Context:
        token=True
        def cookies(self,urls):return [{'name':'li_at','value':'DO-NOT-EXPOSE'}] if self.token else []
    page=Page();context=Context();b.context=context;b.login_pages={'linkedin':page}
    assert b.check_login('linkedin')['status']=='unverified' # cookie alone cannot prove login
    page.marker=True
    assert b.check_login('linkedin')['status']=='verified'
    context.token=False
    assert b.check_login('linkedin')['status']=='unverified'
    context.token=True;page.password=True
    assert b.check_login('linkedin')['status']=='login_required'
    page.password=False;page.url='https://www.linkedin.com/checkpoint/challenge/'
    assert b.check_login('linkedin')['status']=='verification_required'


def test_success_closes_login_but_failed_verification_keeps_it_open(env,monkeypatch):
    app,s,c,h=env;w=app.extensions['worker'];closed=[]
    monkeypatch.setattr(w.browser,'close_verified_login',lambda site:closed.append(site))
    for status in ('login_required','verification_required','unverified','verified'):
        monkeypatch.setattr(w.browser,'check_login',lambda site,status=status:{'status':status,'detail':'Checked','session_present':status=='verified'})
        w.verify_login('linkedin')
    assert closed==['linkedin']
    assert s.get('site_session:linkedin')['status']=='verified'


def test_close_verified_login_preserves_other_reviews(env,monkeypatch):
    app,*_=env;b=app.extensions['worker'].browser
    class Page:
        def __init__(self,url):self.url=url;self.closed=False
        def is_closed(self):return self.closed
        def close(self):self.closed=True
    login=Page('https://www.linkedin.com/feed/');review=Page('https://example.com/apply')
    class Context:pages=[login,review]
    b.context=Context();b.login_pages={'linkedin':login};closed=[]
    monkeypatch.setattr(b,'close',lambda:closed.append(True))
    b.close_verified_login('linkedin')
    assert login.closed and not review.closed and not closed
    assert 'linkedin' not in b.login_pages
    review.close();b.close_verified_login('linkedin')
    assert closed==[True]


def test_kariyer_never_labels_generic_cookies_as_session(env):
    app,*_=env;b=app.extensions['worker'].browser
    class Locator:
        def __init__(self,n=0,visible=False):self.n=n;self.visible=visible
        def count(self):return self.n
        def nth(self,i):return self
        def is_visible(self):return self.visible
        def inner_text(self,timeout):return 'Hesap sayfası'
    class Page:
        url='https://www.kariyer.net/'
        logout_visible=False
        def is_closed(self):return False
        def reload(self,**kwargs):pass
        def wait_for_function(self,*args,**kwargs):pass
        def locator(self,selector):return Locator()
        def get_by_role(self,*args,**kwargs):return Locator(1,self.logout_visible)
    class Context:
        def cookies(self,urls):raise AssertionError('Unknown cookies must not be used as authentication evidence')
    page=Page();b.kariyer_context=Context();b.login_pages={'kariyer':page}
    result=b.check_login('kariyer')
    assert result['status']=='unverified' and result['session_present'] is None
    page.logout_visible=True
    result=b.check_login('kariyer')
    assert result['status']=='verified' and result['session_present'] is None


def test_restart_clears_legacy_kariyer_cookie_claim(env):
    from joblane.worker import Worker
    app,s,*_=env
    s.set('site_session:kariyer',{'status':'unverified','session_present':True,'checked_at':'2026-10-24T21:37:00Z'})
    Worker(s,8765)
    result=s.get('site_session:kariyer')
    assert result['session_present'] is None
    assert result['status']=='unverified' and result['checked_at']=='2026-10-24T21:37:00Z'


def test_kariyer_uses_stable_chrome_and_separate_profile(env):
    app,s,*_=env;b=app.extensions['worker'].browser;launches=[]
    class Context:
        def set_default_timeout(self,value):pass
    class Chromium:
        def launch_persistent_context(self,path,**options):
            launches.append((path,options));return Context()
    class Runtime:chromium=Chromium()
    b.runtime=Runtime();b.start_kariyer();b.start()
    assert launches[0][0].endswith('browser-profile-kariyer-native')
    assert launches[0][1]['channel']=='chrome' and launches[0][1]['headless'] is False
    assert 'user_agent' not in launches[0][1]
    assert set(launches[0][1]['ignore_default_args'])=={'--use-mock-keychain','--password-store=basic'}
    assert launches[0][0]==str(b.kariyer_profile().resolve())
    assert launches[1][0].endswith('browser-profile')
    assert b.context is not b.kariyer_context


def test_verified_kariyer_does_not_close_linkedin(env):
    app,*_=env;b=app.extensions['worker'].browser
    class Page:
        url='https://example.com/'
        closed=False
        def is_closed(self):return self.closed
        def close(self):self.closed=True
    class Context:
        closed=False
        def __init__(self):self.pages=[Page()]
        def close(self):self.closed=True
    linkedin=Context();kariyer=Context();b.context=linkedin;b.kariyer_context=kariyer
    b.login_pages={'kariyer':kariyer.pages[0],'linkedin':linkedin.pages[0]}
    b.close_verified_login('kariyer')
    assert kariyer.closed and not linkedin.closed
    assert b.kariyer_context is None and b.context is linkedin


def test_captcha_forbidden_preserves_error_and_does_not_reload(env):
    app,*_=env;b=app.extensions['worker'].browser
    class Locator:
        def inner_text(self,timeout):return 'Captcha Forbidden\nTekrar dene\nError code: 60500 | diagnostic-id-not-to-be-exposed'
    class Page:
        url='https://www.kariyer.net/'
        def is_closed(self):return False
        def locator(self,selector):return Locator()
        def reload(self,**kwargs):raise AssertionError('Must not restart a rejected challenge')
    b.kariyer_context=object();b.login_pages={'kariyer':Page()}
    result=b.check_login('kariyer')
    assert result['status']=='verification_required' and result['session_present'] is None
    assert '60500' in result['detail']
    assert 'diagnostic-id-not-to-be-exposed' not in str(result)


def test_manual_kariyer_launch_has_no_automation_and_keeps_own_profile(env,monkeypatch):
    from joblane import browser as mod
    app,s,*_=env;b=app.extensions['worker'].browser;launches=[]
    class Process:
        def poll(self):return None
    monkeypatch.setattr(b,'chrome_executable',lambda:'/installed/chrome')
    monkeypatch.setattr(mod.subprocess,'Popen',lambda args,**kwargs:launches.append(args) or Process())
    b.open_manual_kariyer();b.open_manual_kariyer()
    assert len(launches)==1
    args=launches[0]
    assert args[0]=='/installed/chrome' and args[-1]=='https://www.kariyer.net/'
    assert '--user-data-dir='+str(b.kariyer_profile().resolve()) in args
    assert not any('debugging' in x or 'automation' in x or 'user-agent' in x for x in args)
    monkeypatch.setattr(b,'open_login',lambda site:(_ for _ in ()).throw(AssertionError('Must wait for human browser to close')))
    result=b.check_login('kariyer')
    assert result['status']=='manual_login_open' and result['session_present'] is None


def test_live_native_profile_lock_survives_server_restart(env,monkeypatch):
    import os
    app,*_=env;b=app.extensions['worker'].browser
    b.kariyer_profile().mkdir()
    lock=b.kariyer_profile()/'SingletonLock';lock.symlink_to('computer-12345')
    monkeypatch.setattr(os,'kill',lambda pid,sig:None)
    assert b.native_kariyer_running()
    def gone(pid,sig):raise ProcessLookupError()
    monkeypatch.setattr(os,'kill',gone)
    assert not b.native_kariyer_running()
    assert lock.is_symlink()  # Never delete Chrome's lock or touch its cookie files.


def test_manual_login_command_does_not_start_playwright(env,monkeypatch):
    app,s,*_=env;w=app.extensions['worker'];calls=[]
    def manual():calls.append('manual');w.stop_event.set()
    monkeypatch.setattr(w.browser,'open_manual_kariyer',manual)
    monkeypatch.setattr(w.browser,'open_login',lambda site:(_ for _ in ()).throw(AssertionError('Automated launch during manual login')))
    w.commands.put((None,'login:kariyer',False));w.loop()
    assert calls==['manual']
    assert s.get('site_session:kariyer')['status']=='manual_login_open'


def test_captcha_forbidden_inside_iframe_is_not_missed(env):
    app,*_=env;b=app.extensions['worker'].browser
    class Locator:
        def __init__(self,text):self.text=text
        def inner_text(self,timeout):return self.text
    class Frame:
        def locator(self,selector):return Locator('Captcha Forbidden Error code: 60500 | do-not-expose')
    class Page:
        url='https://www.kariyer.net/'
        frames=[Frame()]
        def locator(self,selector):return Locator('Giriş yap')
    result=b.login_blocker(Page())
    assert result['status']=='verification_required'
    assert '60500' in result['detail'] and 'do-not-expose' not in str(result)
