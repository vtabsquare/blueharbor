'use client';
import { useEffect, useState, type SyntheticEvent } from 'react';
/* Protected images and downloads use direct same-origin requests to retain staff cookies. */
/* oxlint-disable next/no-img-element, next/no-html-link-for-pages */
import {
  ShieldCheck,
  LayoutDashboard,
  Users,
  Fish,
  Warehouse,
  Package,
  Bell,
  Settings,
  LogOut,
  ArrowUpRight,
  RefreshCw,
  Search,
  Check,
  X,
  Sun,
  Moon,
  Ship,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import './admin.css';
import './command-center.css';
import './shipping-fixes.css';
import {
  ProductCards,
  OrderCards,
  CommandDashboard,
} from './command-panels';
import ComplianceWorkspace from './compliance-workspace';
import DocumentationConsole from './documentation-console';
import ShippingControlTower from './shipping-control-tower';

// Dynamic editor rows follow the server-validated per-action schemas.
// oxlint-disable-next-line typescript/no-explicit-any
type Row = Record<string, any>;
type State = {
  staff: Row;
  buyers: Row[];
  orders: Row[];
  products: Row[];
  lots: Row[];
  tanks: Row[];
  warehouses: Row[];
  movements: Row[];
  readings: Row[];
  alerts: Row[];
  documents: Row[];
  team: Row[];
  audit: Row[];
  settings: Row;
  countries: Record<string, string[]>;
  services: Record<string, number>;
  destinations: string[];
  emails: Row[];
  integrations: Row;
  monitor: Row;
  discounts: Row[];
  compliance: { rules: Row[]; credentials: Row[]; requirements: Row[] };
  transport_shipments: Row[];
  shipping_schedule: { vessels: Row[]; sailings: Row[] };
};
async function api<T = Row>(path: string, data?: unknown): Promise<T> {
  const res = await fetch('/api/admin/' + path, {
    credentials: 'same-origin',
    ...(data === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-BlueHarbor': '1' },
          body: JSON.stringify(data),
        }),
  });
  const value = (await res.json()) as Row;
  if (!res.ok) throw new Error(value.error || 'Request failed');
  return value as T;
}
const usd = (c: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
    c / 100,
  );
const when = (s: string) => (s ? new Date(s).toLocaleString() : '—');
const nav = [
  ['Dashboard', LayoutDashboard, 'ALL'],
  ['Buyers', Users, 'VERIFIER'],
  ['Products', Fish, 'OPERATIONS'],
  ['Orders', Package, 'OPERATIONS'],
  ['Shipping', Ship, 'OPERATIONS'],
  ['Insights', Bell, 'OPERATIONS'],
  ['Settings', Settings, 'ADMIN'],
] as const;
const viewLabel = (view: string) =>
  ({
    Dashboard: 'Command Center',
    Buyers: 'Buyer Compliance',
    Products: 'Inventory & Catalogue',
    Orders: 'Orders & Shipping',
    Shipping: 'Shipping Control Tower',
    Insights: 'Insights & Reports',
    Settings: 'Administration',
  })[view] || view;

