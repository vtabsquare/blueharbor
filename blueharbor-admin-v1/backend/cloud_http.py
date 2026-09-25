import json
import urllib.request
import urllib.error
from urllib.parse import quote
import cloud_config as cfg

class CloudError(Exception):
    def __init__(self,message,status=502):self.message=message;self.status=status;super().__init__(message)

def request(path,data=None,method=None,token=None,admin=False,raw=False,mime='application/json',extra_headers=None):
    key=cfg.SECRET if admin else cfg.PUBLISHABLE
    headers={'apikey':key,'Content-Type':mime}
    if extra_headers:headers.update(extra_headers)
    # New sb_secret keys authenticate through apikey; JWT service-role keys also
    # supply Authorization for compatibility with legacy Supabase gateways.
    if token:headers['Authorization']='Bearer '+token
    elif admin and key.startswith('eyJ'):headers['Authorization']='Bearer '+key
    body=data if isinstance(data,bytes) else json.dumps(data).encode() if data is not None else None
    req=urllib.request.Request(cfg.URL+path,data=body,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            result=response.read(6*1024*1024)
            return result if raw else json.loads(result) if result else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors='replace')
        print(f"Supabase HTTP Error {exc.code} on {path}: {body}", flush=True)
        # Never return provider bodies, tokens, connection strings or SQL details.
        if '/auth/' in path and exc.code in (400,401,403,422):raise CloudError('Sign-in or account request was rejected. Check credentials, email confirmation and Supabase Auth settings.',401) from None
        if exc.code==429:raise CloudError('Supabase request limit reached. Wait a moment and try again.',429) from None
        raise CloudError(f'Supabase request failed ({exc.code}). Check project status, permissions and configuration.',502) from None
    except (OSError,ValueError):raise CloudError('Supabase is unavailable. Check your internet connection and project settings.',503) from None

def upload(path,content,mime):
    request('/storage/v1/object/'+cfg.BUCKET+'/'+quote(path,safe='/'),content,'POST',admin=True,mime=mime)
    return path
def download(path):
    if not isinstance(path,str) or '..' in path or path.startswith('/'):raise CloudError('Invalid stored object path.')
    return request('/storage/v1/object/'+cfg.BUCKET+'/'+quote(path,safe='/'),admin=True,raw=True)
def remove(paths):request('/storage/v1/object/'+cfg.BUCKET,{'prefixes':paths},'DELETE',admin=True)
