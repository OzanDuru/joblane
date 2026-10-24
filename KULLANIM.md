# Joblane — kişisel kullanım rehberi

24 Ekim 2026 · v0.4 · Mac · Europe/Istanbul

## Şu an ne hazır?

Ana CV profilin korundu. Başvurular, e-posta taslakları, CV sürümleri, AI görevleri, ekran görüntüleri ve işlem geçmişi sıfırlandı. Deneme düğmeleri ve yerel deneme formu kaldırıldı. Temizlik öncesi veriler uygulamanın dışında, `../../work/joblane-backups/` altında özel yedekte duruyor. Orijinal PDF dosyana dokunulmadı.

Codex CLI kurulu. Outlook hesabı, telefondan erişim ve telefon bildirimleri henüz bağlı değil. Zamanlayıcı kapalı; program sen başlatmadan ilan aramıyor veya başvuru göndermiyor.

**Bu sürümde ilan keşfi, analiz ve CV hazırlığı otomatikleşir. Bütün sitelerde uçtan uca otomatik başvuru henüz yok.** İlk şirket başvuruları inceleme ister; LinkedIn/Kariyer.net doğrudan gönderimleri ve desteklenmeyen formlar elle tamamlanır. E-postalar gönderilmeden önce onay ister. Bu sınırlar canlı kullanımda da geçerlidir.

## 1. İlk kurulumda senin yapacakların

1. Panelde **Schedule & settings → Workspace password** bölümünde mevcut kurulum parolanı, yalnızca senin bildiğin en az 12 karakterli yeni bir parolayla değiştir. Bu adım bitmeden canlı işlemler açılmaz. Yeni parolayı sohbetten paylaşma. Diğer açık panel oturumları kapanır.
2. **My profile & CV** bölümünde ana profilini kontrol et. GitHub/LinkedIn/portfolyo bağlantıları şu anda boş; gerçek adreslerini ekle. **Answers & skill levels I have confirmed** alanına çalışma izni, çalışma şekli, taşınma, başlayabileceğin tarih, dil ve beceri seviyeleri gibi doğrulanmış cevaplarını yaz. Bilinmeyen koşullar için kesin cevap uydurulmaz.
3. Yeni CV kullanacaksan **CV yükle veya güncelle** alanından PDF yükle, **Extract CV text** ile metni al, profil alanlarını kontrol ederek güncelle ve **Save master profile** ile kaydet. Mevcut PDF içe aktarma metin çıkarır; alanları kendiliğinden doldurmaz. Mevcut profilin zaten kayıtlı olduğundan yeniden yüklemek zorunda değilsin.
4. **AI & discovery → Check local connection** ile Codex oturumunu kontrol et. Giriş görünmüyorsa aşağıdaki CLI adımlarını kullan.
5. E-posta başvurusu istiyorsan Outlook’u bağla. Bilgisayardan uzaktayken kullanmak istiyorsan Tailscale ve telefon bildirimlerini kur. Bunlar kurulmadan da yerel ilan keşfi ve CV hazırlığı çalışır.
6. Ana ekranda profil ve Codex kullanım onayını işaretle, **Otomasyonu başlat** düğmesine bas. Bu düğme ilan keşfini, analizi, CV hazırlığını ve zamanlayıcıyı açar. Dışarıya gönderim kurallarını değiştirmez. Saat aralığı dışındaysan ilk çalışma sonraki pencereye kalır.

## 2. Günlük başlatma ve durdurma

Terminal:

```sh
cd /Users/ozanduru/Documents/Codex/2026-10-24/v/outputs/joblane
./start-joblane
```

Alternatif: **Start Joblane.command** dosyasına çift tıkla. Yerel panel: **http://127.0.0.1:8765/**. HTML dosyasını doğrudan açma.

