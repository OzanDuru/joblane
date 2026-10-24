function liveOverview(){
 const w=state.worker, a=state.ai;
 if(w.active_job){const job=state.jobs.find(j=>j.id===w.active_job);return {title:job?`${job.company} · ${job.title}`:`Başvuru #${w.active_job} işleniyor`,badge:'BAŞVURU İŞLENİYOR',detail:'Tarayıcı işlemi sürüyor. Sonuç başvuru geçmişine kaydedilecek.'};}
 if(a.active||a.runs.some(r=>['queued','running'].includes(r.status))){const run=a.runs.find(r=>r.id===a.active)||a.runs.find(r=>['queued','running'].includes(r.status));return {title:run?.kind==='discover'?'Yeni ilanlar aranıyor':run?.kind==='email'?'Başvuru e-postası hazırlanıyor':'İlana özel CV analiz ediliyor',badge:run?.status==='queued'?'GÖREV SIRADA':'AI ÇALIŞIYOR',detail:`Görev #${run.id} · ${run.journal?.at(-1)?.title||'Görev hazırlanıyor'}`};}
 if(state.security?.password_change_required)return {title:'Çalışma alanı şifreni değiştir',badge:'KURULUM BEKLİYOR',detail:'Başlatmadan önce ayarlardan kişisel şifreni belirle.'};
 if(!state.profile?.name||!state.profile?.email)return {title:'Ana profilini tamamla',badge:'PROFİL EKSİK',detail:'Başvurular için ad ve e-posta bilgilerini kaydet.'};
 if(w.paused)return {title:'Otomasyon duraklatıldı',badge:'DURAKLATILDI',detail:'Planlı işlemler devam ettirmeni bekliyor.'};
 if(!state.settings.enabled)return {title:'Çalışma planı kapalı',badge:'PLAN KAPALI',detail:state.setup?.profile_confirmed?'Profilin doğrulandı. Kayıtlı planı başlatarak devam edebilirsin.':'Kayıtlı profilini kontrol edip onaylayarak çalışma planını başlatabilirsin.'};
 if(!w.running)return {title:'Başvuru işleyicisi çalışmıyor',badge:'KONTROL GEREKİYOR',detail:'Plan açık ancak arka plan işleyicisi kapalı. Sunucuyu kontrol et.'};
 if(a.config.enabled&&!['ChatGPT','API key'].includes(a.runtime.auth))return {title:'Codex bağlantısını kontrol et',badge:'BAĞLANTI BEKLİYOR',detail:a.runtime.auth==='unchecked'?'Codex oturumu henüz doğrulanmadı. AI bölümünden bağlantıyı kontrol et.':'Codex oturumu kullanıma hazır değil. AI bölümündeki bağlantı durumunu kontrol et.'};
 if(!w.within_window)return {title:'Çalışma saati bekleniyor',badge:'PLAN AÇIK',detail:'Planlı işlemler kayıtlı gün ve saat aralığında devam edecek.'};
 const queued=state.jobs.filter(j=>j.status==='queued').length;
 return {title:queued?`${queued} başvuru sırada`:'Sıradaki ilan araması bekleniyor',badge:'ÇALIŞMA ARALIĞINDA',detail:a.config.enabled&&a.config.discovery_enabled?discoveryWaitText():'Planlı ilan arama kapalı; sıraya eklenen başvurular işlenebilir.'};
}
function discoveryWaitText(){
 const schedule=state.ai.schedule;
 if(!schedule)return 'Arama zamanını görmek için sayfayı yenile.';
 const when=schedule.next_at?new Date(schedule.next_at*1000).toLocaleString('tr-TR',{timeZone:state.settings.timezone,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'';
 const remaining=Math.max(0,Math.ceil((schedule.next_at-schedule.server_now)/60));
 if(schedule.reason==='paused')return 'Otomasyon duraklatıldı. Devam ettirene kadar yeni arama başlamaz.';
 if(schedule.reason==='disabled')return 'Planlı ilan arama kapalı. Çalışma planını ve AI keşif ayarlarını kontrol et.';
 if(schedule.reason==='setup')return 'Çalışma alanı şifresinin değiştirilmesi bekleniyor.';
 if(schedule.reason==='no_window')return 'Uygun çalışma günü veya saati bulunamadı. Plan ayarlarını kontrol et.';
 if(schedule.reason==='busy')return 'Çalışan AI görevinin bitmesi bekleniyor. Yeni planlı arama bundan sonra değerlendirilecek.';
 if(schedule.reason==='ready')return 'Arama zamanı geldi; planlayıcının görevi sıraya alması bekleniyor.';
 return `Son planlı denemeden itibaren ${state.ai.config.discovery_interval} dakikalık aralık uygulanıyor. Sonraki arama: ${when} · ${state.settings.timezone} (yaklaşık ${remaining} dakika).${schedule.reason==='window'?' Çalışma aralığının açılması bekleniyor.':''}`;
}
function liveFlowPanel(){
 const ai=state.ai;
 const active=ai.runs.find(r=>r.id===ai.active)||ai.runs.find(r=>['running','queued'].includes(r.status));
 const run=active||ai.runs[0];
 const events=run?.journal||[];
 const recent=events.slice(-6).reverse();
 const latest=events.at(-1);
 const canSearch=ai.config.enabled&&!state.worker.paused&&!state.security?.password_change_required&&!ai.runs.some(r=>r.kind==='discover'&&['queued','running'].includes(r.status));
 return `<section class="live-flow" id="live-flow"><div class="inline-heading"><h2>Canlı akış</h2><span class="pill">${active?'GÖREV #'+active.id+' · '+esc(aiStatusLabel(active.status)):'BEKLİYOR'}</span></div>
 <p>${esc(active?(latest?.title||'Görev sıraya alındı; ilk işlem bekleniyor.'):discoveryWaitText())}</p>
 ${active&&latest&&!latest.archived?`<p class="small muted">Son görev olayı: ${dates(latest.created)}. Yeni olay gelene kadar son doğrulanan adım gösterilir.</p>`:''}
 <div class="detail-actions"><button class="primary" data-ai-action="discover" ${canSearch?'':'disabled'}>Şimdi ilan ara ↗</button><button class="button" data-nav="ai">Tüm adımları ve kaynakları aç ↗</button></div>
 ${run?`<h3>${active?'Bu görevin son adımları':'Son görevin kayıtları'} · #${run.id} · ${esc(aiStatusLabel(run.status))}</h3>${!active?'<p class="small muted">Aşağıdaki kayıtlar geçmiş göreve ait; şu anda çalışan bir işlem değiller.</p>':''}
 <ol class="live-events">${recent.map(e=>`<li><div class="journal-meta"><span>${e.archived?'Eski kayıt · olay saati bilinmiyor':dates(e.created)}</span><span>${esc({running:'Başladı',completed:'Tamamlandı',failed:'Hata',cancelled:'İptal',interrupted:'Kesinti',skipped:'Atlandı'}[e.state]||e.state)}</span></div><strong>${esc(e.title)}</strong>${e.detail?`<pre>${esc(e.detail)}</pre>`:''}${e.data?.sources?.length?`<p class="small muted">${e.data.sources.length} kaynak kaydedildi. Bağlantıları tüm adımlar ekranından açabilirsin.</p>`:''}</li>`).join('')}</ol>`:'<p class="muted">Henüz görev kaydı yok. Arama başladığında sorgular, kaynak işlemleri ve sonuçlar burada görünecek.</p>'}
 <p class="small muted">Bu alan gerçek işlem kayıtlarını 5 saniyede bir yeniler; tarayıcının video yayını değildir.</p></section>`;
}
function scheduleSummary(){
 const s=state.settings, ai=state.ai.config;
 if(!s.enabled)return '<h3>Çalışma planı kapalı</h3><p>Planlı başvuru ve ilan arama çalışmıyor. Başlatmadan önce çalışma günlerini ve saatlerini ayarlayabilirsin.</p><button class="text-button" data-nav="settings">Çalışma planını ayarla ↗</button>';
 const days=s.days.length===7?'Her gün':s.days.map(d=>['Pzt','Sal','Çar','Per','Cum','Cmt','Paz'][d]).join(', ');
 const zone=s.timezone==='Europe/Istanbul'?'İstanbul saati':s.timezone;
 const discovery=ai.enabled&&ai.discovery_enabled?`${esc(ai.discovery_interval)} dakikada bir planlı ilan arama`:'Planlı ilan arama kapalı';
 return `<h3>${state.worker.paused?'Çalışma planı duraklatıldı':'Çalışma aralığı: '+esc(s.start)+'–'+esc(s.end)}</h3><p>${state.worker.paused?'Kayıtlı aralık: '+esc(s.start)+'–'+esc(s.end)+' · ':''}${esc(days||'Çalışma günü seçilmedi')} · ${esc(zone)} · ${esc(s.daily_limit)} planlı form denemesi/gün · ${discovery}.</p>${state.worker.paused?'<p>Devam ettirene kadar planlı işlemler çalışmaz.</p>':''}<button class="text-button" data-nav="settings">Çalışma planını düzenle ↗</button>`;
}
function homeView(){
 const live=liveOverview();
 return `${heading('İş arayışın','Tercihlerini seç. İlerlemeyi buradan izle; gerektiğinde soruları yanıtla.',false)}
 ${!state.setup?.profile_confirmed?'<section class="form-panel"><h2>Önce profilini tamamla</h2><p>CV ve iletişim bilgilerini bir kez doğrula.</p><button class="primary" data-nav="profile">Profilimi aç ↗</button></section>':''}
 ${searchFilterForm()}
 <section class="form-panel"><div class="inline-heading"><h2 id="live-status-title">${esc(live.title)}</h2><span class="pill" id="live-status-badge">${esc(live.badge)}</span></div><p id="live-status-detail">${esc(live.detail)}</p><p class="small muted" id="state-freshness">Son veri alımı: ${new Date(stateReceivedAt).toLocaleTimeString('tr-TR',{timeZone:'Europe/Istanbul'})}</p>${liveFlowPanel()}</section>
 <section class="form-panel" id="attention-cards">${attentionCards()}</section>
 <details class="form-panel"><summary>Çalışma saatleri ve bağlantılar</summary>${scheduleSummary()}<p>Codex: ${esc(state.ai.runtime.auth)} · Outlook: ${state.outlook.configured?'bağlı':'bağlanmadı'} · Telegram yanıtları: ${state.connection.telegram_replies==='connected'?'dinleniyor':state.connection.telegram_replies==='unavailable'?'bağlantı kontrolü gerekiyor':'henüz bağlanmadı'}</p><div class="detail-actions"><button class="button" data-nav="settings">Bağlantıları düzenle ↗</button><button class="button" data-nav="profile">Profilim ve CV ↗</button></div></details>`;
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('[data-flow-action]');if(!b)return;b.disabled=true;
 try{
  if(b.dataset.flowAction==='start')await api('/automation/start','POST',{confirmed:!!$('#confirm-start')?.checked});
  else if(b.dataset.flowAction==='test-alert'){const result=await api('/notifications/test','POST',{});toast(result.detail,!result.ok);}
  else if(['pause','resume'].includes(b.dataset.flowAction))await api('/worker','POST',{action:b.dataset.flowAction});
  await refresh();
 }catch(err){toast(err.message,true)}finally{b.disabled=false}
});

function siteSessionsPanel(){
 const sessions=state.site_sessions||{};
 const labels={not_configured:'Giriş yapılmadı',opening:'Tarayıcı açılıyor',login_open:'Doğrulama bekliyor',manual_login_open:'Normal Chrome’da giriş bekliyor',checking:'Kontrol ediliyor',verified:'✓ Oturum doğrulandı',login_required:'Giriş gerekli',verification_required:'Güvenlik adımı bekliyor',unverified:'Doğrulanamadı',user_confirmed:'Henüz doğrulanmadı',reopen_required:'Yeniden kontrol gerekli',error:'Kontrol hatası'};
 return `<section class="form-panel" id="site-sessions"><div class="inline-heading"><h2>Başvuru sitesi oturumları</h2><span class="pill">BU BİLGİSAYARDA</span></div><p>Girişi Joblane tarayıcısında tamamla, ardından oturumu doğrula. Oturum verisi bu bilgisayarın ayrı tarayıcı profilinde kalır; token kopyalamana gerek yok.</p><div class="two-col">${[['linkedin','LinkedIn'],['kariyer','Kariyer.net']].map(([id,name])=>{const s=sessions[id]||{status:'not_configured'};const busy=['opening','checking'].includes(s.status);const descriptions={not_configured:'Önce giriş sayfasını aç.',opening:'Giriş penceresi bilgisayarda açılıyor.',checking:'Oturum verisi ve giriş yapılmış hesap ekranı kontrol ediliyor.',login_open:'Girişi ve varsa ikinci doğrulama adımını tamamladıktan sonra kontrol et.',manual_login_open:'Açılan özel Chrome’da giriş yap. Sonra bu Chrome’u tamamen kapat (Mac: ⌘Q; Windows/Linux: tüm pencereleri kapat) ve Oturumu doğrula düğmesine bas. Günlük Chrome oturumun ayrı kalır.',user_confirmed:'Önceki onayın kaydedildi. Şimdi gerçek oturum kontrolü yapabilirsin.',reopen_required:'Sunucu yeniden başladı. Kayıtlı tarayıcı profilindeki oturumu yeniden doğrula.'};return `<div class="connection-card" data-site-card="${id}"><div class="status-line"><h3>${name}</h3><span role="status" class="pill ${s.status==='verified'?'submitted':['error','verification_required','login_required','unverified'].includes(s.status)?'needs_attention':''}">${esc(labels[s.status]||'Bilinmeyen durum')}</span></div><p>${esc(descriptions[s.status]||s.detail||'Giriş durumunu kontrol et.')}</p>${s.checked_at?`<p class="small muted">Son kontrol: ${dates(s.checked_at)}</p>`:''}${s.last_verified_at&&s.status!=='verified'?`<p class="small muted">Son başarılı doğrulama: ${dates(s.last_verified_at)}</p>`:''}<div class="detail-actions"><button type="button" class="button" data-site-session="${id}" data-session-action="open" ${busy?'disabled':''}>${name} girişini aç ↗</button>${!['not_configured','opening'].includes(s.status)?`<button type="button" class="${s.status==='verified'?'button':'primary'}" data-site-session="${id}" data-session-action="check" ${busy?'disabled':''}>${s.status==='checking'?'Kontrol ediliyor…':s.status==='verified'?'Oturumu yeniden kontrol et':'Oturumu doğrula'}</button>`:''}</div>${id==='kariyer'?'<p class="small muted">Giriş sırasında Chrome’a otomasyon bağlanmaz. Kapatınca Joblane aynı özel profili açıp hesabı kontrol eder. Güvenlik çerezleri hesap oturumu sayılmaz.</p>':''}<p class="small muted">Oturum doğrulaması, otomatik başvuru adaptörünün hazır olduğu anlamına gelmez.</p></div>`}).join('')}</div><div class="note">Giriş penceresi Joblane’in çalıştığı bilgisayarda açılır. Son kontrol yalnızca o andaki oturumu gösterir; sitenin oturum süresi dolduğunda tekrar giriş gerekebilir.</div></section>`;
}
function refreshSiteSessions(){const target=$('#site-sessions');if(!target)return;const template=document.createElement('template');template.innerHTML=siteSessionsPanel();const next=template.content.firstElementChild;if(target.innerHTML!==next.innerHTML)target.innerHTML=next.innerHTML}
document.addEventListener('click',async e=>{const b=e.target.closest('[data-site-session]');if(!b)return;b.disabled=true;try{await api('/site-sessions/'+b.dataset.siteSession,'POST',{action:b.dataset.sessionAction});await refresh(false);toast(b.dataset.sessionAction==='open'?'Giriş tarayıcısı bilgisayarda açılıyor.':'Oturum kontrolü başladı. Sonuç kartta görünecek.')}catch(err){toast(err.message,true)}finally{b.disabled=false}});
