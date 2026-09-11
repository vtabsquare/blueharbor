'use client';
import { useEffect, useMemo, useState } from 'react';
import { Anchor, Check, Clock3, Ship } from 'lucide-react';
import countries from '@/data/world-map.json';

type Point={id?:number;event_code?:string;event_label?:string;latitude?:number|string|null;longitude?:number|string|null;location_name?:string;event_type?:string;source_type?:string;source_provider?:string;occurred_at?:string;note?:string};
type Leg={sequence:number;origin_name:string;origin_lat?:number|string|null;origin_lon?:number|string|null;destination_name:string;destination_lat?:number|string|null;destination_lon?:number|string|null};
type Call={id:number;sequence:number;port_name:string;country:string;terminal?:string;latitude?:number|string|null;longitude?:number|string|null;estimated_arrival?:string;estimated_departure?:string;actual_arrival?:string;actual_departure?:string};
type SimulationPoint={index:number;number:number;latitude:number;longitude:number;location:string;label:string;port:boolean;progress:number};
type Simulation={available:boolean;active:boolean;current_step:number;total_steps:number;current?:SimulationPoint|null;points:SimulationPoint[]};
export type Shipment={id:string;updated:string;origin_port:string;destination_port:string;origin_lat?:number|string|null;origin_lon?:number|string|null;destination_lat?:number|string|null;destination_lon?:number|string|null;load_call_id?:number|null;discharge_call_id?:number|null;legs:Leg[];events:Point[];rotation_calls?:Call[];simulation?:Simulation};
type XY=[number,number];
const coords=(lon?:number|string|null,lat?:number|string|null):XY|null=>{const x=Number(lon),y=Number(lat);return Number.isFinite(x)&&Number.isFinite(y)?[x,y]:null};
const project=([lon,lat]:XY):XY=>[(lon+180)/360*1000,(90-lat)/180*500];
const time=(value?:string)=>value?new Date(value).getTime():NaN;
const stamp=(value?:string)=>value&&!Number.isNaN(time(value))?new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Not reported';
const line=(points:XY[])=>points.map(point=>project(point).join(',')).join(' ');
const segments=(points:XY[])=>{const result:XY[][]=[];for(const point of points){const current=result.at(-1);if(!current){result.push([point]);continue}const previous=current.at(-1) as XY,delta=point[0]-previous[0];if(Math.abs(delta)<=180){current.push(point);continue}const adjusted=point[0]+(delta>180?-360:360),boundary=delta>180?-180:180,ratio=(boundary-previous[0])/(adjusted-previous[0]),latitude=previous[1]+(point[1]-previous[1])*ratio;current.push([boundary,latitude]);result.push([[-boundary,latitude],point])}return result};

