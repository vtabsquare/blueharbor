"""Supabase is the sole password authority; local/demo password login is removed."""
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

def login(h,c,d,S,staff=False):
    email=str(d.get('email','')).strip().lower();password=str(d.get('password',''))
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
            local_id=c.execute('INSERT INTO users(auth_uid,email,name,created) VALUES(?,?,?,?)',(uid,email,name,S.now())).lastrowid
            c.execute('INSERT INTO verification_cases(user_id) VALUES(?)',(local_id,))
            user=c.execute('SELECT * FROM users WHERE id=?',(local_id,)).fetchone()
    name='bh_cloud_staff' if staff else 'bh_cloud_buyer';path='/api/admin' if staff else '/'
    age=max(1,min(int(result.get('expires_in',3600)),28800));sessions='staff_sessions' if staff else 'sessions'
    c.execute(f'INSERT INTO {sessions} VALUES(?,?,?) ON CONFLICT(token) DO UPDATE SET expires=excluded.expires',(hashlib.sha256(token.encode()).hexdigest(),user['id'],int(time.time())+age))
    S.admin.record(c,user if staff else None,'STAFF_LOGIN' if staff else 'BUYER_LOGIN',user['id'],'Supabase Auth sign-in',topic='admin' if staff else 'buyer',uid=None if staff else user['id'])
    c.commit()
    h.send({'staff':S.admin.public_staff(user)} if staff else {'user':S.public_user(user)},cookie=f'{name}={token}; HttpOnly; SameSite=Strict; Path={path}; Max-Age={age}')
    return None

def signup(h,c,d,S):
    email=str(d.get('email','')).strip().lower();password=str(d.get('password',''));name=str(d.get('name','')).strip()
    if not d.get('consent') or not name or len(name)>150 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 12<=len(password)<=128:raise S.APIError('Provide your name, valid email, 12–128 character password and consent.')
    cloud.request('/auth/v1/signup',{'email':email,'password':password,'data':{'name':name}})
    return {'message':'If registration is available, check your email to confirm your account, then sign in.','confirmation_required':True}

def logout(h,c,S,staff=False):
    token=token_from(h,staff);name='bh_cloud_staff' if staff else 'bh_cloud_buyer';path='/api/admin' if staff else '/'
    c.execute('DELETE FROM '+('staff_sessions' if staff else 'sessions')+' WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    # Local application revocation is persisted even if Supabase is temporarily unreachable.
    c.commit()
    try:cloud.request('/auth/v1/logout?scope=local',{},token=token)
    except cloud.CloudError:pass
    h.send({'ok':True},cookie=f'{name}=; HttpOnly; SameSite=Strict; Path={path}; Max-Age=0')
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
        result=cloud.request('/auth/v1/admin/users',{'email':email,'password':password,'email_confirm':True,'user_metadata':{'name':name}},admin=True)
        uid=result.get('id') or result.get('user',{}).get('id')
        if not uid:raise S.APIError('Supabase did not return the new staff identity.',502)
        # If database mapping fails, the Auth account has no staff permissions.
        # Recover by linking its UUID using the provided bootstrap SQL, not by deleting users.
        sid=c.execute('INSERT INTO staff(auth_uid,email,name,role,active,created) VALUES(?,?,?,?,?,?)',(uid,email,name,role,active,S.now())).lastrowid
    A.record(c,staff,'STAFF_SAVED',sid,'Supabase-linked staff access updated',after={'name':name,'role':role,'active':active})
