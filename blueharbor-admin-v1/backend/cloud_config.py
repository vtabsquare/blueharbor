"""Server-only configuration. No credentials are sent to either frontend."""
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
def load():
    file=ROOT/'backend'/'.env'
    if file.exists():
        for line in file.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:continue
            key,value=line.split('=',1)
            os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
load()
URL=os.environ.get('SUPABASE_URL', '').rstrip('/')
PUBLISHABLE=os.environ.get('SUPABASE_PUBLISHABLE_KEY','')
SECRET=os.environ.get('SUPABASE_SECRET_KEY','')
DSN=os.environ.get('SUPABASE_DB_URL','')
BUCKET='blueharbor-private'
def validate():
    placeholders=('YOUR_','YOUR-','REPLACE','PASTE','[PASSWORD]')
    missing=[k for k in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY','SUPABASE_SECRET_KEY','SUPABASE_DB_URL', 'BLUEHARBOR_ENCRYPTION_KEY') if not os.environ.get(k) or any(p in os.environ[k].upper() for p in placeholders)]
    if missing:raise RuntimeError('Complete backend/.env settings for this application: '+', '.join(missing))
    parsed=urlparse(URL)
    is_local = parsed.hostname in ('127.0.0.1', 'localhost', 'supabase-kong')
    if not is_local and (parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co')):raise RuntimeError('Use your HTTPS Supabase project URL.')
    if not DSN.startswith(('postgres://','postgresql://')):raise RuntimeError('Use the Postgres connection URI from Supabase Connect.')
