"""Private, outbound Telegram alerts. Tokens stay in the native credential store."""
import hashlib
import json
import re
import secrets
import urllib.error
import urllib.request
from .outlook import secure_keyring


class TelegramError(ValueError):
    pass


def service(directory):
    return 'Joblane-Telegram-' + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:16]


def api(token, method, payload=None):
    if not isinstance(token,str) or not re.fullmatch(r'\d+:[A-Za-z0-9_-]{20,}',token):
        raise TelegramError('Telegram token biçimi geçersiz. BotFather token’ını kontrol et.')
    if method not in ('getMe','getWebhookInfo','getUpdates','getChat','sendMessage'):
        raise TelegramError('Desteklenmeyen Telegram işlemi.')
    req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,
        data=json.dumps(payload or {}).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            result=json.load(response)
        if not isinstance(result,dict) or result.get('ok') is not True:
            raise TelegramError('Telegram isteği kabul etmedi. Token ve bot bağlantısını kontrol et.')
        return result['result']
    except urllib.error.HTTPError as exc:
        # Never log the URL: it contains the bot credential.
        reason={401:'Bot token’ı geçersiz veya iptal edilmiş.',403:'Bot engellenmiş veya sohbete erişemiyor.',409:'Bot başka bir bağlantıda kullanılıyor.',429:'Telegram hız sınırına ulaşıldı.'}.get(exc.code,'Telegram isteği başarısız oldu.')
        raise TelegramError(reason+' Otomatik tekrar denenmedi.') from None
    except TelegramError:
        raise
    except Exception:
        raise TelegramError('Telegram bağlantı sonucu doğrulanamadı. Mesaj ulaşmış olabilir; otomatik tekrar denenmedi.') from None


def paired_chat(updates, code, issued):
    matches={}
    for update in updates:
        msg=update.get('message',{});chat=msg.get('chat',{});sender=msg.get('from',{})
        if (msg.get('text')=='/start '+code and msg.get('date',0)>=issued
            and chat.get('type')=='private' and type(chat.get('id')) is int and chat['id']>0
            and sender.get('id')==chat['id'] and sender.get('is_bot') is False):
            matches[chat['id']]=chat
    if len(matches)>1:raise TelegramError('Birden fazla eşleşme var. Kurulumu yeni kodla tekrar başlat.')
    return next(iter(matches.values()),None)


def status(store):
    config=store.get('telegram',{})
    chat=config.get('chat_id');bot=config.get('bot_id')
    return {'configured':type(chat) is int and chat>0 and type(bot) is int and bot>0,
            'bot_username':config.get('bot_username','')}


def save_pair(directory,token,bot,chat):
    import sqlite3
    if chat.get('type')!='private' or type(chat.get('id')) is not int or chat['id']<=0:
        raise TelegramError('Yalnızca kişisel Telegram sohbeti bağlanabilir.')
    # A unique key keeps the previous pair usable if saving the DB fails.
    credential=secrets.token_hex(16)
    ring=secure_keyring();ring.set_password(service(directory),credential,token)
    config={'chat_id':chat['id'],'bot_id':bot['id'],'bot_username':bot['username'],'credential':credential}
    try:
        with sqlite3.connect(directory/'joblane.sqlite3') as db:
            old=db.execute("SELECT value FROM config WHERE key='telegram'").fetchone()
            db.execute('INSERT OR REPLACE INTO config VALUES (?,?)',('telegram',json.dumps(config)))
    except Exception:
        ring.delete_password(service(directory),credential)
        raise TelegramError('Bağlantı kaydedilemedi.') from None
    if old:
        old_key=json.loads(old[0]).get('credential')
        if old_key:
            try:ring.delete_password(service(directory),old_key)
            except Exception:pass


