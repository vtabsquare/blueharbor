"""Local owner backup, offline restore, and staff password recovery."""
import argparse
import getpass
import os
import socket
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
import server

def backup():
    if not server.DB.exists():raise ValueError('No database exists yet.')
    folder=server.DB.parent/'backups';folder.mkdir(parents=True,exist_ok=True)
    import secrets
    target=folder/('blueharbor-'+server.now().replace(':','-')+'-'+secrets.token_hex(3)+'.sqlite3')
    with closing(sqlite3.connect(server.DB)) as source,closing(sqlite3.connect(target)) as dest:source.backup(dest)
    return target

def main():
    p=argparse.ArgumentParser(description='Run as the local database owner only.')
    sub=p.add_subparsers(dest='action',required=True);sub.add_parser('backup')
    restore=sub.add_parser('restore');restore.add_argument('source');restore.add_argument('--confirm',required=True,choices=['RESTORE'])
    reset=sub.add_parser('reset-staff-password');reset.add_argument('email')
    args=p.parse_args()
    if args.action=='backup':print(backup());return
    if args.action=='reset-staff-password':
        password=getpass.getpass('New staff password (12+ characters): ')
        if len(password)<12 or password!=getpass.getpass('Confirm password: '):p.error('Passwords must match and have at least 12 characters.')
        with server.db() as c:
            staff=c.execute('SELECT * FROM staff WHERE email=?',(args.email.lower(),)).fetchone()
            if not staff:p.error('Staff member not found.')
            c.execute('UPDATE staff SET password=? WHERE id=?',(server.password_hash(password),staff['id']));c.execute('DELETE FROM staff_sessions WHERE staff_id=?',(staff['id'],))
            server.admin.record(c,None,'OWNER_PASSWORD_RESET',staff['id'],'Local owner reset staff password')
        print('Password reset. Staff sessions invalidated.');return
    source=Path(args.source).resolve();target=server.DB.resolve()
    if not source.is_file() or source==target:p.error('Choose an existing backup file distinct from the active database.')
    try:
        with socket.create_connection(('127.0.0.1',server.API_PORT),timeout=1):p.error('Stop the application before restoring. Set BLUEHARBOR_API_PORT if using a custom port.')
    except OSError:pass
    with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True)) as check:
        if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':p.error('Backup failed integrity validation.')
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone():p.error('Not a BlueHarbor database.')
        previous=backup() if target.exists() else None
        target.parent.mkdir(parents=True,exist_ok=True)
        handle=tempfile.NamedTemporaryFile(prefix='restore-',suffix='.sqlite3',dir=target.parent,delete=False);temp=Path(handle.name);handle.close()
        with closing(sqlite3.connect(temp)) as dest:check.backup(dest)
    if target.exists():
        with closing(sqlite3.connect(target)) as existing:existing.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    os.replace(temp,target)
    for suffix in ('-wal','-shm'):
        sidecar=Path(str(target)+suffix)
        if sidecar.exists():sidecar.unlink()
    print(f'Restored {source}. Previous database retained at {previous}. Restart the application.')

if __name__=='__main__':main()
