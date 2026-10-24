"""Install an app-local official Codex CLI; reuse the user's existing CLI login."""
import os
from pathlib import Path
import shutil
import sqlite3
import json
import subprocess

ROOT=Path(__file__).resolve().parent
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
if not npm:
    raise SystemExit('Install Node.js from nodejs.org, reopen the terminal, and run this setup again.')
args=[npm,'install','--prefix',str(ROOT/'.tools'),'@openai/codex@0.164.0','--no-audit','--no-fund']
if os.name=='nt':
    # npm.cmd needs cmd.exe on Windows; every argument is locally generated, never model input.
    subprocess.run(subprocess.list2cmdline(args),check=True,shell=True)
else:
    subprocess.run(args,check=True)
filename='codex.exe' if os.name=='nt' else 'codex'
candidates=list((ROOT/'.tools'/'node_modules'/'@openai').glob(f'codex-*/vendor/*/bin/{filename}'))
if len(candidates)!=1:
    raise SystemExit('Could not locate the platform Codex executable. Set JOBLANE_CODEX_BIN to its full path.')
binary=candidates[0].resolve()
database=Path(os.getenv('JOBLANE_DATA_DIR',str(ROOT/'data')))/'joblane.sqlite3'
if not database.exists():
    raise SystemExit('Initialize Joblane with run.py init before configuring its Codex connection.')
with sqlite3.connect(database) as db:
    db.execute('INSERT OR REPLACE INTO config VALUES (?,?)',('codex_binary',json.dumps(str(binary))))
subprocess.run([str(binary),'--version'],check=True)
status=subprocess.run([str(binary),'login','status'])
if status.returncode:
    print('Sign in using the standard Codex login flow. No credentials are copied to Joblane.')
    subprocess.run([str(binary),'login'],check=True)
print('Codex is ready. Restart Joblane or choose AI & discovery > Check local connection.')