export default function ShipmentMap({shipment,compact=false}:{shipment:Shipment;compact?:boolean}){
 const [now,setNow]=useState(()=>Date.now()),[hovered,setHovered]=useState<number|null>(null);
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),30000);return()=>clearInterval(timer)},[]);
 const model=useMemo(()=>{
  const cargo:XY[]=shipment.legs.flatMap((leg,index)=>{const values=index===0?[coords(leg.origin_lon,leg.origin_lat),coords(leg.destination_lon,leg.destination_lat)]:[coords(leg.destination_lon,leg.destination_lat)];return values.filter((value):value is XY=>value!==null)});
  if(!cargo.length){const origin=coords(shipment.origin_lon,shipment.origin_lat),destination=coords(shipment.destination_lon,shipment.destination_lat);if(origin)cargo.push(origin);if(destination)cargo.push(destination)}
  const calls=(shipment.rotation_calls||[]).filter(call=>coords(call.longitude,call.latitude)).sort((a,b)=>a.sequence-b.sequence);
  const rotation=calls.map(call=>coords(call.longitude,call.latitude) as XY);
  const actual=(shipment.events||[]).filter(event=>event.event_type==='ACTUAL'&&coords(event.longitude,event.latitude)).at(-1);
  if(actual){const simulated=actual.source_provider==='POC simulator';return {cargo,calls,rotation,position:coords(actual.longitude,actual.latitude),positionLabel:actual.location_name||'Last known position',positionBasis:simulated?'POC simulation':actual.source_type==='CARRIER'||actual.source_type==='API'?'Carrier reported':'Staff confirmed'}}
  if(!calls.length)return {cargo,calls,rotation,position:cargo[0]||null,positionLabel:shipment.origin_port,positionBasis:'Schedule estimated'};
  const first=calls[0],last=calls.at(-1) as Call;
  if(now<=time(first.estimated_departure))return {cargo,calls,rotation,position:rotation[0],positionLabel:`At ${first.port_name}`,positionBasis:'Schedule estimated'};
  for(let index=0;index<calls.length-1;index++){const start=time(calls[index].estimated_departure),end=time(calls[index+1].estimated_arrival);if(now>=start&&now<=end){const ratio=Math.max(0,Math.min(1,(now-start)/(end-start||1))),a=rotation[index],b=rotation[index+1];return {cargo,calls,rotation,position:[a[0]+(b[0]-a[0])*ratio,a[1]+(b[1]-a[1])*ratio] as XY,positionLabel:`${calls[index].port_name} → ${calls[index+1].port_name}`,positionBasis:'Schedule estimated'}}}
  return {cargo,calls,rotation,position:rotation.at(-1)||null,positionLabel:`At ${last.port_name}`,positionBasis:'Schedule estimated'};
 },[shipment,now]);
 const simulation=shipment.simulation,currentIndex=simulation?.active?simulation.current_step:-1,points=simulation?.points||[];
 const current=simulation?.active?points[currentIndex]:null,previous=currentIndex>0?points[currentIndex-1]:null,next=currentIndex>=0?points[currentIndex+1]:points[0];
 const simulated=model.positionBasis==='POC simulation',position=model.position?project(model.position):null;
 const portStatus=(call:Call)=>{const matching=points.filter(point=>point.port&&point.location===call.port_name);if(current?.port&&current.location===call.port_name)return 'Current port';if(currentIndex>=0&&matching.some(point=>point.index<=currentIndex))return 'Completed call';const arrival=time(call.actual_arrival||call.estimated_arrival);if(Number.isFinite(arrival)&&arrival<now)return 'Completed call';return 'Upcoming call'};
 const portEvent=(call:Call)=>[...(shipment.events||[])].reverse().find(event=>event.location_name===call.port_name);
 const activeCall=hovered===null?null:model.calls.find(call=>call.id===hovered)||null,activePosition=activeCall?project(coords(activeCall.longitude,activeCall.latitude) as XY):null,activeEvent=activeCall?portEvent(activeCall):null;
 return <section className={'shipment-map geographic-map '+(compact?'compact':'')} aria-label="Shipment route map">
  <div className="map-stage">
   <svg className="world-map-canvas" viewBox="0 0 1000 500" aria-label={`World route from ${shipment.origin_port} to ${shipment.destination_port}`} preserveAspectRatio="xMidYMid meet">
    <defs><linearGradient id={`sea-${shipment.id}`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#dff4f5"/><stop offset="1" stopColor="#abd5dd"/></linearGradient></defs>
    <rect width="1000" height="500" rx="20" fill={`url(#sea-${shipment.id})`}/><g className="map-grid">{[100,200,300,400].map(y=><line key={`h${y}`} x1="0" x2="1000" y1={y} y2={y}/>)}{[125,250,375,500,625,750,875].map(x=><line key={`v${x}`} y1="0" y2="500" x1={x} x2={x}/>)}</g>
    <g className="country-boundaries">{countries.map(country=><path key={country.name} d={country.path}><title>{country.name}</title></path>)}</g>
    {segments(model.rotation).filter(segment=>segment.length>1).map((segment,index)=><polyline className="map-route rotation" points={line(segment)} key={`rotation-${index}`}/>)}
    {segments(model.cargo).filter(segment=>segment.length>1).map((segment,index)=><g key={`cargo-${index}`}><polyline className="map-route cargo-glow" points={line(segment)}/><polyline className="map-route cargo" points={line(segment)}/></g>)}
   </svg>
   <div className="port-overlay">{model.calls.map(call=>{const value=coords(call.longitude,call.latitude);if(!value)return null;const [x,y]=project(value),major=call.id===shipment.load_call_id||call.id===shipment.discharge_call_id,status=portStatus(call);return <button type="button" className={`geo-port ${major?'major':'minor'} ${status.toLowerCase().replaceAll(' ','-')}`} style={{left:`${x/10}%`,top:`${y/5}%`}} key={call.id} onMouseEnter={()=>setHovered(call.id)} onMouseLeave={()=>setHovered(null)} onFocus={()=>setHovered(call.id)} onBlur={()=>setHovered(null)} aria-label={`${call.port_name}, ${status}`}><span/><>{major&&<b>{call.port_name}</b>}</></button>})}</div>
   {position&&<div className="tracked-vessel" style={{left:`${position[0]/10}%`,top:`${position[1]/5}%`}} title={`${model.positionBasis}: ${model.positionLabel}`}><i/><Ship size={24}/><span>Vessel</span></div>}
   {activeCall&&activePosition&&<div className="port-hover-card" style={{left:`${Math.max(14,Math.min(82,activePosition[0]/10))}%`,top:`${Math.max(12,Math.min(74,activePosition[1]/5))}%`}}><header><Anchor size={16}/><div><b>{activeCall.port_name}</b><small>{activeCall.country}{activeCall.terminal?' · '+activeCall.terminal:''}</small></div></header><strong className={portStatus(activeCall).startsWith('Completed')?'complete':''}>{portStatus(activeCall)}</strong><dl><div><dt>Arrival</dt><dd>{stamp(activeCall.actual_arrival||activeCall.estimated_arrival)}</dd></div><div><dt>Departure</dt><dd>{stamp(activeCall.actual_departure||activeCall.estimated_departure)}</dd></div>{activeEvent&&<div><dt>Latest event</dt><dd>{activeEvent.event_label||activeEvent.event_code} · {stamp(activeEvent.occurred_at)}</dd></div>}<div><dt>Information source</dt><dd>{activeEvent?.source_provider||'Published vessel schedule'}</dd></div></dl></div>}
   <div className="map-position-card"><span className={simulated?'simulated':model.positionBasis==='Schedule estimated'?'estimated':'confirmed'}>{model.positionBasis}</span><b>{model.positionLabel}</b><small>{simulated?'Saved from the admin testing simulator':model.positionBasis==='Schedule estimated'?'Calculated from scheduled port calls':'Latest confirmed transport event'}</small></div>
   <div className="map-source-note"><span><i className="major-key"/>Cargo ports</span><span><i className="minor-key"/>Other calls</span><span><i className="cargo-key"/>Cargo route</span></div>
  </div>
  <div className="movement-context"><article className={!previous?'muted':''}><span><Check size={15}/>Previous point</span><b>{previous?.label||'No completed movement'}</b><small>{previous?.location||'Start the simulator to record departure.'}</small></article><article className="current"><span><Ship size={15}/>Current position</span><b>{current?.label||model.positionLabel}</b><small>{current?.location||model.positionBasis}</small></article><article className={!next?'muted':''}><span><Clock3 size={15}/>Next movement</span><b>{next?.label||'Journey complete'}</b><small>{next?.location||'No further scheduled point.'}</small></article></div>
 </section>
}
