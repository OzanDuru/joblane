"""Conservative single-page form adapter. Unknown controls always cause a handoff."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from .form_plan import signature as plan_signature

CHALLENGES = ('verify you are human','checking your browser','unusual traffic','access denied','verify that you are human','security verification','captcha forbidden')
CONFIRMATIONS = ('your application has been submitted','application successfully submitted','thank you for applying','başvurunuz alınmıştır','başvurunuz başarıyla')


def field_value(label, kind, autocomplete, profile):
    label = re.sub(r'[\s_*:]+',' ',label.lower()).strip()
    names = profile['name'].split()
    if kind == 'email' or autocomplete == 'email' or re.fullmatch(r'(e ?mail|email address|e posta)( address)?',label):
        return profile['email']
    if autocomplete == 'given-name' or label in ('first name','given name','ad','adınız'):
        return names[0]
    if autocomplete == 'family-name' or label in ('last name','surname','family name','soyad','soyadınız'):
        return ' '.join(names[1:])
    if autocomplete == 'name' or label in ('name','full name','ad soyad','adınız soyadınız'):
        return profile['name']
    if kind == 'tel' or autocomplete == 'tel' or label in ('phone','phone number','telephone','telefon','telefon numarası'):
        return profile.get('phone') or None
    return None


def form_signature(fields):
    return hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()


class Handoff(Exception):
    pass


class FormBrowser:
    def __init__(self, directory, guard):
        self.directory = directory
        self.guard = guard
        self.runtime = None
        self.context = None
        self.kariyer_context = None
        self.native_kariyer_process = None
        self.pages = {}
        self.last_domain = None
        self.login_pages = {}

    def start(self):
        if self.context: return
        from playwright.sync_api import sync_playwright
        if not self.runtime:self.runtime = sync_playwright().start()
        profile_dir=self.directory/'browser-profile'
        profile_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        if os.name=='posix':profile_dir.chmod(0o700)
        self.context = self.runtime.chromium.launch_persistent_context(
            str(profile_dir),headless=False,
            viewport={'width':1280,'height':900},accept_downloads=False,
            service_workers='block')
        self.context.set_default_timeout(10000)

    def kariyer_profile(self):
        return self.directory/'browser-profile-kariyer-native'

    def native_kariyer_running(self):
        if self.native_kariyer_process and self.native_kariyer_process.poll() is None:return True
        # Chrome leaves a PID lock on macOS/Linux. Check it without changing it;
        # this also handles a manual login window surviving a Joblane restart.
        lock=self.kariyer_profile()/'SingletonLock'
        if lock.is_symlink():
            try:
                pid=int(os.readlink(lock).rsplit('-',1)[-1])
                if pid<=0:return False
                os.kill(pid,0)
                return True
            except ProcessLookupError:pass
            except PermissionError:return True
            except (OSError,ValueError):pass
        return False

    @staticmethod
    def chrome_executable():
        candidates=[]
        if sys.platform=='darwin':
            candidates=[Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),Path.home()/'Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
        elif os.name=='nt':
            candidates=[Path(os.environ[key])/'Google/Chrome/Application/chrome.exe' for key in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA') if os.environ.get(key)]
        for path in candidates:
            if path.is_file():return str(path)
        for name in ('google-chrome','google-chrome-stable'):
            found=shutil.which(name)
            if found:return found
        raise FileNotFoundError('Google Chrome is not installed')

    def open_manual_kariyer(self):
        if self.kariyer_context:
            self.kariyer_context.close();self.kariyer_context=None
            self.login_pages.pop('kariyer',None)
        if self.native_kariyer_running():return
        profile=self.kariyer_profile().resolve()
        profile.mkdir(parents=True,exist_ok=True,mode=0o700)
        if os.name=='posix':profile.chmod(0o700)
        # Human-only login. No debugger, automation flags, routing, UA overrides
        # or access to the user's everyday Chrome profile.
        self.native_kariyer_process=subprocess.Popen([
            self.chrome_executable(),'--user-data-dir='+str(profile),
            '--no-first-run','--no-default-browser-check','--new-window',
            'https://www.kariyer.net/'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def start_kariyer(self):
        """Use installed stable Chrome with its own profile; never reuse a newer test profile."""
        if self.kariyer_context:return
        from playwright.sync_api import sync_playwright
        if not self.runtime:self.runtime=sync_playwright().start()
        profile_dir=self.kariyer_profile()
        profile_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        if os.name=='posix':profile_dir.chmod(0o700)
        self.kariyer_context=self.runtime.chromium.launch_persistent_context(
            str(profile_dir.resolve()),channel='chrome',headless=False,no_viewport=True,
            # Native Chrome encrypts profile cookies with the OS credential store.
            # Playwright's test keychain defaults cannot read those same cookies.
            ignore_default_args=['--use-mock-keychain','--password-store=basic'],
            accept_downloads=False,service_workers='block')
        self.kariyer_context.set_default_timeout(10000)

    def pump(self):
        """Dispatch sync Playwright callbacks for all open login/review contexts."""
        from playwright.sync_api import Error
        for attr in ('context','kariyer_context'):
            context=getattr(self,attr)
            if not context:continue
            try:
                pages=context.pages
                if pages:pages[0].wait_for_timeout(50)
            except Error:
                try:context.close()
                except Exception:pass
                setattr(self,attr,None)
                if attr=='kariyer_context':self.login_pages.pop('kariyer',None)
                else:
                    self.pages.clear();self.login_pages.pop('linkedin',None)
        if not self.context and not self.kariyer_context and self.runtime:self.close()

    def open_login(self,site):
        urls={'linkedin':'https://www.linkedin.com/uas/login','kariyer':'https://www.kariyer.net/'}
        if site not in urls:raise ValueError('Unsupported login site.')
        if site=='kariyer':
            self.start_kariyer();context=self.kariyer_context
        else:
            self.start();context=self.context
        page=self.login_pages.get(site)
        if page and not page.is_closed():
            page.bring_to_front();return
        page=context.new_page()
        from .policy import public_host
        cache={}
        def route_handler(route):
            u=urlsplit(route.request.url);host=u.hostname or ''
            if host not in cache:cache[host]=public_host(host)
            if u.scheme=='https' and u.port in (None,443) and cache[host]:route.continue_()
            else:route.abort()
        page.route('**/*',route_handler)
        self.login_pages[site]=page
        page.goto(urls[site],wait_until='domcontentloaded',timeout=45000)
        page.bring_to_front()

    @staticmethod
    def login_blocker(page):
        # Read the current error before any refresh: reloading loses the useful
        # diagnostic and may start the very same rejected challenge again.
        texts=[page.locator('body').inner_text(timeout=10000).lower()]
        # Challenge providers can render their error in a cross-origin iframe;
        # top-level body text does not contain that message. Read only text,
        # never tokens, cookies, headers or arbitrary frame state.
        for frame in getattr(page,'frames',[])[:12]:
            if frame==getattr(page,'main_frame',None):continue
            try:texts.append(frame.locator('body').inner_text(timeout=500).lower())
            except Exception:pass
        text='\n'.join(texts)
        if 'captcha forbidden' in text:
            code=' (60500)' if re.search(r'\b60500\b',text) else ''
            return {'status':'verification_required','detail':'CAPTCHA isteği doğrulama hizmeti tarafından reddedildi'+code+'. Oturum doğrulanmadı. Günlük kullandığın tarayıcıda girişin çalışıp çalışmadığını kontrol et; otomatik tekrar yapılmıyor.','session_present':None}
        if any(x in text for x in CHALLENGES) or '/checkpoint/' in page.url or '/challenge/' in page.url or page.locator('iframe[src*="challenges.cloudflare"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').count():
            return {'status':'verification_required','detail':'Tarayıcı doğrulaması veya güvenlik adımı tamamlanmalı.','session_present':None}
        return None

    def check_login(self,site):
        if site not in ('linkedin','kariyer'):raise ValueError('Unsupported login site.')
        if site=='kariyer' and not self.kariyer_context and self.native_kariyer_running():
            return {'status':'manual_login_open','detail':'Girişi normal Chrome penceresinde tamamla. Ardından yalnızca bu özel giriş Chrome’unu tamamen kapat (Mac: ⌘Q; Windows/Linux: tüm pencereleri kapat) ve Oturumu doğrula düğmesine tekrar bas.','session_present':None}
        context=self.kariyer_context if site=='kariyer' else self.context
        if not context or not self.login_pages.get(site) or self.login_pages[site].is_closed():
            self.open_login(site)
        page=self.login_pages[site]
        host=(urlsplit(page.url).hostname or '').lower()
        root='linkedin.com' if site=='linkedin' else 'kariyer.net'
        if host!=root and not host.endswith('.'+root):
            return {'status':'verification_required','detail':'Giriş başka bir doğrulama sayfasında bekliyor. Tarayıcıdaki adımı tamamla.','session_present':None}
        blocker=self.login_blocker(page)
        if blocker:return blocker
        # Refresh before checking so an old account DOM is not proof of a live session.
        if '/checkpoint/' not in page.url and '/challenge/' not in page.url:
            page.reload(wait_until='domcontentloaded',timeout=30000)
            from playwright.sync_api import TimeoutError as PlaywrightTimeout
            try:
                page.wait_for_function('''() => !!document.querySelector('input[type="password"], .global-nav__me, .global-nav__me-photo, a[href*="/mynetwork/"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]') || /çıkış yap|oturumu kapat|verify you are human|captcha forbidden/i.test(document.body?.innerText || '')''',timeout=10000)
            except PlaywrightTimeout:pass
        blocker=self.login_blocker(page)
        if blocker:return blocker
        if page.locator('input[type="password"]:visible').count():
            return {'status':'login_required','detail':'Giriş formu hâlâ açık. Şifre ve varsa ikinci doğrulama adımını tamamla.','session_present':None}
        host=(urlsplit(page.url).hostname or '').lower()
        if host!=root and not host.endswith('.'+root):
            return {'status':'verification_required','detail':'Giriş doğrulaması başka bir sayfada bekliyor.','session_present':None}
        # Read locally only; never return cookie names, values or request headers.
        if site=='linkedin':
            cookies=self.context.cookies(['https://www.'+root])
            present=any(c.get('name')=='li_at' and c.get('value') for c in cookies)
            marker=page.locator('.global-nav__me, .global-nav__me-photo, [data-control-name="nav.settings"]').count()>0
            navigation=page.locator('a[href*="/mynetwork/"]').count()>0 and page.locator('a[href*="/messaging/"]').count()>0
            authenticated=present and (marker or navigation)
        else:
            # Kariyer may change its token names: use visible authenticated controls,
            # never treat generic tracking cookies as proof of a valid login.
            present=None  # Generic, analytics and challenge cookies are not auth evidence.
            controls=[page.get_by_role(role,name=re.compile(r'^(çıkış yap|çıkış|oturumu kapat)$',re.I)) for role in ('link','button')]
            authenticated=any(control.nth(i).is_visible() for control in controls for i in range(control.count()))
        if authenticated:
            return {'status':'verified','detail':'Giriş yapılmış hesap kontrolleri doğrulandı. Oturum bu bilgisayarın tarayıcı profilinde saklanıyor.','session_present':present}
        return {'status':'unverified','detail':'Giriş yapılmış hesap ekranı doğrulanamadı. Hesap ana sayfasını açıp yeniden kontrol et.','session_present':present}

    def close_verified_login(self,site):
        """Close the verified login; keep other login/review pages intact."""
        page=self.login_pages.get(site)
        if page and not page.is_closed():page.close()
        self.login_pages.pop(site,None)
        for attr in ('context','kariyer_context'):
            context=getattr(self,attr)
            if not context:continue
            remaining=[p for p in context.pages if not p.is_closed() and p.url not in ('about:blank','chrome://newtab/','chrome://new-tab-page/')]
            if not remaining:
                # Keep the other site's context and its in-progress login intact.
                if (attr=='context' and self.kariyer_context) or (attr=='kariyer_context' and self.context):
                    context.close();setattr(self,attr,None)
                else:self.close()

    def page(self, job):
        self.start()
        page = self.pages.get(job['id'])
        if page and not page.is_closed(): return page
        page = self.context.new_page()
        # Never let an employer page navigate to the local dashboard or private network.
        from .policy import public_host
        cache = {}
        def route_handler(route):
            url = urlsplit(route.request.url)
            host = url.hostname or ''
            if host not in cache: cache[host] = public_host(host)
            okay = url.scheme == 'https' and url.port in (None,443) and cache[host]
            if route.request.is_navigation_request() and route.request.frame == page.main_frame:
                okay = okay and host == job['domain']
            if okay: route.continue_()
            else: route.abort()
        page.route('**/*',route_handler)
        self.pages[job['id']] = page
        page.goto(job['url'],wait_until='domcontentloaded',timeout=45000)
        return page

    def open_application_form(self,page):
        """Follow one unambiguous same-site apply link, never click a submit button."""
        for _ in range(3):
            _,fields=self.inspect(page)
            if fields:return
            links=page.get_by_role('link',name=re.compile(r'^(apply|apply now|apply for this job|apply for this position|başvur|hemen başvur|başvuru yap)$',re.I))
            visible=[links.nth(i) for i in range(links.count()) if links.nth(i).is_visible()]
            if len(visible)!=1:return
            target=urljoin(page.url,visible[0].get_attribute('href') or '')
            before=urlsplit(page.url);dest=urlsplit(target)
            if target==page.url or dest.scheme!='https' or dest.hostname!=before.hostname:return
            self.guard()
            visible[0].click(timeout=15000)
            page.wait_for_load_state('domcontentloaded')

    def inspect(self,page):
        text = page.locator('body').inner_text(timeout=10000).lower()
        if any(s in text for s in CHALLENGES) or page.locator('iframe[src*="challenges.cloudflare"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').count():
            raise Handoff('Browser verification is required. Use remote desktop to complete it in this tab, then resume.')
        if page.locator('input[type="password"]:visible').count():
            raise Handoff('Sign in using remote desktop in this browser, then resume.')
        fields=[]
        controls=page.locator('input, textarea, select')
        for i in range(controls.count()):
            el=controls.nth(i)
            if not el.is_visible() or not el.is_enabled(): continue
            info=el.evaluate('''el => ({
              label: (Array.from(el.labels || []).map(l => l.innerText).join(' ') || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || '').trim(),
              kind: el.type || el.tagName.toLowerCase(), autocomplete: el.autocomplete || '',
              required: el.required || el.getAttribute('aria-required') === 'true',
              value: el.type === 'file' ? Array.from(el.files || []).map(f=>f.name).join(',') : el.value,
              checked: !!el.checked, index: 0, options: el.tagName === 'SELECT' ? Array.from(el.options).map(o=>({value:o.value,label:o.text,disabled:o.disabled})).filter(o=>!o.disabled) : null
            })''')
            if info['kind'] in ('submit','button','reset','hidden'): continue
            info['index']=i
            fields.append(info)
        return controls, fields

    def fill(self,page,profile,cv_path,acknowledge_unknown=False,plan=None):
        controls,fields=self.inspect(page)
        if not fields: raise Handoff('No supported single-page form found. Open the application form in this tab, then resume.')
        if plan and plan.get('signature')!=plan_signature(fields):raise Handoff('Form alanları değişti. Yeni alanlar için tekrar değerlendirme gerekiyor.')
        planned={a['index']:a['value'] for a in (plan or {}).get('answers',[])}
        issues=[]
        for f in fields:
            self.guard()
            el=controls.nth(f['index'])
            identity=el.evaluate('''el => ({label:(Array.from(el.labels || []).map(l=>l.innerText).join(' ') || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || '').trim(),kind:el.type || el.tagName.toLowerCase()})''')
            if identity['label']!=f['label'] or identity['kind']!=f['kind']:
                raise Handoff('The form added or moved fields while filling. Inspect the updated form and resume.')
            if f['kind']=='file':
                if re.search(r'\b(resume|résumé|cv|özgeçmiş)\b',f['label'],re.I):
                    el.set_input_files(str(cv_path))
                elif not acknowledge_unknown or (f['required'] and not f['value']):
                    issues.append('Unrecognized upload: '+f['label'])
            elif f['kind'] in ('checkbox','radio'):
                if not acknowledge_unknown or (f['required'] and not f['checked']):
                    # Radio requiredness belongs to its named group, not each option.
                    if acknowledge_unknown and f['kind']=='radio':
                        name=el.get_attribute('name')
                        checked=el.evaluate('el => Array.from(el.form?.elements || []).some(x => x.type === "radio" && x.name === el.name && x.checked)')
                        if checked: continue
                    issues.append('Choice needs your input: '+f['label'])
            else:
                value=field_value(f['label'],f['kind'],f['autocomplete'],profile)
                if value is None:value=planned.get(f['index'])
                if value is not None:
                    if f['kind']=='select-one':el.select_option(value)
                    else:el.fill(value)
                elif f['required'] and not f['value']:
                    issues.append('Required answer: '+f['label'])
                elif not acknowledge_unknown:
                    issues.append('Unmapped question: '+f['label'])
        _, current=self.inspect(page)
        before=[(f['label'],f['kind'],f['required']) for f in fields]
        after=[(f['label'],f['kind'],f['required']) for f in current]
        if before!=after:
            raise Handoff('The form changed while filling. Inspect the new questions, then resume.')
        if issues: raise Handoff('; '.join(issues[:6])+'. Complete these in the browser, then resume.')
        return form_signature(current)

    def signature(self,page):
        _, fields = self.inspect(page)
        return form_signature(fields)

    def confirmation(self,page):
        text=page.locator('body').inner_text(timeout=10000).lower()
        if page.locator('input[type="email"]:visible, input[type="file"]:visible').count():
            return None
        return next((phrase for phrase in CONFIRMATIONS if phrase in text),None)

    def submit(self,page,expected,mark_submitting):
        if self.signature(page)!=expected:
            raise Handoff('The form changed since preparation. Resume and review the updated form before submitting.')
        if self.confirmation(page):
            raise Handoff('A confirmation already appears on this page. Check status instead of submitting again.')
        # Submission is deliberately restricted to a single, unambiguous button.
        buttons=page.get_by_role('button',name=re.compile(r'^(submit application|send application|apply now|submit|başvur|başvuruyu gönder)$',re.I))
        visible=[buttons.nth(i) for i in range(buttons.count()) if buttons.nth(i).is_visible() and buttons.nth(i).is_enabled()]
        if len(visible)!=1:
            raise Handoff('Could not identify one unambiguous Submit application button. Complete this application manually.')
        legal = page.locator('body').inner_text().lower()
        if any(x in legal for x in ('by submitting','by clicking','terms of service','terms and conditions','göndererek','kabul etmiş')):
            raise Handoff('Submission includes an agreement. Read and submit it yourself in the browser, then check confirmation.')
        self.guard()
        mark_submitting()
        visible[0].click(timeout=15000)
        # Wait for actual confirmation, not merely navigation or disappearance of a button.
        try:
            page.wait_for_function('(phrases) => phrases.some(p => document.body.innerText.toLowerCase().includes(p))', arg=list(CONFIRMATIONS),timeout=20000)
        except Exception:
            raise Handoff('Submission result is uncertain. Check the existing application before retrying; automatic resubmission is disabled.')
        return self.confirmation(page)

    def screenshot(self,page,path):
        page.screenshot(path=str(path),full_page=True)

    def close(self):
        try:
            for context in (self.context,self.kariyer_context):
                if context:
                    try:context.close()
                    except Exception:pass
        except Exception:pass
        finally:
            try:
                if self.runtime:self.runtime.stop()
            except Exception:pass
            self.context=None
            self.kariyer_context=None
            self.runtime=None
            self.pages.clear()
            self.login_pages.clear()
