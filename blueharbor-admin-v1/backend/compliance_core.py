"""Phase 2 order documentation and compliance workflows."""
import csv, hashlib, io, json, zipfile
from datetime import date

DOC_STATES=('WAITING','SUBMITTED','UNDER_REVIEW','CORRECTION_REQUIRED','ISSUED','RELEASED','SUPERSEDED','NOT_REQUIRED')

def _country(destination):
    return destination.rsplit(',',1)[-1].strip() if ',' in destination else destination.strip()

def _sync_order(c,order,S=None):
    country=_country(order['destination'])
    rules=c.execute("SELECT * FROM compliance_rule_sets WHERE active=1 AND (country='*' OR lower(country)=lower(?)) AND (product_category='*' OR product_category=(SELECT category FROM products WHERE id=?)) ORDER BY blocking DESC,document_name",(country,order['product_id'])).fetchall()
    now=S.now() if S else date.today().isoformat()
    for r in rules:
        c.execute("INSERT INTO order_document_requirements(order_id,requirement_code,document_name,owner,blocking,status,source_rule_id,note,updated,required_stage,responsible_party,official_issuer,evidence_type,original_required) VALUES(?,?,?,?,?,'WAITING',?,'',?,?,?,?,?,?) ON CONFLICT(order_id,requirement_code) DO NOTHING",(order['id'],r['requirement_code'],r['document_name'],'BUYER' if r['buyer_owned'] else 'EXPORTER',r['blocking'],r['id'],now,r['required_stage'],r['responsible_party'],r['issuer'],r['evidence_type'],r['original_required']))

def order_readiness(c,order,S=None):
    _sync_order(c,order,S)
    items=[dict(r) for r in c.execute("SELECT r.*,x.source_url,x.issuer FROM order_document_requirements r LEFT JOIN compliance_rule_sets x ON x.id=r.source_rule_id WHERE r.order_id=? ORDER BY r.blocking DESC,r.document_name",(order['id'],)).fetchall()]
    released=0;started=0;blocking=0;departure_blocking=0;progress_points=0
    weights={'WAITING':0,'DRAFT':0.25,'CORRECTION_REQUIRED':0.15,'SUBMITTED':0.25,'UNDER_REVIEW':0.5,'ISSUED':0.75,'RELEASED':1,'NOT_REQUIRED':1,'SUPERSEDED':0}
    for item in items:
        doc=c.execute("SELECT id,name,version,status,document_number,issuer,issue_date,expiry_date,published FROM trade_documents WHERE order_id=? AND lower(kind)=lower(?) ORDER BY version DESC,created DESC LIMIT 1",(order['id'],item['document_name'])).fetchone()
        item['document']=dict(doc) if doc else None
        if doc:item['status']='SUBMITTED' if doc['status']=='DRAFT' else doc['status']
        if item['status'] not in ('WAITING','SUPERSEDED'):started+=1
        progress_points+=weights.get(item['status'],0)
        if item['status'] in ('RELEASED','NOT_REQUIRED'): released+=1
        elif item['blocking']:
            blocking+=1
            if item['required_stage'] in ('PRE_CUSTOMS','PRE_LOADING'):departure_blocking+=1
    return {'country':_country(order['destination']),'items':items,'started':started,'released':released,'total':len(items),'progress':round(progress_points/max(1,len(items))*100),'blocking':blocking,'departure_blocking':departure_blocking,'clearance_blocking':blocking,'departure_ready':departure_blocking==0,'clearance_ready':bool(items) and blocking==0,'ready':bool(items) and blocking==0}

def admin_snapshot(c,S=None):
    requirements=[]
    for order in c.execute('SELECT * FROM orders ORDER BY created DESC').fetchall():
        _sync_order(c,order,S)
        ready=order_readiness(c,order,S);requirements.append({'order_id':order['id'],'product_name':order['product_name'],'destination':order['destination'],**ready})
    return {'rules':[dict(r) for r in c.execute('SELECT * FROM compliance_rule_sets ORDER BY country,product_category,document_name')],
            'credentials':[dict(r) for r in c.execute('SELECT * FROM exporter_credentials ORDER BY expires,name')],
            'requirements':requirements}

