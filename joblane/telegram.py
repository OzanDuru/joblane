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


def send(store,test=False):
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
    result=api(token,'sendMessage',{'chat_id':chat_id,'text':text,'protect_content':True})
    if result.get('chat',{}).get('id')!=chat_id or not result.get('message_id'):
        raise TelegramError('Telegram gönderim sonucu doğrulanamadı; otomatik tekrar denenmedi.')
    return 'Telegram mesajı kabul etti. Telefonundaki bildirimi kontrol et.'