def send(store,test=False,job_id=None):
    config=store.get('telegram',{})
    if not status(store)['configured']:raise TelegramError('Önce connect-telegram.py ile hesabını bağla.')
    try:token=secure_keyring().get_password(service(store.directory),config['credential'])
    except Exception:raise TelegramError('Telegram token’ı sistem kasasından okunamadı. Yerel bağlantıyı yenile.') from None
    if not token:raise TelegramError('Telegram token’ı bulunamadı. Bağlantıyı yenile.')
    chat_id=config['chat_id']
    chat=api(token,'getChat',{'chat_id':chat_id})
    if chat.get('type')!='private' or chat.get('id')!=chat_id:
        raise TelegramError('Hedef kişisel sohbet doğrulanamadı. Bildirim gönderilmedi.')
    text=('Joblane bildirim bağlantısı çalışıyor. Bu bir deneme mesajıdır.' if test else
          'Joblane’de ilgilenmen gereken bir durum var. Ayrıntılar için özel panelindeki “Senden beklenenler” ve AI görevlerini kontrol et.')
    if job_id and not test:
        job=store.job(job_id)
        text=f"Joblane · Başvuru #{job_id}\n{job['company']} · {job['title']}\n"
        with store.connect() as db:row=db.execute("SELECT id,result FROM ai_runs WHERE job_id=? AND status='completed' AND kind IN ('analyze','form') ORDER BY id DESC LIMIT 1",(job_id,)).fetchone()
        questions=json.loads(row[1]).get('questions',[]) if row and row[1] else []
        if store.get(f'source_check:{job_id}',{}).get('employment')=='Unknown':questions=[]
        text+=('\n'.join(f'{i+1}. {q}' for i,q in enumerate(questions[:1])) if questions else job['reason'])
        text+='\n\nBu mesaja Yanıtla ile cevap ver veya /yanit '+str(job_id)+' cevabın yaz. Yanıt yalnızca bu başvuruya kaydedilir.'
        import os
        private_url=os.getenv('JOBLANE_PUBLIC_URL','').rstrip('/')
        if private_url:text+='\nPanel: '+private_url+'/#job-'+str(job_id)
    result=api(token,'sendMessage',{'chat_id':chat_id,'text':text[:3900],'protect_content':True})
    if result.get('chat',{}).get('id')!=chat_id or not result.get('message_id'):
        raise TelegramError('Telegram gönderim sonucu doğrulanamadı; otomatik tekrar denenmedi.')
    if job_id and not test:store.set('telegram_message:'+str(result['message_id']),{'job_id':job_id,'run_id':row[0] if row else None})
    return 'Telegram mesajı kabul etti. Telefonundaki bildirimi kontrol et.'


class ReplyListener:
    """Only the paired private user may answer a specific application's question."""
    def __init__(self,store,answer):
        import threading
        self.store=store;self.answer=answer
        self.stop_event=threading.Event();self.thread=None
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS telegram_inbox (id INTEGER PRIMARY KEY, state TEXT NOT NULL)')

    def start(self):
        import threading
        self.thread=threading.Thread(target=self.loop,name='joblane-telegram-replies',daemon=True)
        self.thread.start()

    def handle(self,update):
        config=self.store.get('telegram',{})
        msg=update.get('message',{});chat=msg.get('chat',{});sender=msg.get('from',{})
        if (chat.get('id')!=config.get('chat_id') or chat.get('type')!='private'
            or sender.get('id')!=config.get('chat_id') or sender.get('is_bot') is not False):return None
        text=msg.get('text','')
        if not isinstance(text,str) or not text.strip() or text.startswith('/start'):return None
        match=re.fullmatch(r'/yanit(?:@\w+)?\s+(\d+)\s+([\s\S]+)',text)
        mapping=self.store.get('telegram_message:'+str(msg.get('reply_to_message',{}).get('message_id')))
        job_id=int(match[1]) if match else mapping.get('job_id') if isinstance(mapping,dict) else mapping
        if not job_id:return 'Yanıtını ilgili Joblane mesajına Yanıtla ile gönder veya /yanit BAŞVURU_NO cevabın yaz. Panelde de yanıtlayabilirsin.'
        update_id=update.get('update_id')
        if type(update_id) is not int:return None
        with self.store.connect() as db:
            added=db.execute("INSERT OR IGNORE INTO telegram_inbox VALUES (?,'processing')",(update_id,)).rowcount
        if not added:return None
        try:
            result=self.answer(job_id,match[2] if match else text,source='telegram',question_run=mapping.get('run_id') if isinstance(mapping,dict) and not match else None)
            state='completed';reply=f"Başvuru #{job_id}: "+result['detail']
        except ValueError as exc:
            state='rejected';reply=f'Başvuru #{job_id}: '+str(exc)
        except Exception:
            state='uncertain';reply=f'Başvuru #{job_id}: Yanıt işleme sonucu doğrulanamadı. Tekrar göndermeden önce panelde kontrol et.'
        with self.store.connect() as db:db.execute('UPDATE telegram_inbox SET state=? WHERE id=?',(state,update_id))
        return reply

    def poll(self):
        config=self.store.get('telegram',{})
        if not status(self.store)['configured']:return
        token=secure_keyring().get_password(service(self.store.directory),config['credential'])
        cursor_key='telegram_cursor:'+str(config['bot_id'])+':'+str(config['chat_id'])
        offset=self.store.get(cursor_key)
        updates=api(token,'getUpdates',{'offset':offset if offset is not None else -1,'timeout':0,'allowed_updates':['message']})
        for update in updates:
            if offset is not None:
                reply=self.handle(update)
                if reply:
                    api(token,'sendMessage',{'chat_id':config['chat_id'],'text':reply[:3500],'protect_content':True})
            # First poll deliberately discards old chat messages, never executes them.
            if type(update.get('update_id')) is int:self.store.set(cursor_key,update['update_id']+1)
        if offset is None and not updates:self.store.set(cursor_key,0)
        self.store.set('telegram_reply_status','connected')

    def loop(self):
        while not self.stop_event.is_set():
            try:self.poll()
            except Exception:self.store.set('telegram_reply_status','unavailable')
            self.stop_event.wait(5)
