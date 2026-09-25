"""Phase 3 transport, customs, reefer and exception workflows."""
import secrets
import math
from datetime import datetime

CUSTOMS_KINDS=('ESANCHIT','SHIPPING_BILL','LEO','EGM')

def _stamp(value,optional=False):
    value=str(value or '').strip()
    if not value and optional:return ''
    if not value:raise ValueError('Date and time are required.')
    return datetime.fromisoformat(value.replace('Z','+00:00')).isoformat(timespec='minutes')

def _float(d,key,minimum,maximum,optional=False):
    value=d.get(key)
    if optional and (value is None or value==''):return None
    result=float(value)
    if result<minimum or result>maximum:raise ValueError(key+' is outside the supported range.')
    return result

def _notify_shipment(c,shipment_id,S,message):
    for row in c.execute('SELECT o.user_id FROM shipment_orders x JOIN orders o ON o.id=x.order_id WHERE x.shipment_id=?',(shipment_id,)).fetchall():S.notify(c,row['user_id'],message)

def _order_milestone(c,shipment_id,title,note,S):
    for row in c.execute('SELECT o.id,o.user_id FROM shipment_orders x JOIN orders o ON o.id=x.order_id WHERE x.shipment_id=?',(shipment_id,)).fetchall():
        if not c.execute('SELECT 1 FROM events WHERE order_id=? AND title=? AND note=?',(row['id'],title,note)).fetchone():
            c.execute('INSERT INTO events(order_id,title,note,created) VALUES(?,?,?,?)',(row['id'],title,note,S.now()))

def schedule_catalog(c):
    vessels=[]
    for row in c.execute('SELECT v.*,a.name carrier_name FROM shipping_vessels v JOIN shipping_carriers a ON a.id=v.carrier_id WHERE v.active=1 ORDER BY v.name').fetchall():
        item=dict(row);item['rotations']=[dict(x) for x in c.execute('SELECT * FROM service_rotations WHERE carrier_id=? AND active=1 ORDER BY name',(row['carrier_id'],)).fetchall()];vessels.append(item)
    sailings=[]
    query='''SELECT s.*,v.name vessel_name,v.imo_number,v.flag,v.image_url,v.capacity_teu,v.reefer_plugs,a.name carrier_name,r.name rotation_name,r.service_code,r.cycle_days
      FROM vessel_sailings s JOIN shipping_vessels v ON v.id=s.vessel_id JOIN shipping_carriers a ON a.id=v.carrier_id
      JOIN service_rotations r ON r.id=s.rotation_id WHERE s.status IN ('SCHEDULED','ACTIVE') ORDER BY s.cycle_start'''
    for row in c.execute(query).fetchall():
        item=dict(row);item['calls']=[dict(x) for x in c.execute('''SELECT sc.*,p.name port_name,p.country,p.latitude,p.longitude FROM sailing_calls sc JOIN shipping_ports p ON p.code=sc.port_code WHERE sc.sailing_id=? ORDER BY sc.sequence''',(row['id'],)).fetchall()];sailings.append(item)
    return {'vessels':vessels,'sailings':sailings}

