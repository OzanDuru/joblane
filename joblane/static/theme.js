(function(){
 const key='joblane-theme';const media=window.matchMedia('(prefers-color-scheme: dark)');
 let preference='system';try{preference=localStorage.getItem(key)||'system'}catch{}
 if(!['light','dark','system'].includes(preference))preference='system';
 function apply(){document.documentElement.dataset.theme=preference==='system'?(media.matches?'dark':'light'):preference;document.documentElement.style.colorScheme=document.documentElement.dataset.theme;document.querySelectorAll('[data-theme-select]').forEach(el=>el.value=preference)}
 apply();document.addEventListener('DOMContentLoaded',apply);
 document.addEventListener('change',e=>{if(!e.target.matches('[data-theme-select]'))return;preference=e.target.value;try{localStorage.setItem(key,preference)}catch{}apply()});
 media.addEventListener('change',()=>{if(preference==='system')apply()});
})();
