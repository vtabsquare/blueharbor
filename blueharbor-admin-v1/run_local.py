"""Run only this BlueHarbor application. No sibling project is required."""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
from app_mode import ROLE
children=[]

def ports():
    sockets=[]
    try:
        for preferred in ((3000,8001) if ROLE=='buyer' else (3001,8002)):
            sock=socket.socket()
            try:sock.bind(('127.0.0.1',preferred))
            except OSError:sock.bind(('127.0.0.1',0))
            sockets.append(sock)
        return tuple(s.getsockname()[1] for s in sockets)
    finally:
        for sock in sockets:sock.close()

def start(args,env):
    child=subprocess.Popen(args,cwd=ROOT,env=env,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
    children.append(child);return child

def ready(url,timeout=90):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if any(p.poll() is not None for p in children):raise RuntimeError('A service stopped. Check the message above.')
        try:
            with urllib.request.urlopen(url,timeout=2) as r:
                if r.status==200:return
        except Exception:pass
        time.sleep(.5)
    raise RuntimeError('Startup timed out. Check Supabase configuration and the messages above.')

def main():
    import cloud_config
    cloud_config.validate()
    REQUIREMENTS = ROOT / 'backend' / 'requirements.txt'
    if importlib.util.find_spec('psycopg') is None:
        print('Installing this application’s backend packages (first run only)...', flush=True)
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS),
            "--disable-pip-version-check",
            "--break-system-packages",
        ]
        subprocess.run(command, check=True)
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:raise RuntimeError('Install Node.js 22.13+ and reopen VS Code.')
    with open(ROOT/'.launcher.lock','a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('This application is already running. Use its terminal or stop it with Ctrl+C.')
        else:
            import fcntl
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('This application is already running.')
        web,api=ports()
        env=os.environ.copy()
        env.update(BLUEHARBOR_WEB_PORT=str(web),BLUEHARBOR_WEB_PORTS=str(web),BLUEHARBOR_API_PORT=str(api),
                   NEXT_PUBLIC_BUYER_URL=os.environ.get('BLUEHARBOR_BUYER_URL','http://localhost:3000'),PYTHONUNBUFFERED='1')
        frontend={k:v for k,v in env.items() if not k.startswith(('SUPABASE_','SMTP_','OLLAMA_','BLUEHARBOR_SMTP_','BLUEHARBOR_AI_','GEMINI_'))}
        if not any((ROOT/'node_modules'/'.bin'/name).exists() for name in ('vinext','vinext.cmd')):
            print('Installing this application’s frontend packages (first run only)...',flush=True)
            subprocess.run([npm,'ci','--no-audit','--no-fund'],cwd=ROOT,env=frontend,check=True)
        start([sys.executable,str(ROOT/'backend'/'server.py')],env)
        ready(f'http://127.0.0.1:{api}/api/health',35)
        start([npm,'run','dev','--','--port',str(web)],frontend)
        suffix='/admin' if ROLE=='admin' else '/'
        ready(f'http://127.0.0.1:{web}{suffix}')
        url=f'http://localhost:{web}{suffix}'
        print(f'\nBlueHarbor {ROLE}: {url}\nConfiguration: {ROOT / "backend" / ".env"}\nOnly this application is running. Ctrl+C stops only its services.',flush=True)
        if '--no-browser' not in sys.argv:webbrowser.open(url)
        while all(p.poll() is None for p in children):time.sleep(1)
        raise RuntimeError('A service stopped. See its message above.')

if __name__=='__main__':
    failed=False
    try:main()
    except KeyboardInterrupt:print('\nStopping this application...')
    except (RuntimeError,subprocess.CalledProcessError) as e:print(str(e));failed=True
    finally:
        for child in reversed(children):
            if child.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                else:child.terminate()
    sys.exit(1 if failed else 0)