def allocate_order(c,order_id,S,force=False):
    order=c.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
    if not order or order['status'] in ('CANCELLED','DELIVERED'):return None
    linked=c.execute('SELECT x.shipment_id,t.vessel,t.booking_reference,t.sailing_id,t.allocated_teu FROM shipment_orders x JOIN transport_shipments t ON t.id=x.shipment_id WHERE x.order_id=?',(order_id,)).fetchone()
    if linked and linked['vessel'] and not force:return linked['shipment_id']
    rule=c.execute("SELECT r.*,p.name,p.latitude,p.longitude FROM destination_port_rules r JOIN shipping_ports p ON p.code=r.port_code WHERE lower(?) LIKE '%%'||lower(r.pattern)||'%%' ORDER BY r.priority LIMIT 1",(order['destination'],)).fetchone()
    if not rule:return None
    required=max(1,math.ceil(order['kg']/24000));sort='(CAST(dest.estimated_arrival AS timestamp)-CAST(load.estimated_departure AS timestamp)),CAST(load.estimated_departure AS timestamp)' if str(order['service']).upper()=='EXPRESS' else 'CAST(load.estimated_departure AS timestamp)'
    sailing=c.execute(f'''SELECT s.*,v.name vessel_name,v.imo_number,v.image_url,v.flag,a.name carrier_name,
      load.id load_call_id,load.sequence load_sequence,load.estimated_departure,orig.name origin_name,orig.latitude origin_lat,orig.longitude origin_lon,
      dest.id discharge_call_id,dest.sequence discharge_sequence,dest.estimated_arrival,dport.name destination_name,dport.latitude destination_lat,dport.longitude destination_lon
      FROM vessel_sailings s JOIN shipping_vessels v ON v.id=s.vessel_id JOIN shipping_carriers a ON a.id=v.carrier_id
      JOIN sailing_calls load ON load.sailing_id=s.id JOIN shipping_ports orig ON orig.code=load.port_code
      JOIN sailing_calls dest ON dest.sailing_id=s.id JOIN shipping_ports dport ON dport.code=dest.port_code
      WHERE load.port_code='INCOK' AND dest.port_code=? AND load.sequence<dest.sequence AND s.status='SCHEDULED'
      AND s.available_teu>=? AND s.available_reefer>=? AND CAST(load.estimated_departure AS timestamp)>CURRENT_TIMESTAMP
      ORDER BY {sort} LIMIT 1''',(rule['port_code'],required,required)).fetchone()
    if not sailing:return None
    sid=linked['shipment_id'] if linked else 'SHP-'+secrets.token_hex(5).upper();now=S.now();cutoff=datetime.fromisoformat(str(sailing['estimated_departure']).replace(' ','T')).timestamp()-2*86400
    booking='AUTO-'+sailing['voyage_number']+'-'+order_id[-5:]
    values=(booking,'OCEAN',sailing['carrier_name'],sailing['vessel_name'],sailing['voyage_number'],'ALLOCATED',sailing['origin_name'],sailing['destination_name'],sailing['origin_lat'],sailing['origin_lon'],sailing['destination_lat'],sailing['destination_lon'],str(sailing['estimated_departure']),str(sailing['estimated_arrival']),datetime.fromtimestamp(cutoff).isoformat(timespec='minutes'),sailing['id'],sailing['load_call_id'],sailing['discharge_call_id'],'SCHEDULE_ENGINE',required,now)
    if linked:c.execute('''UPDATE transport_shipments SET booking_reference=?,mode=?,carrier=?,vessel=?,voyage=?,status=?,origin_port=?,destination_port=?,origin_lat=?,origin_lon=?,destination_lat=?,destination_lon=?,planned_departure=?,planned_arrival=?,booking_cutoff=?,sailing_id=?,load_call_id=?,discharge_call_id=?,allocation_source=?,allocated_teu=?,updated=? WHERE id=?''',(*values,sid))
    else:
        c.execute('''INSERT INTO transport_shipments(id,booking_reference,mode,carrier,vessel,voyage,status,origin_port,destination_port,origin_lat,origin_lon,destination_lat,destination_lon,planned_departure,planned_arrival,booking_cutoff,sailing_id,load_call_id,discharge_call_id,allocation_source,allocated_teu,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,*values[:-1],now,now))
        c.execute('INSERT INTO shipment_orders(shipment_id,order_id,created) VALUES(?,?,?)',(sid,order_id,now))
    c.execute('DELETE FROM transport_legs WHERE shipment_id=?',(sid,))
    calls=c.execute('''SELECT sc.*,p.name port_name,p.latitude,p.longitude FROM sailing_calls sc JOIN shipping_ports p ON p.code=sc.port_code WHERE sc.sailing_id=? AND sc.sequence BETWEEN ? AND ? ORDER BY sc.sequence''',(sailing['id'],sailing['load_sequence'],sailing['discharge_sequence'])).fetchall()
    for index,(origin,destination) in enumerate(zip(calls,calls[1:]),1):
        c.execute('''INSERT INTO transport_legs(shipment_id,sequence,mode,carrier,vessel,voyage,origin_name,origin_lat,origin_lon,destination_name,destination_lat,destination_lon,planned_departure,planned_arrival,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,index,'VESSEL',sailing['carrier_name'],sailing['vessel_name'],sailing['voyage_number'],origin['port_name'],origin['latitude'],origin['longitude'],destination['port_name'],destination['latitude'],destination['longitude'],origin['estimated_departure'],destination['estimated_arrival'],'PLANNED'))
    if not linked or linked['sailing_id']!=sailing['id']:
        if linked and linked['sailing_id']:
            released=linked['allocated_teu'] or 0
            c.execute('UPDATE vessel_sailings SET available_teu=available_teu+?,available_reefer=available_reefer+?,updated=? WHERE id=?',(released,released,now,linked['sailing_id']))
        c.execute('UPDATE vessel_sailings SET available_teu=available_teu-?,available_reefer=available_reefer-?,updated=? WHERE id=?',(required,required,now,sailing['id']))
    note=f"Automatically matched to {sailing['vessel_name']} voyage {sailing['voyage_number']}; discharge at {sailing['destination_name']}."
    _order_milestone(c,sid,'Shipment allocated',note,S);_notify_shipment(c,sid,S,note)
    return sid

