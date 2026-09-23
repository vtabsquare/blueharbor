"""Shared administrative operations. No buyer endpoint may invoke staff actions."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import sys
import supabase_auth
import time
from datetime import date, datetime, timedelta, timezone
from http.cookies import SimpleCookie

# Set by server after import, avoiding a second __main__ server module/database.
S = None

def rules(c): return {r['country']:json.loads(r['requirements']) for r in c.execute('SELECT * FROM country_rules')}
def services(c): return {r['name']:r['cents'] for r in c.execute('SELECT * FROM shipping_services')}
def destinations(c): return [r[0] for r in c.execute('SELECT name FROM destinations ORDER BY name')]
def settings(c): return {r['key']:json.loads(r['value']) for r in c.execute('SELECT * FROM settings')}
def change(c, topic='admin', uid=None):
    c.execute('INSERT INTO changes(topic,user_id,created) VALUES(?,?,?)',(topic,uid,S.now()))
    if topic=='catalog':
        from operations_monitor import monitor
        monitor(c)
def record(c, staff, action, entity, reason, before=None, after=None, topic='admin', uid=None):
    c.execute('INSERT INTO admin_audit(staff_id,action,entity,reason,before_json,after_json,created) VALUES(?,?,?,?,?,?,?)',(staff['id'] if staff else None,action,str(entity),reason,json.dumps(before or {},default=str),json.dumps(after or {},default=str),S.now()))
    change(c,topic,uid)
def text(d,key,limit=500,required=True):
    value=str(d.get(key,'')).strip()
    if (required and not value) or len(value)>limit: raise S.APIError(f'Enter a valid {key.replace("_"," ")}.')
    return value
def integer(d,key,minimum=0,maximum=100000000):
    value=d.get(key)
    if type(value)!=int or not minimum<=value<=maximum: raise S.APIError(f'{key} must be a whole number between {minimum} and {maximum}.')
    return value
def require(staff,*roles):
    if staff['role'] not in ('ADMIN',*roles): raise S.APIError('Your staff role does not allow this action.',403)
def staff_user(h,c): return supabase_auth.current(h,c,staff=True)

def public_staff(row): return {k:row[k] for k in ('id','email','name','role','active')}
def case_revision(c,uid):
    c.execute('INSERT OR IGNORE INTO verification_cases(user_id) VALUES(?)',(uid,))
    c.execute('UPDATE verification_cases SET revision=revision+1,decided=NULL,decision_by=NULL WHERE user_id=?',(uid,))
def movement(c,lot,kind,available,reserved,reason,staff=None,order=None):
    c.execute('INSERT INTO stock_movements(lot_id,kind,available_delta,reserved_delta,reason,staff_id,order_id,created) VALUES(?,?,?,?,?,?,?,?)',(lot,kind,available,reserved,reason,staff,order,S.now()))
def valid_date(value,optional=False):
    if not value and optional:return ''
    return date.fromisoformat(str(value)).isoformat()

def route(h,c,path,d,write):
    endpoint=path.removeprefix('/api/admin/')
    if endpoint=='login' and write:return supabase_auth.login(h,c,d,S,staff=True)
    staff=staff_user(h,c)
    if endpoint=='logout' and write:return supabase_auth.logout(h,c,S,staff=True)
    if endpoint=='state' and not write: return snapshot(c,staff)
    if endpoint.startswith('product-image/') and not write:
        require(staff,'OPERATIONS');row=c.execute('SELECT * FROM product_images WHERE id=?',(endpoint.split('/')[-1],)).fetchone()
        if not row:raise S.APIError('Image not found.',404)
        h.send(row['content'],mime=row['mime']);return None
    if endpoint.startswith('buyer/') and not write:
        require(staff,'VERIFIER');uid=int(endpoint.split('/')[-1]);u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not u:raise S.APIError('Buyer not found.',404)
        case=c.execute('SELECT * FROM verification_cases WHERE user_id=?',(uid,)).fetchone()
        docs=[dict(r) for r in c.execute("SELECT d.id,d.kind,d.name,d.mime,d.expiry,d.created,length(content) size,COALESCE(r.status,'PENDING') review_status,COALESCE(r.note,'') review_note FROM documents d LEFT JOIN document_reviews r ON r.document_id=d.id WHERE d.user_id=? ORDER BY d.created DESC,d.rowid DESC",(uid,))]
        return {'buyer':S.public_user(u),'case':dict(case) if case else {'revision':1},'documents':docs,'required':rules(c).get(u['country'],[])}
    if endpoint.startswith('document/') and not write:
        require(staff,'VERIFIER');row=c.execute('SELECT * FROM documents WHERE id=?',(endpoint.split('/')[-1],)).fetchone()
        if not row:raise S.APIError('Document not found.',404)
        decrypted = S.fernet.decrypt(row['content']) if row['content'].startswith(b'gAAAAA') else row['content']
        h.send(decrypted,mime=row['mime']);return None
    if not write:
        return downloads(h,c,staff,endpoint)
    # All administrative writes are serialized; stale edits are rejected where needed.
    c.execute('BEGIN IMMEDIATE')
    if endpoint=='verification':
        require(staff,'VERIFIER');uid=integer(d,'user_id',1);reason=text(d,'reason',2000);status=text(d,'status');revision=integer(d,'revision',1)
        if status not in ('VERIFIED','REJECTED','ADDITIONAL_INFORMATION_REQUIRED','SUSPENDED','UNDER_REVIEW'):raise S.APIError('Invalid verification decision.')
        u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone();case=c.execute('SELECT * FROM verification_cases WHERE user_id=?',(uid,)).fetchone()
        if not u or not case:raise S.APIError('Buyer not found.',404)
        if revision!=case['revision']:raise S.APIError('This case changed. Reload before making a decision.',409)
        if status=='VERIFIED':
            if u['verified']!='UNDER_REVIEW' or not S.valid_verification(c,u):raise S.APIError('Buyer must submit complete, unexpired documents for review.',409)
            for kind in rules(c).get(u['country'],[]):
                doc=c.execute('SELECT d.id,r.status FROM documents d LEFT JOIN document_reviews r ON r.document_id=d.id WHERE d.user_id=? AND d.kind=? ORDER BY d.created DESC,d.rowid DESC LIMIT 1',(uid,kind)).fetchone()
                if not doc or doc['status']!='APPROVED':raise S.APIError('Review and approve each current required document first.',409)
        c.execute('UPDATE users SET verified=? WHERE id=?',(status,uid))
        c.execute('UPDATE verification_cases SET note=?,decision_by=?,decided=?,revision=revision+1 WHERE user_id=?',(reason,staff['id'],S.now(),uid))
        S.notify(c,uid,f'Verification: {status.replace("_"," ")}. {reason}')
        record(c,staff,'BUYER_DECISION',uid,reason,{'status':u['verified']},{'status':status},'buyer',uid)
    elif endpoint=='document-review':
        require(staff,'VERIFIER');did=text(d,'id');status=text(d,'status');reason=text(d,'reason',2000)
        if status not in ('APPROVED','REJECTED','PENDING'):raise S.APIError('Invalid document review.')
        doc=c.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone()
        if not doc:raise S.APIError('Document not found.',404)
        if status=='APPROVED' and doc['expiry']<date.today().isoformat():raise S.APIError('Expired documents cannot be approved.')
        c.execute('INSERT INTO document_reviews VALUES(?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET status=excluded.status,note=excluded.note,reviewer=excluded.reviewer',(did,status,reason,staff['id']))
        case_revision(c,doc['user_id'])
        if status=='REJECTED':
            c.execute("UPDATE users SET verified='ADDITIONAL_INFORMATION_REQUIRED' WHERE id=?",(doc['user_id'],))
            S.notify(c,doc['user_id'],f'{doc["kind"]} requires correction: {reason}')
        record(c,staff,'DOCUMENT_REVIEW',did,reason,after={'status':status},topic='buyer',uid=doc['user_id'])
    elif endpoint=='assign-case':
        require(staff,'VERIFIER');uid=integer(d,'user_id',1);assignee=integer(d,'assignee',1)
        if not c.execute("SELECT 1 FROM staff WHERE id=? AND active=1 AND role IN ('ADMIN','VERIFIER')",(assignee,)).fetchone():raise S.APIError('Select an active reviewer.')
        c.execute('UPDATE verification_cases SET assignee=? WHERE user_id=?',(assignee,uid));record(c,staff,'CASE_ASSIGNED',uid,'Reviewer assigned',after={'assignee':assignee})
    elif endpoint=='product': save_product(c,staff,d)
    elif endpoint in ('arrival','discount-propose','discount-decision'):
        from command_core import action
        action(c,staff,endpoint,d)
    elif endpoint=='warehouse':
        require(staff,'OPERATIONS');name=text(d,'name');location=text(d,'location');kind=text(d,'kind')
        c.execute('INSERT INTO warehouses(name,location,kind) VALUES(?,?,?)',(name,location,kind));record(c,staff,'WAREHOUSE_CREATED',name,'New facility',after=d)
    elif endpoint in ('lot','adjust-stock','transfer','quality','tank','reading'): inventory_action(c,staff,endpoint,d)
    elif endpoint in ('order-status','order-hold','shipment','tracking-event'): order_action(c,staff,endpoint,d)
    elif endpoint=='alert': alert_action(c,staff,d)
    elif endpoint in ('compliance-rule','exporter-credential','document-requirement','document-status'):
        from compliance_core import admin_action
        admin_action(c,staff,endpoint,d,S,sys.modules[__name__])
    elif endpoint in ('auto-allocate','shipment-simulation','shipment-plan','shipment-leg','shipment-container','customs-milestone','transport-event','reefer-reading','shipping-exception'):
        from shipping_core import admin_action
        admin_action(c,staff,endpoint,d,S,sys.modules[__name__])
    elif endpoint in ('country','shipping','destination','settings','staff','password'): configuration(c,staff,endpoint,d)
    elif endpoint in ('trade-document','publish-document','generate-document'): document_action(c,staff,endpoint,d)
    elif endpoint=='notify':
        require(staff);uid=integer(d,'user_id',1);message=text(d,'message',2000)
        if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise S.APIError('Buyer not found.',404)
        S.notify(c,uid,message);record(c,staff,'BUYER_MESSAGE',uid,'Staff message',after={'message':message},topic='buyer',uid=uid)
    elif endpoint=='email-retry':
        require(staff);eid=integer(d,'id',1)
        from local_email import configured
        if not configured() or not settings(c).get('email_enabled'):raise S.APIError('Configure SMTP environment variables and enable email in Settings first.')
        row=c.execute('SELECT e.*,u.email FROM email_outbox e JOIN users u ON u.id=e.user_id WHERE e.id=?',(eid,)).fetchone()
        if not row or row['status'] not in ('FAILED','NOT_CONNECTED'):raise S.APIError('Only failed or undelivered messages can be queued.')
        if row['email'].endswith('.local'):raise S.APIError('Testing-only .local accounts cannot receive email.')
        c.execute("UPDATE email_outbox SET status='QUEUED',error='',updated=? WHERE id=?",(S.now(),eid));record(c,staff,'EMAIL_REQUEUED',eid,'Staff explicitly queued delivery')
    else: raise S.APIError('Not found.',404)
    return {'ok':True}

def snapshot(c,staff):
    from command_core import enrich_lots,priced,monitoring
    from local_email import configured
    is_verify=staff['role'] in ('ADMIN','VERIFIER');is_ops=staff['role'] in ('ADMIN','OPERATIONS')
    buyers=[dict(r) for r in c.execute('SELECT u.id,u.name,u.email,u.company,u.country,u.verified,u.created,v.revision,v.assignee,v.submitted FROM users u LEFT JOIN verification_cases v ON v.user_id=u.id ORDER BY u.id DESC')] if is_verify else []
    orders=[dict(r) for r in c.execute("SELECT o.*,u.company,u.name buyer_name,COALESCE(x.on_hold,0) on_hold,COALESCE(x.internal_note,'') internal_note FROM orders o JOIN users u ON u.id=o.user_id LEFT JOIN order_operations x ON x.order_id=o.id ORDER BY o.created DESC")] if is_ops else []
    for order in orders:
        order['events']=[dict(r) for r in c.execute('SELECT * FROM events WHERE order_id=? ORDER BY id',(order['id'],))]
        shipment=c.execute('SELECT * FROM shipments WHERE order_id=?',(order['id'],)).fetchone();order['shipment']=dict(shipment) if shipment else {}
        from compliance_core import order_readiness
        order['compliance']=order_readiness(c,order,S)
    products=[dict(r) for r in c.execute('SELECT p.*,a.published,a.image,a.reorder_kg,a.scientific_name,s.region,s.export_port,s.facility FROM products p JOIN product_admin a ON a.product_id=p.id LEFT JOIN product_sources s ON s.product_id=p.id ORDER BY p.id')] if is_ops else []
    lots=[dict(r) for r in c.execute('SELECT l.*,p.name,a.warehouse_id,a.quality,a.production_date,w.name warehouse FROM lots l JOIN products p ON p.id=l.product_id LEFT JOIN lot_admin a ON a.lot_id=l.id LEFT JOIN warehouses w ON w.id=a.warehouse_id ORDER BY l.expiry')] if is_ops else []
    tanks=[dict(r) for r in c.execute('SELECT t.*,a.capacity_kg,a.status,l.available_kg,l.reserved_kg,p.name FROM tanks t JOIN tank_admin a ON a.tank_id=t.id JOIN lots l ON l.id=t.lot_id JOIN products p ON p.id=l.product_id')] if is_ops else []
    for product in products:
        price=priced(c,product);product['effective_cents_per_kg']=price['cents_per_kg'];product['promotion']=price['promotion']
    from compliance_core import admin_snapshot
    compliance=admin_snapshot(c) if is_ops else {'rules':[],'credentials':[],'requirements':[]}
    from shipping_core import admin_snapshot as shipping_snapshot,schedule_catalog
    return {'staff':public_staff(staff),'buyers':buyers,'orders':orders,'products':products,'lots':enrich_lots(c,lots),'tanks':tanks,
        'transport_shipments':shipping_snapshot(c,S) if is_ops else [],'shipping_schedule':schedule_catalog(c) if is_ops else {'vessels':[],'sailings':[]},
        'compliance':compliance,
        'monitor':monitoring(c),'discounts':[dict(r) for r in c.execute('SELECT * FROM discount_proposals ORDER BY id DESC LIMIT 200')] if is_ops else [],
        'warehouses':[dict(r) for r in c.execute('SELECT * FROM warehouses')] if is_ops else [],
        'movements':[dict(r) for r in c.execute('SELECT * FROM stock_movements ORDER BY id DESC LIMIT 200')] if is_ops else [],
        'readings':[dict(r) for r in c.execute('SELECT * FROM condition_readings ORDER BY id DESC LIMIT 50')] if is_ops else [],
        'alerts':[dict(r) for r in c.execute('SELECT * FROM alerts ORDER BY updated DESC') ] if is_ops else [],
        'jobs':[],
        'documents':[dict(r) for r in c.execute('SELECT id,order_id,kind,name,mime,published,version,created,status,issuer,document_number,issue_date,expiry_date FROM trade_documents ORDER BY created DESC')] if is_ops else [],
        'team':[public_staff(r) for r in c.execute('SELECT * FROM staff') ] if staff['role']=='ADMIN' or is_verify else [],
        'audit':[dict(r) for r in c.execute("SELECT 'admin-'||a.id id,a.staff_id,a.action,a.entity,a.reason,a.before_json,a.after_json,a.created AS created,s.name staff_name FROM admin_audit a LEFT JOIN staff s ON s.id=a.staff_id UNION ALL SELECT 'buyer-'||a.id,NULL,a.action,CAST(a.user_id AS TEXT),a.detail,'{}','{}',a.created,'Buyer: '||COALESCE(u.name,'Unknown') FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY created DESC LIMIT 250")] if staff['role']=='ADMIN' else [],
        'settings':settings(c) if staff['role']=='ADMIN' else {k:v for k,v in settings(c).items() if k in ('last_monitor','monitor_seconds','expiry_days')},'countries':rules(c),'services':services(c),'destinations':destinations(c),
        'emails':[dict(r) for r in c.execute('SELECT id,user_id,subject,status,attempts,error,created FROM email_outbox ORDER BY id DESC LIMIT 100')] if staff['role']=='ADMIN' else [],
        'integrations':{'identity':'Not connected','email':'SMTP enabled' if configured() and settings(c).get('email_enabled') else 'Not connected','sensors':'Manual readings','carrier':'Manual updates'}}

def save_product(c,staff,d):
    require(staff,'OPERATIONS');pid=d.get('id');name=text(d,'name');category=text(d,'category');grade=text(d,'grade');origin=text(d,'origin');description=text(d,'description',3000)
    if category not in ('Live fish','Fish','Shrimp','Cephalopods','Crab'):raise S.APIError('Select a supported category.')
    price=integer(d,'cents_per_kg',1);minimum=integer(d,'minimum_kg',1);reorder=integer(d,'reorder_kg');published=integer(d,'published',0,1)
    image=text(d,'image',500,False)
    if image and not (re.fullmatch(r'/catalog/[a-z0-9-]+\.jpg',image) or re.fullmatch(r'/api/product-image/[a-f0-9]{24}',image)):raise S.APIError('Choose a catalogue image or upload a product photo.')
    if d.get('photo_content'):
        content=base64.b64decode(d['photo_content'],validate=True)
        if not content or len(content)>5*1024*1024:raise S.APIError('Product photo must be under 5 MB.')
        mime='image/png' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else None
        if not mime:raise S.APIError('Product photos must be PNG or JPEG.')
        image_id=secrets.token_hex(12);c.execute('INSERT INTO product_images VALUES(?,?,?,?)',(image_id,text(d,'photo_name',120),mime,content));image='/api/product-image/'+image_id
    if published and (not pid or pid>12) and not image:raise S.APIError('Add a relevant species photo before publishing a new product.')
    if pid:
        before=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not before:raise S.APIError('Product not found.',404)
        c.execute('UPDATE products SET name=?,category=?,grade=?,origin=?,cents_per_kg=?,minimum_kg=?,description=? WHERE id=?',(name,category,grade,origin,price,minimum,description,pid))
    else:
        before=None;pid=c.execute('INSERT INTO products(name,category,grade,origin,cents_per_kg,minimum_kg,description) VALUES(?,?,?,?,?,?,?)',(name,category,grade,origin,price,minimum,description)).lastrowid
    c.execute('INSERT INTO product_admin VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET published=excluded.published,image=excluded.image,reorder_kg=excluded.reorder_kg,scientific_name=excluded.scientific_name',(pid,published,image,reorder,text(d,'scientific_name',150,False)))
    c.execute('INSERT INTO product_sources VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET region=excluded.region,export_port=excluded.export_port,facility=excluded.facility',(pid,text(d,'region'),text(d,'export_port'),text(d,'facility')))
    record(c,staff,'PRODUCT_SAVED',pid,'Catalogue update',dict(before) if before else {},{k:v for k,v in d.items() if k!='photo_content'},'catalog')

def inventory_action(c,staff,action,d):
    require(staff,'OPERATIONS');reason=text(d,'reason',1000)
    if action=='lot':
        lot=text(d,'id',100);pid=integer(d,'product_id',1);qty=integer(d,'quantity',1);warehouse=integer(d,'warehouse_id',1);expiry=valid_date(d.get('expiry'))
        if expiry<date.today().isoformat():raise S.APIError('New stock must have a future expiry.')
        production=valid_date(d.get('production_date'),True)
        if production and production>expiry:raise S.APIError('Production date must precede expiry.')
        c.execute('INSERT INTO lots VALUES(?,?,?,?,?)',(lot,pid,qty,0,expiry));c.execute('INSERT INTO lot_admin VALUES(?,?,?,?,?)',(lot,warehouse,'RELEASED',production,reason));movement(c,lot,'RECEIPT',qty,0,reason,staff['id'])
        from command_core import arrival
        arrival(c,lot,d.get('received_date',date.today().isoformat()),expiry,production)
        record(c,staff,'LOT_RECEIVED',lot,reason,after=d,topic='catalog');return
    if action in ('tank','reading'):
        tank=text(d,'tank_id',100)
        if action=='tank':
            capacity=integer(d,'capacity_kg',1);status=text(d,'status')
            if status not in ('ACTIVE','MAINTENANCE'):raise S.APIError('Invalid tank status.')
            lot=text(d,'lot_id',100);row=c.execute('SELECT * FROM lots WHERE id=?',(lot,)).fetchone()
            if not row or row['available_kg']+row['reserved_kg']>capacity:raise S.APIError('Capacity must cover this lot’s current stock.')
            existing=c.execute('SELECT lot_id FROM tanks WHERE id=?',(tank,)).fetchone()
            if existing and existing['lot_id']!=lot:raise S.APIError('Existing tank lot assignments cannot be changed; transfer through inventory instead.')
            c.execute('INSERT INTO tanks VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET zone=excluded.zone',(tank,lot,text(d,'zone')))
            c.execute('INSERT INTO tank_admin VALUES(?,?,?) ON CONFLICT(tank_id) DO UPDATE SET capacity_kg=excluded.capacity_kg,status=excluded.status',(tank,capacity,status))
            if status=='MAINTENANCE':c.execute("UPDATE lot_admin SET quality='HOLD',note=? WHERE lot_id=?",(reason,lot))
        else:
            temp=float(d.get('temperature'));oxygen=float(d.get('oxygen'))
            if not -40<=temp<=60 or not 0<=oxygen<=30:raise S.APIError('Reading outside supported range.')
            c.execute('INSERT INTO condition_readings(tank_id,temperature,oxygen,note,created,staff_id) VALUES(?,?,?,?,?,?)',(tank,temp,oxygen,reason,S.now(),staff['id']))
        record(c,staff,action.upper(),tank,reason,after=d,topic='catalog');return
    lot=text(d,'lot_id',100);row=c.execute('SELECT * FROM lots WHERE id=?',(lot,)).fetchone()
    if not row:raise S.APIError('Lot not found.',404)
    if action=='adjust-stock':
        delta=integer(d,'delta',-100000000);expected=integer(d,'expected_available')
        if expected!=row['available_kg']:raise S.APIError('Stock changed. Reload before adjusting.',409)
        if row['available_kg']+delta<0:raise S.APIError('Adjustment cannot consume reserved stock.',409)
        cap=c.execute('SELECT a.capacity_kg FROM tanks t JOIN tank_admin a ON a.tank_id=t.id WHERE t.lot_id=?',(lot,)).fetchone()
        if cap and row['available_kg']+row['reserved_kg']+delta>cap[0]:raise S.APIError('Adjustment exceeds tank capacity.',409)
        c.execute('UPDATE lots SET available_kg=available_kg+? WHERE id=?',(delta,lot));movement(c,lot,'ADJUSTMENT',delta,0,reason,staff['id'])
    elif action=='transfer':
        if row['reserved_kg']:raise S.APIError('Reconcile active reservations before relocating a lot.',409)
        if c.execute('SELECT 1 FROM tanks WHERE lot_id=?',(lot,)).fetchone():raise S.APIError('Tank lots cannot be relocated through a warehouse transfer.')
        c.execute('UPDATE lot_admin SET warehouse_id=? WHERE lot_id=?',(integer(d,'warehouse_id',1),lot));movement(c,lot,'TRANSFER',0,0,reason,staff['id'])
    elif action=='quality':
        quality=text(d,'quality')
        if quality not in ('RELEASED','HOLD','REJECTED'):raise S.APIError('Invalid quality status.')
        if quality=='RELEASED' and c.execute("SELECT 1 FROM tanks t JOIN tank_admin a ON a.tank_id=t.id WHERE t.lot_id=? AND a.status='MAINTENANCE'",(lot,)).fetchone():raise S.APIError('Finish tank maintenance before releasing its stock.')
        c.execute('UPDATE lot_admin SET quality=?,note=? WHERE lot_id=?',(quality,reason,lot));movement(c,lot,'QUALITY',0,0,reason,staff['id'])
    record(c,staff,action.upper(),lot,reason,dict(row),d,'catalog')

def order_action(c,staff,action,d):
    require(staff,'OPERATIONS');oid=text(d,'id');reason=text(d,'reason',2000);o=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not o:raise S.APIError('Order not found.',404)
    if action=='tracking-event':
        title=text(d,'title',100)
        if o['status']=='CANCELLED':raise S.APIError('Cancelled orders cannot receive shipment milestones.')
        c.execute('INSERT INTO events(order_id,title,note,created) VALUES(?,?,?,?)',(oid,title,reason,S.now()))
        S.notify(c,o['user_id'],f'{oid}: {title}. {reason}')
    elif action=='order-hold':
        hold=integer(d,'on_hold',0,1)
        if o['status'] in ('DELIVERED','CANCELLED'):raise S.APIError('Closed orders cannot be held.')
        c.execute('INSERT INTO order_operations VALUES(?,?,?) ON CONFLICT(order_id) DO UPDATE SET on_hold=excluded.on_hold,internal_note=excluded.internal_note',(oid,hold,reason))
    elif action=='shipment':
        fields=[text(d,k,300,False) for k in ('origin_port','carrier','container','vessel','departure','eta','arrival','location')]
        for i in (4,5,6):fields[i]=valid_date(fields[i],True)
        if fields[4] and fields[5] and fields[5]<fields[4]:raise S.APIError('ETA must not precede departure.')
        c.execute('INSERT INTO shipments VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET origin_port=excluded.origin_port,carrier=excluded.carrier,container=excluded.container,vessel=excluded.vessel,departure=excluded.departure,eta=excluded.eta,arrival=excluded.arrival,location=excluded.location',(oid,*fields))
        S.notify(c,o['user_id'],f'{oid}: shipment details updated. {reason}')
    else:
        status=text(d,'status');transitions={'CONFIRMED':('PROCESSING','CANCELLED'),'PROCESSING':('SHIPPED',),'SHIPPED':('DELIVERED',)}
        if status not in transitions.get(o['status'],()):raise S.APIError('Invalid or stale order transition.',409)
        if status=='SHIPPED':
            from shipping_core import dispatch_ready
            ready,blocker=dispatch_ready(c,o)
            if not ready:raise S.APIError(blocker,409)
        if status=='SHIPPED':
            from compliance_core import order_readiness
            readiness=order_readiness(c,o,S)
            if readiness['departure_blocking']:raise S.APIError(f'{readiness["departure_blocking"]} pre-departure document gates remain. Release them before dispatch.',409)
        hold=c.execute('SELECT on_hold FROM order_operations WHERE order_id=?',(oid,)).fetchone()
        if hold and hold[0] and status!='CANCELLED':raise S.APIError('Release the order hold before progressing.',409)
        allocations=c.execute('SELECT a.*,l.expiry,COALESCE(x.quality,\'RELEASED\') quality FROM allocations a JOIN lots l ON l.id=a.lot_id LEFT JOIN lot_admin x ON x.lot_id=l.id WHERE a.order_id=?',(oid,)).fetchall()
        if status in ('PROCESSING','SHIPPED') and any(a['quality']!='RELEASED' or a['expiry']<date.today().isoformat() for a in allocations):raise S.APIError('An allocated lot is expired or on quality hold.',409)
        for a in allocations:
            if status=='SHIPPED':
                c.execute('UPDATE lots SET reserved_kg=reserved_kg-? WHERE id=?',(a['kg'],a['lot_id']));movement(c,a['lot_id'],'SHIP',0,-a['kg'],reason,staff['id'],oid)
            elif status=='CANCELLED':
                c.execute('UPDATE lots SET reserved_kg=reserved_kg-?,available_kg=available_kg+? WHERE id=?',(a['kg'],a['kg'],a['lot_id']));movement(c,a['lot_id'],'CANCEL',a['kg'],-a['kg'],reason,staff['id'],oid)
        c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid));c.execute('INSERT INTO events(order_id,title,note,created) VALUES(?,?,?,?)',(oid,status,reason,S.now()))
        S.notify(c,o['user_id'],f'{oid}: {status}. {reason}');change(c,'catalog')
    record(c,staff,action.upper(),oid,reason,dict(o),d,'buyer',o['user_id'])

def alert_action(c,staff,d):
    require(staff,'OPERATIONS');aid=integer(d,'id',1);state=text(d,'state');reason=text(d,'reason',1000)
    if state not in ('ACKNOWLEDGED','RESOLVED','OPEN'):raise S.APIError('Invalid alert state.')
    assignee=d.get('assignee') or None
    if assignee and not c.execute('SELECT 1 FROM staff WHERE id=? AND active=1',(assignee,)).fetchone():raise S.APIError('Choose an active staff member.')
    c.execute('UPDATE alerts SET state=?,resolution=?,assignee=?,updated=? WHERE id=?',(state,reason,assignee,S.now(),aid));record(c,staff,'ALERT_UPDATED',aid,reason,after=d)

def configuration(c,staff,action,d):
    if action in ('password','staff'):return supabase_auth.staff_change(c,staff,action,d,S)
    require(staff)
    if action=='country':
        country=text(d,'country',80);requirements=d.get('requirements')
        if not isinstance(requirements,list) or not 1<=len(requirements)<=12 or any(not isinstance(x,str) or not x.strip() or len(x)>100 for x in requirements):raise S.APIError('Provide 1–12 document requirement names.')
        c.execute('INSERT INTO country_rules(country,requirements) VALUES(?,?) ON CONFLICT(country) DO UPDATE SET requirements=excluded.requirements,version=version+1',(country,json.dumps(list(dict.fromkeys(requirements)))))
        for u in c.execute('SELECT * FROM users WHERE country=?',(country,)).fetchall():
            case_revision(c,u['id'])
            if u['verified']=='VERIFIED' and not S.valid_verification(c,u):
                c.execute("UPDATE users SET verified='ADDITIONAL_INFORMATION_REQUIRED' WHERE id=?",(u['id'],));S.notify(c,u['id'],'Document requirements changed. Please review your verification checklist.')
        entity=country
    elif action=='shipping':
        entity=text(d,'name',80);c.execute('INSERT INTO shipping_services VALUES(?,?) ON CONFLICT(name) DO UPDATE SET cents=excluded.cents',(entity,integer(d,'cents')))
    elif action=='destination':
        entity=text(d,'name',150);c.execute('INSERT OR IGNORE INTO destinations VALUES(?)',(entity,))
    elif action=='settings':
        entity='settings';values={'expiry_days':integer(d,'expiry_days',1,365),'monitor_seconds':integer(d,'monitor_seconds',15,3600),'handling_cents':integer(d,'handling_cents'),'email_enabled':d.get('email_enabled') is True}
        for key,value in values.items():c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    record(c,staff,action.upper()+'_SAVED',entity,'Configuration changed',after=d,topic='catalog')

def document_action(c,staff,action,d):
    require(staff,'OPERATIONS')
    if action=='publish-document':
        did=text(d,'id');published=integer(d,'published',0,1);row=c.execute('SELECT t.*,o.user_id FROM trade_documents t JOIN orders o ON o.id=t.order_id WHERE t.id=?',(did,)).fetchone()
        if not row:raise S.APIError('Document not found.',404)
        if published and row['status']!='RELEASED':raise S.APIError('Review and release this document before publishing it.',409)
        c.execute('UPDATE trade_documents SET published=? WHERE id=?',(published,did));S.notify(c,row['user_id'],f'{row["order_id"]}: {row["kind"]} '+('available.' if published else 'withdrawn.'))
        record(c,staff,'DOCUMENT_PUBLISHED',did,'Publication state changed',after={'published':published},topic='buyer',uid=row['user_id']);return
    oid=text(d,'order_id');kind=text(d,'kind',80);order=c.execute('SELECT o.*,u.company FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=?',(oid,)).fetchone()
    if not order:raise S.APIError('Order not found.',404)
    if action=='generate-document':
        if kind not in ('Order confirmation','Informational invoice','Packing list'):raise S.APIError('Select a supported document template.')
        from pdf_documents import render_document
        content=render_document(kind,dict(order));mime='application/pdf';name=oid+'-'+kind+'.pdf'
    else:
        content=base64.b64decode(d.get('content',''),validate=True);name=text(d,'name',120)
        if not content or len(content)>5*1024*1024:raise S.APIError('File must be under 5 MB.')
        mime='application/pdf' if content.startswith(b'%PDF-') else 'image/png' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else None
        if not mime:raise S.APIError('Use PDF, PNG or JPEG.')
    version=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM trade_documents WHERE order_id=? AND kind=?',(oid,kind)).fetchone()[0];did=secrets.token_hex(12)
    c.execute('INSERT INTO trade_documents(id,order_id,kind,name,mime,content,published,version,created,staff_id,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,oid,kind,name,mime,S.fernet.encrypt(content),0,version,S.now(),staff['id'],'DRAFT'))
    c.execute("UPDATE order_document_requirements SET status='SUBMITTED',note='Soft copy attached for staff review.',updated=? WHERE order_id=? AND lower(document_name)=lower(?)",(S.now(),oid,kind))
    record(c,staff,'TRADE_DOCUMENT_CREATED',did,'Draft document saved',after={'order':oid,'kind':kind,'version':version})

def downloads(h,c,staff,endpoint):
    if endpoint.startswith('trade-document/'):
        require(staff,'OPERATIONS');row=c.execute('SELECT * FROM trade_documents WHERE id=?',(endpoint.split('/')[-1],)).fetchone()
        if not row:raise S.APIError('Document not found.',404)
        decrypted = S.fernet.decrypt(row['content']) if row['content'].startswith(b'gAAAAA') else row['content']
        h.send(decrypted,mime=row['mime'],filename=row['id']+'.'+('pdf' if row['mime']=='application/pdf' else 'png' if row['mime']=='image/png' else 'jpg'));return None
    if endpoint=='report':
        require(staff,'OPERATIONS');import csv,io
        out=io.StringIO();writer=csv.writer(out);writer.writerow(['Order','Buyer','Product','kg','USD total','Status','Destination','Created'])
        for row in c.execute('SELECT o.id,u.company,o.product_name,o.kg,o.total/100.0,o.status,o.destination,o.created FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.created DESC'):
            writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in row])
        h.send(out.getvalue().encode('utf-8-sig'),mime='text/csv',filename='blueharbor-orders.csv');return None
    raise S.APIError('Not found.',404)
