"""Allowlisted operational events, never model reasoning or raw tool output."""
import json
import re
from urllib.parse import urlsplit, urlunsplit
from .store import now


def clean_text(value, limit=1500):
    value=str(value or '')
    value=re.sub(r'(?i)(bearer\s+)[\w.\-]+',r'\1[gizlendi]',value)
    value=re.sub(r'(?i)((?:token|password|secret|api[_-]?key)\s*[=:]\s*)[^\s&,;]+',r'\1[gizlendi]',value)
    value=re.sub(r'\b\d{6,}:[\w-]{20,}\b','[gizlendi]',value)
    return value[:limit]


def public_url(value):
    try:
        u=urlsplit(str(value))
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:return ''
        return urlunsplit((u.scheme,u.netloc,u.path,'',''))[:1000]
    except ValueError:return ''


class RunJournal:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS ai_events (
                id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, event_key TEXT NOT NULL,
                stage TEXT NOT NULL, state TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL,
                created TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0,
                UNIQUE(run_id,event_key));
                CREATE INDEX IF NOT EXISTS ai_events_run ON ai_events(run_id,id);''')
            if 'data' not in {r[1] for r in db.execute('PRAGMA table_info(ai_events)')}:
                db.execute("ALTER TABLE ai_events ADD COLUMN data TEXT NOT NULL DEFAULT '{}'")

    def record(self,run_id,key,stage,state,title,detail='',archived=False,created=None,data=None):
        with self.store.connect() as db:
            # Bound each task's journal without dropping terminal lifecycle events.
            if key.startswith('cli:') and db.execute('SELECT count(*) FROM ai_events WHERE run_id=?',(run_id,)).fetchone()[0]>=500:return
            db.execute('INSERT INTO ai_events(run_id,event_key,stage,state,title,detail,created,archived,data) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,event_key) DO UPDATE SET stage=excluded.stage,state=excluded.state,title=excluded.title,detail=excluded.detail,data=excluded.data',
                       (run_id,key,stage,state,clean_text(title,200),clean_text(detail),created or now(),int(archived),json.dumps(data or {},ensure_ascii=False)))

    def ingest(self,run_id,path,offset=0,archived=False):
        if not path.exists():return offset
        with path.open('rb') as stream:
            stream.seek(offset)
            # Bounded reads; incomplete lines are retried on the next poll.
            for _ in range(1000):
                start=stream.tell();line=stream.readline(2_000_001)
                if not line:return stream.tell()
                if not line.endswith(b'\n'):return start
                offset=stream.tell()
                try:event=json.loads(line)
                except (ValueError,UnicodeError):continue
                self.normalize(run_id,event,f'cli:{start}',archived)
        return offset

    def normalize(self,run_id,event,key,archived=False):
        if not isinstance(event,dict):return
        kind=event.get('type');item=event.get('item') or {}
        if not isinstance(item,dict):return
        title=detail=stage=status=None
        data={}
        if kind=='thread.started':stage,status,title='session','completed','Codex oturumu açıldı'
        elif kind=='turn.started':stage,status,title='model','running','AI görevi işleniyor'
        elif kind in ('item.started','item.completed') and item.get('type')=='web_search':
            action=item.get('action') or {};action=action if isinstance(action,dict) else {}
            stage='search';status='running' if kind=='item.started' else 'completed'
            title='Web araması başladı' if status=='running' else 'Web araması tamamlandı'
            if action.get('type') in ('open_page','open'):
                title='Kaynak sayfa açılıyor' if status=='running' else 'Kaynak sayfa açıldı'
            elif action.get('type') in ('find','find_in_page'):
                title='Kaynak sayfada metin aranıyor' if status=='running' else 'Kaynak içi arama tamamlandı'
            queries=action.get('queries') or [action.get('query') or item.get('query')]
            if not isinstance(queries,list):queries=[queries]
            parts=[str(q) for q in queries[:6] if isinstance(q,str) and q]
            url=public_url(action.get('url',''))
            if url:parts.append(url)
            if isinstance(action.get('pattern'),str):parts.append('Aranan metin: '+action['pattern'])
            results=item.get('results') or []
            if not isinstance(results,list):results=[]
            sources=[]
            for result in results[:20]:
                if not isinstance(result,dict):continue
                source_url=public_url(result.get('url',''))
                if not source_url:continue
                sources.append({'title':clean_text(result.get('title') or result.get('domain') or 'Kaynak',240),'url':source_url})
            data={'action':clean_text(action.get('type','search'),30),'queries':[clean_text(q,600) for q in queries[:6] if isinstance(q,str) and q],
                  'url':url,'pattern':clean_text(action.get('pattern',''),300),'sources':sources,'source_count':len(results)}
            detail='Arama sorgusu: '+ '\n'.join(parts) if parts else 'CLI bu adım için sorgu veya kaynak ayrıntısı paylaşmadı.'
            if results:detail+=f'\nArama çıktısında {len(results)} kaynak kaydı var. Bunlar henüz doğrulanmış başvuru ilanları değildir.'

        elif kind=='item.completed' and item.get('type')=='agent_message':
            stage,status,title='response','completed','AI yanıtı alındı'
            detail='Yapılandırılmış sonuç doğrulaması bekleniyor.'
        elif kind=='turn.completed':stage,status,title='model','completed','Model işlemi tamamlandı'
        # Ignore reasoning, arbitrary messages, results and unknown tool payloads.
        if title:self.record(run_id,key,stage,status,title,detail,archived,data=data)

    def for_runs(self,ids):
        result={i:[] for i in ids}
        if not ids:return result
        with self.store.connect() as db:
            rows=db.execute('SELECT * FROM ai_events WHERE run_id IN ('+','.join('?' for _ in ids)+') ORDER BY id DESC LIMIT 2000',ids).fetchall()
        for row in rows:
            event=dict(row);event['data']=json.loads(event['data']);events=result[event['run_id']]
            if len(events)<80:events.append(event)
        for events in result.values():events.reverse()
        return result