def allocate_pending(c,S):
    for row in c.execute("SELECT id FROM orders WHERE status NOT IN ('CANCELLED','DELIVERED') ORDER BY created").fetchall():allocate_order(c,row['id'],S)

def _simulation_steps(c,shipment_id):
    shipment=c.execute('SELECT * FROM transport_shipments WHERE id=?',(shipment_id,)).fetchone()
    if not shipment or not shipment['sailing_id']:return []
    load=c.execute('SELECT sequence FROM sailing_calls WHERE id=?',(shipment['load_call_id'],)).fetchone();discharge=c.execute('SELECT sequence FROM sailing_calls WHERE id=?',(shipment['discharge_call_id'],)).fetchone()
    if not load or not discharge:return []
    calls=c.execute('''SELECT sc.*,p.name port_name,p.latitude,p.longitude FROM sailing_calls sc JOIN shipping_ports p ON p.code=sc.port_code WHERE sc.sailing_id=? AND sc.sequence BETWEEN ? AND ? ORDER BY sc.sequence''',(shipment['sailing_id'],load['sequence'],discharge['sequence'])).fetchall()
    steps=[]
    for index,(origin,destination) in enumerate(zip(calls,calls[1:])):
        if index==0:steps.append({'latitude':float(origin['latitude']),'longitude':float(origin['longitude']),'location':origin['port_name'],'label':'Cargo at loading port','port':True})
        for fraction in (.2,.4,.6,.8):
            progress=round(fraction*100)
            steps.append({'latitude':float(origin['latitude'])+(float(destination['latitude'])-float(origin['latitude']))*fraction,'longitude':float(origin['longitude'])+(float(destination['longitude'])-float(origin['longitude']))*fraction,'location':f"{origin['port_name']} to {destination['port_name']}",'label':f'Underway to {destination["port_name"]} · {progress}%','port':False})
        final=index==len(calls)-2
        steps.append({'latitude':float(destination['latitude']),'longitude':float(destination['longitude']),'location':destination['port_name'],'label':'Cargo arrived at discharge port' if final else 'Transshipment port reached','port':True})
    for index,step in enumerate(steps):
        step['index']=index;step['number']=index+1;step['progress']=round(index*100/max(1,len(steps)-1))
    return steps

def _simulation_state(c,shipment_id):
    steps=_simulation_steps(c,shipment_id)
    latest=c.execute("SELECT event_code FROM carrier_events WHERE shipment_id=? AND source_provider='POC simulator' ORDER BY id DESC LIMIT 1",(shipment_id,)).fetchone()
    current=int(latest['event_code'].split('_')[-1]) if latest and latest['event_code'].startswith('SIM_') else -1
    return {'available':bool(steps),'active':current>=0,'current_step':current,'total_steps':len(steps),'current':steps[current] if 0<=current<len(steps) else None,'points':steps}

