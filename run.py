import argparse
import getpass
import json
import os
import secrets
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description='Joblane private application workspace')
    parser.add_argument('command',choices=['init','serve','reset-password'],nargs='?',default='serve')
    parser.add_argument('--data-dir',default=os.getenv('JOBLANE_DATA_DIR',str(Path(__file__).parent/'data')))
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open',action='store_true',help='Open the dashboard once the server is ready')
    args=parser.parse_args()
    if args.command=='serve':
        import urllib.request
        import socket
        import webbrowser
        with socket.socket() as sock:
            sock.settimeout(.5)
            occupied=sock.connect_ex(('127.0.0.1',args.port))==0
        if occupied:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/session',timeout=2) as response:
                    existing=json.load(response)
                if existing.get('app')=='joblane':
                    print(f'Joblane is already running at http://127.0.0.1:{args.port}')
                    if args.open:webbrowser.open(os.getenv('JOBLANE_PUBLIC_URL') or f'http://127.0.0.1:{args.port}')
                    return
            except Exception:pass
            raise SystemExit(f'Port {args.port} is in use. Stop the other service or choose --port.')
    from joblane.store import Store
    from werkzeug.security import generate_password_hash
    store=Store(args.data_dir)
    if args.command in ('init','reset-password'):
        if args.command=='init' and store.get('password_hash'):
            print('Already initialized. Use reset-password to change the login.'); return
        print('Create a private dashboard password. This is separate from ChatGPT.')
        password=getpass.getpass('Password (at least 12 characters): ')
        if len(password)<12 or password!=getpass.getpass('Repeat password: '):
            raise SystemExit('Passwords must match and contain at least 12 characters.')
        store.set('password_hash',generate_password_hash(password))
        store.set('secret',secrets.token_hex(32))
        store.set('password_change_required',False)
        if not store.get('profile'):
            store.set('profile',json.loads((Path(__file__).parent/'starter-profile.json').read_text(encoding='utf-8')))
        print('Setup saved locally. Restart the service if it was running.')
        return
    if not store.get('password_hash'):
        raise SystemExit('Run python run.py init first.')
    from joblane.server import create_app
    from waitress import serve
    app=create_app(args.data_dir,args.port)
    print(f'Joblane is running at http://127.0.0.1:{args.port}',flush=True)
    print('Keep this service running. Use Tailscale Serve for private phone access.',flush=True)
    if args.open:
        import threading
        import time
        import urllib.request
        import webbrowser
        def open_when_ready():
            for _ in range(40):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/session',timeout=1):
                        webbrowser.open(os.getenv('JOBLANE_PUBLIC_URL') or f'http://127.0.0.1:{args.port}/')
                        return
                except OSError:
                    time.sleep(.25)
        threading.Thread(target=open_when_ready,daemon=True).start()
    try:
        serve(app,host='127.0.0.1',port=args.port,threads=6)
    finally:
        agent=app.extensions['agent']
        agent.stop_event.set()
        if agent.active:
            try:agent.cancel(agent.active)
            except ValueError:pass
        worker=app.extensions['worker']
        worker.stop_event.set()
        if worker.thread:worker.thread.join(timeout=10)
        if agent.thread:agent.thread.join(timeout=5)


if __name__=='__main__': main()
