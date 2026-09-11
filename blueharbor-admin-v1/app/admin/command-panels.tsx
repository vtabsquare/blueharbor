'use client';
/* oxlint-disable next/no-img-element */
import { useEffect, useState, type ReactNode } from 'react';
import {
  CheckCircle2,
  Clock3,
  AlertTriangle,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Fish,
  Activity,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/ui/native-select';
// These records are validated by the shared administrative API.
// oxlint-disable-next-line typescript/no-explicit-any
type Row = Record<string, any>;
const kg = (n: number) => `${Number(n).toLocaleString()} kg`;
const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
    n / 100,
  );
const date = (s: string) =>
  s ? new Date(s).toLocaleDateString() : 'Not recorded';
const tone = (s: string) =>
  ['VERIFIED', 'DELIVERED', 'COMPLETED', 'RUNNING'].includes(s)
    ? 'good'
    : [
          'UNDER_REVIEW',
          'PROCESSING',
          'SHIPPED',
          'QUEUED',
          'SCHEDULED',
          'MANUAL',
        ].includes(s)
      ? 'waiting'
      : 'attention';
export function Status({ value }: { value: string }) {
  return (
    <span className={`cc-status ${tone(value)}`}>
      {tone(value) === 'good' ? (
        <CheckCircle2 size={15} />
      ) : tone(value) === 'waiting' ? (
        <Clock3 size={15} />
      ) : (
        <AlertTriangle size={15} />
      )}{' '}
      {value.replaceAll('_', ' ')}
    </span>
  );
}
export function MonitorPanel({ monitor = {} }: { monitor?: Row }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const remaining = monitor.next_scan
    ? Math.max(0, new Date(monitor.next_scan).getTime() - now)
    : 0;
  const countdown = `${String(Math.floor(remaining / 60000)).padStart(2, '0')}:${String(Math.floor((remaining % 60000) / 1000)).padStart(2, '0')}`;
  return (
    <section className="cc-monitor" aria-label="Operations monitoring status">
      <div className="cc-monitor-title">
        <Activity size={21} />
        <div>
          <b>Operations monitor</b>
          <small>Rule-based checks from saved inventory records</small>
        </div>
      </div>
      <div>
        <span>Stock rules</span>
        <Status value={monitor.rules_status || 'NOT_STARTED'} />
        <small>
          Last check:{' '}
          {monitor.last_scan
            ? new Date(monitor.last_scan).toLocaleTimeString()
            : 'Not yet run'}
        </small>
      </div>
      <div>
        <span>Next stock check</span>
        <b className="live-countdown">{monitor.next_scan ? countdown : 'Awaiting worker'}</b>
        <small>{monitor.error || (monitor.next_scan ? `Due ${new Date(monitor.next_scan).toLocaleTimeString()} · live ${new Date(now).toLocaleTimeString()}` : 'Runs while the backend is running')}</small>
      </div>
    </section>
  );
}
export function BuyerCards({
  buyers,
  team,
  open,
}: {
  buyers: Row[];
  team: Row[];
  open: (id: number) => void;
}) {
  const [filter, setFilter] = useState('ALL');
  const shown = buyers.filter((b) => filter === 'ALL' || b.verified === filter);
  return (
    <>
      <div className="cc-toolbar">
        <p>One buyer record. One verification workflow.</p>
        <NativeSelect
          aria-label="Filter buyers by verification"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {[
            'ALL',
            'DRAFT',
            'UNDER_REVIEW',
            'VERIFIED',
            'ADDITIONAL_INFORMATION_REQUIRED',
            'REJECTED',
            'SUSPENDED',
          ].map((s) => (
            <option key={s} value={s}>
              {s.replaceAll('_', ' ')}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="cc-card-grid">
        {shown.map((b) => (
          <article
            key={b.id}
            className={`cc-buyer cc-card ${tone(b.verified)}`}
          >
            <header>
              <span className="cc-company-avatar">
                {(b.company || b.name).slice(0, 2).toUpperCase()}
              </span>
              <Status value={b.verified} />
            </header>
            <h2>{b.company || b.name}</h2>
            <p>{b.email}</p>
            {b.email.endsWith('.local') && (
              <small>Testing account · synthetic evidence</small>
            )}
            <dl>
              <div>
                <dt>Country</dt>
                <dd>{b.country}</dd>
              </div>
              <div>
                <dt>Submitted</dt>
                <dd>{date(b.submitted)}</dd>
              </div>
              <div>
                <dt>Reviewer</dt>
                <dd>
                  {team.find((s) => s.id === b.assignee)?.name || 'Unassigned'}
                </dd>
              </div>
            </dl>
            <Button variant="outline" onClick={() => open(b.id)}>
              Open buyer & evidence <ArrowUpRight size={16} />
            </Button>
          </article>
        ))}
      </div>
      {!shown.length && (
        <Empty text="No buyers match this filter. New registrations appear here automatically." />
      )}
    </>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="cc-empty">
      <Fish size={28} />
      <p>{text}</p>
    </div>
  );
}
const images = [
  'vannamei-shrimp',
  'black-tiger-shrimp',
  'yellowfin-tuna',
  'indian-mackerel',
  'asian-sea-bass',
  'tilapia',
  'silver-pomfret',
  'red-snapper',
  'sardine',
  'squid',
  'cuttlefish',
  'mud-crab',
];
function productImage(p: Row) {
  return (
    p.image?.replace('/api/product-image/', '/api/admin/product-image/') ||
    (p.id >= 1 && p.id <= 12 ? `/catalog/${images[p.id - 1]}.jpg` : '')
  );
}
export function ProductCards({
  products,
  lots,
  edit,
  add,
  renderLots,
}: {
  products: Row[];
  lots: Row[];
  edit: (p: Row) => void;
  add: () => void;
  renderLots: (id: number) => ReactNode;
}) {
  const [selected, setSelected] = useState<number | null>(null),
    [filter, setFilter] = useState('ALL'),
    [slide, setSlide] = useState(0);
  useEffect(() => {
    if (selected !== null)
      document
        .getElementById('batch-workspace')
        ?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [selected]);
  const shown = products.filter(
    (p) => filter === 'ALL' || p.category === filter,
  );
  const featured = shown[Math.min(slide, Math.max(0, shown.length - 1))];
  return (
    <>
      <div className="cc-toolbar">
        <p>Catalogue, availability and batch quality in one place.</p>
        <div>
          <NativeSelect
            aria-label="Filter product category"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setSlide(0);
            }}
          >
            {['ALL', ...new Set(products.map((p) => p.category))].map((s) => (
              <option key={s} value={s}>
                {s === 'ALL' ? 'All categories' : s}
              </option>
            ))}
          </NativeSelect>
          <Button onClick={add}>Add product</Button>
        </div>
      </div>
      {featured && (
        <section className="cc-feature">
          <div className="cc-feature-photo">
            {productImage(featured) && (
              <img src={productImage(featured)} alt={featured.name} />
            )}
          </div>
          <div>
            <span className="admin-eyebrow">
              CATALOGUE SPOTLIGHT · {Math.min(slide + 1, shown.length)} /{' '}
              {shown.length}
            </span>
            <h2>{featured.name}</h2>
            <p>{featured.description}</p>
            <small>
              {featured.region} · {featured.grade}
            </small>
            <div className="cc-feature-actions">
              <Button
                variant="outline"
                onClick={() => setSelected(featured.id)}
              >
                Manage batches
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Previous product"
                onClick={() =>
                  setSlide(
                    (Math.min(slide, shown.length - 1) - 1 + shown.length) %
                      shown.length,
                  )
                }
              >
                <ChevronLeft />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Next product"
                onClick={() => setSlide((slide + 1) % shown.length)}
              >
                <ChevronRight />
              </Button>
            </div>
          </div>
        </section>
      )}
      <div className="cc-card-grid">
        {shown.map((p) => {
          const batches = lots.filter((l) => l.product_id === p.id),
            sellable = batches.reduce(
              (n, l) => n + (l.sellable ? l.available_kg : 0),
              0,
            ),
            reserved = batches.reduce((n, l) => n + l.reserved_kg, 0),
            held = batches.reduce(
              (n, l) => n + (!l.sellable ? l.available_kg : 0),
              0,
            ),
            total = sellable + reserved + held;
          const nearest = batches
            .filter((l) => l.available_kg + l.reserved_kg > 0)
            .sort((a, b) => a.expiry.localeCompare(b.expiry))[0];
          return (
            <article className="cc-product cc-card" key={p.id}>
              <div className="cc-product-photo">
                {productImage(p) ? (
                  <img src={productImage(p)} alt={p.name} loading="lazy" />
                ) : (
                  <Fish size={35} />
                )}
                <span className="cc-photo-label">
                  {p.published ? 'Published' : 'Hidden'}
                </span>
              </div>
              <div className="cc-product-body">
                <small>
                  {p.category} · {p.grade}
                </small>
                <h2>{p.name}</h2>
                <p>{p.region}</p>
                <div className="cc-stock-number">
                  <b>{kg(sellable)}</b>
                  <span>
                    {(sellable / 1000).toLocaleString()} tonnes available
                  </span>
                </div>
                <div className="cc-stock-bar" aria-hidden="true">
                  <i
                    style={{
                      width: `${total ? (sellable / total) * 100 : 0}%`,
                    }}
                  />
                  <i
                    style={{
                      width: `${total ? (reserved / total) * 100 : 0}%`,
                    }}
                  />
                  <i
                    style={{ width: `${total ? (held / total) * 100 : 0}%` }}
                  />
                </div>
                <div className="cc-stock-legend">
                  <span>Available</span>
                  <span>{kg(reserved)} reserved</span>
                  <span>{kg(held)} blocked</span>
                </div>
                <dl>
                  <div>
                    <dt>Buyer price / kg</dt>
                    <dd>
                      {money(p.effective_cents_per_kg ?? p.cents_per_kg)}
                      {p.promotion && (
                        <small>{p.promotion.percent}% off · product-wide</small>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Nearest expiry</dt>
                    <dd>
                      {nearest ? date(nearest.expiry) : 'No stock'}
                      {nearest && (
                        <small>
                          {nearest.days_to_expiry < 0
                            ? 'Expired'
                            : `${nearest.days_to_expiry} days left`}
                        </small>
                      )}
                    </dd>
                  </div>
                </dl>
                <div className="cc-card-actions">
                  <Button
                    onClick={() => setSelected(selected === p.id ? null : p.id)}
                  >
                    {selected === p.id ? 'Close batches' : 'Manage stock'}
                  </Button>
                  <Button variant="outline" onClick={() => edit(p)}>
                    Edit product
                  </Button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {!shown.length && (
        <Empty text="No products match. Add a product or change the filter." />
      )}
      {selected !== null && (
        <section id="batch-workspace" className="cc-batch-workspace">
          <header>
            <div>
              <span className="admin-eyebrow">BATCH WORKSPACE</span>
              <h2>
                {products.find((p) => p.id === selected)?.name ||
                  'Selected product'}
              </h2>
            </div>
            <Button variant="ghost" onClick={() => setSelected(null)}>
              Close
            </Button>
          </header>
          {renderLots(selected)}
        </section>
      )}
    </>
  );
}
export function OrderCards({
  orders,
  renderActions,
}: {
  orders: Row[];
  renderActions: (o: Row) => ReactNode;
}) {
  const [filter, setFilter] = useState('ALL');
  const shown = orders.filter(
    (o) =>
      filter === 'ALL' || (filter === 'HOLD' ? o.on_hold : o.status === filter),
  );
  return (
    <>
      <div className="cc-toolbar">
        <p>
          Fulfilment and shipping updates reach the buyer’s tracking timeline.
        </p>
        <NativeSelect
          aria-label="Filter order stage"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {[
            'ALL',
            'CONFIRMED',
            'PROCESSING',
            'SHIPPED',
            'DELIVERED',
            'CANCELLED',
            'HOLD',
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </NativeSelect>
      </div>
      <div className="cc-orders">
        {shown.map((o) => (
          <article className="cc-order cc-card" key={o.id}>
            <header>
              <div>
                <small>
                  {o.id} · {date(o.created)}
                </small>
                <h2>{o.company || o.buyer_name}</h2>
              </div>
              <Status value={o.on_hold ? 'HOLD' : o.status} />
            </header>
            <div className="cc-order-facts">
              <div>
                <small>Product</small>
                <b>{o.product_name}</b>
                <span>
                  {kg(o.kg)} · {money(o.total)}
                </span>
              </div>
              <div>
                <small>Destination</small>
                <b>{o.destination}</b>
                <span>{o.service}</span>
              </div>
              <div>
                <small>Carrier / vessel</small>
                <b>{o.shipment?.carrier || 'Not assigned'}</b>
                <span>{o.shipment?.vessel || 'Vessel not recorded'}</span>
              </div>
              <div>
                <small>Estimated arrival</small>
                <b>{date(o.shipment?.eta)}</b>
                <span>{o.shipment?.location || 'Location not recorded'}</span>
              </div>
            </div>
            <ol className="cc-stages" aria-label="Order progress">
              {['CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED'].map(
                (stage, index) => (
                  <li
                    className={
                      o.status !== 'CANCELLED' &&
                      index <=
                        [
                          'CONFIRMED',
                          'PROCESSING',
                          'SHIPPED',
                          'DELIVERED',
                        ].indexOf(o.status)
                        ? 'done'
                        : ''
                    }
                    key={stage}
                  >
                    <CheckCircle2 size={17} />
                    {stage}
                  </li>
                ),
              )}
            </ol>
            {o.on_hold && (
              <p className="cc-internal">
                Staff-only hold:{' '}
                {o.internal_note || 'Review before progressing'}
              </p>
            )}
            {renderActions(o)}
            <details>
              <summary>
                Buyer-visible timeline · {o.events.length} events
              </summary>
              <ol className="cc-timeline">
                {o.events.map((e: Row) => (
                  <li key={e.id}>
                    <small>{new Date(e.created).toLocaleString()}</small>
                    <b>{e.title}</b>
                    <p>{e.note}</p>
                  </li>
                ))}
              </ol>
            </details>
          </article>
        ))}
      </div>
      {!shown.length && (
        <Empty text="No orders in this stage. A buyer order will appear here once placed." />
      )}
    </>
  );
}
export function CommandDashboard({
  state,
  go,
  openBuyer,
}: {
  state: Row;
  go: (s: string) => void;
  openBuyer: (id: number) => void;
}) {
  const ops = ['ADMIN', 'OPERATIONS'].includes(state.staff.role),
    verify = ['ADMIN', 'VERIFIER'].includes(state.staff.role),
    pending = state.buyers.filter((b: Row) => b.verified === 'UNDER_REVIEW'),
    active = state.orders.filter(
      (o: Row) => !['DELIVERED', 'CANCELLED'].includes(o.status),
    ),
    alerts = state.alerts.filter((a: Row) => a.state !== 'RESOLVED'),
    available = state.lots.reduce(
      (n: number, l: Row) => n + (l.sellable ? l.available_kg : 0),
      0,
    ),
    atRisk = state.lots.filter(
      (l: Row) =>
        l.available_kg + l.reserved_kg > 0 &&
        l.days_to_expiry <= state.settings.expiry_days,
    );
  return (
    <>
      <div className="cc-dashboard-heading">
        <div>
          <span className="admin-eyebrow">BLUEHARBOR / OPERATIONS</span>
          <h1>Command center</h1>
          <p>Your stock, buyers and deliveries. One operating picture.</p>
        </div>
        <span>
          {new Date().toLocaleDateString(undefined, {
            weekday: 'long',
            month: 'short',
            day: 'numeric',
          })}
        </span>
      </div>
      <div className="cc-metrics">
        {verify && (
          <button onClick={() => go('Buyers')}>
            <span>
              Review queue <ArrowUpRight size={18} />
            </span>
            <strong>{pending.length.toString().padStart(2, '0')}</strong>
            <small>Buyers awaiting a decision</small>
          </button>
        )}
        {ops && (
          <>
            <button onClick={() => go('Orders')}>
              <span>
                Active orders <ArrowUpRight size={18} />
              </span>
              <strong>{active.length.toString().padStart(2, '0')}</strong>
              <small>Confirmed through in transit</small>
            </button>
            <button onClick={() => go('Products')}>
              <span>
                Available inventory <ArrowUpRight size={18} />
              </span>
              <strong>
                {(available / 1000).toLocaleString()}
                <em> t</em>
              </strong>
              <small>Released, unexpired stock</small>
            </button>
            <button onClick={() => go('Insights')}>
              <span>
                Needs attention <ArrowUpRight size={18} />
              </span>
              <strong>{alerts.length.toString().padStart(2, '0')}</strong>
              <small>{atRisk.length} batches inside expiry window</small>
            </button>
          </>
        )}
      </div>
      <MonitorPanel monitor={state.monitor} />
      <div className="cc-dashboard-columns">
        <section className="cc-card">
          <header>
            <h2>{ops ? 'Stock attention' : 'Buyer review queue'}</h2>
            <Button
              variant="ghost"
              onClick={() => go(ops ? 'Products' : 'Buyers')}
            >
              View workspace <ArrowUpRight size={16} />
            </Button>
          </header>
          {ops ? (
            atRisk.length ? (
              atRisk.slice(0, 5).map((l: Row) => (
                <div className="cc-attention-row" key={l.id}>
                  <AlertTriangle size={19} />
                  <div>
                    <b>{l.name}</b>
                    <small>
                      {l.id} · {kg(l.available_kg)} available
                    </small>
                  </div>
                  <Status
                    value={
                      l.days_to_expiry < 0
                        ? 'EXPIRED'
                        : `${l.days_to_expiry}_DAYS_LEFT`
                    }
                  />
                </div>
              ))
            ) : (
              <Empty text="No batches inside the configured expiry window." />
            )
          ) : pending.length ? (
            pending.slice(0, 5).map((b: Row) => (
              <button
                className="cc-attention-row"
                key={b.id}
                onClick={() => openBuyer(b.id)}
              >
                {b.company || b.name}
                <ArrowUpRight size={16} />
              </button>
            ))
          ) : (
            <Empty text="No buyers awaiting review." />
          )}
        </section>
        <section className="cc-card">
          <header>
            <h2>{ops ? 'Fulfilment pipeline' : 'Verification overview'}</h2>
          </header>
          {(ops
            ? ['CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED']
            : ['DRAFT', 'UNDER_REVIEW', 'VERIFIED', 'REJECTED']
          ).map((stage) => {
            const rows = ops ? state.orders : state.buyers,
              n = rows.filter(
                (r: Row) => (ops ? r.status : r.verified) === stage,
              ).length;
            return (
              <button
                className="cc-pipeline"
                key={stage}
                onClick={() => go(ops ? 'Orders' : 'Buyers')}
              >
                <span>{stage.replaceAll('_', ' ')}</span>
                <div>
                  <i
                    style={{
                      width: `${rows.length ? (n / rows.length) * 100 : 0}%`,
                    }}
                  />
                </div>
                <b>{n}</b>
              </button>
            );
          })}
          <p className="admin-muted">
            Live database records only. No sample activity added.
          </p>
        </section>
      </div>
    </>
  );
}