def shipment_snapshot(c,shipment_id):
    shipment=c.execute('SELECT * FROM transport_shipments WHERE id=?',(shipment_id,)).fetchone()
    if not shipment:return None
    result=dict(shipment)
    result['orders']=[dict(r) for r in c.execute('SELECT o.id,o.product_name,o.kg,o.destination,u.company FROM shipment_orders x JOIN orders o ON o.id=x.order_id JOIN users u ON u.id=o.user_id WHERE x.shipment_id=?',(shipment_id,)).fetchall()]
    result['legs']=[dict(r) for r in c.execute('SELECT * FROM transport_legs WHERE shipment_id=? ORDER BY sequence',(shipment_id,)).fetchall()]
    result['containers']=[dict(r) for r in c.execute('SELECT * FROM shipment_containers WHERE shipment_id=? ORDER BY id',(shipment_id,)).fetchall()]
    result['events']=[dict(r) for r in c.execute('SELECT * FROM carrier_events WHERE shipment_id=? ORDER BY occurred_at,id',(shipment_id,)).fetchall()]
    result['customs']=[dict(r) for r in c.execute('SELECT * FROM customs_milestones WHERE shipment_id=? ORDER BY id',(shipment_id,)).fetchall()]
    result['eta_history']=[dict(r) for r in c.execute('SELECT * FROM eta_history WHERE shipment_id=? ORDER BY id DESC',(shipment_id,)).fetchall()]
    result['reefer']=[dict(r) for r in c.execute('SELECT * FROM reefer_readings WHERE shipment_id=? ORDER BY occurred_at DESC,id DESC LIMIT 100',(shipment_id,)).fetchall()]
    result['exceptions']=[dict(r) for r in c.execute('SELECT * FROM operational_exceptions WHERE shipment_id=? ORDER BY status,created DESC',(shipment_id,)).fetchall()]
    result['sailing']=None;result['rotation_calls']=[]
    if result.get('sailing_id'):
        sailing=c.execute('''SELECT s.*,v.name vessel_name,v.imo_number,v.flag,v.image_url,v.capacity_teu,v.reefer_plugs,a.name carrier_name,r.name rotation_name,r.service_code,r.cycle_days FROM vessel_sailings s JOIN shipping_vessels v ON v.id=s.vessel_id JOIN shipping_carriers a ON a.id=v.carrier_id JOIN service_rotations r ON r.id=s.rotation_id WHERE s.id=?''',(result['sailing_id'],)).fetchone()
        result['sailing']=dict(sailing) if sailing else None
        result['rotation_calls']=[dict(x) for x in c.execute('''SELECT sc.*,p.name port_name,p.country,p.latitude,p.longitude FROM sailing_calls sc JOIN shipping_ports p ON p.code=sc.port_code WHERE sc.sailing_id=? ORDER BY sc.sequence''',(result['sailing_id'],)).fetchall()]
    result['simulation']=_simulation_state(c,shipment_id)
    return result

def buyer_order(c,order_id,S=None):
    row=c.execute('SELECT shipment_id FROM shipment_orders WHERE order_id=?',(order_id,)).fetchone()
    if not row and S:
        allocate_order(c,order_id,S);row=c.execute('SELECT shipment_id FROM shipment_orders WHERE order_id=?',(order_id,)).fetchone()
    if not row:return None
    result=shipment_snapshot(c,row['shipment_id'])
    result['exceptions']=[x for x in result['exceptions'] if x['buyer_visible']]
    return result

def admin_snapshot(c,S=None):
    if S:allocate_pending(c,S)
    return [shipment_snapshot(c,r['id']) for r in c.execute('SELECT id FROM transport_shipments ORDER BY updated DESC').fetchall()]

def dispatch_ready(c,order):
    from compliance_core import order_readiness
    docs=order_readiness(c,order)
    if docs['departure_blocking']:return False,f'{docs["departure_blocking"]} pre-departure document gates remain.'
    # Check new carrier booking (transport_shipments workflow)
    row=c.execute('SELECT shipment_id FROM shipment_orders WHERE order_id=?',(order['id'],)).fetchone()
    if row:
        sid=row['shipment_id'];leo=c.execute("SELECT 1 FROM customs_milestones WHERE shipment_id=? AND kind='LEO' AND status='CLEARED'",(sid,)).fetchone()
        if not leo:return False,'Let Export Order has not been cleared.'
        containers=c.execute("SELECT * FROM shipment_containers WHERE shipment_id=?",(sid,)).fetchall()
        if not containers or any(not x['seal_number'] or not x['verified_gross_kg'] or x['stuffing_status'] not in ('SEALED','GATE_IN','LOADED') for x in containers):return False,'Every container requires stuffing completion, seal and VGM.'
        return True,''
    # Fallback: legacy shipments table (backward-compatible workflow)
    legacy=c.execute("SELECT vessel FROM shipments WHERE order_id=?",(order['id'],)).fetchone()
    if legacy and legacy['vessel']:return True,''
    return False,'Create and assign a carrier booking before dispatch.'

