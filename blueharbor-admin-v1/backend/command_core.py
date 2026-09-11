"""Additive batch aging and human-approved, time-bounded product promotions."""
from datetime import date, datetime, timezone
import admin_core as A

def arrival(c,lot,value,expiry,production=''):
    value=A.valid_date(value)
    if value>date.today().isoformat() or value>expiry or (production and value<production):
        raise A.S.APIError('Arrival must be on or before today/expiry and not before production.')
    c.execute('INSERT INTO lot_arrivals VALUES(?,?) ON CONFLICT(lot_id) DO UPDATE SET received_date=excluded.received_date',(lot,value))

def enrich_lots(c,lots):
    arrivals={r['lot_id']:r['received_date'] for r in c.execute('SELECT * FROM lot_arrivals')}
    for lot in lots:
        received=arrivals.get(lot['id']);days=(date.fromisoformat(lot['expiry'])-date.today()).days
        lot.update(received_date=received,storage_days=(date.today()-date.fromisoformat(received)).days if received else None,days_to_expiry=days,sellable=lot['quality']=='RELEASED' and days>=0)
    return lots

def active_promotion(c,p):
    return c.execute("SELECT d.* FROM discount_proposals d JOIN lots l ON l.id=d.lot_id JOIN lot_admin a ON a.lot_id=l.id JOIN product_admin pa ON pa.product_id=d.product_id WHERE d.product_id=? AND d.status='APPROVED' AND d.ends_on>=? AND l.expiry>=? AND a.quality='RELEASED' AND l.available_kg>0 AND pa.published=1 AND d.base_cents=? ORDER BY d.id DESC LIMIT 1",(p['id'],date.today().isoformat(),date.today().isoformat(),p['cents_per_kg'])).fetchone()

def priced(c,p):
    result=dict(p);promotion=active_promotion(c,p)
    result['base_cents_per_kg']=p['cents_per_kg']
    result['promotion']={'id':promotion['id'],'percent':promotion['percent'],'ends_on':promotion['ends_on'],'scope':'PRODUCT'} if promotion else None
    if promotion:result['cents_per_kg']=max(1,(p['cents_per_kg']*(100-promotion['percent'])+50)//100)
    return result

def valid_source(c,lot,ends):
    row=c.execute('SELECT l.*,a.quality,p.cents_per_kg,pa.published FROM lots l JOIN lot_admin a ON a.lot_id=l.id JOIN products p ON p.id=l.product_id JOIN product_admin pa ON pa.product_id=p.id WHERE l.id=?',(lot,)).fetchone()
    if not row or not row['published'] or row['quality']!='RELEASED' or row['available_kg']<=0 or row['expiry']<date.today().isoformat():
        raise A.S.APIError('Promotion source must be published, available, released and unexpired. Unsafe stock cannot be discounted.',409)
    if ends<date.today().isoformat() or ends>row['expiry']:raise A.S.APIError('Promotion must end between today and the source lot expiry.')
    return row

def action(c,staff,endpoint,d):
    A.require(staff,'OPERATIONS');reason=A.text(d,'reason',2000)
    if endpoint=='arrival':
        lot=A.text(d,'lot_id');row=c.execute('SELECT l.expiry,a.production_date FROM lots l JOIN lot_admin a ON a.lot_id=l.id WHERE l.id=?',(lot,)).fetchone()
        if not row:raise A.S.APIError('Lot not found.',404)
        before=c.execute('SELECT received_date FROM lot_arrivals WHERE lot_id=?',(lot,)).fetchone()
        arrival(c,lot,d.get('received_date'),row['expiry'],row['production_date'])
        A.record(c,staff,'ARRIVAL_RECORDED',lot,reason,dict(before) if before else {},{'received_date':d['received_date']},'catalog');return
    if endpoint=='discount-propose':
        lot=A.text(d,'lot_id');ends=A.valid_date(d.get('ends_on'));percent=A.integer(d,'percent',1,90);row=valid_source(c,lot,ends)
        identifier=c.execute('INSERT INTO discount_proposals(product_id,lot_id,percent,ends_on,reason,created,proposed_by,base_cents) VALUES(?,?,?,?,?,?,?,?)',(row['product_id'],lot,percent,ends,reason,A.S.now(),staff['id'],row['cents_per_kg'])).lastrowid
        A.record(c,staff,'DISCOUNT_PROPOSED',identifier,reason,after={'lot_id':lot,'percent':percent,'scope':'PRODUCT'});return
    identifier=A.integer(d,'id',1);status=A.text(d,'status');proposal=c.execute('SELECT * FROM discount_proposals WHERE id=?',(identifier,)).fetchone()
    if status not in ('APPROVED','REJECTED','WITHDRAWN') or not proposal:raise A.S.APIError('Invalid proposal decision.')
    if (status in ('APPROVED','REJECTED') and proposal['status']!='PROPOSED') or (status=='WITHDRAWN' and proposal['status']!='APPROVED'):raise A.S.APIError('Proposal changed. Refresh before deciding.',409)
    if status=='APPROVED':
        row=valid_source(c,proposal['lot_id'],proposal['ends_on'])
        if row['cents_per_kg']!=proposal['base_cents']:raise A.S.APIError('Base price changed. Create a fresh proposal.',409)
        c.execute("UPDATE discount_proposals SET status='WITHDRAWN',decision_note='Replaced by a newer approved promotion',decided=?,decided_by=? WHERE product_id=? AND status='APPROVED'",(A.S.now(),staff['id'],proposal['product_id']))
    c.execute('UPDATE discount_proposals SET status=?,decided=?,decided_by=?,decision_note=? WHERE id=?',(status,A.S.now(),staff['id'],reason,identifier))
    A.record(c,staff,'DISCOUNT_'+status,identifier,reason,dict(proposal),{'status':status},'catalog')

def monitoring(c):
    cfg=A.settings(c);last=cfg.get('worker_heartbeat');fresh=bool(last and (datetime.now(timezone.utc)-datetime.fromisoformat(last)).total_seconds()<20)
    return {'rules_status':'FAILED' if fresh and cfg.get('monitor_error') else 'RUNNING' if fresh else 'OFFLINE','last_scan':cfg.get('last_monitor'),'next_scan':cfg.get('next_monitor') if fresh else None,'error':cfg.get('monitor_error','')}
