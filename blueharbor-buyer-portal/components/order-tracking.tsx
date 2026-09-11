'use client';
/* oxlint-disable next/no-img-element */

import {
  Check,
  ChevronDown,
  Download,
  MapPin,
  Package,
  Ship,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import ShipmentMap from '@/components/shipment-map';

type Order = {
  id: string;
  product_name: string;
  kg: number;
  total: number;
  destination: string;
  service: string;
  status: string;
  created: string;
  shipment?: {
    carrier?: string;
    vessel?: string;
    container?: string;
    eta?: string;
    location?: string;
  } | null;
  documents?: { id: string; kind: string; version: number }[];
  compliance?: {
    country:string;started:number;released:number;total:number;progress:number;
    departure_blocking:number;clearance_blocking:number;departure_ready:boolean;clearance_ready:boolean;
    items:{requirement_code:string;document_name:string;status:string;required_stage:string;responsible_party:string;official_issuer:string;original_required:number;source_url?:string;document?:{id:string;version:number}}[];
  };
  transport?: {
    id:string;booking_reference:string;carrier:string;vessel:string;voyage:string;status:string;origin_port:string;destination_port:string;planned_departure:string;actual_departure:string;planned_arrival:string;actual_arrival:string;updated:string;origin_lat?:number;origin_lon?:number;destination_lat?:number;destination_lon?:number;load_call_id?:number;discharge_call_id?:number;
    sailing?:{vessel_name:string;imo_number:string;flag:string;image_url:string;carrier_name:string;rotation_name:string;service_code:string;cycle_days:number;schedule_source:string;voyage_number:string}|null;
    rotation_calls?:{id:number;sequence:number;port_name:string;country:string;estimated_arrival:string;estimated_departure:string;latitude?:number;longitude?:number}[];
    legs:{id:number;sequence:number;origin_name:string;origin_lat?:number;origin_lon?:number;destination_name:string;destination_lat?:number;destination_lon?:number;planned_departure:string;actual_departure:string;planned_arrival:string;actual_arrival:string;vessel:string;voyage:string;status:string}[];
    containers:{id:number;container_number:string;container_type:string;seal_number:string;stuffing_status:string;reefer_setpoint?:number;verified_gross_kg:number}[];
    events:{id:number;event_code:string;event_label:string;event_type:string;occurred_at:string;location_name:string;latitude?:number;longitude?:number;source_type:string;source_provider:string;note:string}[];
    customs:{id:number;kind:string;reference:string;status:string;occurred_at:string;source_type:string;source_provider:string;note:string}[];
    eta_history:{id:number;previous_eta:string;revised_eta:string;reason:string;source_type:string;changed_at:string}[];
    reefer:{id:number;container_id:number;setpoint:number;supply_temperature:number;return_temperature:number;humidity_percent?:number;severity:string;occurred_at:string;source_type:string;source_provider:string}[];
    exceptions:{id:number;severity:string;title:string;required_action:string;status:string;due_at:string}[];
  } | null;
  events: { id: number; title: string; note: string; created: string }[];
};
const steps = [
  { status: 'CONFIRMED', label: 'Order confirmed', note: 'Stock reserved' },
  {
    status: 'PROCESSING',
    label: 'Preparing your order',
    note: 'Warehouse processing',
  },
  { status: 'SHIPPED', label: 'On the way', note: 'Dispatched from origin' },
  { status: 'DELIVERED', label: 'Delivered', note: 'Delivery confirmed' },
];
const date = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
const gateLabels:Record<string,string>={PRE_CUSTOMS:'Before customs filing',PRE_LOADING:'Before loading',POST_DEPARTURE:'After departure',PRE_ARRIVAL:'Before arrival',DESTINATION_RELEASE:'Destination release'};
const vesselPhoto=(name?:string)=>name?.toLowerCase().includes('pacific')?'/vessels/blueharbor-pacific-realistic.png':'/vessels/blueharbor-atlas-realistic.png';

export default function OrderTracking({
  order,
  expanded,
  toggle,
  cancel,
  busy,
}: {
  order: Order;
  expanded: boolean;
  toggle: () => void;
  cancel: () => void;
  busy: boolean;
}) {
  const cancelled = order.status === 'CANCELLED';
  const current = steps.findIndex((s) => s.status === order.status);
  const latest = order.events[order.events.length - 1];
  return (
    <article className={`shipment-card ${cancelled ? 'is-cancelled' : ''}`}>
      <div className="shipment-top">
        <span>{order.id}</span>
        <span>Placed {date(order.created)}</span>
        <span className="status-pill">
          {cancelled ? 'Cancelled' : steps[current]?.label || order.status}
        </span>
      </div>
      <div className="shipment-summary">
        <span className="shipment-symbol">
          <Package size={26} />
        </span>
        <div className="shipment-product">
          <h2>{order.product_name}</h2>
          <p>
            {order.kg.toLocaleString()} kg · {order.service} shipping
          </p>
        </div>
        <div className="shipment-destination">
          <small>DESTINATION</small>
          <b>
            <MapPin size={16} />
            {order.destination}
          </b>
        </div>
        <strong className="shipment-total">
          {new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
          }).format(order.total / 100)}
        </strong>
      </div>
      <div className="shipment-actions">
        <p>
          <span className="dot" />
          {cancelled
            ? 'Reservation released'
            : latest?.note || 'Awaiting warehouse update'}
        </p>
        <Button
          variant="outline"
          aria-expanded={expanded}
          aria-controls={`tracking-${order.id}`}
          onClick={toggle}
        >
          {' '}
          {expanded ? 'Hide tracking' : 'Track order'}{' '}
          <ChevronDown size={16} className={expanded ? 'rotated' : ''} />
        </Button>
      </div>
      {expanded && (
        <section
          className="shipment-tracking"
          id={`tracking-${order.id}`}
          aria-label={`Tracking for ${order.id}`}
        >
          <div className="tracking-heading">
            <div>
              <span className="eyebrow">SHIPMENT PROGRESS</span>
              <h3>
                {cancelled
                  ? 'Order cancelled'
                  : steps[current]?.label || order.status}
              </h3>
            </div>
            <Ship size={28} />
          </div>
          {cancelled ? (
            <div className="cancelled-note">
              <X size={20} />
              This order will not proceed to delivery. Reserved stock has been
              released.
            </div>
          ) : (
            <ol className="shipment-steps">
              {steps.map((s, i) => {
                const event = order.events.find(
                  (e) =>
                    e.title === s.status ||
                    (s.status === 'CONFIRMED' && e.title === 'Order confirmed'),
                );
                return (
                  <li
                    key={s.status}
                    className={
                      i < current
                        ? 'complete'
                        : i === current
                          ? 'current'
                          : 'upcoming'
                    }
                    aria-current={i === current ? 'step' : undefined}
                  >
                    <span className="milestone-marker">
                      {i <= current ? <Check size={17} /> : i + 1}
                    </span>
                    <div>
                      <b>{s.label}</b>
                      <span>{i > current ? 'Upcoming' : s.note}</span>
                      <small>
                        {event
                          ? date(event.created)
                          : i <= current
                            ? 'Time not recorded'
                            : 'Awaiting update'}
                      </small>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
          {order.transport ? <section className="live-shipment-workspace">
            <div className="tracking-heading"><div><span className="eyebrow">LIVE SHIPMENT WORKSPACE</span><h3>{order.transport.origin_port} → {order.transport.destination_port}</h3><p>Last synchronized {date(order.transport.updated)}</p></div><span className="status-pill">{order.transport.status.replaceAll('_',' ')}</span></div>
            {order.transport.sailing&&<article className="buyer-vessel-card"><img src={vesselPhoto(order.transport.sailing.vessel_name)} alt={`${order.transport.sailing.vessel_name} refrigerated container vessel`}/><div><span className="eyebrow">{order.transport.sailing.schedule_source==='SAMPLE'?'SCHEDULE SAMPLE':'CARRIER SCHEDULE'}</span><h3>{order.transport.sailing.vessel_name}</h3><p>{order.transport.sailing.carrier_name} · Voyage {order.transport.voyage}</p><small>IMO {order.transport.sailing.imo_number} · {order.transport.sailing.flag} · {order.transport.sailing.rotation_name}</small><span className="vessel-photo-note">Representative vessel photograph</span></div></article>}
            <ShipmentMap shipment={order.transport}/>
            <div className="transport-facts"><span><small>BOOKING</small><b>{order.transport.booking_reference||'Pending'}</b></span><span><small>CARRIER</small><b>{order.transport.carrier||'Pending'}</b></span><span><small>VESSEL / VOYAGE</small><b>{[order.transport.vessel,order.transport.voyage].filter(Boolean).join(' · ')||'Pending'}</b></span><span><small>ESTIMATED ARRIVAL</small><b>{order.transport.planned_arrival?date(order.transport.planned_arrival):'Pending'}</b></span></div>
            {!!order.transport.rotation_calls?.length&&<section className="buyer-vessel-journey"><div><span className="eyebrow">FULL VESSEL JOURNEY</span><h4>Where the vessel travels</h4><p>Your cargo uses the highlighted part of this continuing rotation.</p></div><ol>{order.transport.rotation_calls.map(call=>{const load=call.id===order.transport?.load_call_id,discharge=call.id===order.transport?.discharge_call_id;const loadSequence=order.transport?.rotation_calls?.find(x=>x.id===order.transport?.load_call_id)?.sequence||0,dischargeSequence=order.transport?.rotation_calls?.find(x=>x.id===order.transport?.discharge_call_id)?.sequence||0,cargo=call.sequence>=loadSequence&&call.sequence<=dischargeSequence;return <li key={call.id} className={(cargo?'cargo-window ':'')+(load?'load-call ':discharge?'discharge-call ':'')}><span>{call.sequence}</span><div><b>{call.port_name}</b><small>{call.country}</small></div><time>{call.estimated_arrival?date(call.estimated_arrival):'Rotation start'}</time>{load?<em>Your cargo loads</em>:discharge?<em>Your cargo arrives</em>:null}</li>})}</ol></section>}
            {!!order.transport.exceptions.filter(x=>x.status!=='RESOLVED').length&&<div className="shipment-exceptions">{order.transport.exceptions.filter(x=>x.status!=='RESOLVED').map(x=><article key={x.id}><b>{x.title}</b><p>{x.required_action}</p><small>{x.severity} · {x.due_at?`due ${date(x.due_at)}`:'action required'}</small></article>)}</div>}
            <div className="transport-grid">
              <div><h4>Route and transshipments</h4>{order.transport.legs.map(leg=><article className="transport-row" key={leg.id}><span>{leg.sequence}</span><div><b>{leg.origin_name} → {leg.destination_name}</b><small>{[leg.vessel,leg.voyage].filter(Boolean).join(' · ')||'Transport pending'} · {leg.status}</small></div></article>)}</div>
              <div><h4>Containers and reefer</h4>{order.transport.containers.map(c=>{const reading=order.transport?.reefer.find(r=>r.container_id===c.id);return <article className="transport-row" key={c.id}><Package size={18}/><div><b>{c.container_number} · {c.container_type}</b><small>Seal {c.seal_number||'pending'} · {c.stuffing_status.replaceAll('_',' ')}</small>{typeof c.reefer_setpoint==='number'?<span className={reading&&reading.severity!=='NORMAL'?'temp-alert':'temp-normal'}>{reading?`${reading.supply_temperature}°C supply · ${reading.severity}`:`Set point ${c.reefer_setpoint}°C · awaiting reading`}</span>:null}</div></article>})}</div>
            </div>
            <div className="customs-strip"><h4>Customs progress</h4>{['ESANCHIT','SHIPPING_BILL','LEO','EGM'].map(kind=>{const item=order.transport?.customs.find(x=>x.kind===kind);const done=item?.status==='CLEARED'||item?.status==='FILED';return <div key={kind} className={done?'done':''}><span>{done?<Check size={14}/>:null}</span><b>{kind.replaceAll('_',' ')}</b><small>{item?`${item.status}${item.reference?' · '+item.reference:''}`:'Pending'}</small></div>})}</div>
            <div className="carrier-timeline"><h4>Transport events</h4>{[...order.transport.events].reverse().map(event=>{const simulated=event.source_provider==='POC simulator';return <article key={event.id}><time>{date(event.occurred_at)}</time><span className={'source-badge '+(simulated?'source-simulation':'source-'+event.source_type.toLowerCase())}>{simulated?'POC simulation':event.source_type==='STAFF'?'Staff entered':event.source_type.toLowerCase()+' reported'}</span><div><b>{event.event_label}</b><p>{event.location_name}{event.note?' · '+event.note:''}</p><small>{event.event_type}</small></div></article>})}</div>
          </section>:<section className="shipment-awaiting"><Ship size={25}/><div><b>Shipment planning has not started</b><p>BlueHarbor will publish the booking, route and confirmed transport events here.</p></div></section>}
          {order.compliance && (
            <section className="order-document-gates">
              <div className="gate-summary">
                <article className={order.compliance.departure_ready?'gate-clear':'gate-wait'}><small>DEPARTURE GATE</small><b>{order.compliance.departure_ready?'Ready for loading':`${order.compliance.departure_blocking} items blocking`}</b><span>Exporter-side documents required before dispatch</span></article>
                <article className={order.compliance.clearance_ready?'gate-clear':'gate-wait'}><small>DESTINATION GATE</small><b>{order.compliance.clearance_ready?'Clearance pack ready':`${order.compliance.clearance_blocking} items remaining`}</b><span>Includes carrier and importer evidence produced later</span></article>
              </div>
              <div className="gate-progress"><div><b>Order documentation</b><span>{order.compliance.started}/{order.compliance.total} started · {order.compliance.released} released</span></div><i><span style={{width:`${order.compliance.progress}%`}}/></i></div>
              <div className="gate-documents">{Object.entries(gateLabels).map(([stage,label])=>{
                const items=order.compliance?.items.filter(item=>item.required_stage===stage)||[];
                return items.length?<div className="gate-stage" key={stage}><h4>{label}</h4>{items.map(item=><article key={item.requirement_code}><span className={'doc-state '+item.status.toLowerCase()}>{item.status.replaceAll('_',' ')}</span><div><b>{item.document_name}</b><small>{item.responsible_party.replaceAll('_',' ')} · issued by {item.official_issuer||'designated authority'}{item.original_required?' · original required':''}</small></div>{item.document&&item.status==='RELEASED'?<a className="download" href={'/api/trade-document/'+item.document.id}><Download size={15}/>Download</a>:item.source_url?<a className="download" href={item.source_url} target="_blank" rel="noreferrer">Guidance</a>:null}</article>)}</div>:null;
              })}</div>
              {order.compliance.clearance_ready&&<a className="clearance-pack" href={'/api/clearance-pack/'+order.id}><Download size={17}/>Download clearance pack</a>}
            </section>
          )}
          <div className="tracking-log">
            {order.shipment && (
              <div className="origin-details">
                {Object.entries(order.shipment)
                  .filter(
                    ([key, value]) =>
                      [
                        'carrier',
                        'vessel',
                        'container',
                        'eta',
                        'location',
                      ].includes(key) && value,
                  )
                  .map(([key, value]) => (
                    <span key={key}>
                      <b>{key === 'eta' ? 'Estimated arrival' : key}</b>
                      {value}
                    </span>
                  ))}
              </div>
            )}
            <h4>Recorded updates</h4>
            {[...order.events].reverse().map((e) => (
              <div className="tracking-event" key={e.id}>
                <time dateTime={e.created}>{date(e.created)}</time>
                <p>
                  <b>
                    {steps.find((s) => s.status === e.title)?.label || e.title}
                  </b>
                  {e.note}
                </p>
              </div>
            ))}
          </div>
          <div className="tracking-footer">
            <a className="download" href={'/api/confirmation/' + order.id}>
              <Download size={16} />
              Order confirmation PDF
            </a>
            {order.status === 'CONFIRMED' && (
              <Button variant="ghost" disabled={busy} onClick={cancel}>
                Cancel order
              </Button>
            )}
          </div>
          <p className="tracking-disclosure">
            Warehouse-recorded milestones · refreshes every 15 seconds. Delivery
            timing appears only when recorded; no carrier or sensor feed is
            connected.
          </p>
        </section>
      )}
    </article>
  );
}