def admin_action(c,staff,action,d,S,A):
    A.require(staff,'OPERATIONS');now=S.now()
    if action=='shipment-simulation':
        sid=A.text(d,'shipment_id');mode=A.text(d,'mode',30).upper();steps=_simulation_steps(c,sid)
        if not steps:raise S.APIError('Allocate this order to a scheduled sailing before using the simulator.')
        if mode=='RESET':
            c.execute("DELETE FROM carrier_events WHERE shipment_id=? AND source_provider='POC simulator'",(sid,));label='Simulation reset';detail='Testing events removed'
        else:
            previous=c.execute("SELECT event_code FROM carrier_events WHERE shipment_id=? AND source_provider='POC simulator' ORDER BY id DESC LIMIT 1",(sid,)).fetchone();current=int(previous['event_code'].split('_')[-1]) if previous else -1
            if mode=='START':
                c.execute("DELETE FROM carrier_events WHERE shipment_id=? AND source_provider='POC simulator'",(sid,));target=0
            elif mode=='PREVIOUS':target=max(current-1,0)
            elif mode=='NEXT_PORT':
                target=next((i for i,x in enumerate(steps) if i>current and x['port']),len(steps)-1)
            elif mode=='COMPLETE':target=len(steps)-1
            elif mode=='STEP':target=min(current+1,len(steps)-1)
            elif mode=='JUMP':
                try:target=int(d.get('step'))
                except (TypeError,ValueError):raise S.APIError('Choose a valid simulation point.')
                if target<0 or target>=len(steps):raise S.APIError('The selected simulation point is outside this cargo journey.')
            else:raise S.APIError('Unknown simulation control.')
            point=steps[target];label=f"POC simulation · {point['label']}";detail=f"Step {target+1} of {len(steps)}"
            c.execute('INSERT INTO carrier_events(shipment_id,event_code,event_label,event_type,occurred_at,location_name,latitude,longitude,source_type,source_provider,received_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,f'SIM_{target:03d}',label,'ACTUAL',S.now(),point['location'],point['latitude'],point['longitude'],'STAFF','POC simulator',S.now(),f'Testing only · {detail}'))
        owner=c.execute('SELECT o.user_id FROM shipment_orders x JOIN orders o ON o.id=x.order_id WHERE x.shipment_id=? LIMIT 1',(sid,)).fetchone()
        A.record(c,staff,'SHIPMENT_SIMULATION',sid,label,after={'mode':mode,'detail':detail},topic='buyer',uid=owner['user_id'] if owner else None)
    elif action=='auto-allocate':
        oid=A.text(d,'order_id');sid=allocate_order(c,oid,S,force=True)
        if not sid:raise S.APIError('No suitable scheduled sailing is available for this destination and capacity.')
        A.record(c,staff,'SHIPMENT_AUTO_ALLOCATED',sid,'Order matched to the best available sailing',after={'order_id':oid},topic='buyer')
    elif action=='shipment-plan':
        oid=A.text(d,'order_id');order=c.execute("SELECT * FROM orders WHERE id=? AND status NOT IN ('CANCELLED','DELIVERED')",(oid,)).fetchone()
        if not order:raise S.APIError('Choose an active order.')
        existing=c.execute('SELECT shipment_id FROM shipment_orders WHERE order_id=?',(oid,)).fetchone();sid=d.get('id') or (existing['shipment_id'] if existing else 'SHP-'+secrets.token_hex(5).upper())
        old=c.execute('SELECT * FROM transport_shipments WHERE id=?',(sid,)).fetchone();eta=_stamp(d.get('planned_arrival'),True)
        values=(A.text(d,'booking_reference',120,False),A.text(d,'mode',20),A.text(d,'carrier',120,False),A.text(d,'vessel',120,False),A.text(d,'voyage',120,False),A.text(d,'origin_port',160),A.text(d,'destination_port',160),_float(d,'origin_lat',-90,90),_float(d,'origin_lon',-180,180),_float(d,'destination_lat',-90,90),_float(d,'destination_lon',-180,180),_stamp(d.get('planned_departure'),True),eta,_stamp(d.get('booking_cutoff'),True),_stamp(d.get('documentation_cutoff'),True),_stamp(d.get('vgm_cutoff'),True),A.text(d,'shipping_instructions',2000,False))
        if old:
            if old['planned_arrival'] and eta and old['planned_arrival']!=eta:c.execute('INSERT INTO eta_history(shipment_id,previous_eta,revised_eta,reason,source_type,source_provider,changed_at) VALUES(?,?,?,?,?,?,?)',(sid,old['planned_arrival'],eta,'Staff revised shipment plan','STAFF',staff['name'],now));_notify_shipment(c,sid,S,f'{sid}: estimated arrival changed to {eta}.')
            c.execute('UPDATE transport_shipments SET booking_reference=?,mode=?,carrier=?,vessel=?,voyage=?,origin_port=?,destination_port=?,origin_lat=?,origin_lon=?,destination_lat=?,destination_lon=?,planned_departure=?,planned_arrival=?,booking_cutoff=?,documentation_cutoff=?,vgm_cutoff=?,shipping_instructions=?,updated=? WHERE id=?',(*values,now,sid))
        else:c.execute("INSERT INTO transport_shipments(id,booking_reference,mode,carrier,vessel,voyage,status,origin_port,destination_port,origin_lat,origin_lon,destination_lat,destination_lon,planned_departure,planned_arrival,booking_cutoff,documentation_cutoff,vgm_cutoff,shipping_instructions,created,updated) VALUES(?,?,?,?,?,?,'BOOKED',?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,*values,now,now))
        c.execute('INSERT INTO shipment_orders VALUES(?,?,?) ON CONFLICT(order_id) DO UPDATE SET shipment_id=excluded.shipment_id',(sid,oid,now))
        c.execute("INSERT INTO transport_legs(shipment_id,sequence,mode,carrier,vessel,voyage,origin_name,origin_lat,origin_lon,destination_name,destination_lat,destination_lon,planned_departure,planned_arrival) VALUES(?,1,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(shipment_id,sequence) DO UPDATE SET mode=excluded.mode,carrier=excluded.carrier,vessel=excluded.vessel,voyage=excluded.voyage,origin_name=excluded.origin_name,origin_lat=excluded.origin_lat,origin_lon=excluded.origin_lon,destination_name=excluded.destination_name,destination_lat=excluded.destination_lat,destination_lon=excluded.destination_lon,planned_departure=excluded.planned_departure,planned_arrival=excluded.planned_arrival",(sid,values[1],values[2],values[3],values[4],values[5],values[7],values[8],values[6],values[9],values[10],values[11],values[12]))
        A.record(c,staff,'SHIPMENT_PLAN_SAVED',sid,'Carrier booking and route updated',after=d,topic='buyer',uid=order['user_id'])
    elif action=='shipment-leg':
        sid=A.text(d,'shipment_id');seq=A.integer(d,'sequence',1,20)
        if not c.execute('SELECT 1 FROM transport_shipments WHERE id=?',(sid,)).fetchone():raise S.APIError('Shipment not found.',404)
        values=(A.text(d,'mode',30),A.text(d,'carrier',120,False),A.text(d,'vessel',120,False),A.text(d,'voyage',120,False),A.text(d,'origin_name',160),_float(d,'origin_lat',-90,90),_float(d,'origin_lon',-180,180),A.text(d,'destination_name',160),_float(d,'destination_lat',-90,90),_float(d,'destination_lon',-180,180),_stamp(d.get('planned_departure'),True),_stamp(d.get('planned_arrival'),True))
        c.execute("INSERT INTO transport_legs(shipment_id,sequence,mode,carrier,vessel,voyage,origin_name,origin_lat,origin_lon,destination_name,destination_lat,destination_lon,planned_departure,planned_arrival) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(shipment_id,sequence) DO UPDATE SET mode=excluded.mode,carrier=excluded.carrier,vessel=excluded.vessel,voyage=excluded.voyage,origin_name=excluded.origin_name,origin_lat=excluded.origin_lat,origin_lon=excluded.origin_lon,destination_name=excluded.destination_name,destination_lat=excluded.destination_lat,destination_lon=excluded.destination_lon,planned_departure=excluded.planned_departure,planned_arrival=excluded.planned_arrival",(sid,seq,*values));A.record(c,staff,'SHIPMENT_LEG_SAVED',sid,'Route leg updated',after=d,topic='buyer')
    elif action=='shipment-container':
        sid=A.text(d,'shipment_id');number=A.text(d,'container_number',20).upper();status=A.text(d,'stuffing_status',30);gross=A.integer(d,'verified_gross_kg',0);tare=A.integer(d,'tare_kg',0)
        if status not in ('PLANNED','STUFFING','SEALED','GATE_IN','LOADED'):raise S.APIError('Invalid stuffing stage.')
        seal=A.text(d,'seal_number',60,False);vgm=A.text(d,'vgm_reference',120,False)
        if status in ('SEALED','GATE_IN','LOADED') and (not seal or gross<=tare or not vgm):raise S.APIError('Seal, valid VGM weight and VGM reference are required before sealing.')
        values=(A.text(d,'container_type',20),seal,status,_stamp(d.get('stuffed_at'),True),_float(d,'reefer_setpoint',-35,20,True),_float(d,'ventilation_cbm',0,500,True),_float(d,'humidity_percent',0,100,True),tare,gross,A.text(d,'vgm_method',30,False),A.text(d,'vgm_party',160,False),vgm,_stamp(d.get('vgm_at'),True),now)
        c.execute('INSERT INTO shipment_containers(shipment_id,container_number,container_type,seal_number,stuffing_status,stuffed_at,reefer_setpoint,ventilation_cbm,humidity_percent,tare_kg,verified_gross_kg,vgm_method,vgm_party,vgm_reference,vgm_at,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(container_number) DO UPDATE SET container_type=excluded.container_type,seal_number=excluded.seal_number,stuffing_status=excluded.stuffing_status,stuffed_at=excluded.stuffed_at,reefer_setpoint=excluded.reefer_setpoint,ventilation_cbm=excluded.ventilation_cbm,humidity_percent=excluded.humidity_percent,tare_kg=excluded.tare_kg,verified_gross_kg=excluded.verified_gross_kg,vgm_method=excluded.vgm_method,vgm_party=excluded.vgm_party,vgm_reference=excluded.vgm_reference,vgm_at=excluded.vgm_at,updated=excluded.updated',(sid,number,*values));A.record(c,staff,'CONTAINER_SAVED',number,'Container, seal and VGM updated',after=d,topic='buyer')
    elif action=='customs-milestone':
        sid=A.text(d,'shipment_id');kind=A.text(d,'kind').upper();status=A.text(d,'status').upper()
        if kind not in CUSTOMS_KINDS or status not in ('PENDING','SUBMITTED','ACKNOWLEDGED','QUERY','HOLD','CLEARED','FILED'):raise S.APIError('Invalid customs milestone.')
        c.execute('INSERT INTO customs_milestones(shipment_id,kind,reference,status,occurred_at,source_type,source_provider,note,updated) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(shipment_id,kind) DO UPDATE SET reference=excluded.reference,status=excluded.status,occurred_at=excluded.occurred_at,source_type=excluded.source_type,source_provider=excluded.source_provider,note=excluded.note,updated=excluded.updated',(sid,kind,A.text(d,'reference',160,False),status,_stamp(d.get('occurred_at'),True),'STAFF',staff['name'],A.text(d,'note',1000,False),now));_notify_shipment(c,sid,S,f'{sid}: {kind.replace("_"," ")} is {status.lower()}.');A.record(c,staff,'CUSTOMS_MILESTONE',sid,kind+' '+status,after=d,topic='buyer')
    elif action=='transport-event':
        sid=A.text(d,'shipment_id');code=A.text(d,'event_code',60).upper();label=A.text(d,'event_label',120);etype=A.text(d,'event_type',20)
        if etype not in ('ESTIMATED','ACTUAL'):raise S.APIError('Choose estimated or actual.')
        lat=_float(d,'latitude',-90,90,True);lon=_float(d,'longitude',-180,180,True)
        c.execute('INSERT INTO carrier_events(shipment_id,event_code,event_label,event_type,occurred_at,location_name,latitude,longitude,source_type,source_provider,received_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,code,label,etype,_stamp(d.get('occurred_at')),A.text(d,'location_name',160),lat,lon,'STAFF',staff['name'],now,A.text(d,'note',1000,False)))
        if etype=='ACTUAL' and code in ('DEPARTED','ARRIVED','DELIVERED'):c.execute('UPDATE transport_shipments SET status=?,updated=? WHERE id=?',({'DEPARTED':'IN_TRANSIT','ARRIVED':'ARRIVED','DELIVERED':'DELIVERED'}[code],now,sid))
        _order_milestone(c,sid,label,f'{d.get("location_name")}{" · "+d.get("note") if d.get("note") else ""}',S)
        if etype=='ACTUAL':_order_milestone(c,sid,label,f'{label} at {d.get("location_name")}. '+A.text(d,'note',1000,False),S)
        _notify_shipment(c,sid,S,f'{sid}: {label} at {d.get("location_name")}.');A.record(c,staff,'TRANSPORT_EVENT',sid,label,after=d,topic='buyer')
    elif action=='reefer-reading':
        sid=A.text(d,'shipment_id');cid=A.integer(d,'container_id',1);container=c.execute('SELECT * FROM shipment_containers WHERE id=? AND shipment_id=?',(cid,sid)).fetchone()
        if not container:raise S.APIError('Container not found.',404)
        supply=_float(d,'supply_temperature',-50,40);returned=_float(d,'return_temperature',-50,40);setpoint=_float(d,'setpoint',-35,20);delta=max(abs(supply-setpoint),abs(returned-setpoint));severity='CRITICAL' if delta>5 else 'WARNING' if delta>2 else 'NORMAL'
        c.execute('INSERT INTO reefer_readings(shipment_id,container_id,setpoint,supply_temperature,return_temperature,humidity_percent,alarm_code,severity,occurred_at,source_type,source_provider,received_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,cid,setpoint,supply,returned,_float(d,'humidity_percent',0,100,True),A.text(d,'alarm_code',80,False),severity,_stamp(d.get('occurred_at')),'STAFF',staff['name'],now,A.text(d,'note',1000,False)))
        if severity!='NORMAL':
            c.execute("INSERT INTO operational_exceptions(shipment_id,kind,severity,title,evidence,required_action,owner,status,buyer_visible,created,updated) VALUES(?,?,?,?,?,?,?,'OPEN',1,?,?)",(sid,'TEMPERATURE_EXCURSION',severity,'Reefer temperature exception',f'Set point {setpoint} C; supply {supply} C; return {returned} C','Inspect reefer and record cargo disposition','Cold-chain manager',now,now));_notify_shipment(c,sid,S,f'{sid}: reefer temperature exception recorded for {container["container_number"]}.')
        A.record(c,staff,'REEFER_READING',container['container_number'],severity,after=d,topic='buyer')
    elif action=='shipping-exception':
        eid=d.get('id')
        if eid:
            status=A.text(d,'status',30);resolution=A.text(d,'resolution',1000,False)
            if status not in ('OPEN','ACKNOWLEDGED','RESOLVED'):raise S.APIError('Invalid exception status.')
            c.execute('UPDATE operational_exceptions SET status=?,resolution=?,updated=? WHERE id=?',(status,resolution,now,eid));A.record(c,staff,'SHIPPING_EXCEPTION_UPDATED',eid,resolution or status,after=d,topic='buyer')
        else:
            sid=A.text(d,'shipment_id');severity=A.text(d,'severity',20)
            if severity not in ('INFO','WARNING','CRITICAL'):raise S.APIError('Invalid severity.')
            c.execute('INSERT INTO operational_exceptions(shipment_id,kind,severity,title,evidence,required_action,owner,due_at,buyer_visible,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,A.text(d,'kind',80),severity,A.text(d,'title',160),A.text(d,'evidence',1000),A.text(d,'required_action',1000),A.text(d,'owner',120),_stamp(d.get('due_at'),True),A.integer(d,'buyer_visible',0,1),now,now));_notify_shipment(c,sid,S,f'{sid}: {d.get("title")}. Action: {d.get("required_action")}');A.record(c,staff,'SHIPPING_EXCEPTION_CREATED',sid,d.get('title','Exception'),after=d,topic='buyer')
    else:raise S.APIError('Unknown shipping action.',404)