def admin_action(c,staff,action,d,S,A):
    A.require(staff,'OPERATIONS');now=S.now()
    if action=='compliance-rule':
        rid=d.get('id');values=(A.text(d,'country',80),A.text(d,'product_category',80),A.text(d,'requirement_code',80),A.text(d,'document_name',120),A.text(d,'issuer',160),A.integer(d,'buyer_owned',0,1),A.integer(d,'blocking',0,1),A.integer(d,'lead_days',0,365),A.text(d,'source_url',500),A.valid_date(d.get('reviewed_on')),A.integer(d,'active',0,1),A.text(d,'required_stage',40),A.text(d,'responsible_party',60),A.text(d,'evidence_type',20),A.integer(d,'original_required',0,1))
        if values[11] not in ('PRE_CUSTOMS','PRE_LOADING','POST_DEPARTURE','PRE_ARRIVAL','DESTINATION_RELEASE') or values[13] not in ('DOCUMENT','REFERENCE'):raise S.APIError('Choose a valid stage and evidence type.')
        if rid:c.execute('UPDATE compliance_rule_sets SET country=?,product_category=?,requirement_code=?,document_name=?,issuer=?,buyer_owned=?,blocking=?,lead_days=?,source_url=?,reviewed_on=?,active=?,required_stage=?,responsible_party=?,evidence_type=?,original_required=?,version=version+1,updated=? WHERE id=?',(*values,now,rid))
        else:c.execute('INSERT INTO compliance_rule_sets(country,product_category,requirement_code,document_name,issuer,buyer_owned,blocking,lead_days,source_url,reviewed_on,active,required_stage,responsible_party,evidence_type,original_required,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*values,now))
        A.record(c,staff,'COMPLIANCE_RULE_SAVED',rid or values[2],'Rule pack updated',after=d)
    elif action=='exporter-credential':
        cid=d.get('id');values=(A.text(d,'name',120),A.text(d,'authority',160),A.text(d,'number',120),A.text(d,'scope',500),A.valid_date(d.get('issued'),True),A.valid_date(d.get('expires')),A.text(d,'status',40),A.text(d,'notes',1000,False),now)
        if values[6] not in ('ACTIVE','RENEWAL_DUE','EXPIRED','SUSPENDED'):raise S.APIError('Invalid credential status.')
        if cid:c.execute('UPDATE exporter_credentials SET name=?,authority=?,number=?,scope=?,issued=?,expires=?,status=?,notes=?,updated=? WHERE id=?',(*values,cid))
        else:c.execute('INSERT INTO exporter_credentials(name,authority,number,scope,issued,expires,status,notes,updated) VALUES(?,?,?,?,?,?,?,?,?)',values)
        A.record(c,staff,'EXPORTER_CREDENTIAL_SAVED',cid or values[2],'Credential register updated',after=d)
    elif action=='document-requirement':
        oid=A.text(d,'order_id');code=A.text(d,'requirement_code');status=A.text(d,'status');note=A.text(d,'note',1000,False)
        if status not in DOC_STATES:raise S.APIError('Invalid requirement status.')
        c.execute('UPDATE order_document_requirements SET status=?,note=?,updated=? WHERE order_id=? AND requirement_code=?',(status,note,now,oid,code))
        A.record(c,staff,'DOCUMENT_REQUIREMENT_UPDATED',oid, note or status,after=d,topic='buyer',uid=c.execute('SELECT user_id FROM orders WHERE id=?',(oid,)).fetchone()[0])
    else:
        did=A.text(d,'id');status=A.text(d,'status');row=c.execute('SELECT t.*,o.user_id FROM trade_documents t JOIN orders o ON o.id=t.order_id WHERE t.id=?',(did,)).fetchone()
        if not row:raise S.APIError('Document not found.',404)
        if status not in ('DRAFT','UNDER_REVIEW','CORRECTION_REQUIRED','ISSUED','RELEASED','SUPERSEDED'):raise S.APIError('Invalid document status.')
        issuer=A.text(d,'issuer',160,False);number=A.text(d,'document_number',120,False);issue=A.valid_date(d.get('issue_date'),True);expiry=A.valid_date(d.get('expiry_date'),True);note=A.text(d,'note',1000,False)
        if expiry and issue and expiry<issue:raise S.APIError('Expiry date cannot precede issue date.')
        if status=='RELEASED' and (not issuer or not number or not issue):raise S.APIError('Issuer, document number and issue date are required for release.')
        published=1 if status=='RELEASED' else 0
        c.execute('UPDATE trade_documents SET status=?,issuer=?,document_number=?,issue_date=?,expiry_date=?,published=? WHERE id=?',(status,issuer,number,issue,expiry,published,did))
        c.execute('UPDATE order_document_requirements SET status=?,note=?,updated=? WHERE order_id=? AND document_name=?',(status,note,now,row['order_id'],row['kind']))
        S.notify(c,row['user_id'],f'{row["order_id"]}: {row["kind"]} is {status.replace("_"," ").lower()}.')
        A.record(c,staff,'TRADE_DOCUMENT_STATUS',did,note or status,after=d,topic='buyer',uid=row['user_id'])

def clearance_pack(c,uid,oid,Error):
    if not c.execute('SELECT 1 FROM orders WHERE id=? AND user_id=?',(oid,uid)).fetchone():raise Error('Order not found.',404)
    docs=c.execute("SELECT * FROM trade_documents WHERE order_id=? AND published=1 AND status='RELEASED' ORDER BY kind,version DESC",(oid,)).fetchall()
    if not docs:raise Error('No released clearance documents are available yet.',409)
    out=io.BytesIO();index=io.StringIO();writer=csv.writer(index);writer.writerow(['Document','File','Version','Issuer','Number','Issue date','Expiry date','SHA-256'])
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,row in enumerate(docs,1):
            ext='pdf' if row['mime']=='application/pdf' else 'png' if row['mime']=='image/png' else 'jpg';name=f'{n:02d}-{row["kind"].replace("/","-")}-v{row["version"]}.{ext}';content=bytes(row['content']);digest=hashlib.sha256(content).hexdigest();z.writestr(name,content);writer.writerow([row['kind'],name,row['version'],row['issuer'],row['document_number'],row['issue_date'],row['expiry_date'],digest])
        z.writestr('clearance-pack-index.csv',index.getvalue().encode('utf-8-sig'))
    return out.getvalue()
