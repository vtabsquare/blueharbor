"""Loopback-only gateway. Supabase Auth, PostgreSQL and Storage are authoritative."""
import argparse
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import threading
import psycopg
import cloud_config
import uuid
from cryptography.fernet import Fernet
from app_mode import ROLE
import cloud_http
import supabase_auth
from postgres_store import db
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone, date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import admin_core as admin

def get_fernet():
    key = os.environ.get('BLUEHARBOR_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError('BLUEHARBOR_ENCRYPTION_KEY environment variable is required for secure document encryption.')
    return Fernet(key)

fernet = get_fernet()

admin.S = sys.modules[__name__]

ROOT = Path(__file__).resolve().parent.parent
BACKEND_KIND = 'supabase'
COUNTRIES = {'UAE': ['Business registration', 'Trade licence', 'Representative ID'], 'India': ['Business registration', 'Import export code', 'Representative ID'], 'Netherlands': ['Business registration', 'EORI registration', 'Representative ID']}
DESTINATIONS = ['Jebel Ali, UAE', 'Rotterdam, Netherlands', 'Singapore', 'Colombo, Sri Lanka', 'Mumbai, India']
SERVICES = {'Economy': 150000, 'Standard': 200000, 'Express': 320000}
WEB_PORT=int(os.environ.get('BLUEHARBOR_WEB_PORT','3000'))
WEB_PORTS=tuple(int(p) for p in os.environ.get('BLUEHARBOR_WEB_PORTS','3000,3001').split(','))
API_PORT=int(os.environ.get('BLUEHARBOR_API_PORT','8001'))

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def init():
    cloud_config.validate()
    with db() as c:
        c.execute('SELECT id FROM staff LIMIT 1')
        c.execute('SELECT lot_id FROM lot_arrivals LIMIT 1')
        c.execute('SELECT id FROM compliance_rule_sets LIMIT 1')
        c.execute('SELECT required_stage FROM compliance_rule_sets LIMIT 1')
        c.execute('SELECT id FROM transport_shipments LIMIT 1')
        c.execute('SELECT id FROM vessel_sailings LIMIT 1')
        if not c.execute("SELECT 1 FROM settings WHERE key='handling_cents'").fetchone():
            raise RuntimeError('Run Supabase scripts 01 and 02 before starting.')

def audit(c, uid, action, detail=''):
    c.execute('INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)',(uid,action,detail,now()))
    admin.change(c,'buyer',uid)

def notify(c, uid, message):
    c.execute('INSERT INTO notifications(user_id,message,created) VALUES(?,?,?)',(uid,message,now()))
    admin.change(c,'buyer',uid)
    from local_email import queue_status
    c.execute('INSERT INTO email_outbox(user_id,subject,body,status,created,updated) VALUES(?,?,?,?,?,?)',(uid,'BlueHarbor update',message,queue_status(c,uid),now(),now()))

def public_user(u):
    return {**{k:u[k] for k in ('id','email','name','company','country','registration','address','phone','verified')},'demo':False}

def valid_verification(c, u):
    docs = c.execute("SELECT d.kind,d.expiry FROM documents d LEFT JOIN document_reviews r ON r.document_id=d.id WHERE d.user_id=? AND COALESCE(r.status,'PENDING')!='REJECTED' AND d.rowid=(SELECT d2.rowid FROM documents d2 WHERE d2.user_id=d.user_id AND d2.kind=d.kind ORDER BY d2.created DESC,d2.rowid DESC LIMIT 1)",(u['id'],)).fetchall()
    valid = {d['kind'] for d in docs if d['expiry'] >= date.today().isoformat()}
    required=admin.rules(c).get(u['country'])
    return bool(required) and all(x in valid for x in required) and all(u[k].strip() for k in ('company','registration','address'))

class APIError(Exception):
    def __init__(self, message, status=400):
        self.message,self.status=message,status

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass  # Avoid storing personal data and session tokens in request logs.

    def send(self, value, status=200, cookie=None, mime='application/json', filename=None):
        data = json.dumps(value).encode() if mime=='application/json' else value
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if hasattr(self, 'request_id'):
            self.send_header('X-Request-ID', self.request_id)
        if cookie: self.send_header('Set-Cookie',cookie)
        if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def user(self,c): return supabase_auth.current(self,c)

    def do_GET(self): self.handle_api(False)
    def do_POST(self): self.handle_api(True)

    def handle_api(self, write):
        self.request_id = str(uuid.uuid4())
        start_time = time.time()
        def log_request(status, error=None):
            log_data = {
                'time': now(),
                'request_id': self.request_id,
                'method': self.command,
                'path': self.path,
                'status': status,
                'duration_ms': round((time.time() - start_time) * 1000, 2)
            }
            if error:
                log_data['error'] = error
            print(json.dumps(log_data), flush=True)

        try:
            self.check_surface(self.path.split('?')[0])
            # Reject DNS rebinding and cross-origin writes. Vite preserves Host.
            if self.headers.get('Host') not in tuple(f'{host}:{port}' for host in ('localhost','127.0.0.1') for port in (*WEB_PORTS,API_PORT)):
                raise APIError('Local access only.',403)
            if write and (self.headers.get('Origin') not in (None,*(f'http://{host}:{port}' for host in ('localhost','127.0.0.1') for port in WEB_PORTS)) or self.headers.get('X-BlueHarbor') != '1'):
                raise APIError('Request origin rejected.',403)
            if not write and self.path in ('/api/stream','/api/admin/stream'):
                log_request(200)
                return self.stream_changes(self.path.startswith('/api/admin/'))
            if not write and self.path.split('?')[0] == '/api/health':
                import realtime_bus
                
                # Check DB readiness
                db_ok = True
                try:
                    with db() as c:
                        c.execute("SELECT 1")
                except Exception:
                    db_ok = False
                    
                log_request(200 if db_ok else 503)
                return self.send({'status':'ok' if db_ok else 'error','service':'blueharbor-supabase','database':'Supabase PostgreSQL','db_connected':db_ok,'realtime':realtime_bus.status}, status=200 if db_ok else 503)
            data={}
            if write:
                length=int(self.headers.get('Content-Length','0'))
                if length<=0 or length>7200000: raise APIError('Request too large or empty.',413)
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict): raise APIError('Invalid request.')
            with db() as c:
                if write:c.execute('BEGIN IMMEDIATE')
                result=self.route(c,self.path.split('?')[0],data,write)
                c.commit()
            if result is not None: self.send(result)
            log_request(200)
        except APIError as e: 
            self.send({'error':e.message},e.status)
            log_request(e.status, e.message)
        except (ValueError,TypeError,KeyError): 
            self.send({'error':'Invalid input.'},400)
            log_request(400, 'Invalid input')
        except cloud_http.CloudError as e: 
            self.send({'error':e.message},e.status)
            log_request(e.status, e.message)
        except psycopg.IntegrityError as e: 
            self.send({'error':'This record conflicts with existing data. Check IDs, quantities and required links.'},409)
            log_request(409, str(e))
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.send({'error':'The request could not be completed. Please retry.'},500)
            log_request(500, f"{type(e).__name__}: {str(e)}\n{error_trace}")

    def check_surface(self,path):
        allowed = path == '/api/health' or (path.startswith('/api/admin/') if ROLE == 'admin' else path.startswith('/api/') and not path.startswith('/api/admin/'))
        if not allowed: raise APIError('This endpoint is not part of this application.',404)

    def route(self,c,path,d,write):
        self.check_surface(path)
        if path.startswith('/api/admin/'):
            return admin.route(self,c,path,d,write)
        if path.startswith('/api/product-image/') and not write:
            self.user(c)
            image_id=path.rsplit('/',1)[-1]
            row=c.execute('SELECT i.* FROM product_images i JOIN product_admin p ON p.image=? AND p.published=1 WHERE i.id=?',(path,image_id)).fetchone()
            if not row:raise APIError('Image not found.',404)
            self.send(row['content'],mime=row['mime']);return None
        if path=='/api/catalog' and not write:
            from command_core import priced
            try: self.user(c)
            except cloud_http.CloudError as e:
                if e.status!=401: raise
                return {'products':[],'tanks':[],'countries':admin.rules(c),'destinations':admin.destinations(c),'services':admin.services(c),'handling_cents':admin.settings(c)['handling_cents'],'demo_available':False}
            rows=c.execute("SELECT p.*,s.region,s.export_port,s.facility,a.image,COALESCE((SELECT SUM(l.available_kg) FROM lots l LEFT JOIN lot_admin la ON la.lot_id=l.id WHERE l.product_id=p.id AND l.expiry>=? AND COALESCE(la.quality,'RELEASED')='RELEASED'),0) available_kg FROM products p JOIN product_admin a ON a.product_id=p.id LEFT JOIN product_sources s ON s.product_id=p.id WHERE a.published=1 ORDER BY p.id",(date.today().isoformat(),)).fetchall()
            tanks=c.execute("SELECT t.id,t.zone,l.product_id,CASE WHEN a.quality='RELEASED' AND l.expiry>=? THEN l.available_kg ELSE 0 END available_kg,l.reserved_kg,p.name FROM tanks t JOIN lots l ON l.id=t.lot_id JOIN products p ON p.id=l.product_id JOIN product_admin pa ON pa.product_id=p.id JOIN lot_admin a ON a.lot_id=l.id WHERE pa.published=1 ORDER BY t.id",(date.today().isoformat(),)).fetchall()
            return {'products':[priced(c,r) for r in rows],'tanks':[dict(r) for r in tanks],'countries':admin.rules(c),'destinations':admin.destinations(c),'services':admin.services(c),'handling_cents':admin.settings(c)['handling_cents'],'demo_available':False}
        if path=='/api/register' and write:return supabase_auth.signup(self,c,d,sys.modules[__name__])
        if path=='/api/login' and write:return supabase_auth.login(self,c,d,sys.modules[__name__])
        u=self.user(c); uid=u['id']
        if path=='/api/state' and not write:
            orders=[dict(r) for r in c.execute('SELECT * FROM orders WHERE user_id=? ORDER BY created DESC',(uid,))]
            for order in orders:
                order['events']=[dict(r) for r in c.execute('SELECT * FROM events WHERE order_id=? ORDER BY id',(order['id'],))]
                shipment=c.execute('SELECT * FROM shipments WHERE order_id=?',(order['id'],)).fetchone()
                order['shipment']=dict(shipment) if shipment else None
                order['documents']=[dict(r) for r in c.execute('SELECT id,kind,name,version,created FROM trade_documents WHERE order_id=? AND published=1 ORDER BY created DESC',(order['id'],))]
            return {'user':public_user(u),'orders':orders,'documents':[dict(r) for r in c.execute('SELECT id,kind,name,mime,expiry,created,length(content) size FROM documents WHERE user_id=? ORDER BY created DESC',(uid,))], 'notifications':[dict(r) for r in c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC',(uid,))]}
        if path=='/api/logout' and write:return supabase_auth.logout(self,c,sys.modules[__name__])
        if path=='/api/profile' and write:
            country=d.get('country')
            if country not in admin.rules(c): raise APIError('Select a supported country.')
            fields=[str(d.get(k,'')).strip() for k in ('name','company','registration','address','phone')]
            if not fields[0] or any(len(v)>500 for v in fields): raise APIError('Invalid profile fields.')
            c.execute("UPDATE users SET name=?,company=?,registration=?,address=?,phone=?,country=?,verified='DRAFT' WHERE id=?",(*fields,country,uid))
            admin.case_revision(c,uid)
            audit(c,uid,'profile_updated'); return {'ok':True}
        if path=='/api/export' and write:
            orders=[dict(r) for r in c.execute('SELECT * FROM orders WHERE user_id=?',(uid,))]
            docs=[dict(r) for r in c.execute('SELECT id,kind,name,created FROM documents WHERE user_id=?',(uid,))]
            audit(c,uid,'data_exported')
            return {'user':public_user(u),'orders':orders,'documents':docs}
        if path=='/api/delete-account' and write:
            # Delete PII but retain immutable audit records (they only contain IDs).
            c.execute('DELETE FROM documents WHERE user_id=?',(uid,))
            c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
            c.execute("UPDATE users SET email='deleted@example.com', name='Deleted User', company='Deleted', address='', phone='', auth_uid='' WHERE id=?",(uid,))
            audit(c,uid,'account_deleted')
            # Trigger Supabase auth deletion in the background or instruct admin.
            return {'ok':True}
        if path=='/api/documents' and write:
            if d.get('kind') not in admin.rules(c).get(u['country'],[]): raise APIError('Unsupported document type.')
            expiry=str(d.get('expiry',''))
            if date.fromisoformat(expiry)<date.today(): raise APIError('Document is expired.')
            content=base64.b64decode(d.get('content',''),validate=True)
            if not content or len(content)>5*1024*1024: raise APIError('Upload a file smaller than 5 MB.')
            mime='application/pdf' if content.startswith(b'%PDF-') else 'image/png' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else None
            if not mime: raise APIError('Only PDF, PNG, and JPEG are accepted.')
            name=Path(str(d.get('name','document'))).name[:120]
            encrypted_content = fernet.encrypt(content)
            c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',(secrets.token_hex(12),uid,d['kind'],name,mime,encrypted_content,expiry,now()))
            c.execute("UPDATE users SET verified='DRAFT' WHERE id=?",(uid,))
            admin.case_revision(c,uid)
            audit(c,uid,'document_uploaded',d['kind']); return {'ok':True}
        if path.startswith('/api/document/') and not write:
            row=c.execute('SELECT * FROM documents WHERE id=? AND user_id=?',(path.rsplit('/',1)[-1],uid)).fetchone()
            if not row: raise APIError('Document not found.',404)
            ext={'application/pdf':'pdf','image/png':'png','image/jpeg':'jpg','text/plain':'txt'}[row['mime']]
            decrypted = fernet.decrypt(row['content']) if row['content'].startswith(b'gAAAAA') else row['content']
            self.send(decrypted,mime=row['mime'],filename=f'document-{row["id"]}.{ext}'); return None
        if path=='/api/verification' and write:
            if not valid_verification(c,u): raise APIError('Complete company details and upload all required unexpired documents.')
            c.execute("UPDATE users SET verified='UNDER_REVIEW' WHERE id=?",(uid,))
            admin.case_revision(c,uid)
            c.execute('UPDATE verification_cases SET submitted=? WHERE user_id=?',(now(),uid))
            notify(c,uid,'Verification submitted. Awaiting operator review.')
            audit(c,uid,'verification_submitted'); return {'ok':True}
        if path=='/api/ai-review' and write:
            raise APIError('Automated verification is not enabled. Authorized staff review every case.',403)
        if path=='/api/orders' and write:
            c.execute('BEGIN IMMEDIATE')
            u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if u['verified']!='VERIFIED' or not valid_verification(c,u): raise APIError('An approved buyer with valid documents is required.',403)
            kg=d.get('kg'); pid=d.get('product_id'); key=str(d.get('request_key',''))
            if type(kg)!=int or kg<=0 or len(key)<16 or len(key)>100: raise APIError('Enter a whole kilogram quantity and valid request key.')
            fingerprint=json.dumps([pid,kg,d.get('destination'),d.get('service')])
            old=c.execute('SELECT id,fingerprint FROM orders WHERE user_id=? AND request_key=?',(uid,key)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint: raise APIError('Request key already used for another order.',409)
                return {'id':old['id']}
            p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
            pub=c.execute('SELECT published FROM product_admin WHERE product_id=?',(pid,)).fetchone()
            if not p or not pub or not pub[0] or kg<p['minimum_kg']: raise APIError('Product is unavailable or quantity is below its minimum.')
            from command_core import priced
            p=priced(c,p)
            shipping_services=admin.services(c)
            if d.get('destination') not in admin.destinations(c) or d.get('service') not in shipping_services: raise APIError('Select a valid route and shipping service.')
            lots=c.execute("SELECT l.* FROM lots l LEFT JOIN lot_admin a ON a.lot_id=l.id WHERE product_id=? AND expiry>=? AND COALESCE(a.quality,'RELEASED')='RELEASED' ORDER BY expiry,l.id",(pid,date.today().isoformat())).fetchall()
            if sum(x['available_kg'] for x in lots)<kg: raise APIError('Insufficient stock. Refresh availability.',409)
            oid='BH-'+secrets.token_hex(5).upper(); shipping=shipping_services[d['service']]; total=kg*p['cents_per_kg']+shipping+admin.settings(c)['handling_cents']
            c.execute('INSERT INTO orders(id,user_id,product_id,product_name,kg,cents_per_kg,shipping,total,destination,service,created,request_key,fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,uid,pid,p['name'],kg,p['cents_per_kg'],shipping,total,d['destination'],d['service'],now(),key,fingerprint))
            left=kg
            for lot in lots:
                take=min(left,lot['available_kg'])
                if take:
                    c.execute('UPDATE lots SET available_kg=available_kg-?,reserved_kg=reserved_kg+? WHERE id=?',(take,take,lot['id']))
                    c.execute('INSERT INTO allocations VALUES(?,?,?)',(oid,lot['id'],take)); left-=take
                    admin.movement(c,lot['id'],'RESERVE',-take,take,'Buyer order confirmed',order=oid)
            c.execute('INSERT INTO events(order_id,title,note,created) VALUES(?,?,?,?)',(oid,'Order confirmed','Inventory reserved. Awaiting warehouse processing. No payment collected.',now()))
            notify(c,uid,f'{oid} confirmed. Inventory reserved; no payment collected.')
            admin.change(c,'catalog')
            audit(c,uid,'order_confirmed',oid); return {'id':oid}
        if path=='/api/cancel' and write:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(d.get('id'),uid)).fetchone()
            if not row: raise APIError('Order not found.',404)
            if row['status']=='CANCELLED': return {'ok':True}
            if row['status']!='CONFIRMED': raise APIError('Processing has started. Contact the operator.',409)
            for a in c.execute('SELECT * FROM allocations WHERE order_id=?',(row['id'],)).fetchall():
                c.execute('UPDATE lots SET available_kg=available_kg+?,reserved_kg=reserved_kg-? WHERE id=?',(a['kg'],a['kg'],a['lot_id']))
                admin.movement(c,a['lot_id'],'CANCEL',a['kg'],-a['kg'],'Buyer cancelled',order=row['id'])
            c.execute("UPDATE orders SET status='CANCELLED' WHERE id=?",(row['id'],))
            c.execute('INSERT INTO events(order_id,title,note,created) VALUES(?,?,?,?)',(row['id'],'Cancelled','Reservation released.',now()))
            admin.change(c,'catalog')
            audit(c,uid,'order_cancelled',row['id']); notify(c,uid,f'{row["id"]} cancelled. Stock released.'); return {'ok':True}
        if path.startswith('/api/trade-document/') and not write:
            row=c.execute('SELECT t.* FROM trade_documents t JOIN orders o ON o.id=t.order_id WHERE t.id=? AND t.published=1 AND o.user_id=?',(path.rsplit('/',1)[-1],uid)).fetchone()
            if not row:raise APIError('Document not found.',404)
            decrypted = fernet.decrypt(row['content']) if row['content'].startswith(b'gAAAAA') else row['content']
            self.send(decrypted,mime=row['mime'],filename=row['id']+'.'+('pdf' if row['mime']=='application/pdf' else 'png' if row['mime']=='image/png' else 'jpg'));return None
        if path=='/api/read-notifications' and write:
            c.execute('UPDATE notifications SET seen=1 WHERE user_id=?',(uid,)); return {'ok':True}
        if path.startswith('/api/confirmation/') and not write:
            o=c.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(path.rsplit('/',1)[-1],uid)).fetchone()
            if not o: raise APIError('Order not found.',404)
            lines=[('Order',o['id']),('Created',o['created']),('Status',o['status']),('Product',o['product_name']),('Quantity',str(o['kg'])+' kg'),('Destination',o['destination']),('Shipping service',o['service']),('Estimated total',f'USD {o["total"]/100:,.2f}')]
            body='<!doctype html><meta charset="utf-8"><title>Order confirmation</title><style>body{font:16px Arial;max-width:780px;margin:60px auto;padding:24px}h1{color:#075e66}td{padding:12px;border-bottom:1px solid #ddd}table{width:100%}</style><h1>BlueHarbor · Order confirmation</h1><p>Local POC · No payment collected. Not a tax invoice.</p><table>'+''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(v)+'</td></tr>' for k,v in lines)+'</table><p>Configured estimates only. This document does not certify legal or regulatory compliance.</p>'
            self.send(body.encode(),mime='text/html; charset=utf-8',filename=o['id']+'.html'); return None
        raise APIError('Not found.',404)

    def stream_changes(self, is_admin):
        with db() as c:
            user=admin.staff_user(self,c) if is_admin else self.user(c)
            cursor=c.execute('SELECT COALESCE(MAX(id),0) FROM changes').fetchone()[0]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.send_header('X-Accel-Buffering','no');self.end_headers()
        import realtime_bus
        generation=realtime_bus.generation
        try:
            self.wfile.write(b'retry: 3000\nevent: ready\ndata: connected\n\n');self.wfile.flush()
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                generation=realtime_bus.wait(generation,timeout=10)
                with db() as c:
                    try: user=admin.staff_user(self,c) if is_admin else self.user(c)
                    except (APIError,cloud_http.CloudError):
                        self.wfile.write(b'event: session-ended\ndata: expired\n\n');self.wfile.flush();return
                    latest=c.execute('SELECT COALESCE(MAX(id),0) FROM changes').fetchone()[0]
                    changed=is_admin and latest>cursor or c.execute("SELECT 1 FROM changes WHERE id>? AND (topic IN ('catalog','catalog-refresh') OR (topic='buyer' AND user_id=?)) LIMIT 1",(cursor,user['id'])).fetchone()
                self.wfile.write(b'event: refresh\ndata: changed\n\n' if changed else b': heartbeat\n\n');self.wfile.flush();cursor=latest
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError,OSError):pass
        self.close_connection=True

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=API_PORT)
    args=parser.parse_args(); init()
    from operations_monitor import start_worker
    stop_worker=start_worker() if ROLE == 'admin' else threading.Event()
    import realtime_bus
    realtime_bus.start(stop_worker)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'BlueHarbor {ROLE} Supabase API: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: stop_worker.set();server.server_close()

if __name__=='__main__':
    try: main()
    except RuntimeError as e: print(str(e),flush=True);sys.exit(1)
    except psycopg.Error as e: print(e, flush=True); print('Cannot initialize Supabase PostgreSQL. Check the session-pooler URI, database password, network access, and SQL scripts 01/02. Credentials were not printed.',flush=True);sys.exit(1)
