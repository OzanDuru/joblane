function searchFilterForm(){
 const f=state.ai.config.search_filters||{geography:'turkey_first',sources:['linkedin','kariyer','company'],work_mode:'any',roles:''};
 return `<form id="search-scope-form" class="form-panel"><div class="inline-heading"><h2>Nasıl bir iş arayalım?</h2><span class="small muted">Bir kez seç; gerektiğinde değiştir.</span></div><div class="two-col"><label>Konum<select name="geography">${[['turkey_first','Türkiye öncelikli, yurt dışı dahil'],['turkey','Yalnızca Türkiye'],['abroad','Yalnızca yurt dışı'],['worldwide','Tüm dünya']].map(([v,t])=>`<option value="${v}" ${f.geography===v?'selected':''}>${t}</option>`).join('')}</select></label><label>Çalışma şekli<select name="work_mode">${[['any','Uzaktan, hibrit veya ofis'],['remote','Uzaktan'],['hybrid','Hibrit'],['office','Ofis']].map(([v,t])=>`<option value="${v}" ${f.work_mode===v?'selected':''}>${t}</option>`).join('')}</select></label></div>${input('Pozisyonlar (boş bırakırsan kayıtlı arama hedefin kullanılır)','roles',f.roles)}<div class="source-options">${[['linkedin','LinkedIn'],['kariyer','Kariyer.net'],['company','Şirket kariyer sayfaları']].map(([v,t])=>`<label class="check-label"><input type="checkbox" name="source" value="${v}" ${f.sources.includes(v)?'checked':''}> ${t}</label>`).join('')}</div><label class="check-label"><input type="checkbox" name="auto_fill" ${state.ai.config.auto_fill?'checked':''}> Bilgiler yeterliyse profilim ve ilana özel PDF ile desteklenen şirket formlarını otomatik doldur.</label><p class="small muted">LinkedIn ve Kariyer.net şu anda ilan kaynağıdır; bu sitelerde otomatik gönderim henüz desteklenmiyor. İlk form gönderimi ve e-posta gönderimi inceleme bekler.</p>${!state.setup?.profile_confirmed?'<label class="check-label"><input type="checkbox" name="confirm_profile"> Profilimi doğruladım; kariyer bilgilerimin Codex ile işlenmesini onaylıyorum.</label>':''}<div class="detail-actions"><button type="submit" class="primary">Bu filtrelerle şimdi başlat ↗</button><button type="button" class="button" data-save-scope>Yalnızca tercihleri kaydet</button></div><p data-save-status class="small muted" role="status">Başlat: ilk aramayı hemen yapar; sonraki işlemler kayıtlı çalışma saatlerine uyar.</p></form>`;
}
function answerBox(job){
 const latest=state.ai.runs.find(r=>r.job_id===job.id&&['analyze','observe','form'].includes(r.kind)&&r.status==='completed');
 const questions=latest?.result?.questions||[];
 const busy=state.ai.runs.some(r=>r.job_id===job.id&&['running','queued'].includes(r.status));
 return `<div class="answer-box" data-answer-box="${job.id}" data-question-run="${latest?.id||''}">${questions.length?`<ol>${questions.slice(0,1).map(q=>`<li>${esc(q)}</li>`).join('')}</ol>`:`<p>${esc(job.reason)}</p>`}${job.status==='needs_attention'?`<label>Yanıtın<textarea data-answer-text="${job.id}" rows="3" placeholder="Tek mesajda yanıtla; AI ilgili başvuruda devam etsin." ${busy?'disabled':''}></textarea></label><p class="small muted">Yanıtın bu sorunun bağlamıyla saklanır; aynı bilgi tekrar gerekirse kullanılır.</p><button class="primary" data-answer-submit="${job.id}" ${busy?'disabled':''}>${busy?'AI yanıtı işliyor…':'Yanıtla ve devam et ↗'}</button>`:''}${job.answers?.length?`<details><summary>Kaydedilen yanıtlar (${job.answers.length})</summary>${job.answers.map(a=>`<p>${esc(a.text)}<br><small>${dates(a.created)}</small></p>`).join('')}</details>`:''}</div>`;
}
function attentionCards(){
 const waiting=state.jobs.filter(j=>['needs_attention','ready_review'].includes(j.status)&&!state.ai.runs.some(r=>r.job_id===j.id&&['running','queued'].includes(r.status))).reverse();
 return `<div class="inline-heading"><h2>Senden gerekenler</h2><span class="pill">${waiting.length}</span></div>${waiting.length?waiting.slice(0,1).map(j=>`<article class="attention-card"><div class="inline-heading"><h3>${esc(j.company)} · ${esc(j.title)}</h3><button class="text-button" data-job="${j.id}">${j.status==='ready_review'?'Formu incele':'Ayrıntılar'} ↗</button></div>${answerBox(j)}</article>`).join('')+(waiting.length>1?`<p class="small muted">${waiting.length-1} başvuru daha bekliyor. Bu adımı bitirince sıradaki gösterilecek.</p>`:''):'<p>Şu anda yanıtlaman gereken bir soru yok. Gerektiğinde burada ve bağlı Telegram sohbetinde haber vereceğiz.</p>'}`;
}
function refreshOverview(){
 const live=liveOverview();
 for(const [id,text] of [['live-status-title',live.title],['live-status-badge',live.badge],['live-status-detail',live.detail],['state-freshness','Son veri alımı: '+new Date(stateReceivedAt).toLocaleTimeString('tr-TR',{timeZone:'Europe/Istanbul'})]]){const el=$('#'+id);if(el)el.textContent=text;}
 const feed=$('#live-flow');
 if(feed){const scroll=feed.querySelector('.live-events')?.scrollTop||0;const template=document.createElement('template');template.innerHTML=liveFlowPanel();if(template.content.firstElementChild.innerHTML!==feed.innerHTML){feed.innerHTML=template.content.firstElementChild.innerHTML;const list=feed.querySelector('.live-events');if(list)list.scrollTop=scroll;}}
 const attention=$('#attention-cards');
 if(attention&&!attention.contains(document.activeElement)&&![...attention.querySelectorAll('textarea')].some(t=>t.value)){const content=attentionCards();if(attention.innerHTML!==content)attention.innerHTML=content;}
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
 try{const result=await api('/jobs/'+id+'/answers','POST',{text:box.querySelector('[data-answer-text]').value,question_run:box.dataset.questionRun?Number(box.dataset.questionRun):null});box.querySelector('textarea').value='';await refresh(false);if($('#detail-dialog').open)renderDetail(Number(id));toast(result.detail)}catch(err){toast(err.message,true)}finally{b.disabled=false;}
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
