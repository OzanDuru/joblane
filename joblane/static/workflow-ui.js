let attentionJobId=null;
function searchFilterForm(){
 const f=state.ai.config.search_filters||{geography:'turkey_first',sources:['linkedin','kariyer','company'],work_mode:'any',roles:''};
 return `<form id="search-scope-form" class="form-panel"><div class="inline-heading"><h2>Nasıl bir iş arayalım?</h2><span class="small muted">Bir kez seç; gerektiğinde değiştir.</span></div><div class="two-col"><label>Konum<select name="geography">${[['turkey_first','Türkiye öncelikli, yurt dışı dahil'],['turkey','Yalnızca Türkiye'],['abroad','Yalnızca yurt dışı'],['worldwide','Tüm dünya']].map(([v,t])=>`<option value="${v}" ${f.geography===v?'selected':''}>${t}</option>`).join('')}</select></label><label>Çalışma şekli<select name="work_mode">${[['any','Uzaktan, hibrit veya ofis'],['remote','Uzaktan'],['hybrid','Hibrit'],['office','Ofis']].map(([v,t])=>`<option value="${v}" ${f.work_mode===v?'selected':''}>${t}</option>`).join('')}</select></label></div>${input('Pozisyonlar (boş bırakırsan kayıtlı arama hedefin kullanılır)','roles',f.roles)}<div class="source-options">${[['linkedin','LinkedIn'],['kariyer','Kariyer.net'],['company','Şirket kariyer sayfaları']].map(([v,t])=>`<label class="check-label"><input type="checkbox" name="source" value="${v}" ${f.sources.includes(v)?'checked':''}> ${t}</label>`).join('')}</div><label class="check-label"><input type="checkbox" name="auto_fill" ${state.ai.config.auto_fill?'checked':''}> Bilgiler yeterliyse profilim ve ilana özel PDF ile desteklenen şirket formlarını otomatik doldur.</label><p class="small muted">LinkedIn ve Kariyer.net şu anda ilan kaynağıdır; bu sitelerde otomatik gönderim henüz desteklenmiyor. İlk form gönderimi ve e-posta gönderimi inceleme bekler.</p>${!state.setup?.profile_confirmed?'<label class="check-label"><input type="checkbox" name="confirm_profile"> Profilimi doğruladım; kariyer bilgilerimin Codex ile işlenmesini onaylıyorum.</label>':''}<div class="detail-actions"><button type="submit" class="primary">${state.settings.enabled&&!state.worker.paused?'Tercihleri kaydet ve yeni arama başlat ↗':'Bu filtrelerle şimdi başlat ↗'}</button><button type="button" class="button" data-save-scope>Yalnızca tercihleri kaydet</button></div><p data-save-status class="small muted" role="status">Başlat: ilk aramayı hemen yapar; sonraki işlemler kayıtlı çalışma saatlerine uyar.</p></form>`;
}
function jobHealth(job){
 const check=job.source_check||{};
 const stale=!check.posting_status||!check.checked_at||Date.now()-Date.parse(check.checked_at)>86400000;
 const status={open:'Son kontrolde açık',closed:'İlan kapalı',unknown:'Açıklığı doğrulanamadı'}[check.posting_status]||'Henüz kontrol edilmedi';
 const deadline=check.deadline?(check.deadline.length===10?check.deadline+' · saat belirtilmemiş':dates(check.deadline)+' · İstanbul saati'):'Kaynakta doğrulanmış son tarih yok';
 return `<div class="job-health"><div class="status-line"><span class="pill">${esc(status)}</span>${stale?'<span class="small muted">Güncellik kontrolü gerekiyor</span>':''}</div><p><strong>Son başvuru:</strong> ${esc(deadline)}${check.opens_on?`<br><strong>Başlangıç:</strong> ${esc(check.opens_on)}`:''}</p><p class="small muted">Son kaynak kontrolü: ${check.checked_at?dates(check.checked_at):'henüz yapılmadı'}. Bekleyen ilanlar çalışma saatlerinde kontrol edilir; 24 saatten eski bilgiyle form doldurulmaz.</p></div>`;
}
function answerBox(job){
 const latest=state.ai.runs.find(r=>r.job_id===job.id&&['analyze','form'].includes(r.kind)&&r.status==='completed');
 const questions=latest?.result?.questions||[];
 if(job.reason?.includes('Employment type is not confirmed')||job.source_check?.employment==='Unknown')return `<div class="answer-box"><p>İstihdam türünü ilan kaynağından sistem kontrol etmeli. Senden bilgi girmen gerekmiyor.</p>${job.source_check?.limitation?`<p class="small muted">${esc(job.source_check.limitation)}</p>`:''}<button class="button" data-verify-source="${job.id}">Kaynak kontrolünü yeniden dene ↗</button></div>`;
 const busy=state.ai.runs.some(r=>r.job_id===job.id&&['running','queued'].includes(r.status));
 if(!questions.length&&job.status==='needs_attention'&&job.reason?.startsWith('CV inceleme bekliyor:'))return `<div class="answer-box"><h3>İlk paylaşım için CV onayın gerekiyor</h3><p>${esc(latest?.result?.assessment||job.reason)}</p><p>Yeni bir bilgi istenmiyor. Bu başvuruya ait CV’yi kontrol ettikten sonra ${esc(job.domain)} üzerindeki formun hazırlanmasına izin verebilirsin. Bu düğme başvuruyu göndermez.</p><div class="detail-actions"><a class="button" href="/api/jobs/${job.id}/cv" target="_blank" rel="noopener">Hazırlanan PDF’yi aç ↗</a><button class="primary" data-approve-preparation="${job.id}">CV’yi onayla, formu doldur ↗</button></div></div>`;

 return `<div class="answer-box" data-answer-box="${job.id}" data-question-run="${latest?.id||''}">${questions.length?`<ol>${questions.slice(0,1).map(q=>`<li>${esc(q)}</li>`).join('')}</ol>`:`<p>${esc(latest?.result?.assessment||job.reason)}</p>${latest?.result?.next_step?`<p class="small muted">${esc(latest.result.next_step)}</p>`:''}<p class="small muted">Bu adımda yanıtlaman gereken bir soru yok.</p>${!job.source_check&&latest?.result?.requires_review?`<button class="button" data-verify-source="${job.id}">İlan koşullarını sistem kontrol etsin ↗</button>`:''}`}${job.status==='needs_attention'&&questions.length?`<label>Yanıtın<textarea data-answer-text="${job.id}" rows="3" placeholder="Tek mesajda yanıtla; AI ilgili başvuruda devam etsin." ></textarea></label><p class="small muted">Yanıtın bu sorunun bağlamıyla saklanır; aynı bilgi tekrar gerekirse kullanılır.</p><button class="primary" data-answer-submit="${job.id}">Yanıtla ve devam et ↗</button>`:''}${job.answers?.length?`<details><summary>Kaydedilen yanıtlar (${job.answers.length})</summary>${job.answers.map(a=>`<p>${esc(a.text)}<br><small>${dates(a.created)}</small></p>`).join('')}</details>`:''}</div>`;
}
function jobNeedsAnswer(job){
 if(job.status==='ready_review')return true;
 const run=state.ai.runs.find(r=>r.job_id===job.id&&['analyze','form'].includes(r.kind)&&r.status==='completed');
 const operational=/Employment type is not confirmed|source_check_required:|Browser verification|No supported single-page|Browser could not|manual application|Sign in using|İlan kaynağındaki/.test(job.reason||'');
 if(operational||job.source_check?.employment==='Unknown')return false;
 return !!run?.result?.questions?.length||job.reason?.startsWith('CV inceleme bekliyor:');
}
function pendingAttention(){return state.jobs.filter(j=>!j.answer_pending&&['needs_attention','ready_review'].includes(j.status)&&jobNeedsAnswer(j)&&!state.ai.runs.some(r=>r.job_id===j.id&&['running','queued'].includes(r.status))).reverse();}
function blockedPanel(){
 const jobs=state.jobs.filter(j=>j.status==='needs_attention'&&!j.answer_pending&&!jobNeedsAnswer(j)&&!state.ai.runs.some(r=>r.job_id===j.id&&['running','queued'].includes(r.status)));
 return `<div class="inline-heading"><h2>Otomasyonun takıldığı işlemler</h2><span class="pill">${jobs.length}</span></div>${jobs.length?'<p class="small muted">Bunlar yanıt bekleyen sorular değil. Yalnızca ilgili başvuru bekletilir; diğer işler devam eder.</p>':''}${jobs.map(j=>{
 let detail='Otomasyon bu başvurudaki adımı tamamlayamadı. Son tarayıcı görüntüsü ayrıntılarda.';
 if(j.source_check?.employment==='Unknown'||/İlan kaynağındaki|Employment type|source_check_required/.test(j.reason||''))detail='Kaynak sayfadaki bilgiler otomatik doğrulanamadı. Bu, ilanın kapandığı anlamına gelmez. Sistem çalışma saatlerinde yeniden kontrol eder; senden metin kopyalaman istenmiyor.';
 else if(/Browser verification/.test(j.reason||''))detail='Tarayıcı doğrulaması algılandı. Aynı Mac tarayıcı sekmesinde görünen doğrulamayı tamamlamak gerekebilir; kaydedilen görüntüyü ayrıntılardan kontrol et.';
 else if(/No supported|manual application/.test(j.reason||''))detail='Bu sayfada desteklenen başvuru formu bulunamadı. Bu sürüm bu adımı otomatik tamamlayamıyor; başvuru bekletildi.';
 return `<article class="attention-card"><h3>${esc(j.company)} · ${esc(j.title)}</h3><p>${esc(detail)}</p>${jobHealth(j)}<div class="detail-actions"><button class="button" data-job="${j.id}">Engelin ayrıntısını aç ↗</button>${j.source_check?.employment==='Unknown'?`<button class="button" data-verify-source="${j.id}">Kaynağı yeniden kontrol et ↗</button>`:''}<button class="text-button" data-attention-skip="${j.id}">Bu ilanı atla</button></div></article>`;
 }).join('')||'<p class="muted">Şu anda kaydedilmiş bir otomasyon engeli yok.</p>'}`;
}
function attentionCards(){
 const waiting=pendingAttention();
 if(!waiting.some(j=>j.id===attentionJobId))attentionJobId=waiting[0]?.id||null;
 const index=waiting.findIndex(j=>j.id===attentionJobId),job=waiting[index];
 return `<div class="inline-heading"><h2>Senden gerekenler</h2><span class="pill">${waiting.length}</span></div>${job?`<div class="attention-navigation"><button class="button" data-attention-direction="-1" ${index===0?'disabled':''}>← Önceki</button><span class="small muted">${index+1} / ${waiting.length}</span><button class="button" data-attention-direction="1" ${index===waiting.length-1?'disabled':''}>Sonraki →</button></div><article class="attention-card"><div class="inline-heading"><h3>${esc(job.company)} · ${esc(job.title)}</h3><button class="text-button" data-job="${job.id}">${job.status==='ready_review'?'Formu incele':'Ayrıntılar'} ↗</button></div>${jobHealth(job)}${answerBox(job)}<div class="detail-actions"><button class="button" data-attention-later ${waiting.length<2?'disabled':''}>Sonraya bırak</button><button class="text-button" data-attention-skip="${job.id}">Bu ilanı atla</button></div><p class="small muted">Sonraya bırak soruyu saklar. İlanı atlamak bu başvuruyu durdurur; kayıt geçmişte kalır.</p></article>`:'<p>Şu anda yanıtlaman gereken bir soru yok. Gerektiğinde burada ve bağlı Telegram sohbetinde haber vereceğiz.</p>'}`;
}
function moveAttention(direction,wrap=false){
 const waiting=pendingAttention();if(!waiting.length)return;
 const index=Math.max(0,waiting.findIndex(j=>j.id===attentionJobId));
 const next=wrap?(index+1)%waiting.length:Math.max(0,Math.min(waiting.length-1,index+direction));
 const current=$('#attention-cards [data-answer-text]');if(current)attentionDrafts[attentionJobId]=current.value;
 attentionJobId=waiting[next].id;$('#attention-cards').innerHTML=attentionCards();restoreAttentionDraft();
}
const attentionDrafts={};
function restoreAttentionDraft(){const box=$('#attention-cards [data-answer-text]');if(box)box.value=attentionDrafts[attentionJobId]||'';}
document.addEventListener('click',async e=>{
 const direction=e.target.closest('[data-attention-direction]');if(direction){moveAttention(Number(direction.dataset.attentionDirection));return;}
 if(e.target.closest('[data-attention-later]')){moveAttention(1,true);return;}
 const skip=e.target.closest('[data-attention-skip]');if(!skip)return;skip.disabled=true;
 try{await api('/jobs/'+skip.dataset.attentionSkip+'/action','POST',{action:'skip'});delete attentionDrafts[skip.dataset.attentionSkip];const text=$('#attention-cards [data-answer-text]');if(text)text.value='';await refresh(false);toast('İlan atlandı; kayıt geçmişte korunuyor.')}catch(err){toast(err.message,true)}finally{skip.disabled=false;}
});
function answerProgress(){
 const jobs=state.jobs.filter(j=>j.answers?.length).sort((a,b)=>Date.parse(b.answers.at(-1).created)-Date.parse(a.answers.at(-1).created)).slice(0,3);
 return `<div class="inline-heading"><h2>Yanıtlarından sonra</h2><span class="small muted">Son ${jobs.length} başvuru</span></div>${jobs.length?jobs.map(j=>{
 const run=state.ai.runs.find(r=>r.job_id===j.id),answer=j.answers.at(-1);
 let label='Yanıtın kaydedildi';
 if(j.status==='submitted')label='Başvuru gönderildi';
 else if(j.status==='skipped')label='Bu başvuru akıştan çıkarıldı';
 else if(j.answer_pending)label='Yanıtın alındı → çalışan görevin ardından yeni bilgilerle devam edilecek';
 else if(run?.status==='running')label=run.kind==='verify'?'Yanıtın alındı → ilan güncelliği kontrol ediliyor':'Yanıtın alındı → AI bu başvuruyu işliyor';
 else if(run?.status==='queued')label='Yanıtın alındı → AI görevi sırada';
 else if(['running','queued'].includes(j.status))label='Yanıtın işlendi → form hazırlığı '+(j.status==='running'?'çalışıyor':'sırada');
 else if(j.status==='ready_review')label='Form hazır → gönderim onayın bekleniyor';
 else if(run?.status==='failed')label='Yanıtın kaydedildi → işlem tamamlanamadı';
 else if(j.status==='needs_attention')label=run?.result?.questions?.length?'Yanıtın işlendi → ek bir soru var':j.reason?.startsWith('CV inceleme')?'Yanıtın işlendi → CV paylaşım onayın gerekiyor':'Yanıtın işlendi → bir başvuru adımı bekliyor';
 else if(run?.status==='completed')label='Yanıtın işlendi → hazırlık tamamlandı';
 return `<div class="answer-progress-row"><div><strong>${esc(j.company)} · ${esc(j.title)}</strong><p role="status">${esc(label)}</p><small>${dates(answer.created)} · ${answer.source==='telegram'?'Telegram yanıtı':'Panel yanıtı'}${run?' · görev #'+run.id:''}</small></div><button class="text-button" data-job="${j.id}">Başvuruyu aç ↗</button></div>`;
 }).join(''):'<p class="muted">Bir soruyu yanıtladığında, ilgili başvurunun devam durumu burada kalıcı olarak görünecek.</p>'}`;
}
function refreshOverview(){
 const live=liveOverview();
 const blocked=$('#blocked-steps');if(blocked){const content=blockedPanel();if(blocked.innerHTML!==content)blocked.innerHTML=content;}
 const progress=$('#answer-progress');if(progress){const content=answerProgress();if(progress.innerHTML!==content)progress.innerHTML=content;}
 for(const [id,text] of [['live-status-title',live.title],['live-status-badge',live.badge],['live-status-detail',live.detail],['state-freshness','Son veri alımı: '+new Date(stateReceivedAt).toLocaleTimeString('tr-TR',{timeZone:'Europe/Istanbul'})]]){const el=$('#'+id);if(el)el.textContent=text;}
 const feed=$('#live-flow');
 if(feed){const scroll=feed.querySelector('.live-events')?.scrollTop||0;const template=document.createElement('template');template.innerHTML=liveFlowPanel();if(template.content.firstElementChild.innerHTML!==feed.innerHTML){feed.innerHTML=template.content.firstElementChild.innerHTML;const list=feed.querySelector('.live-events');if(list)list.scrollTop=scroll;}}
 const attention=$('#attention-cards');
 if(attention&&!attention.querySelector('textarea:focus')&&![...attention.querySelectorAll('textarea')].some(t=>t.value)){const content=attentionCards();if(attention.innerHTML!==content){attention.innerHTML=content;restoreAttentionDraft();}}
}
async function saveSearchScope(start){
 const form=$('#search-scope-form'),fd=new FormData(form);
 const filters={geography:fd.get('geography'),work_mode:fd.get('work_mode'),roles:fd.get('roles'),sources:fd.getAll('source')};
 setSaveStatus(form,'Kaydediliyor…',true);
 try{
  if(start)await api('/automation/start','POST',{confirmed:!!state.setup?.profile_confirmed||fd.has('confirm_profile'),search_filters:filters,auto_fill:fd.has('auto_fill'),immediate:true});
  else await api('/ai/config','PUT',{search_filters:filters,auto_fill:fd.has('auto_fill')});
  await refresh();toast(start?'Arama başladı. Adımlar canlı akışta görünecek.':'Arama tercihleri kaydedildi.');
 }catch(err){setSaveStatus(form,err.message);toast(err.message,true);}
}
document.addEventListener('submit',e=>{if(e.target.id==='search-scope-form'){e.preventDefault();saveSearchScope(true)}});
document.addEventListener('input',e=>{const f=e.target.closest('#search-scope-form');if(f)setSaveStatus(f,'Kaydedilmemiş değişiklikler var.')});
document.addEventListener('click',async e=>{
 if(e.target.closest('[data-save-scope]')){await saveSearchScope(false);return;}
 const b=e.target.closest('[data-answer-submit]');if(!b)return;
 const id=b.dataset.answerSubmit;const box=b.closest('[data-answer-box]');b.disabled=true;
 try{const result=await api('/jobs/'+id+'/answers','POST',{text:box.querySelector('[data-answer-text]').value,question_run:box.dataset.questionRun?Number(box.dataset.questionRun):null});box.querySelector('textarea').value='';delete attentionDrafts[id];await refresh(false);if($('#detail-dialog').open)renderDetail(Number(id));toast(result.detail)}catch(err){toast(err.message,true)}finally{b.disabled=false;}
});

