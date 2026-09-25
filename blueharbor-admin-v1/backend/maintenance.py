"""PostgreSQL backup, offline restore, and staff password recovery for Supabase."""
import argparse
import os
import subprocess
from pathlib import Path
import cloud_config
import server

cloud_config.load()
DB_URL = os.environ.get('SUPABASE_DB_URL')

def backup():
    if not DB_URL: raise ValueError('SUPABASE_DB_URL is not set.')
    folder = server.ROOT / 'backend' / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    import secrets
    from urllib.parse import urlparse
    target = folder / (f"blueharbor-{server.now().replace(':','-')}-{secrets.token_hex(3)}.sql")
    print(f"Creating backup at {target}...")
    parsed = urlparse(DB_URL)
    is_local = parsed.hostname in ('127.0.0.1', 'localhost', 'supabase-kong')
    if is_local:
        # supabase db dump uses the bundled pg_dump matching the local PG version
        result = subprocess.run(
            ['supabase', 'db', 'dump', '--local', '-f', str(target)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f'supabase db dump failed: {result.stderr}')
    else:
        subprocess.run(['pg_dump', DB_URL, '-f', str(target), '--clean', '--if-exists', '--no-owner', '--no-privileges', '-n', 'blueharbor', '-n', 'public'], check=True)
    return target

def restore(source):
    if not DB_URL: raise ValueError('SUPABASE_DB_URL is not set.')
    print(f"Restoring from {source}...")
    subprocess.run(['psql', DB_URL, '-f', str(source)], check=True)
    print("Restore complete.")

def main():
    p = argparse.ArgumentParser(description='Run as the local database owner only.')
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('backup')
    rest = sub.add_parser('restore')
    rest.add_argument('source')
    rest.add_argument('--confirm', required=True, choices=['RESTORE'])
    
    reset = sub.add_parser('reset-staff-password')
    reset.add_argument('email')
    
    args = p.parse_args()
    if args.action == 'backup':
        print(backup())
        return
    
    if args.action == 'reset-staff-password':
        print("Note: Password resets for staff should now be performed via the Supabase Auth Dashboard.")
        return
        
    if args.action == 'restore':
        source = Path(args.source).resolve()
        if not source.is_file():
            p.error('Choose an existing backup file.')
        restore(source)

if __name__ == '__main__':
    main()
