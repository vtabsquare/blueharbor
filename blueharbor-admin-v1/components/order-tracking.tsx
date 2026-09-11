'use client';

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
            {!!order.documents?.length && (
              <div className="tracking-footer">
                {order.documents.map((doc) => (
                  <a
                    className="download"
                    key={doc.id}
                    href={'/api/trade-document/' + doc.id}
                  >
                    <Download size={16} />
                    {doc.kind} · v{doc.version}
                  </a>
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
              Order confirmation
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