export default function Admin() {
  const [theme, setTheme] = useState('dark');
  useEffect(() => {
    if (window.location.search)
      window.history.replaceState({}, '', window.location.pathname);
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const saved = localStorage.getItem('blueharbor-admin-theme');
        if (saved === 'light' || saved === 'dark') setTheme(saved);
      } catch {}
    }, 0);
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.adminTheme = theme;
    return () => {
      delete document.documentElement.dataset.adminTheme;
    };
  }, [theme]);
  const toggleTheme = () =>
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem('blueharbor-admin-theme', next);
      } catch {}
      return next;
    });
  const [state, setState] = useState<State | null>(null),
    [view, setView] = useState('Dashboard'),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [busy, setBusy] = useState(false),
    [connected, setConnected] = useState(false),
    [query, setQuery] = useState(''),
    [detail, setDetail] = useState<Row | null>(null),
    [editor, setEditor] = useState<Row | null>(null);
  async function refresh() {
    try {
      const value = await api<State>('state');
      setState(value);
      setConnected(true);
    } catch (e) {
      const message = (e as Error).message;
      if (message.includes('sign in') || message.includes('session'))
        setState(null);
      else setError(message);
      setConnected(false);
    }
  }
  useEffect(() => {
    const initial = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 15000);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (!state?.staff.id) return;
    const stream = new EventSource('/api/admin/stream');
    stream.addEventListener('refresh', () => void refresh());
    stream.addEventListener('ready', () => {
      setConnected(true);
      void refresh();
    });
    stream.addEventListener('session-ended', () => {
      stream.close();
      setState(null);
    });
    stream.onerror = () => setConnected(false);
    return () => stream.close();
  }, [state?.staff.id]);
  async function act(path: string, data: unknown) {
    setBusy(true);
    setError('');
    try {
      await api(path, data);
      await refresh();
      const labels: Record<string, string> = {
        verification: 'Buyer decision recorded',
        'document-review': 'Document review recorded',
        'adjust-stock': 'Stock balance updated',
        notify: 'Buyer message queued',
        product: 'Product saved',
        settings: 'Operations settings saved',
        'compliance-rule': 'Compliance rule saved',
        'exporter-credential': 'Exporter credential saved',
        'document-requirement': 'Order requirement updated',
        'document-status': 'Document review status saved',
        'shipment-plan': 'Carrier booking and shipment plan saved',
        'shipment-leg': 'Route leg saved',
        'shipment-container': 'Container, seal and VGM saved',
        'customs-milestone': 'Customs milestone saved',
        'transport-event': 'Transport event saved',
        'reefer-reading': 'Reefer reading recorded',
        'shipping-exception': 'Operational exception saved',
        'shipment-simulation': 'POC vessel simulation updated',
      };
      setNotice(`${labels[path] || 'Change saved'}. Connected views will refresh.`);
      setEditor(null);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function openBuyer(id: number) {
    setBusy(true);
    setError('');
    try {
      setView('Buyers');
      setDetail(await api('buyer/' + id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!detail?.buyer.id) return;
    const id = detail.buyer.id;
    let active = true;
    void api('buyer/' + id)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [state, detail?.buyer.id]);
  function go(next: string) {
    setView(next);
    setQuery('');
    setNotice('');
  }
  if (!state)
    return (
      <main className="admin-login">
        <section>
          <span className="admin-mark">
            <Fish size={30} />
          </span>
          <p className="admin-eyebrow">BLUEHARBOR / OPERATIONS</p>
          <h1>
            Your export desk.
            <br />
            <em>One clear view.</em>
          </h1>
          <p>
            Buyer verification, warehouse inventory and shipment operations—with
            traceable decisions.
          </p>
          <a href={process.env.NEXT_PUBLIC_BUYER_URL || "http://localhost:3000"}>
            Open buyer marketplace <ArrowUpRight size={16} />
          </a>
        </section>
        <form
          method="post"
          action="/admin"
          onSubmit={async (e: SyntheticEvent<HTMLFormElement>) => {
            e.preventDefault();
            setBusy(true);
            setError('');
            try {
              await api(
                'login',
                Object.fromEntries(new FormData(e.currentTarget)),
              );
              await refresh();
            } catch (ex) {
              setError((ex as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <ShieldCheck size={28} />
          <h2>Staff sign in</h2>
          <p>Use your administrator or assigned staff account.</p>
          <label htmlFor="staff-email">
            Email
            <Input
              name="email"
              id="staff-email"
              type="email"
              required
              autoComplete="username"
              placeholder="you@company.com"
            />
          </label>
          <label htmlFor="staff-password">
            Password
            <Input
              name="password"
              id="staff-password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          {error && (
            <p role="alert" className="admin-error">
              {error}
            </p>
          )}
          <Button disabled={busy} type="submit">
            {busy ? 'Signing in…' : 'Open admin console'}
            <ArrowUpRight size={17} />
          </Button>
          <small>
            Use the Supabase account linked by script 03, or an account created by your administrator. Buyer registration alone does not grant staff access.
          </small>
        </form>
      </main>
    );
  const pending = state.buyers.filter((b) => b.verified === 'UNDER_REVIEW');
  const filtered = (rows: Row[]) =>
    rows.filter((r) =>
      JSON.stringify(r).toLowerCase().includes(query.toLowerCase()),
    );
  return (
    <div className="admin-app">
      <aside className="admin-rail">
        <button className="admin-brand" onClick={() => go('Dashboard')}>
          <span className="admin-mark">
            <Fish size={25} />
          </span>
          <span>
            blueharbor<small>OPERATIONS CONSOLE</small>
          </span>
        </button>
        <nav aria-label="Admin navigation">
          {nav
            .filter(
              ([, , role]) =>
                role === 'ALL' ||
                state.staff.role === 'ADMIN' ||
                state.staff.role === role,
            )
            .map(([name, Icon]) => (
              <button
                key={name}
                onClick={() => go(name)}
                className={view === name ? 'active' : ''}
                aria-current={view === name ? 'page' : undefined}
              >
                <Icon size={18} />
                {viewLabel(name)}
                {name === 'Buyers' && pending.length > 0 && (
                  <i>{pending.length}</i>
                )}
              </button>
            ))}
        </nav>
        <div className="admin-rail-bottom">
          <span>
            <i className={connected ? 'live-dot' : 'offline-dot'} />
            {connected ? 'Live connection' : 'Refresh fallback'}
          </span>
          <a href={process.env.NEXT_PUBLIC_BUYER_URL || "http://localhost:3000"} target="_blank" rel="noreferrer">
            Buyer application <ArrowUpRight size={15} />
          </a>
          <button onClick={() => void act('logout', {})}>
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>
      <main className="admin-main">
        <header className="admin-topbar">
          <div>
            <span>India export operations</span>
            <b>{viewLabel(view)}</b>
          </div>
          <div>
            <Button
              variant="ghost"
              size="icon"
              aria-label={
                theme === 'dark'
                  ? 'Switch to light theme'
                  : 'Switch to dark theme'
              }
              onClick={toggleTheme}
            >
              {theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Refresh admin data"
              onClick={() => void refresh()}
            >
              <RefreshCw size={17} />
            </Button>
            <span className="staff-avatar">{state.staff.name[0]}</span>
            <button
              className="staff-profile"
              aria-label="Change your staff password"
              onClick={() =>
                setEditor({
                  title: 'Change your password',
                  path: 'password',
                  data: {},
                  fields: [
                    {
                      key: 'current_password',
                      label: 'Current password',
                      type: 'password',
                    },
                    {
                      key: 'password',
                      label: 'New password (12+ characters)',
                      type: 'password',
                    },
                  ],
                })
              }
            >
              {state.staff.name}
              <small>{state.staff.role.toLowerCase()}</small>
            </button>
          </div>
        </header>
        <div className="admin-content">
          {error && (
            <div role="alert" className="admin-error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <output className="admin-notice">
              {notice}
              <button aria-label="Dismiss notice" onClick={() => setNotice('')}>
                <X size={16} />
              </button>
            </output>
          )}
          {view === 'Dashboard' && (
            <CommandDashboard
              state={state}
              go={go}
              openBuyer={(id) => void openBuyer(id)}
            />
          )}
          {view !== 'Dashboard' && view !== 'Buyers' && (
            <>
              <div className="admin-heading">
                <div>
                  <p className="admin-eyebrow">BLUEHARBOR OPERATIONS</p>
                  <h1>{viewLabel(view)}</h1>
                </div>
                <div className="admin-search">
                  <Search size={17} />
                  <Input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search this view…"
                    aria-label="Search this admin view"
                  />
                </div>
              </div>
            </>
          )}
          {view === 'Buyers' ? (
            <ComplianceWorkspace
              buyers={filtered(state.buyers)}
              team={state.team}
              detail={detail}
              busy={busy}
              openBuyer={openBuyer}
              closeBuyer={() => setDetail(null)}
              act={act}
            />
          ) : (
            <>
              <WorkspaceTabs view={view} go={go} role={state.staff.role} />
              <AdminViews state={state} view={view} filtered={filtered} setEditor={setEditor} act={act} busy={busy} />
            </>
          )}
        </div>
      </main>
      <Dialog
        open={!!editor}
        onOpenChange={(open) => {
          if (!open) setEditor(null);
        }}
      >
        <DialogContent className="admin-dialog">
          <DialogTitle>{editor?.title || 'Edit record'}</DialogTitle>
          <DialogDescription>
            Changes are saved to the shared database and audited.
          </DialogDescription>
          {editor && (
            <Editor
              editor={editor}
              state={state}
              busy={busy}
              error={error}
              act={act}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Pill({ value }: { value: string }) {
  return (
    <span
      className={'admin-pill pill-' + value.toLowerCase().replaceAll('_', '-')}
    >
      {value.replaceAll('_', ' ')}
    </span>
  );
}
function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div className="admin-table-wrap">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((c, i) => (
              <TableHead key={i}>{c}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {row.map((cell, j) => (
                <TableCell key={j}>{cell}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!rows.length && (
        <div className="admin-empty">
          <Check size={24} />
          <b>No records in this view</b>
          <p>New activity will appear here automatically.</p>
        </div>
      )}
    </div>
  );
}

function WorkspaceTabs({ view, go, role }: { view: string; go: (view: string) => void; role: string }) {
  const groups: string[][] = [
    ['Products', 'Inventory', 'Warehouses & tanks'],
    ['Orders', 'Documents'],
    ['Insights', 'Reports'],
    ['Settings', 'Notifications', 'Staff & access', 'Audit trail'],
  ];
  const group = groups.find((items) => items.includes(view));
  if (!group) return null;
  const visible = group.filter((item) => {
    if (['Settings', 'Notifications', 'Staff & access', 'Audit trail'].includes(item)) return role === 'ADMIN';
    return true;
  });
  return (
    <nav className="workspace-tabs" aria-label="Workspace sections">
      {visible.map((item) => (
        <button key={item} className={view === item ? 'active' : ''} onClick={() => go(item)}>
          {({ Products: 'Catalogue', Inventory: 'Batches', 'Warehouses & tanks': 'Facilities & tanks', Orders: 'Orders', Shipping: 'Shipping control tower', Documents: 'Trade documents', Insights: 'Operational alerts', Reports: 'Reports', Settings: 'Configuration', Notifications: 'Buyer messages', 'Staff & access': 'Staff access', 'Audit trail': 'Audit trail' } as Record<string, string>)[item]}
        </button>
      ))}
    </nav>
  );
}

// Expanded workflow views are composed below; access is also enforced on the server.
type Action = (path: string, data: unknown) => Promise<boolean>;
type Field = {
  key: string;
  label: string;
  type?: string;
  options?: [string | number, string][];
  optional?: boolean;
};
function AdminViews({
  state: s,
  view,
  filtered,
  setEditor,
  act,
  busy = false,
}: {
  state: State;
  view: string;
  filtered: (rows: Row[]) => Row[];
  setEditor: (e: Row) => void;
  act?: Action;
  busy?: boolean;
}) {
  const edit = (title: string, path: string, data: Row, fields: Field[]) =>
    setEditor({ title, path, data, fields });
  const reason: Field = {
    key: 'reason',
    label: 'Reason / supporting details',
    type: 'textarea',
  };
  const orderOptions = s.orders.map(
    (o) => [o.id, `${o.id} · ${o.product_name}`] as [string, string],
  );
  const warehouseOptions = s.warehouses.map(
    (w) => [w.id, `${w.name} · ${w.location}`] as [number, string],
  );
  const productFields: Field[] = [
    { key: 'name', label: 'Product name' },
    { key: 'scientific_name', label: 'Scientific name', optional: true },
    {
      key: 'category',
      label: 'Category',
      options: ['Live fish', 'Fish', 'Shrimp', 'Cephalopods', 'Crab'].map(
        (x) => [x, x],
      ),
    },
    { key: 'grade', label: 'Grade / product form' },
    { key: 'origin', label: 'Origin country' },
    { key: 'region', label: 'Source region' },
    { key: 'export_port', label: 'Export port' },
    { key: 'facility', label: 'Source facility' },
    { key: 'cents_per_kg', label: 'Buyer price per kg (USD)', type: 'usd' },
    { key: 'minimum_kg', label: 'Minimum kg', type: 'number' },
    { key: 'reorder_kg', label: 'Low-stock threshold kg', type: 'number' },
    {
      key: 'published',
      label: 'Buyer visibility',
      options: [
        [1, 'Published'],
        [0, 'Hidden'],
      ],
    },
    {
      key: 'image',
      label: 'Species reference image',
      optional: true,
      options: [
        ['', 'Existing/default image'],
        ...[
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
        ].map((x) => ['/catalog/' + x + '.jpg', x] as [string, string]),
      ],
    },
    {
      key: 'photo',
      label: 'Or upload a product photo (PNG/JPEG, max 5 MB)',
      type: 'image',
      optional: true,
    },
    {
      key: 'description',
      label: 'Description / handling requirements',
      type: 'textarea',
    },
  ];
  const statusEdit = (o: Row) =>
    edit(
      'Progress ' + o.id,
      'order-status',
      {
        id: o.id,
        status:
          o.status === 'CONFIRMED'
            ? 'PROCESSING'
            : o.status === 'PROCESSING'
              ? 'SHIPPED'
              : 'DELIVERED',
        reason: '',
      },
      [
        {
          key: 'status',
          label: 'Next stage',
          options: (o.status === 'CONFIRMED'
            ? ['PROCESSING', 'CANCELLED']
            : o.status === 'PROCESSING'
              ? ['SHIPPED']
              : ['DELIVERED']
          ).map((x) => [x, x]),
        },
        reason,
      ],
    );
  const shipmentEdit = (o: Row) =>
    edit(
      'Shipment · ' + o.id,
      'shipment',
      { id: o.id, ...o.shipment, reason: '' },
      [
        { key: 'origin_port', label: 'Origin port', optional: true },
        { key: 'carrier', label: 'Carrier', optional: true },
        { key: 'container', label: 'Container number', optional: true },
        { key: 'vessel', label: 'Vessel', optional: true },
        {
          key: 'departure',
          label: 'Departure date',
          type: 'date',
          optional: true,
        },
        {
          key: 'eta',
          label: 'Estimated arrival',
          type: 'date',
          optional: true,
        },
        {
          key: 'arrival',
          label: 'Actual arrival',
          type: 'date',
          optional: true,
        },
        { key: 'location', label: 'Last recorded location', optional: true },
        reason,
      ],
    );
  const controlRequirement = (o: Row, item: Row) => {
    if (item.document)
      return edit('Review '+item.document_name,'document-status',{id:item.document.id,status:item.document.status,issuer:item.document.issuer,document_number:item.document.document_number,issue_date:item.document.issue_date,expiry_date:item.document.expiry_date,note:''},[
        {key:'status',label:'Document status',options:['DRAFT','UNDER_REVIEW','CORRECTION_REQUIRED','ISSUED','RELEASED','SUPERSEDED'].map(x=>[x,x.replaceAll('_',' ')] as [string,string])},{key:'issuer',label:'Official issuer',optional:true},{key:'document_number',label:'Document number / reference',optional:true},{key:'issue_date',label:'Issue date',type:'date',optional:true},{key:'expiry_date',label:'Expiry date',type:'date',optional:true},{key:'note',label:'Review note',type:'textarea',optional:true}
      ]);
    if (item.evidence_type === 'DOCUMENT')
      return edit('Attach '+item.document_name,'trade-document',{order_id:o.id,kind:item.document_name},[{key:'order_id',label:'Order',options:[[o.id,`${o.id} · ${o.product_name}`]]},{key:'kind',label:'Document type'},{key:'file',label:'Soft copy (PDF, PNG or JPEG · max 5 MB)',type:'file'}]);
    return edit(item.document_name,'document-requirement',{order_id:o.id,requirement_code:item.requirement_code,status:item.status,note:item.note||''},[{key:'status',label:'Evidence status',options:['WAITING','SUBMITTED','UNDER_REVIEW','CORRECTION_REQUIRED','ISSUED','RELEASED','NOT_REQUIRED'].map(x=>[x,x.replaceAll('_',' ')] as [string,string])},{key:'note',label:'Authority reference / evidence',type:'textarea'}]);
  };
  if (view === 'Shipping')
    return <ShippingControlTower state={s} edit={edit} act={act as Action} busy={busy} />;
  if (view === 'Documents')
    return <DocumentationConsole state={s} filtered={filtered} edit={edit} />;
  if (view === 'Products')
    return (
      <ProductCards
        products={filtered(s.products)}
        lots={s.lots}
        add={() =>
          edit(
            'Add seafood product',
            'product',
            {
              category: 'Fish',
              origin: 'India',
              published: 0,
              cents_per_kg: 500,
              minimum_kg: 100,
              reorder_kg: 1000,
            },
            productFields,
          )
        }
        edit={(p) => edit('Edit ' + p.name, 'product', p, productFields)}
        renderLots={(id) => (
          <AdminViews
            state={{
              ...s,
              products: s.products.filter((p) => p.id === id),
              lots: s.lots.filter((l) => l.product_id === id),
              movements: s.movements.filter((m) =>
                s.lots.some((l) => l.product_id === id && l.id === m.lot_id),
              ),
            }}
            view="Inventory"
            filtered={(rows) => rows}
            setEditor={setEditor}
          />
        )}
      />
    );
  if (view === 'Inventory')
    return (
      <>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <h2>Lot-level inventory</h2>
              <p className="admin-muted">
                Adjustments affect available stock only. Reserved stock stays
                protected.
              </p>
            </div>
            <Button
              onClick={() =>
                edit(
                  'Receive a stock lot',
                  'lot',
                  {
                    quantity: 1000,
                    received_date: new Date().toISOString().slice(0, 10),
                    warehouse_id: s.warehouses[0]?.id,
                    product_id: s.products[0]?.id,
                  },
                  [
                    { key: 'id', label: 'Unique lot / batch ID' },
                    {
                      key: 'product_id',
                      label: 'Product',
                      type: 'number',
                      options: s.products.map((p) => [p.id, p.name]),
                    },
                    {
                      key: 'warehouse_id',
                      label: 'Warehouse',
                      type: 'number',
                      options: warehouseOptions,
                    },
                    {
                      key: 'quantity',
                      label: 'Received quantity kg',
                      type: 'number',
                    },
                    {
                      key: 'production_date',
                      label: 'Production date',
                      type: 'date',
                      optional: true,
                    },
                    {
                      key: 'received_date',
                      label: 'Warehouse arrival date',
                      type: 'date',
                    },
                    { key: 'expiry', label: 'Expiry date', type: 'date' },
                    reason,
                  ],
                )
              }
            >
              Receive stock
            </Button>
          </div>
          <DataTable
            columns={[
              'Lot / product',
              'Warehouse',
              'Available kg',
              'Reserved kg',
              'Arrival / storage age',
              'Expiry / time left',
              'Quality',
              'Actions',
            ]}
            rows={filtered(s.lots).map((l) => [
              <span key="l">
                <b>{l.id}</b>
                <small>{l.name}</small>
              </span>,
              l.warehouse,
              l.available_kg.toLocaleString(),
              l.reserved_kg.toLocaleString(),
              <span key="age">
                {l.received_date || 'Not recorded'}
                <small>
                  {l.storage_days === null
                    ? 'Record arrival to calculate age'
                    : l.storage_days + ' days in storage'}
                </small>
              </span>,
              <span key="expiry">
                {l.expiry}
                <small>
                  {l.days_to_expiry < 0
                    ? 'EXPIRED'
                    : l.days_to_expiry + ' days remaining'}
                </small>
              </span>,
              <Pill key="q" value={l.quality} />,
              <div key="a" className="admin-row-actions">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    edit(
                      'Arrival date · ' + l.id,
                      'arrival',
                      { lot_id: l.id, received_date: l.received_date || '' },
                      [
                        {
                          key: 'received_date',
                          label: 'Actual warehouse arrival',
                          type: 'date',
                        },
                        reason,
                      ],
                    )
                  }
                >
                  Arrival date
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!l.sellable || !l.available_kg}
                  onClick={() =>
                    edit(
                      'Propose product-wide discount · ' + l.name,
                      'discount-propose',
                      { lot_id: l.id, percent: 10, ends_on: l.expiry },
                      [
                        {
                          key: 'percent',
                          label: 'Discount % (1–90, subject to staff approval)',
                          type: 'number',
                        },
                        {
                          key: 'ends_on',
                          label: 'End date (no later than lot expiry)',
                          type: 'date',
                        },
                        reason,
                      ],
                    )
                  }
                >
                  Propose discount
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    edit(
                      'Adjust ' + l.id,
                      'adjust-stock',
                      {
                        lot_id: l.id,
                        expected_available: l.available_kg,
                        delta: 0,
                      },
                      [
                        {
                          key: 'delta',
                          label: 'Quantity',
                          type: 'number',
                        },
                        reason,
                      ],
                    )
                  }
                >
                  Adjust
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    edit(
                      'Quality · ' + l.id,
                      'quality',
                      { lot_id: l.id, quality: l.quality },
                      [
                        {
                          key: 'quality',
                          label: 'Quality disposition',
                          options: ['RELEASED', 'HOLD', 'REJECTED'].map((x) => [
                            x,
                            x,
                          ]),
                        },
                        reason,
                      ],
                    )
                  }
                >
                  Quality
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    edit(
                      'Relocate whole lot',
                      'transfer',
                      { lot_id: l.id, warehouse_id: l.warehouse_id },
                      [
                        {
                          key: 'warehouse_id',
                          label: 'Destination warehouse',
                          type: 'number',
                          options: warehouseOptions,
                        },
                        reason,
                      ],
                    )
                  }
                >
                  Transfer
                </Button>
              </div>,
            ])}
          />
        </section>
        <section className="admin-panel">
          <h2>Discount proposals</h2>
          <p className="admin-muted">
            An approved discount applies to the whole product. It stops when the
            source lot is unavailable, held or expired, the end date passes, or
            its base price changes. Check warehouse quality evidence before
            approval.
          </p>
          <DataTable
            columns={['Source lot', 'Discount', 'Ends', 'Status', 'Actions']}
            rows={s.discounts
              .filter((d) => s.products.some((p) => p.id === d.product_id))
              .map((d) => [
                d.lot_id,
                d.percent + '%',
                d.ends_on,
                <Pill key="s" value={d.status} />,
                <div key="a" className="admin-row-actions">
                  {(d.status === 'PROPOSED'
                    ? ['APPROVED', 'REJECTED']
                    : d.status === 'APPROVED'
                      ? ['WITHDRAWN']
                      : []
                  ).map((status) => (
                    <Button
                      key={status}
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        edit(
                          status + ' · proposal ' + d.id,
                          'discount-decision',
                          { id: d.id, status },
                          [reason],
                        )
                      }
                    >
                      {status === 'APPROVED'
                        ? 'Approve discount'
                        : status === 'REJECTED'
                          ? 'Reject'
                          : 'Withdraw'}
                    </Button>
                  ))}
                </div>,
              ])}
          />
        </section>
        <section className="admin-panel">
          <h2>Stock movement history</h2>
          <DataTable
            columns={[
              'When',
              'Lot',
              'Movement',
              'Available Δ',
              'Reserved Δ',
              'Reason',
            ]}
            rows={filtered(s.movements).map((m) => [
              when(m.created),
              m.lot_id,
              m.kind,
              m.available_delta,
              m.reserved_delta,
              m.reason,
            ])}
          />
        </section>
      </>
    );
  if (view === 'Warehouses & tanks')
    return (
      <>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Facilities</h2>
            <Button
              onClick={() =>
                edit('Add warehouse', 'warehouse', {}, [
                  { key: 'name', label: 'Name' },
                  { key: 'location', label: 'Location' },
                  { key: 'kind', label: 'Storage / holding type' },
                ])
              }
            >
              Add warehouse
            </Button>
          </div>
          <DataTable
            columns={['Warehouse', 'Location', 'Type']}
            rows={filtered(s.warehouses).map((w) => [
              w.name,
              w.location,
              w.kind,
            ])}
          />
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Holding tanks</h2>
            <Button
              onClick={() =>
                edit(
                  'Add holding tank',
                  'tank',
                  { capacity_kg: 5000, status: 'ACTIVE' },
                  [
                    { key: 'tank_id', label: 'Tank ID' },
                    {
                      key: 'lot_id',
                      label: 'Lot',
                      options: s.lots.map((l) => [l.id, l.id + ' · ' + l.name]),
                    },
                    { key: 'zone', label: 'Holding zone' },
                    {
                      key: 'capacity_kg',
                      label: 'Capacity kg',
                      type: 'number',
                    },
                    {
                      key: 'status',
                      label: 'Status',
                      options: [
                        ['ACTIVE', 'Active'],
                        ['MAINTENANCE', 'Maintenance'],
                      ],
                    },
                    reason,
                  ],
                )
              }
            >
              Add tank
            </Button>
          </div>
          <div className="admin-tank-grid">
            {filtered(s.tanks).map((t) => (
              <article key={t.id} className="admin-tank-card">
                <div>
                  <Warehouse size={22} />
                  <Pill value={t.status} />
                </div>
                <h3>{t.id}</h3>
                <p>
                  {t.name} · {t.zone}
                </p>
                <strong>
                  {t.available_kg.toLocaleString()} <small>kg available</small>
                </strong>
                <p>
                  {t.reserved_kg.toLocaleString()} kg reserved /{' '}
                  {t.capacity_kg.toLocaleString()} kg capacity
                </p>
                <progress
                  max={t.capacity_kg}
                  value={t.available_kg + t.reserved_kg}
                  aria-label={`${t.id} occupied capacity`}
                />
                <div className="admin-row-actions">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      edit(
                        'Record manual reading',
                        'reading',
                        { tank_id: t.id },
                        [
                          {
                            key: 'temperature',
                            label: 'Temperature °C',
                            type: 'decimal',
                          },
                          {
                            key: 'oxygen',
                            label: 'Dissolved oxygen mg/L',
                            type: 'decimal',
                          },
                          reason,
                        ],
                      )
                    }
                  >
                    Record reading
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      edit('Manage ' + t.id, 'tank', { ...t, tank_id: t.id }, [
                        { key: 'zone', label: 'Zone' },
                        {
                          key: 'capacity_kg',
                          label: 'Capacity kg',
                          type: 'number',
                        },
                        {
                          key: 'status',
                          label: 'Status',
                          options: [
                            ['ACTIVE', 'Active'],
                            ['MAINTENANCE', 'Maintenance'],
                          ],
                        },
                        reason,
                      ])
                    }
                  >
                    Manage
                  </Button>
                </div>
              </article>
            ))}
          </div>
          <p className="admin-muted">
            Readings are entered by staff, not live sensor data. Maintenance
            places the linked lot on quality hold; release it explicitly after
            checks.
          </p>
        </section>
        <section className="admin-panel">
          <h2>Recorded condition checks</h2>
          <DataTable
            columns={[
              'Tank',
              'Temperature °C',
              'Oxygen mg/L',
              'Recorded',
              'Notes',
            ]}
            rows={s.readings.map((r) => [
              r.tank_id,
              r.temperature,
              r.oxygen,
              when(r.created),
              r.note,
            ])}
          />
        </section>
      </>
    );
  if (view === 'Orders')
    return (
      <OrderCards
        orders={filtered(s.orders)}
        renderActions={(o) => (
          <div key="a">
          {o.compliance && <section className="admin-order-gates"><div className="admin-gate-summary"><span className={o.compliance.departure_ready?'clear':'blocked'}><small>DEPARTURE</small><b>{o.compliance.departure_ready?'Ready':`${o.compliance.departure_blocking} blockers`}</b></span><span className={o.compliance.clearance_ready?'clear':'blocked'}><small>DESTINATION CLEARANCE</small><b>{o.compliance.clearance_ready?'Ready':`${o.compliance.clearance_blocking} remaining`}</b></span><span><small>DOCUMENT PROGRESS</small><b>{o.compliance.started}/{o.compliance.total} started · {o.compliance.released} released</b></span></div><details><summary>Manage document gates</summary><div className="admin-gate-items">{o.compliance.items.map((item: Row)=><button key={item.requirement_code} onClick={()=>controlRequirement(o,item)}><Pill value={item.status}/><span><b>{item.document_name}</b><small>{item.required_stage.replaceAll('_',' ')} · {item.responsible_party.replaceAll('_',' ')} · issuer: {item.official_issuer}</small></span><em>{item.document?'Review':item.evidence_type==='DOCUMENT'?'Attach file':'Record reference'}</em></button>)}</div></details></section>}
          <div className="admin-row-actions">
            {!['CANCELLED', 'DELIVERED'].includes(o.status) && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => statusEdit(o)}
                >
                  Update stage
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    edit(
                      o.on_hold ? 'Release order hold' : 'Hold order',
                      'order-hold',
                      { id: o.id, on_hold: o.on_hold ? 0 : 1 },
                      [reason],
                    )
                  }
                >
                  {o.on_hold ? 'Release hold' : 'Hold'}
                </Button>
              </>
            )}
            <Button size="sm" variant="ghost" onClick={() => shipmentEdit(o)}>
              Shipment details
            </Button>
            {o.status !== 'CANCELLED' && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  edit(
                    'Add buyer-visible milestone',
                    'tracking-event',
                    { id: o.id },
                    [
                      {
                        key: 'title',
                        label: 'Milestone (e.g. Packed / Customs clearance)',
                      },
                      reason,
                    ],
                  )
                }
              >
                Add milestone
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                setEditor({
                  title: o.id,
                  path: 'view-order',
                  data: o,
                  fields: [],
                })
              }
            >
              History
            </Button>
          </div>
          </div>
        )}
      />
    );
  if (view === 'Insights')
    return (
      <>
        <section className="admin-hero insights-hero">
          <div>
            <p className="admin-eyebrow">RULE-BASED OPERATIONS</p>
            <h1>Evidence, without the noise.</h1>
            <p>Stock rules identify conditions that need a staff decision using saved operational records.</p>
          </div>
          <div className="rule-health">
            <span className={s.monitor.rules_status === 'RUNNING' ? 'live-dot' : 'offline-dot'} />
            <div><b>{s.monitor.rules_status === 'RUNNING' ? 'Stock checks active' : 'Stock checks need attention'}</b><small>Last check {when(s.monitor.last_scan)}</small></div>
          </div>
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div><h2>Operational alerts</h2><p className="admin-muted">Every alert is calculated from saved stock, expiry, quality, and movement records.</p></div>
            <span className="attention-count">{s.alerts.filter((alert) => alert.state !== 'RESOLVED').length} open</span>
          </div>
          <DataTable
            columns={['Priority', 'Condition', 'Evidence and recommended action', 'State', 'Action']}
            rows={filtered(s.alerts).map((alert) => [
              <Pill key="priority" value={alert.severity} />,
              <span key="condition"><b>{alert.title}</b><small>{alert.kind.replaceAll('_', ' ')}</small></span>,
              <span key="evidence">{alert.evidence}<small>{alert.recommendation}</small></span>,
              <Pill key="state" value={alert.state} />,
              <Button key="action" size="sm" variant="outline" onClick={() => edit('Resolve operational alert', 'alert', { id: alert.id, state: alert.state, assignee: alert.assignee, reason: '' }, [
                { key: 'state', label: 'Next state', options: [['OPEN', 'Open'], ['ACKNOWLEDGED', 'Acknowledged'], ['RESOLVED', 'Resolved']] },
                { key: 'assignee', label: 'Assign to staff', type: 'number', optional: true, options: s.team.filter((person) => person.active).map((person) => [person.id, person.name]) },
                reason,
              ])}>Review alert</Button>,
            ])}
          />
        </section>
      </>
    );  if (view === 'Documents')
    return (
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <div>
            <h2>Order document library</h2>
            <p className="admin-muted">
              New documents start private. Publish only after checking their
              contents.
            </p>
          </div>
          <div className="admin-row-actions">
            <Button
              variant="outline"
              onClick={() =>
                edit(
                  'Upload trade document',
                  'trade-document',
                  { order_id: s.orders[0]?.id },
                  [
                    { key: 'order_id', label: 'Order', options: orderOptions },
                    { key: 'kind', label: 'Document type / title' },
                    {
                      key: 'file',
                      label: 'PDF, PNG or JPEG · max 5 MB',
                      type: 'file',
                    },
                  ],
                )
              }
            >
              Upload
            </Button>
            <Button
              onClick={() =>
                edit(
                  'Generate informational PDF',
                  'generate-document',
                  { order_id: s.orders[0]?.id, kind: 'Order confirmation' },
                  [
                    { key: 'order_id', label: 'Order', options: orderOptions },
                    {
                      key: 'kind',
                      label: 'Template',
                      options: [
                        'Order confirmation',
                        'Informational invoice',
                        'Packing list',
                      ].map((x) => [x, x]),
                    },
                  ],
                )
              }
            >
              Generate PDF
            </Button>
          </div>
        </div>
        <DataTable
          columns={['Order', 'Document', 'Version', 'Visibility', 'Actions']}
          rows={filtered(s.documents).map((d) => [
            d.order_id,
            <span key="d">
              {d.kind}
              <small>{d.name}</small>
            </span>,
            d.version,
            d.published ? 'Buyer-visible' : 'Private draft',
            <div key="a" className="admin-row-actions">
              <a
                href={'/api/admin/trade-document/' + d.id}
                className="admin-link"
              >
                Download
              </a>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  edit(
                    d.published ? 'Withdraw document' : 'Publish to buyer',
                    'publish-document',
                    { id: d.id, published: d.published ? 0 : 1 },
                    [],
                  )
                }
              >
                {d.published ? 'Withdraw' : 'Publish'}
              </Button>
            </div>,
          ])}
        />
      </section>
    );
  if (view === 'Notifications')
    return (
      <>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <h2>Buyer notifications</h2>
              <p className="admin-muted">
                Messages appear in the buyer’s Activity view. Email is not
                connected until an SMTP provider is configured.
              </p>
            </div>
            <Button
              onClick={() =>
                edit('Send buyer notification', 'notify', {}, [
                  {
                    key: 'user_id',
                    label: 'Buyer',
                    type: 'number',
                    options: s.buyers.map((b) => [b.id, b.email]),
                  },
                  {
                    key: 'message',
                    label: 'Buyer-visible message',
                    type: 'textarea',
                  },
                ])
              }
            >
              New notification
            </Button>
          </div>
          <DataTable
            columns={[
              'Created',
              'Buyer ID',
              'Subject',
              'Email status',
              'Details',
              'Action',
            ]}
            rows={filtered(s.emails).map((e) => [
              when(e.created),
              e.user_id,
              e.subject,
              <Pill key="s" value={e.status} />,
              e.error || 'In-app notification saved',
              ['FAILED', 'NOT_CONNECTED'].includes(e.status) ? (
                <Button
                  key="retry"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    edit(
                      'Queue email delivery',
                      'email-retry',
                      { id: e.id },
                      [],
                    )
                  }
                >
                  Queue delivery
                </Button>
              ) : null,
            ])}
          />
        </section>
      </>
    );
  if (view === 'Reports')
    return (
      <>
        <div className="admin-stats">
          {[
            [
              'Confirmed order value',
              usd(
                s.orders
                  .filter((o) => o.status !== 'CANCELLED')
                  .reduce((a, o) => a + o.total, 0),
              ),
            ],
            [
              'Delivered',
              s.orders.filter((o) => o.status === 'DELIVERED').length,
            ],
            [
              'Stock reserved',
              s.lots.reduce((a, l) => a + l.reserved_kg, 0).toLocaleString() +
                ' kg',
            ],
            [
              'Cancellation count',
              s.orders.filter((o) => o.status === 'CANCELLED').length,
            ],
          ].map(([label, value]) => (
            <article className="admin-stat" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
              <small>Saved database records · no payment collection</small>
            </article>
          ))}
        </div>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Order export</h2>
            <a className="admin-link" href="/api/admin/report">
              Download CSV
            </a>
          </div>
          <DataTable
            columns={['Product', 'Order count', 'Ordered kg', 'Delivered kg']}
            rows={s.products.map((p) => {
              const orders = s.orders.filter(
                (o) => o.product_id === p.id && o.status !== 'CANCELLED',
              );
              return [
                p.name,
                orders.length,
                orders.reduce((a, o) => a + o.kg, 0),
                orders
                  .filter((o) => o.status === 'DELIVERED')
                  .reduce((a, o) => a + o.kg, 0),
              ];
            })}
          />
        </section>
      </>
    );
  if (view === 'Staff & access')
    return (
      <>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Staff accounts</h2>
            <Button
              onClick={() =>
                edit(
                  'Create staff account',
                  'staff',
                  { role: 'OPERATIONS', active: 1 },
                  [
                    { key: 'name', label: 'Full name' },
                    { key: 'email', label: 'Email', type: 'email' },
                    {
                      key: 'password',
                      label: 'Initial password · at least 12 characters',
                      type: 'password',
                    },
                    {
                      key: 'role',
                      label: 'Role',
                      options: ['ADMIN', 'VERIFIER', 'OPERATIONS'].map((x) => [
                        x,
                        x,
                      ]),
                    },
                    {
                      key: 'active',
                      label: 'Access',
                      type: 'number',
                      options: [
                        [1, 'Active'],
                        [0, 'Disabled'],
                      ],
                    },
                  ],
                )
              }
            >
              Add staff
            </Button>
          </div>
          <DataTable
            columns={['Name', 'Email', 'Role', 'Access', '']}
            rows={filtered(s.team).map((t) => [
              t.name,
              t.email,
              t.role,
              t.active ? 'Active' : 'Disabled',
              <Button
                key="e"
                size="sm"
                variant="outline"
                onClick={() =>
                  edit('Edit staff access', 'staff', t, [
                    { key: 'name', label: 'Name' },
                    { key: 'email', label: 'Email', type: 'email' },
                    {
                      key: 'role',
                      label: 'Role',
                      options: ['ADMIN', 'VERIFIER', 'OPERATIONS'].map((x) => [
                        x,
                        x,
                      ]),
                    },
                    {
                      key: 'active',
                      label: 'Access',
                      type: 'number',
                      options: [
                        [1, 'Active'],
                        [0, 'Disabled'],
                      ],
                    },
                  ])
                }
              >
                Edit
              </Button>,
            ])}
          />
        </section>
        <section className="admin-panel">
          <h2>Your password</h2>
          <p className="admin-muted">
            Changing it signs out all your staff sessions.
          </p>
          <Button
            variant="outline"
            onClick={() =>
              edit('Change your password', 'password', {}, [
                {
                  key: 'current_password',
                  label: 'Current password',
                  type: 'password',
                },
                {
                  key: 'password',
                  label: 'New password · at least 12 characters',
                  type: 'password',
                },
              ])
            }
          >
            Change password
          </Button>
        </section>
      </>
    );
  if (view === 'Audit trail')
    return (
      <section className="admin-panel">
        <h2>Who changed what, and why</h2>
        <DataTable
          columns={['Time', 'Actor', 'Action', 'Record', 'Reason', '']}
          rows={filtered(s.audit).map((a) => [
            when(a.created),
            a.staff_name || 'System process',
            a.action,
            a.entity,
            a.reason,
            <Button
              key="b"
              size="sm"
              variant="ghost"
              onClick={() =>
                setEditor({
                  title: 'Audit #' + a.id,
                  path: 'view-audit',
                  data: a,
                  fields: [],
                })
              }
            >
              Compare
            </Button>,
          ])}
        />
      </section>
    );
  if (view === 'Settings')
    return (
      <>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <h2>Operations settings</h2>
              <p className="admin-muted">
                Configure deterministic stock checks, export charges, and optional email delivery.
              </p>
            </div>
            <Button
              onClick={() =>
                edit('Operations settings', 'settings', s.settings, [
                  {
                    key: 'email_enabled',
                    label: 'Enable configured SMTP for new notifications',
                    type: 'boolean',
                  },
                  {
                    key: 'monitor_seconds',
                    label: 'Stock rule scan interval · seconds (15–3600)',
                    type: 'number',
                  },
                  {
                    key: 'expiry_days',
                    label: 'Expiry warning horizon · days',
                    type: 'number',
                  },
                  {
                    key: 'handling_cents',
                    label: 'Handling/documentation fee (USD)',
                    type: 'usd',
                  },
                ])
              }
            >
              Configure
            </Button>
          </div>
          <div className="admin-setting-grid">
            {Object.entries(s.integrations).map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <b>
                  {typeof value === 'boolean'
                    ? value
                      ? 'Configured'
                      : 'Not configured'
                    : value}
                </b>
              </div>
            ))}
          </div>
          <p className="admin-muted">
            Automated analysis is not active in this release. Buyer approvals remain entirely human-led.
          </p>
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Country document rules</h2>
            <Button
              onClick={() =>
                edit('Add country requirements', 'country', {}, [
                  { key: 'country', label: 'Country' },
                  {
                    key: 'requirements',
                    label: 'One document requirement per line',
                    type: 'lines',
                  },
                ])
              }
            >
              Add country
            </Button>
          </div>
          <DataTable
            columns={['Country', 'Required documents', '']}
            rows={Object.entries(s.countries).map(([country, requirements]) => [
              country,
              requirements.join(' · '),
              <Button
                key="e"
                variant="outline"
                size="sm"
                onClick={() =>
                  edit(
                    'Edit ' + country + ' checklist',
                    'country',
                    { country, requirements },
                    [
                      {
                        key: 'requirements',
                        label: 'One required document per line',
                        type: 'lines',
                      },
                    ],
                  )
                }
              >
                Edit rules
              </Button>,
            ])}
          />
          <p className="admin-muted">
            POC configuration, not legal advice. Added requirements can block
            existing buyers until their documents are updated.
          </p>
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Shipping services</h2>
            <Button
              onClick={() =>
                edit('Add shipping service', 'shipping', { cents: 200000 }, [
                  { key: 'name', label: 'Service name' },
                  {
                    key: 'cents',
                    label: 'Shipping fee (USD)',
                    type: 'usd',
                  },
                ])
              }
            >
              Add service
            </Button>
          </div>
          <DataTable
            columns={['Service', 'Configured fee', '']}
            rows={Object.entries(s.services).map(([name, cents]) => [
              name,
              usd(cents),
              <Button
                key="e"
                variant="outline"
                size="sm"
                onClick={() =>
                  edit('Edit shipping fee', 'shipping', { name, cents }, [
                    { key: 'cents', label: 'Fee (USD)', type: 'usd' },
                  ])
                }
              >
                Edit
              </Button>,
            ])}
          />
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Destination ports</h2>
            <Button
              onClick={() =>
                edit('Add destination', 'destination', {}, [
                  { key: 'name', label: 'Port / city, country' },
                ])
              }
            >
              Add destination
            </Button>
          </div>
          <p>{s.destinations.join(' · ')}</p>
        </section>
        <section className="admin-panel">
          <h2>Backup and local operation</h2>
          <p className="admin-muted">
            Both applications use one database. Stop the app before restoring a
            backup. The README contains the owner-only backup and restore
            procedure. The verified buyer shortcut is disabled with
            BLUEHARBOR_DEMO=0.
          </p>
        </section>
      </>
    );
  return null;
}

