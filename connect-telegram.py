"""Pair a fresh, dedicated bot with one private chat. No token command-line arguments."""
import getpass
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from joblane.telegram import api, paired_chat, save_pair, TelegramError
from joblane.outlook import secure_keyring


def main():
    directory=Path(os.getenv('JOBLANE_DATA_DIR',str(Path(__file__).resolve().parent/'data'))).resolve()
    if not (directory/'joblane.sqlite3').exists():raise TelegramError('Önce Joblane’i kur.')
    secure_keyring()
    print('BotFather ile oluşturduğun yalnızca Joblane’e ait botu bağla.')
    print('Token gizli girilir; sohbete veya tarayıcı adres çubuğuna yapıştırma.')
    token=getpass.getpass('Bot token: ').strip()
    bot=api(token,'getMe')
    if not bot.get('is_bot') or not re.fullmatch(r'[A-Za-z0-9_]+',bot.get('username','')):
        raise TelegramError('Bot kimliği doğrulanamadı.')
    if api(token,'getWebhookInfo').get('url'):
        raise TelegramError('Bu botta başka bir webhook var. Joblane için yeni bir bot oluştur; mevcut bağlantıya dokunulmadı.')
    code='joblane_'+secrets.token_urlsafe(18);issued=int(time.time())
    print('\nKendi Telegram hesabında bu bağlantıyı aç ve Başlat / Start düğmesine bas:')
    print('https://t.me/'+bot['username']+'?start='+code)
    print('Bu eşleştirme bağlantısını paylaşma. 5 dakika bekleniyor. İptal: Ctrl+C.')
    deadline=time.monotonic()+300;offset=None
    while time.monotonic()<deadline:
        payload={'timeout':10,'allowed_updates':['message']}
        if offset is not None:payload['offset']=offset
        updates=api(token,'getUpdates',payload)
        match=paired_chat(updates,code,issued)
        if updates:offset=max(u['update_id'] for u in updates)+1
        if match:
            label=match.get('username') or match.get('first_name') or str(match['id'])
            print('Eşleşen kişisel hesap:',label)
            if input('Bildirimler bu hesaba gitsin mi? [e/H]: ').strip().lower() not in ('e','evet'):
                print('İptal edildi; mevcut ayarlar korunuyor.');return
            save_pair(directory,token,bot,match)
            print('Telegram bağlandı. Token sistem kasasına kaydedildi; mesaj gönderilmedi.')
            print('Joblane panelini yenile ve Ayarlar → Telefon bildirimini dene düğmesini kullan.')
            return
    raise TelegramError('Eşleştirme süresi doldu. Betiği tekrar çalıştır ve yeni bağlantıyı kullan.')


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nKurulum iptal edildi.')
    except TelegramError as exc:raise SystemExit(str(exc))
    except Exception:raise SystemExit('Kurulum tamamlanamadı. Sistem kimlik kasasını, bağımlılıkları ve bağlantıyı kontrol et.')