// This switch is a persisted preference; it must not wait for a separate Save click.
document.addEventListener('change',async e=>{
 const toggle=e.target.closest('#search-scope-form [name="auto_fill"]');if(!toggle)return;
 const desired=toggle.checked,form=toggle.closest('form');toggle.disabled=true;
 setSaveStatus(form,'Otomatik doldurma tercihi kaydediliyor…',true);
 try{
  const result=await api('/ai/config','PUT',{auto_fill:desired});
  if(result.config?.auto_fill!==desired)throw Error('Sunucu bu tercihi doğrulamadı. Sayfayı yenileyip tekrar dene.');
  state.ai.config=result.config;
  setSaveStatus(form,desired?'Otomatik form doldurma açık · kaydedildi.':'Otomatik form doldurma kapalı · kaydedildi.');
 }catch(err){toggle.checked=!desired;setSaveStatus(form,'Kaydedilemedi: '+err.message);toast(err.message,true)}
 finally{toggle.disabled=false;}
});

document.addEventListener('click',async e=>{const b=e.target.closest('[data-verify-source]');if(!b)return;b.disabled=true;try{await api('/jobs/'+b.dataset.verifySource+'/verify-source','POST',{});await refresh(false);toast('İlan kaynağı kontrol ediliyor.')}catch(err){toast(err.message,true)}finally{b.disabled=false}});

document.addEventListener('click',async e=>{const b=e.target.closest('[data-approve-preparation]');if(!b)return;b.disabled=true;try{await api('/jobs/'+b.dataset.approvePreparation+'/action','POST',{action:'fill',authorize:true});await refresh(false);toast('CV onayın alındı; form hazırlığı devam ediyor.')}catch(err){toast(err.message,true)}finally{b.disabled=false}});
