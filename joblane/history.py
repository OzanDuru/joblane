"""Immutable CV copies and records of exactly what was attempted."""
import hashlib
import json
from pathlib import Path
from .store import now

class History:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS cv_versions(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL,label TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(job_id,sha256));
            CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL,channel TEXT NOT NULL,destination TEXT NOT NULL,status TEXT NOT NULL,cv_version_id INTEGER NOT NULL,subject TEXT NOT NULL DEFAULT '',body TEXT NOT NULL DEFAULT '',details TEXT NOT NULL DEFAULT '',created TEXT NOT NULL,updated TEXT NOT NULL);
            ''')
            db.execute("UPDATE deliveries SET status='uncertain',details='Service restarted during submission. Check the destination before any retry.',updated=? WHERE status='sending'",(now(),))

    def archive_cv(self,job_id,label):
        job=self.store.job(job_id)
        if not job['cv_path']:raise ValueError('Prepare a CV first.')
        content=Path(job['cv_path']).read_bytes()
        sha=hashlib.sha256(content).hexdigest()
        with self.store.lock,self.store.connect() as db:
            row=db.execute('SELECT id FROM cv_versions WHERE job_id=? AND sha256=?',(job_id,sha)).fetchone()
            if row:return row[0]
            directory=(self.store.directory/'history'/'cvs').resolve();directory.mkdir(parents=True,exist_ok=True)
            path=directory/f'{job_id}-{sha}.pdf'
            if not path.exists():
                with path.open('xb') as f:f.write(content)
            cur=db.execute('INSERT INTO cv_versions(job_id,label,path,sha256,created) VALUES (?,?,?,?,?)',(job_id,label,str(path),sha,now()))
            return cur.lastrowid

    def version(self,version_id):
        with self.store.connect() as db:row=db.execute('SELECT * FROM cv_versions WHERE id=?',(version_id,)).fetchone()
        if not row:raise ValueError('CV version not found.')
        return dict(row)

    def cv_bytes(self,version_id):
        v=self.version(version_id);data=Path(v['path']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=v['sha256']:raise ValueError('Archived CV integrity check failed.')
        return data

    def delivery(self,delivery_id):
        with self.store.connect() as db:row=db.execute('SELECT * FROM deliveries WHERE id=?',(delivery_id,)).fetchone()
        if not row:raise ValueError('Delivery not found.')
        return dict(row)

    def create(self,job_id,channel,destination,status,cv_version_id,subject='',body='',details=''):
        stamp=now()
        with self.store.connect() as db:
            cur=db.execute('INSERT INTO deliveries(job_id,channel,destination,status,cv_version_id,subject,body,details,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?)',(job_id,channel,destination,status,cv_version_id,subject,body,details,stamp,stamp))
            return cur.lastrowid

    def update(self,delivery_id,status,details):
        with self.store.connect() as db:db.execute('UPDATE deliveries SET status=?,details=?,updated=? WHERE id=?',(status,details,now(),delivery_id))

    def data(self):
        with self.store.connect() as db:
            versions=[dict(r) for r in db.execute('SELECT id,job_id,label,sha256,created FROM cv_versions ORDER BY id DESC LIMIT 500')]
            deliveries=[dict(r) for r in db.execute('SELECT * FROM deliveries ORDER BY id DESC LIMIT 300')]
        return {'versions':versions,'deliveries':deliveries}
