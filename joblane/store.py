import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SETTINGS = {
    'enabled': False, 'mode': 'review', 'start': '15:00', 'end': '20:00',
    'timezone': 'Europe/Istanbul', 'days': list(range(7)), 'daily_limit': 10,
    'allowed_domains': [], 'roles': '', 'locations': '', 'employment': 'Any',
}


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'joblane.sqlite3'
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, company TEXT NOT NULL,
                title TEXT NOT NULL, description TEXT NOT NULL, track TEXT NOT NULL,
                domain TEXT NOT NULL, demo INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'draft', reason TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL, updated TEXT NOT NULL, cv_path TEXT,
                snapshot TEXT, authorized INTEGER NOT NULL DEFAULT 0,
                reviewed INTEGER NOT NULL DEFAULT 0, submitted TEXT, evidence TEXT,
                attempt_started TEXT, approval_digest TEXT);
              CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, job_id INTEGER, message TEXT NOT NULL,
                created TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY, job_id INTEGER, state TEXT NOT NULL,
                detail TEXT NOT NULL, created TEXT NOT NULL);
            ''')
        if self.get('settings') is None:
            self.set('settings', DEFAULT_SETTINGS.copy())
        # A process crash during submission is ambiguous: never retry automatically.
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='needs_attention', reason='Worker restarted. Check the employer for an existing application before continuing.', updated=? WHERE status IN ('running','submitting')", (now(),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO config VALUES (?,?)', (key, json.dumps(value)))

    def jobs(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY id DESC')]

    def job(self, job_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise ValueError('Application not found.')
        return dict(row)

    def add(self, **values):
        stamp = now()
        with self.connect() as db:
            try:
                cur = db.execute('INSERT INTO jobs(url,company,title,description,track,domain,demo,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                    tuple(values[k] for k in ('url','company','title','description','track','domain','demo')) + (stamp, stamp))
            except sqlite3.IntegrityError:
                raise ValueError('This application URL is already in your workspace.')
        self.event(cur.lastrowid, 'Application added.')
        return cur.lastrowid

    def update(self, job_id, **values):
        allowed = {'description','status','reason','cv_path','snapshot','authorized','reviewed','submitted','evidence','attempt_started','approval_digest'}
        if not set(values).issubset(allowed):
            raise ValueError('Invalid update.')
        values['updated'] = now()
        with self.connect() as db:
            db.execute('UPDATE jobs SET ' + ','.join(k+'=?' for k in values) + ' WHERE id=?', tuple(values.values())+(job_id,))

    def event(self, job_id, message):
        with self.connect() as db:
            db.execute('INSERT INTO events(job_id,message,created) VALUES (?,?,?)', (job_id, message, now()))

    def events(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 50')]

    def reviewed_count(self, domain):
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM jobs WHERE domain=? AND reviewed=1 AND status='submitted' AND demo=0", (domain,)).fetchone()[0]