function Editor({
  editor: e,
  state,
  busy,
  error,
  act,
}: {
  editor: Row;
  state: State;
  busy: boolean;
  error: string;
  act: Action;
}) {
  const [uploadError, setUploadError] = useState('');
  const [stockDirection, setStockDirection] = useState<'add' | 'remove'>('add');
  const [stockAmount, setStockAmount] = useState('');
  if (e.path === 'view-audit')
    return (
      <div className="audit-comparison">
        <h3>Before</h3>
        <pre>{JSON.stringify(JSON.parse(e.data.before_json), null, 2)}</pre>
        <h3>After</h3>
        <pre>{JSON.stringify(JSON.parse(e.data.after_json), null, 2)}</pre>
      </div>
    );
  if (e.path === 'view-order')
    return (
      <div>
        <Pill value={e.data.status} />
        <h3>
          {e.data.product_name} · {e.data.kg} kg
        </h3>
        <p>
          {e.data.destination} · {usd(e.data.total)}
        </p>
        <div className="case-info-grid">
          <div>
            <small>Internal note</small>
            <b>{e.data.internal_note || 'None'}</b>
          </div>
        </div>
        {e.data.events.map((event: Row) => (
          <div className="admin-history" key={event.id}>
            <b>{event.title}</b>
            <small>{when(event.created)}</small>
            <p>{event.note}</p>
          </div>
        ))}
      </div>
    );
  if (e.path === 'adjust-stock') {
    const current = Number(e.data.expected_available || 0);
    const amount = Math.max(0, Number(stockAmount) || 0);
    const projected = current + (stockDirection === 'add' ? amount : -amount);
    return (
      <form
        className="admin-edit-form stock-adjust-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setUploadError('');
          const form = new FormData(event.currentTarget);
          if (!Number.isInteger(amount) || amount <= 0) {
            setUploadError('Enter a whole-number quantity greater than zero.');
            return;
          }
          if (projected < 0) {
            setUploadError('The quantity removed is greater than the available stock.');
            return;
          }
          await act(e.path, {
            ...e.data,
            delta: stockDirection === 'add' ? amount : -amount,
            reason:
              typeof form.get('reason') === 'string'
                ? (form.get('reason') as string)
                : '',
          });
        }}
      >
        <div className="stock-balance-preview">
          <span><small>Current available</small><b>{current.toLocaleString()} kg</b></span>
          <span><small>After this change</small><b>{projected.toLocaleString()} kg</b></span>
        </div>
        <div className="admin-form-grid">
          <label htmlFor="stock-direction">Adjustment type
            <NativeSelect id="stock-direction" value={stockDirection} onChange={(event) => setStockDirection(event.target.value as 'add' | 'remove')}>
              <option value="add">Add stock</option>
              <option value="remove">Remove stock</option>
            </NativeSelect>
          </label>
          <label htmlFor="stock-amount">Quantity (kg)
            <Input id="stock-amount" type="number" min="1" step="1" value={stockAmount} onChange={(event) => setStockAmount(event.target.value)} required />
          </label>
          <label className="wide" htmlFor="stock-reason">Reason / supporting details
            <textarea id="stock-reason" name="reason" required maxLength={3000} placeholder="Example: Physical count completed at Kochi cold store" />
          </label>
        </div>
        {(error || uploadError) && <p role="alert" className="admin-error">{uploadError || error}</p>}
        <Button disabled={busy} type="submit">{busy ? 'Saving…' : 'Confirm stock adjustment'}</Button>
        <p className="admin-muted">The saved balance is checked again before the change is committed. Signed in as {state.staff.name}.</p>
      </form>
    );
  }
  async function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadError('');
    const form = new FormData(event.currentTarget);
    const data: Row = { ...e.data };
    try {
      for (const field of e.fields as Field[]) {
        const value = form.get(field.key);
        if (field.type === 'file' || field.type === 'image') {
          const file = value as File;
          if (!file?.size) {
            if (!field.optional) throw new Error('Choose a file.');
            continue;
          }
          if (file.size > 5 * 1024 * 1024)
            throw new Error('Maximum file size is 5 MB.');
          const encoded = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () =>
              resolve((reader.result as string).split(',')[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
          });
          if (field.type === 'image') {
            data.photo_content = encoded;
            data.photo_name = file.name;
          } else {
            data.content = encoded;
            data.name = file.name;
          }
        } else if (field.type === 'lines')
          data[field.key] = (typeof value === 'string' ? value : '')
            .split('\n')
            .map((x) => x.trim())
            .filter(Boolean);
        else if (field.type === 'boolean') data[field.key] = value === 'true';
        else if (field.type === 'usd')
          data[field.key] = Math.round(Number(value) * 100);
        else if (
          field.type === 'number' ||
          field.type === 'decimal' ||
          ['published', 'active', 'assignee'].includes(field.key)
        )
          data[field.key] = Number(value);
        else data[field.key] = typeof value === 'string' ? value : '';
      }
      await act(e.path, data);
    } catch (ex) {
      setUploadError((ex as Error).message);
    }
  }
  return (
    <form onSubmit={submit} className="admin-edit-form" key={e.title}>
      <div className="admin-form-grid">
        {(e.fields as Field[]).map((field) => (
          <label
            key={field.key}
            htmlFor={'edit-' + field.key}
            className={
              ['textarea', 'lines', 'file', 'image'].includes(field.type || '')
                ? 'wide'
                : ''
            }
          >
            {field.label}
            {field.options ? (
              <NativeSelect
                id={'edit-' + field.key}
                name={field.key}
                defaultValue={e.data[field.key] ?? field.options[0]?.[0]}
                required={!field.optional}
              >
                {e.data[field.key] &&
                  !field.options.some(
                    ([value]) => value === e.data[field.key],
                  ) && (
                    <option value={e.data[field.key]}>Current selection</option>
                  )}
                {field.options.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </NativeSelect>
            ) : field.type === 'boolean' ? (
              <NativeSelect
                id={'edit-' + field.key}
                name={field.key}
                defaultValue={String(e.data[field.key] ?? false)}
              >
                <option value="false">Disabled</option>
                <option value="true">Enabled</option>
              </NativeSelect>
            ) : ['textarea', 'lines'].includes(field.type || '') ? (
              <textarea
                id={'edit-' + field.key}
                name={field.key}
                defaultValue={
                  Array.isArray(e.data[field.key])
                    ? e.data[field.key].join('\n')
                    : e.data[field.key] || ''
                }
                required={!field.optional}
                maxLength={3000}
              />
            ) : field.type === 'file' || field.type === 'image' ? (
              <input
                id={'edit-' + field.key}
                name={field.key}
                type="file"
                accept={
                  field.type === 'image'
                    ? '.png,.jpg,.jpeg'
                    : '.pdf,.png,.jpg,.jpeg'
                }
                required={!field.optional}
              />
            ) : (
              <Input
                id={'edit-' + field.key}
                name={field.key}
                type={
                  field.type === 'decimal' || field.type === 'usd'
                    ? 'number'
                    : field.type || 'text'
                }
                step={
                  field.type === 'usd'
                    ? '0.01'
                    : field.type === 'decimal'
                    ? '0.1'
                    : field.type === 'number'
                      ? '1'
                      : undefined
                }
                defaultValue={field.type === 'usd' ? Number(e.data[field.key] || 0) / 100 : e.data[field.key] ?? ''}
                required={!field.optional}
                minLength={field.type === 'password' ? 12 : undefined}
                maxLength={500}
              />
            )}
          </label>
        ))}
      </div>
      {['verification', 'publish-document', 'order-status'].includes(
        e.path,
      ) && (
        <p className="admin-muted">
          This action may change what the buyer can see or do.
        </p>
      )}
      {(error || uploadError) && (
        <p role="alert" className="admin-error">
          {uploadError || error}
        </p>
      )}
      <Button disabled={busy} type="submit">
        {busy
          ? 'Saving…'
          : e.path === 'notify'
            ? 'Send notification'
            : 'Save changes'}
      </Button>
      <p className="admin-muted">
        Signed in as {state.staff.name}. Actions are recorded in the audit
        trail.
      </p>
    </form>
  );
}