Terminali açık tut. Zamanlayıcı ayarın kaydedilir; uygulama tekrar açılınca etkinse çalışma saatinde devam eder. Yeni işleri durdurmak için panelde **Pause all / Otomasyonu duraklat**, sunucuyu kapatmak için onu çalıştırdığın terminalde **Ctrl+C** kullan. Önce aktif işlemin bitmesini bekle. Gönderilmiş ağ istekleri duraklatmayla geri alınmaz.

Mac’in boşta uyumasını çalıştığın oturum boyunca engellemek için mevcut sunucuyu durdurduktan sonra:

```sh
caffeinate -i ./start-joblane
```

Mac açık, internete bağlı ve kullanıcı oturumu açık olmalı. Kapak kapatılınca çalışma garanti edilmez. Joblane henüz Mac açılışında kendiliğinden başlayan bir sistem servisi değildir. Tailscale açık olması tek başına Joblane’i başlatmaz.

## 3. Otomasyon nasıl ilerler?

Varsayılan pencere **15:00–20:00 İstanbul**, her gün; keşif aralığı **120 dakika**, günlük planlı form denemesi sınırı **10**. Filtreler boş. Bunları **Schedule & settings** ve **AI & discovery** içinde değiştirebilirsin.

- Joblane çalışma penceresinde ilan arar; her aramada en fazla altı kaynaklı ilan ister. Aynı normalize URL tekrar eklenmez. Tüm interneti taradığı veya ilanın hâlâ açık olduğu garanti edilmez.
- Yeni ilanı profilinle analiz eder, ilgili özeti/proje ifadelerini kullanarak ayrı PDF hazırlar. Ana profilin değişmez.
- Eksik bilgi veya AI inceleme gereksinimi varsa başvuru **Needs you** durumuna gelir. Bildirim kurulmuşsa tek bildirim denemesi yapılır. AI hataları ve tarayıcı engelleri de bildirim üretir.
- İlk gönderimler için başvuruyu açıp CV’yi kontrol edersin. Uygun şirket formunda paylaşım onayını verip **Fill now** veya **Queue for schedule** kullanırsın. Form dolunca ekran görüntüsünü inceleyip **Submit reviewed application** ile gönderirsin.
- **Automatic on qualified company domains** seçildiğinde yalnızca açıkça yetkilendirdiğin tam şirket alan adları kullanılabilir. Aynı alanda beş incelenmiş ve tarayıcı tarafından doğrulanmış başvuru gerekir. AI inceleme istemiyorsa ve form destekleniyorsa sonraki başvurular otomatik ilerleyebilir. Yeni bir alan adı bu yetkiyi devralmaz.
- LinkedIn/Kariyer.net doğrudan gönderimleri, çok adımlı/özel formlar ve bilinmeyen zorunlu sorular müdahale gerektirebilir. Uygunsa şirketin kendi başvuru bağlantısını kullan.

**Find jobs now** ve **Fill now** tek seferlik açık talimatlardır; çalışma penceresi dışında da çalışabilir. Günlük sınır planlı form denemelerine uygulanır; AI kullanım kotası veya e-posta limiti değildir. CV’nin bire bir uygunluğu ya da işe alınma garantisi yoktur.

## 4. Codex CLI kullanımı

CLI’ı ayrıca açık tutman gerekmez. Python sunucusu işi alınca CLI’ı başlatır; sonuç gelince süreç çıkar. Başvuruya ait oturum kimliği saklanır. **Continue this session** aynı başvurunun oturumunda yeni talimat vermek içindir. **AI task history** durumları gösterir.

Joblane’ın yerel kurulumu `.tools` içindedir; global `codex` sürümünden ayrıdır. Kurulumu veya girişi yenilemek için:

```sh
.venv/bin/python setup-codex.py
```

