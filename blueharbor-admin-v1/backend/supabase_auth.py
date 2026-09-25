"""Supabase is the sole password authority; local/demo password login is removed."""
import os
import hashlib
import re
import time
from http.cookies import SimpleCookie
import cloud_http as cloud

def token_from(h,staff=False):
    cookie=SimpleCookie(h.headers.get('Cookie','')).get('bh_cloud_staff' if staff else 'bh_cloud_buyer')
    return cookie.value if cookie else ''

def current(h,c,staff=False):
    token=token_from(h,staff)
    if not token:raise cloud.CloudError('Please sign in'+(' as staff.' if staff else '.'),401)
    table='staff' if staff else 'users';sessions='staff_sessions' if staff else 'sessions';fk='staff_id' if staff else 'user_id'
    # The SHA-256 token hash stored at login is the sole authentication gate.
    # Re-verifying with Supabase on every request causes 500 cascades when
    # Supabase is slow (cold-starts, transient latency, rate-limits).
    row=c.execute(f'SELECT u.* FROM {table} u JOIN {sessions} s ON s.{fk}=u.id WHERE s.token=? AND s.expires>?'+(' AND u.active=1' if staff else ''),(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
    if not row:raise cloud.CloudError('Session expired. Please sign in again.',401)
    return row


def sso_login(h,c,d,S,staff=False):
    token=d.get('access_token')
    if not token: raise S.APIError('Missing access token')
    result = {'access_token': token, 'expires_in': d.get('expires_in', 3600)}
    try:
        user_info = cloud.request('/auth/v1/user', method='GET', token=token)
    except cloud.CloudError:
        raise S.APIError('Invalid SSO token', 403)

    uid=user_info.get('id')
    email=user_info.get('email','').lower()

    if staff:
        user=c.execute('SELECT * FROM staff WHERE auth_uid=? AND active=1',(uid,)).fetchone()
        if not user:raise S.APIError('This account has no active staff access. Ask your administrator.',403)
    else:
        user=c.execute('SELECT * FROM users WHERE auth_uid=?',(uid,)).fetchone()
        if not user:
            name=str(email.split('@')[0])[:150]
            existing=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if existing:
                c.execute('UPDATE users SET auth_uid=? WHERE id=?',(uid,existing['id']))
                local_id=existing['id']
                if not c.execute('SELECT 1 FROM verification_cases WHERE user_id=?',(local_id,)).fetchone():
                    c.execute('INSERT INTO verification_cases(user_id) VALUES(?)',(local_id,))
            else:
                local_id=c.execute('INSERT INTO users(auth_uid,email,name,created) VALUES(?,?,?,?)',(uid,email,name,S.now())).lastrowid
                c.execute('INSERT INTO verification_cases(user_id) VALUES(?)',(local_id,))
            user=c.execute('SELECT * FROM users WHERE id=?',(local_id,)).fetchone()

    name='bh_cloud_staff' if staff else 'bh_cloud_buyer';path='/api/admin' if staff else '/'
    age=max(1,min(int(result.get('expires_in',3600)),28800));sessions='staff_sessions' if staff else 'sessions'
    c.execute(f'INSERT INTO {sessions} VALUES(?,?,?) ON CONFLICT(token) DO UPDATE SET expires=excluded.expires',(hashlib.sha256(token.encode()).hexdigest(),user['id'],int(time.time())+age if 'time' in locals() else int(S.time.time())+age))
    S.admin.record(c,user if staff else None,'STAFF_LOGIN' if staff else 'BUYER_LOGIN',user['id'],'Supabase SSO sign-in',topic='admin' if staff else 'buyer',uid=None if staff else user['id'])
    c.commit()
    import os
    secure_flag = '; Secure' if os.environ.get('NODE_ENV', 'production') == 'production' else ''
    h.send({'staff':S.admin.public_staff(user)} if staff else {'user':S.public_user(user)},cookie=f'{name}={token}; HttpOnly{secure_flag}; SameSite=Strict; Path={path}; Max-Age={age}')
    return None

def login(h,c,d,S,staff=False):
    email=str(d.get('email','')).strip().lower();password=str(d.get('password',''))
    token_input=d.get('access_token')
    if token_input:
        # SSO / OAuth flow: verify token directly
        result=cloud.request('/auth/v1/user',{},token=token_input)
        identity=result
        uid=identity.get('id'); token=token_input
        email=identity.get('email', '')
    else:
        # Password flow
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not password:raise S.APIError('Enter your email and password.')
        result=cloud.request('/auth/v1/token?grant_type=password',{'email':email,'password':password})
        identity=result.get('user',{});uid=identity.get('id');token=result.get('access_token')
    if not uid or not token or not identity.get('email_confirmed_at'):raise S.APIError('Confirm your email in Supabase before signing in.',403)
    if staff:
        user=c.execute('SELECT * FROM staff WHERE auth_uid=? AND active=1',(uid,)).fetchone()
        if not user:raise S.APIError('This account has no active staff access. Ask your administrator.',403)
    else:
        # Supabase-confirmed identity only; no client-supplied role or verification state.
        user=c.execute('SELECT * FROM users WHERE auth_uid=?',(uid,)).fetchone()
        if not user:
            name=str(identity.get('user_metadata',{}).get('name') or email.split('@')[0])[:150]
            existing=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if existing:
                c.execute('UPDATE users SET auth_uid=? WHERE id=?',(uid,existing['id']))
                local_id=existing['id']
                if not c.execute('SELECT 1 FROM verification_cases WHERE user_id=?',(local_id,)).fetchone():
                    c.execute('INSERT INTO verification_cases(user_id) VALUES(?)',(local_id,))
            else:
                local_id=c.execute('INSERT INTO users(auth_uid,email,name,created) VALUES(?,?,?,?)',(uid,email,name,S.now())).lastrowid
                c.execute('INSERT INTO verification_cases(user_id) VALUES(?)',(local_id,))
            user=c.execute('SELECT * FROM users WHERE id=?',(local_id,)).fetchone()
    name='bh_cloud_staff' if staff else 'bh_cloud_buyer';path='/api/admin' if staff else '/'
    age=max(1,min(int(result.get('expires_in',3600)),28800));sessions='staff_sessions' if staff else 'sessions'
    c.execute(f'INSERT INTO {sessions} VALUES(?,?,?) ON CONFLICT(token) DO UPDATE SET expires=excluded.expires',(hashlib.sha256(token.encode()).hexdigest(),user['id'],int(time.time())+age))
    S.admin.record(c,user if staff else None,'STAFF_LOGIN' if staff else 'BUYER_LOGIN',user['id'],'Supabase Auth sign-in',topic='admin' if staff else 'buyer',uid=None if staff else user['id'])
    c.commit()
    secure_flag = '; Secure' if os.environ.get('NODE_ENV', 'production') == 'production' else ''
    h.send({'staff':S.admin.public_staff(user)} if staff else {'user':S.public_user(user)},cookie=f'{name}={token}; HttpOnly{secure_flag}; SameSite=Strict; Path={path}; Max-Age={age}')
    return None

def signup(h,c,d,S):
    email=str(d.get('email','')).strip().lower();password=str(d.get('password',''));name=str(d.get('name','')).strip()
    if not d.get('consent') or not name or len(name)>150 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 12<=len(password)<=128:raise S.APIError('Provide your name, valid email, 12–128 character password and consent.')
    origin=h.headers.get('Origin')
    if not origin:
        host=h.headers.get('Host')
        if host:
            proto=h.headers.get('X-Forwarded-Proto', 'http' if host.startswith('localhost') else 'https')
            origin=f"{proto}://{host}"
    extra_headers={'Redirect-To': origin} if origin else None
    cloud.request('/auth/v1/signup',{'email':email,'password':password,'data':{'name':name}}, extra_headers=extra_headers)
    return {'message':'If registration is available, check your email to confirm your account, then sign in.','confirmation_required':True}

def logout(h,c,S,staff=False):
    token=token_from(h,staff);name='bh_cloud_staff' if staff else 'bh_cloud_buyer';path='/api/admin' if staff else '/'
    c.execute('DELETE FROM '+('staff_sessions' if staff else 'sessions')+' WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    # Local application revocation is persisted even if Supabase is temporarily unreachable.
    c.commit()
    try:cloud.request('/auth/v1/logout?scope=local',{},token=token)
    except cloud.CloudError:pass
    secure_flag = '; Secure' if os.environ.get('NODE_ENV', 'production') == 'production' else ''
    h.send({'ok':True},cookie=f'{name}=; HttpOnly{secure_flag}; SameSite=Strict; Path={path}; Max-Age=0')
    return None

def staff_change(c,staff,action,d,S):
    A=S.admin
    if action=='password':
        old=A.text(d,'current_password',128);new=A.text(d,'password',128)
        if len(new)<12:raise S.APIError('Use at least 12 characters.')
        result=cloud.request('/auth/v1/token?grant_type=password',{'email':staff['email'],'password':old})
        if str(result['user']['id'])!=str(staff['auth_uid']):raise S.APIError('Identity mismatch.',403)
        cloud.request('/auth/v1/user',{'password':new},'PUT',token=result['access_token'])
        c.execute('DELETE FROM staff_sessions WHERE staff_id=?',(staff['id'],))
        c.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE auth_uid=?)',(staff['auth_uid'],))
        A.record(c,staff,'PASSWORD_CHANGED',staff['id'],'Password changed in Supabase Auth; sign in again');return
    A.require(staff);sid=d.get('id');role=A.text(d,'role');name=A.text(d,'name');active=A.integer(d,'active',0,1);email=A.text(d,'email',254).lower()
    if role not in ('ADMIN','VERIFIER','OPERATIONS'):raise S.APIError('Invalid staff role.')
    if sid:
        old=c.execute('SELECT * FROM staff WHERE id=?',(sid,)).fetchone()
        if not old:raise S.APIError('Staff account not found.',404)
        if email!=old['email']:raise S.APIError('Change account email through Supabase Auth; staff email cannot be changed here.')
        if sid==staff['id'] and (role!='ADMIN' or not active):raise S.APIError('You cannot remove your own administrator access.')
        if old['role']=='ADMIN' and old['active'] and (role!='ADMIN' or not active) and c.execute("SELECT COUNT(*) FROM staff WHERE role='ADMIN' AND active=1").fetchone()[0]<=1:raise S.APIError('Keep at least one active administrator.')
        c.execute('UPDATE staff SET name=?,role=?,active=? WHERE id=?',(name,role,active,sid))
        c.execute('DELETE FROM staff_sessions WHERE staff_id=?',(sid,))
    else:
        password=A.text(d,'password',128)
        if len(password)<12:raise S.APIError('Use at least 12 characters.')
        # Try to create the user; if already exists, look up and reuse the UUID.
        try:
            result=cloud.request('/auth/v1/admin/users',{'email':email,'password':password,'email_confirm':True,'user_metadata':{'name':name}},admin=True)
            uid=result.get('id') or result.get('user',{}).get('id')
        except cloud.CloudError:
            # User already exists in Supabase Auth (e.g. from a previous test run).
            existing_resp=cloud.request('/auth/v1/admin/users?email='+email,{},method='GET',admin=True)
            existing_users=existing_resp.get('users') or []
            match=[u for u in existing_users if u.get('email','').lower()==email]
            if not match:raise S.APIError('Supabase Auth rejected the request. Check project limits and configuration.',502)
            uid=match[0]['id']
            # Update the password so the staff can sign in with the specified password.
            cloud.request('/auth/v1/admin/users/'+uid,{'password':password,'email_confirm':True},method='PUT',admin=True)
        if not uid:raise S.APIError('Supabase did not return the new staff identity.',502)
        # If database mapping fails, the Auth account has no staff permissions.
        # Recover by linking its UUID using the provided bootstrap SQL, not by deleting users.
        # Check if this auth_uid is already in staff table
        existing_staff=c.execute('SELECT * FROM staff WHERE auth_uid=?',(uid,)).fetchone()
        if existing_staff:
            sid=existing_staff['id']
            c.execute('UPDATE staff SET name=?,role=?,active=? WHERE id=?',(name,role,active,sid))
        else:
            sid=c.execute('INSERT INTO staff(auth_uid,email,name,role,active,created) VALUES(?,?,?,?,?,?)',(uid,email,name,role,active,S.now())).lastrowid
    A.record(c,staff,'STAFF_SAVED',sid,'Supabase-linked staff access updated',after={'name':name,'role':role,'active':active})
