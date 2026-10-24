"""Offline removal of legacy demo data. Stop the service before calling."""
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def remove_demo_data(directory, backup_root):
    directory = Path(directory).resolve()
    backup_root = Path(backup_root).resolve()
    if backup_root == directory or directory in backup_root.parents:
        raise ValueError('Backups must be outside the active data directory.')
    with sqlite3.connect(directory / 'joblane.sqlite3') as db:
        db.row_factory = sqlite3.Row
        jobs = list(db.execute('SELECT * FROM jobs WHERE demo=1'))
        if not jobs:
            return {'removed_jobs': [], 'backup': None}
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if any(db.execute("SELECT count(*) FROM jobs WHERE status IN ('running','submitting')").fetchone()):
            raise ValueError('An application is active. Stop and reconcile it before cleanup.')
        if 'ai_runs' in tables and db.execute("SELECT count(*) FROM ai_runs WHERE status IN ('running','queued')").fetchone()[0]:
            raise ValueError('Finish or cancel pending AI tasks before cleanup.')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = backup_root / ('before-demo-removal-' + stamp)
        backup.mkdir(parents=True, mode=0o700)
        shutil.copytree(directory, backup / 'data')
        # Snapshot through SQLite too, so WAL contents are included.
        with sqlite3.connect(backup / 'data' / 'joblane.sqlite3') as target:
            db.backup(target)
        paths = set()
        for job in jobs:
            ident = job['id']
            for key in ('cv_path', 'evidence'):
                if job[key]: paths.add(Path(job[key]))
            paths.update((directory / 'cvs').glob(f'application-{ident}-*.pdf'))
            paths.add(directory / 'cvs' / f'application-{ident}.pdf')
            if 'cv_versions' in tables:
                paths.update(Path(r[0]) for r in db.execute('SELECT path FROM cv_versions WHERE job_id=?', (ident,)))
            if 'ai_runs' in tables:
                paths.update(directory / 'ai' / f'run-{r[0]}' for r in db.execute('SELECT id FROM ai_runs WHERE job_id=?', (ident,)))
            if 'deliveries' in tables:
                for row in db.execute('SELECT id FROM deliveries WHERE job_id=?', (ident,)).fetchall():
                    for prefix in ('email-sender', 'email-digest'):
                        db.execute('DELETE FROM config WHERE key=?', (f'{prefix}:{row[0]}',))
            for prefix in ('attempt', 'delivery', 'observation', 'cv_variant', 'discovery'):
                db.execute('DELETE FROM config WHERE key=?', (f'{prefix}:{ident}',))
            for table in ('events', 'notifications', 'ai_runs', 'ai_sessions', 'deliveries', 'cv_versions'):
                if table in tables: db.execute(f'DELETE FROM {table} WHERE job_id=?', (ident,))
            db.execute('DELETE FROM jobs WHERE id=?', (ident,))
        # Reject unexpected external paths rather than deleting outside application storage.
        if any(directory not in p.resolve().parents for p in paths):
            raise ValueError('Unexpected artifact path; cleanup rolled back. Backup retained.')
        db.commit()
    removed_files = []
    for path in paths:
        if path.is_dir(): shutil.rmtree(path)
        elif path.exists(): path.unlink()
        removed_files.append(str(path.relative_to(directory)))
    result = {'removed_jobs': [j['id'] for j in jobs], 'backup': str(backup), 'removed_files': sorted(removed_files)}
    (backup / 'cleanup-report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