Panelden tekrar bağlantı kontrolü yap. ChatGPT oturumuyla abonelik erişimi ve API anahtarıyla ücretlendirme ayrı giriş yollarıdır; mevcut kurulum kayıtlı CLI girişini kullanır. Kullanım sınırı veya oturum sorunu oluşursa iş durur ve hata kaydedilir. [OpenAI resmi giriş belgesi](https://learn.chatgpt.com/docs/auth)

Telefon paneli ChatGPT uygulamasına ihtiyaç duymaz. Ancak aynı ChatGPT hesabını başka biriyle paylaşmak ayrı bir gizlilik sınırı değildir; CLI girişini, işletim sistemi hesabını ve uzaktan erişim hesaplarını yalnızca kendi kontrolünde tut.

## 5. Outlook’u bir kez bağlama

Microsoft Graph üzerinden gönderim için kendi Microsoft uygulama kaydın gerekir. Outlook masaüstü uygulamasının açık olması gerekmez.

1. [Microsoft Entra](https://entra.microsoft.com/) içinde **App registrations → New registration** aç. Ad: `Joblane Personal`.
2. Hesap türü: **Accounts in any organizational directory and personal Microsoft accounts**.
3. **Authentication → Add a platform → Mobile and desktop applications** altında redirect URI: `http://localhost`.
4. **API permissions → Microsoft Graph → Delegated permissions → Mail.Send** ekle. **Client secret oluşturma.** Kurumsal hesap politikası yönetici onayı isteyebilir.
5. **Application (client) ID** değerini al ve Joblane klasöründe çalıştır:

```sh
.venv/bin/python -m pip install -r requirements-outlook.txt
.venv/bin/python connect-outlook.py
```

Client ID’yi terminale gir, açılan Microsoft sayfasında başvuruları göndereceğin kendi Outlook hesabını seç ve izinleri incele. Parola ve token’ı buraya yapıştırma. Token’lar sistemin kimlik bilgisi kasasında saklanır. Paneli yenilediğinde bağlı hesap görünmeli. Entra kaydı oluşturamıyorsan doğrudan gönderim kurulamaz; `.eml` ve CV indirme kullanılabilir. [Uygulama kaydı](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app), [Mail.Send izni](https://learn.microsoft.com/en-us/graph/permissions-reference#mail-send)

Başvuruda **Outlook application email** bölümünü aç. İlan için **Advertised role**, açık ilan doğrulanmamış şirkete yazmak için **General / speculative application** seç. Dili seçip **Draft naturally with Codex** kullan. Şirketin yayımladığı işe alım adresini gir; konu, gövde ve CV’yi incele. **Save draft + CV attachment**, ardından **Send reviewed email** kullan. Taslak üretmek veya kaydetmek gönderim yapmaz.

**Outlook accepted**, Microsoft’un isteği kabul ettiğini gösterir; alıcıya teslim garantisi değildir. **Sent Items / Gönderilmiş Öğeler** içinde kontrol et. **Uncertain** durumunda kontrol etmeden yeniden gönderme. Gelen cevapları okumak bu sürümde yok. [Microsoft sendMail davranışı](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)

## 6. Tailscale ile telefondan panel

1. [Tailscale’i](https://tailscale.com/download) Mac’e ve telefonuna kur. Yalnızca kontrol ettiğin hesapla giriş yap. Ağ/VPN izinlerini cihaz üzerinde tamamla.
2. Mac sürümünde CLI entegrasyonunu aç. Terminalde:

```sh
tailscale status
tailscale serve --bg http://127.0.0.1:8765
tailscale serve status
```

`tailscale` komutu bulunmazsa uygulamanın CLI entegrasyonunu kur veya şu tam yolu kullan:

```sh
/Applications/Tailscale.app/Contents/MacOS/Tailscale status
```

3. Çıktıdaki gerçek HTTPS adresini al. Joblane klasöründe `config.example.sh` dosyasını `config.local.sh` adıyla kopyala; şu satırı kendi gerçek adresinle ekle:

```sh
export JOBLANE_PUBLIC_URL='https://MAKINE.TAILNET.ts.net'
```

Örnek adresi aynen kullanma. `./start-joblane` bu dosyayı her açılışta yükler. Ayarı değiştirdikten sonra sunucuyu yeniden başlat. HTTPS ayarı açıkken Mac’te de aynı HTTPS adresini kullan; oturum çerezleri HTTPS ister.

4. Telefonda Tailscale’i aç; Safari/Chrome’da özel HTTPS adresini ziyaret edip Joblane parolanla giriş yap. Mobil internetten de dene. İstersen ana ekrana ekle.

Serve, tailnet içinden erişim sağlar; Funnel açma. Paylaşımı kapatmak için `tailscale serve off`. `--bg`, Tailscale paylaşımını sürdürür; Python sunucusunu veya Mac’i uyanık tutmaz. [Tailscale Serve belgesi](https://tailscale.com/docs/reference/tailscale-cli/serve)

## 7. Telegram ile kritik bildirimler

Pushover zorunlu değil. Joblane, Telegram bağlandıysa Telegram’ı kullanır; başarısızlıkta başka bir hesaba veya kanala otomatik geçmez. Başlangıç için yalnızca Joblane’e ait yeni bir bot oluştur.

1. Telegram’da resmi [@BotFather](https://t.me/BotFather) sohbetini aç ve `/newbot` gönder.
2. Görünen ad olarak `Joblane` yaz. Kullanıcı adı benzersiz olmalı ve `bot` ile bitmeli; örneğin kullanılabiliyorsa `ozan_joblane_alert_bot`.
3. BotFather’ın verdiği token’ı gizli tut; sohbetimize, tarayıcı adres çubuğuna veya komut satırının içine yapıştırma.
4. Mac’te yeni terminalde Joblane klasörüne geçip çalıştır:

```sh
.venv/bin/python -m pip install -r requirements-telegram.txt
.venv/bin/python connect-telegram.py
```

`Bot token:` sorulduğunda token’ı terminale yapıştır. Yazı görünmez. Betik botu doğrular, tek kullanımlık eşleştirme bağlantısı gösterir. Bu bağlantıyı kendi Telegram hesabında açıp **Başlat / Start** düğmesine bas. Beş dakika içinde eşleştirme yapılır. Terminalde görünen hesabın sana ait olduğunu kontrol edip `e` ile onayla. Yalnızca kişisel sohbet kabul edilir; rastgele gelen `/start` mesajları veya gruplar eşleşmez. Bağlantı başarısızsa eski ayar korunur. Başka bir webhook’u olan botu betik değiştirmez.

Token Mac Keychain / desteklenen işletim sistemi kasasında saklanır. Veri tabanına yalnızca bağlantı bilgileri kaydedilir; Joblane API’si token’ı döndürmez. Kurulum betiği bildirim göndermez. Bu güncellemeden önce açılmış Joblane’i bir kez yeniden başlat; bundan sonraki hesap eşleştirmelerinde paneli yenilemek yeterlidir.

5. Panelde **Schedule & settings → Telefon bildirimini dene** düğmesine bas. Telegram sohbetinde mesajı ve iPhone bildirimini kontrol et. “Telegram kabul etti” telefonun bildirimi gösterdiğinin garantisi değildir; Telegram ve iOS bildirim izinleri açık olmalı.

Eksik cevap, ilk başvuru incelemesi, AI hatası ve tarayıcı engelinde genel bir uyarı gönderilir; CV, şirket adı, form yanıtları veya hata ayrıntıları gönderilmez. Ayrıntıları Tailscale üzerinden özel panelde açarsın. Telegram aynı hesabının açık olduğu diğer cihazlarda da görünebilir; sadece sana ait bir hesap kullan. Bot şu anda bildirim içindir; Telegram mesajlarıyla başvuru başlatma veya onaylama komutları çalışmaz. Eşleştirme bittikten sonra sürekli mesaj okuma veya herkese açık webhook gerekmez.

Botu engellersen veya token’ı BotFather’dan iptal edersen sonraki bildirim başarısızlığı panelde kaydedilir. Yeniden bağlamak için betiği tekrar çalıştır. Token kayıp/iptal olduğunda otomatik yeniden gönderim yapılmaz.

Pushover eski yapılandırması da desteklenir; Telegram bağlıysa öncelik Telegram’dadır. [Telegram bot oluşturma](https://core.telegram.org/bots/tutorial), [Bot API](https://core.telegram.org/bots/api).

## 8. Bir işlem takıldığında

Ana ekrandaki **Senden beklenenler** veya başvurudaki **Needs you** alanını aç. Eksik cevapları ana profile eklediğinde ilgili CV’yi yeniden analiz et; önceki onaylar geçersizleşir.

Giriş, CAPTCHA veya tarayıcı doğrulaması için **Pause all** kullan. Panel uzak masaüstü sağlamaz; ayrıca kurduğun uzak masaüstü bağlantısıyla Joblane’ın mevcut Chromium sekmesini açıp adımı tamamla. Ardından worker’ı ve başvurudaki **Resume after my fix** akışını devam ettir. Tailscale tek başına ekran kontrolü değildir.

Gönderim sonucu belirsizse **Check confirmation** kullan; gerekirse işverenin başvuru geçmişini kontrol et ve **I applied myself** üzerinden aldığın teyidi kaydet. Körlemesine tekrar gönderme. Manuel kayıtlar otomatik alan adı yeterliliğine sayılmaz.

## 9. Geçmiş, yedek ve parola kurtarma

**History & files**, üretilen CV sürümlerini, gönderim anındaki sabit eki ve e-posta metnini indirilebilir tutar. Başka bir CV’yi değiştirmek eski kaydı değiştirmez. Şu anda geçmiş bilerek boştur.

Yedek almak için aktif işleri bitir, sunucuyu durdur ve `data/` klasörünün tamamını kendi özel yedeğine kopyala. Veri tabanı, CV’ler ve tarayıcı oturumu bu klasördedir. `config.local.sh` dosyasını da özel tut. Outlook token kasası ayrı olduğundan başka bilgisayarda yeniden giriş gerekir. Mevcut veri tabanında dosya yolları mutlak olduğundan başka klasöre/Windows’a taşımak yalnızca klasör kopyalamakla tamamlanmaz; yolların taşınması da gerekir.

Panel parolasını unuttuğunda, sunucuyu durdurup:

```sh
.venv/bin/python run.py reset-password
./start-joblane
```

Bu işlem başvuruları silmez; eski panel oturumlarını geçersizleştirir.

## Görünüm, işlem günlüğü ve oturum hazırlığı

- Üst çubuktaki **Görünüm → Açık / Koyu / Sistem** seçimi tarayıcıda saklanır. Açık veya Koyu seçildiğinde sistem teması seçimi değiştirmez. Her cihaz ve tarayıcı kendi tercihini tutar.
- Kartlar, formlar, düğmeler ve mobil görünüm ortak boşluk ve renk kurallarını kullanır. Yeni sürüm için açık sayfayı yenile.
- **AI ve ilan keşfi → AI görevleri ve işlem günlüğü → Playbook**: sıra, hazırlık, gerçek web sorguları, kaynak başlıkları/bağlantıları, sonuç doğrulaması, eklenen/atlanan ilanlar ve CV dosyası adımları görünür. Bir görev için son 80 olay gösterilir. CLI’ın bildirmediği ayrıntılar tahmin edilmez. Eski CLI olaylarının gerçek zamanı bulunmadığında bu açıkça yazılır.
- **Yalnızca bu görevi iptal et** genel planı kapatmaz. İptal Telegram uyarısı göndermez. **Tüm otomasyonu duraklat** planlı çalışmayı duraklatır ve aktif AI görevini iptal eder; düğme **Otomasyonu devam ettir** olur. Devam ettirmek iptal edilen görevi tekrar çalıştırmaz.
- **Plan ve ayarlar → Başvuru sitesi oturumları** içinden LinkedIn veya Kariyer.net girişini aç. Tarayıcı Joblane’in çalıştığı bilgisayarda açılır. Girişi, iki aşamalı doğrulamayı ve gerekiyorsa tarayıcı doğrulamasını bu pencerede tamamla; sonra **Oturumu doğrula** düğmesine bas.
- LinkedIn oturumu `data/browser-profile`, Kariyer.net oturumu normal Google Chrome için ayrılmış `data/browser-profile-kariyer-native` profilinde kalır. Kariyer.net için bilgisayarda Google Chrome kurulu olmalıdır. Eski test tarayıcısı profili taşınmaz; yeni Chrome profilinde ilk giriş yeniden yapılır. Profil klasörünü başka kişilerle paylaşma. Mac/Linux üzerinde klasör erişimi kullanıcıya özel tutulur. Şifre ve token panele veya sohbete yapıştırılmaz.
- Oturumu doğrula, sayfayı yenileyerek hesap kontrollerini ve yerel oturum verisini denetler. Yeşil durum ve son kontrol zamanı gösterilir; kullanıcı beyanı tek başına doğrulama sayılmaz. Oturumun sonradan süresi dolabilir. Oturum hazırlığı LinkedIn/Kariyer.net otomatik gönderim desteğinin tamamlandığı anlamına gelmez. Bu platformlarda gerçek form akışı ayrıca uygulanıp doğrulanmalıdır. Desteklenmeyen formlar ve doğrulama engelleri kullanıcıya devredilir.

Başarılı oturum doğrulamasından sonra ilgili giriş sekmesi otomatik kapanır. Başka giriş/başvuru sekmesi yoksa Joblane tarayıcısı tamamen kapanır; kalıcı profil korunur. Giriş veya güvenlik adımı eksikse pencere açık kalır.

Kariyer.net için genel HttpOnly veya bot doğrulama çerezleri hesap oturumu kanıtı değildir. Başarılı durum yalnızca yenilenmiş hesap sayfasındaki görünür hesap kontrolüyle gösterilir. Bilinmeyen oturum verisi için “bulundu/bulunamadı” tahmini yapılmaz. Chrome uyumluluk seçimi güvenlik doğrulamasını geçme garantisi vermez.

### Kariyer.net: normal Chrome ile giriş

1. **Plan ve ayarlar → Kariyer.net girişini aç** düğmesine bas.
2. Açılan ayrı Chrome’da giriş yap. Bu aşamada Playwright/otomasyon veya sayfa isteği filtreleme çalışmaz. Günlük Chrome profilin kullanılmaz; oradaki açık oturumun kopyalanmaz.
3. Girişten sonra yalnızca bu özel Chrome’u tamamen kapat. Mac’te bu pencere öndeyken **⌘Q**; Windows/Linux’ta bu özel profilin tüm pencerelerini kapat. Mac’te yalnızca pencerenin kırmızı düğmesi işlemi sonlandırmayabilir.
4. Panelde **Oturumu doğrula** düğmesine bas. Joblane aynı profili otomasyon tarayıcısında açıp hesabı denetler. Manuel pencere hâlâ açıksa bekler; başarı varsaymaz.
5. Hesap doğrulanırsa giriş tarayıcısı kapanır. Güvenlik hizmeti tekrar engellerse durum panelde gösterilir; bu yöntem sonraki otomatik işlemlerin kabul edileceğini garanti etmez.

Eski `browser-profile-kariyer-chrome` profili silinmez. Yeni akış farklı, kalıcı bir profil kullanır. Joblane yeniden başlatılırken elle açılmış Chrome kapatılmaz; doğrulamadan önce özel Chrome’dan çıkış yapmalısın (Kariyer.net hesabından çıkış yapma).
