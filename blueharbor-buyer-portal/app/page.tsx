'use client';
/* Native local images avoid a runtime image-optimizer dependency in the local POC. */
/* oxlint-disable next/no-img-element */
import { useEffect, useState, type SyntheticEvent } from 'react';
import {
  ArrowUpRight,
  ArrowRight,
  Check,
  Fish,
  Package,
  ShieldCheck,
  FileText,
  Bell,
  LogOut,
  X,
  Globe,
  Sparkles,
  RefreshCw,
  Download,
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
import { Checkbox } from '@/components/ui/checkbox';
import './portal.css';
import './shipment-map.css';
import './ocean.css';
import './exchange.css';
import OrderTracking from '@/components/order-tracking';
import ComplianceWorkspace from '@/components/compliance-workspace';
import BlueHarborGuide from '@/components/blueharbor-guide';
import SeafoodMarketplace, {
  productImage,
} from '@/components/seafood-marketplace';

type Product = {
  image?: string;
  id: number;
  name: string;
  category: string;
  grade: string;
  origin: string;
  region: string;
  export_port: string;
  facility: string;
  cents_per_kg: number;
  minimum_kg: number;
  available_kg: number;
  description: string;
};
type Buyer = {
  demo: boolean;
  id: number;
  email: string;
  name: string;
  company: string;
  country: string;
  registration: string;
  address: string;
  phone: string;
  verified: string;
};
type Order = {
  id: string;
  product_name: string;
  kg: number;
  total: number;
  destination: string;
  service: string;
  status: string;
  created: string;
  events: { id: number; title: string; note: string; created: string }[];
  documents: { id: string; kind: string; name: string; version: number; created: string }[];
  compliance?: {
    country: string;
    released: number;
    started: number;
    progress: number;
    total: number;
    blocking: number;
    departure_blocking: number;
    clearance_blocking: number;
    departure_ready: boolean;
    clearance_ready: boolean;
    ready: boolean;
    items: { requirement_code: string; document_name: string; owner: string; blocking: number; status: string; note: string; issuer: string; official_issuer: string; source_url: string; required_stage: string; responsible_party: string; evidence_type: string; original_required: number; document?: { id: string; version: number; document_number: string; expiry_date: string } }[];
  };
};
type Doc = {
  id: string;
  kind: string;
  name: string;
  expiry: string;
  size: number;
};
type State = {
  user: Buyer;
  orders: Order[];
  documents: Doc[];
  notifications: {
    id: number;
    message: string;
    seen: number;
    created: string;
  }[];
  ai_available: boolean;
};
type Catalog = {
  demo_available: boolean;
  handling_cents: number;
  tanks: {
    id: string;
    zone: string;
    product_id: number;
    available_kg: number;
    reserved_kg: number;
    name: string;
  }[];
  products: Product[];
  countries: Record<string, string[]>;
  destinations: string[];
  services: Record<string, number>;
};
const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
    n / 100,
  );
const time = (s: string) => new Date(s).toLocaleString();
async function api<T = Record<string, unknown>>(
  path: string,
  data?: unknown,
): Promise<T> {
  const r = await fetch('/api/' + path, {
    credentials: 'same-origin',
    ...(data === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-BlueHarbor': '1' },
          body: JSON.stringify(data),
        }),
  });
  const value = (await r.json()) as { error?: string };
  if (!r.ok) throw new Error(value.error || 'Request failed');
  return value as T;
}
const navigation = [
  ['Overview', Globe],
  ['Marketplace', Fish],
  ['Orders', Package],
  ['Profile & Compliance', ShieldCheck],
  ['Activity', Bell],
] as const;

export default function Portal() {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [state, setState] = useState<State | null>(null),
    [view, setView] = useState('Marketplace'),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [auth, setAuth] = useState<'login' | 'register' | null>(null),
    [consent, setConsent] = useState(false),
    [product, setProduct] = useState<Product | null>(null),
    [kg, setKg] = useState(1000),
    [unit, setUnit] = useState('kg'),
    [destination, setDestination] = useState('Jebel Ali, UAE'),
    [service, setService] = useState('Standard'),
    [requestKey, setRequestKey] = useState(''),
    [review, setReview] = useState(false),
    [expandedOrder, setExpandedOrder] = useState<string | null>(null),
    [connected, setConnected] = useState(true),
    [cancelConfirm, setCancelConfirm] = useState<string | null>(null);
  async function refresh() {
    const c = await api<Catalog>('catalog');
    setCatalog(c);
    try {
      setState(await api<State>('state'));
    } catch (e) {
      if (
        (e as Error).message.includes('sign in') ||
        (e as Error).message.includes('Session')
      )
        setState(null);
      else throw e;
    }
    setConnected(true);
  }

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash.includes('access_token')) {
      const params = new URLSearchParams(window.location.hash.substring(1));
      const access_token = params.get('access_token');
      const expires_in = params.get('expires_in');
      if (access_token) {
        setBusy(true);
        api<{ user: Buyer }>('sso-login', { access_token, expires_in: parseInt(expires_in || '3600') })
          .then(result => {
            window.location.hash = '';
            setAuth(null);
            setView(result.user.verified === 'VERIFIED' ? 'Overview' : 'Profile & Compliance');
            setNotice(
              result.user.verified === 'VERIFIED'
                ? 'Welcome. Your trading workspace is ready.'
                : 'Welcome. Continue your compliance journey to unlock trading.',
            );
            void refresh();
          })
          .catch(e => setError(e.message))
          .finally(() => setBusy(false));
      }
    }
  }, []);

  useEffect(() => {
    const initial = setTimeout(() => {
      void refresh()
        .catch((e) => {
          setError(e.message);
          setConnected(false);
        })
        .finally(() => setLoading(false));
    }, 0);
    const t = setInterval(
      () => refresh().catch(() => setConnected(false)),
      15000,
    );
    return () => {
      clearInterval(t);
      clearTimeout(initial);
    };
  }, []);
  useEffect(() => {
    if (!state?.user.id) return;
    const stream = new EventSource('/api/stream');
    const sync = () => {
      void refresh().catch(() => setConnected(false));
    };
    stream.addEventListener('refresh', sync);
    stream.addEventListener('ready', sync);
    stream.addEventListener('session-ended', () => {
      stream.close();
      setState(null);
      setNotice('Your session has ended. Please sign in again.');
    });
    stream.onerror = () => setConnected(false);
    return () => stream.close();
  }, [state?.user.id]);
  async function act(action: () => Promise<void>): Promise<boolean> {
    setBusy(true);
    setError('');
    try {
      await action();
      await refresh();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  function go(v: string) {
    if (!state && v !== 'Marketplace') {
      setAuth('login');
      return;
    }
    setView(v);
    setNotice('');
  }
  function openProduct(p: Product) {
    setProduct(p);
    setKg(p.minimum_kg);
    setUnit('kg');
    setRequestKey(crypto.randomUUID());
    setReview(false);
    setError('');
  }
  const orders = state?.orders || [],
    docs = state?.documents || [],
    required = catalog?.countries[state?.user.country || 'UAE'] || [];
  const total = product
    ? product.cents_per_kg * kg +
      (catalog?.services[service] || 0) +
      (catalog?.handling_cents ?? 50000)
    : 0;
  const field = (label: string, name: string, value = '', type = 'text') => (
    <label className="field" htmlFor={`input-${name}`}>
      <span>{label}</span>
      <Input
        id={`input-${name}`}
        name={name}
        defaultValue={value}
        type={type}
        required
        maxLength={500}
      />
    </label>
  );
  async function demoLogin() {
    setAuth('login');
  }
  async function login(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    await act(async () => {
      if (auth === 'register') {
        const result = await api<{ message: string }>('register', {
          ...f,
          consent,
        });
        setAuth('login');
        setNotice(result.message);
        return;
      }
      const result = await api<{ user: Buyer }>('login', f);
      setAuth(null);
      setView(result.user.verified === 'VERIFIED' ? 'Overview' : 'Profile & Compliance');
      setNotice(
        result.user.verified === 'VERIFIED'
          ? 'Welcome. Your trading workspace is ready.'
          : 'Welcome. Continue your compliance journey to unlock trading.',
      );
    });
  }
  async function upload(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      f = new FormData(form),
      file = f.get('file') as File;
    if (file.size > 5 * 1024 * 1024) {
      setError('Maximum upload size is 5 MB.');
      return;
    }
    await act(async () => {
      const content = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string).split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      await api('documents', {
        kind: f.get('kind'),
        expiry: f.get('expiry'),
        name: file.name,
        content,
      });
      form.reset();
      setNotice('Document securely saved to private Supabase Storage.');
    });
  }
  if (loading)
    return <main className="buyer-access-shell"><section className="buyer-access-card loading"><span className="brand-icon"><Fish /></span><p className="eyebrow">BLUEHARBOR FISH EXCHANGE</p><h1>Opening your trade desk…</h1><p>Connecting to the secure buyer workspace.</p></section></main>;
  if (!state) {
    const registering=auth==='register';
    return <main className="buyer-access-shell"><section className="buyer-access-story"><span className="brand-icon"><Fish /></span><p className="eyebrow">INDIA TO GLOBAL MARKETS</p><h1>Your seafood orders, vessel journeys and clearance documents in one place.</h1><p>Verified buyers can reserve stock, follow the vessel’s complete port rotation and see the exact loading-to-discharge cargo window.</p><div><span>USD trading</span><span>Private compliance</span><span>Live shipment milestones</span></div></section><section className="buyer-access-card"><ShieldCheck size={30}/><p className="eyebrow">SECURE BUYER ACCESS</p><h2>{registering?'Create your buyer account':'Sign in to continue'}</h2><p>{registering?'Account creation is the first stage. Company and document verification follow inside the portal.':'Your marketplace, orders and shipment information are protected.'}</p>{notice&&<p className="access-notice">{notice}</p>}<form onSubmit={login} className="auth-form">{registering&&field('Full name','name')}{field('Email','email','','email')}<label className="field" htmlFor="gate-password"><span>{registering?'Password · 12–128 characters':'Password'}</span><Input id="gate-password" name="password" type="password" required minLength={registering?12:undefined} maxLength={128} autoComplete={registering?'new-password':'current-password'}/></label>{registering&&<label className="consent" htmlFor="gate-consent"><Checkbox id="gate-consent" checked={consent} onCheckedChange={v=>setConsent(!!v)}/>I agree to secure storage of my account and verification information.</label>}{error&&<p role="alert" className="inline-error">{error}</p>}<div className="auth-buttons"><Button disabled={busy||(registering&&!consent)} type="submit">{busy?'Please wait…':registering?'Create account':'Sign in'}<ArrowRight size={16}/></Button>{!registering && <Button type="button" variant="outline" onClick={() => window.location.href='http://127.0.0.1:54321/auth/v1/sso?provider_id=1f135138-bdea-420f-a350-1bd4539cf295&redirect_to=http://localhost:3000'}>Enterprise Sign-In (SSO)</Button>}</div><button type="button" className="text-link" onClick={()=>{setError('');setAuth(registering?'login':'register')}}>{registering?'Already registered? Sign in':'New buyer? Create an account'}</button><p className="fine">Confirm your email before signing in. Supabase Auth securely manages passwords.</p></form></section></main>;
  }
  return (
    <div className="bh">
      <aside className="rail">
        <button className="brand" onClick={() => go('Marketplace')}>
          <span className="brand-icon">
            <Fish />
          </span>
          <strong>
            blueharbor<span>FISH EXCHANGE</span>
          </strong>
        </button>
        <nav aria-label="Buyer navigation">
          {navigation.map(([name, Icon]) => (
            <button
              key={name}
              className={view === name ? 'active' : ''}
              aria-current={view === name ? 'page' : undefined}
              onClick={() => go(name)}
            >
              <Icon size={18} />
              {name}
              {name === 'Activity' &&
                !!state?.notifications.filter((n) => !n.seen).length && (
                  <i>{state.notifications.filter((n) => !n.seen).length}</i>
                )}
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <div className="connection">
            <span className={connected ? 'dot' : 'dot offline'} />
            {connected ? 'Inventory connected' : 'Connection interrupted'}
          </div>
          {state && (
            <button
              onClick={() =>
                act(async () => {
                  await api('logout', {});
                  setState(null);
                  setView('Marketplace');
                })
              }
            >
              <LogOut size={16} />
              Sign out
            </button>
          )}
        </div>
      </aside>
      <main className="workspace-main">
        <header className="topbar">
          <div>
            <span className="crumb">India export desk</span>
            <span className="slash">/</span>
            <b>{view}</b>
          </div>
          <div className="header-actions">
            <span className="desktop-only currency">USD · kg / MT</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Refresh data"
              onClick={() => act(async () => {})}
            >
              <RefreshCw size={17} />
            </Button>
            {state ? (
              <button className="account" onClick={() => go('Profile & Compliance')}>
                <span className="account-copy">
                  {state.user.name}
                  <small
                    className={
                      state.user.verified === 'VERIFIED'
                        ? 'buyer-verified'
                        : 'buyer-pending'
                    }
                  >
                    <ShieldCheck size={14} />{' '}
                    {state.user.verified === 'VERIFIED'
                      ? 'Verified buyer'
                      : state.user.verified.replaceAll('_', ' ')}
                  </small>
                </span>
                <span className="avatar small">{state.user.name[0]}</span>
              </button>
            ) : (
              <Button onClick={() => setAuth('login')}>
                Sign in <ArrowUpRight size={16} />
              </Button>
            )}
          </div>
        </header>
        <div className="content">
          {error && (
            <div className="feedback error" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <output className="feedback success">
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice('')}
              >
                <X size={16} />
              </button>
            </output>
          )}
          {loading ? (
            <div className="empty">Connecting to your workspace…</div>
          ) : (
            <>
              {view === 'Marketplace' && catalog && (
                <>
                  {state && state.user.verified !== 'VERIFIED' && (
                    <section className="trade-gate">
                      <span><ShieldCheck size={20} /></span>
                      <div>
                        <small>TRADE ACCESS LOCKED</small>
                        <b>Browse every listing while your buyer identity is verified.</b>
                        <p>Reservations unlock only after company details, documents, submission, and staff approval are complete.</p>
                      </div>
                      <Button onClick={() => go('Profile & Compliance')}>Continue compliance <ArrowRight size={16} /></Button>
                    </section>
                  )}
                  <SeafoodMarketplace
                    products={catalog.products}
                    tanks={catalog.tanks}
                    onProduct={openProduct}
                    onDemo={() => void demoLogin()}
                    signedIn={!!state}
                    demoAvailable={catalog.demo_available}
                    busy={busy}
                  />
                </>
              )}
              {view === 'Overview' && state && (
                <>
                  <Title
                    tag="YOUR TRADE, AT A GLANCE"
                    title={`Welcome, ${state.user.name.split(' ')[0]}.`}
                    text="Your real orders, next steps, and latest activity in one place."
                  />
                  <div className="stats">
                    <Stat
                      label="Open orders"
                      value={
                        orders.filter(
                          (o) => !['DELIVERED', 'CANCELLED'].includes(o.status),
                        ).length
                      }
                    />
                    <Stat
                      label="Reserved volume"
                      value={
                        orders
                          .filter((o) =>
                            ['CONFIRMED', 'PROCESSING'].includes(o.status),
                          )
                          .reduce((a, o) => a + o.kg, 0) /
                          1000 +
                        ' MT'
                      }
                    />
                    <Stat
                      label="Delivered orders"
                      value={
                        orders.filter((o) => o.status === 'DELIVERED').length
                      }
                    />
                  </div>
                  <div className="overview-grid">
                    <section className="dark-panel">
                      <ShieldCheck size={32} />
                      <p className="eyebrow">BUYER ACCESS</p>
                      <h2>
                        {state.user.verified === 'VERIFIED'
                          ? 'You’re cleared to order.'
                          : 'Let’s get you export-ready.'}
                      </h2>
                      <p>
                        {state.user.verified === 'VERIFIED'
                          ? 'Browse available lots and configure your shipment.'
                          : 'Complete your company profile, upload required documents, and submit for review.'}
                      </p>
                      <Button
                        onClick={() =>
                          go(
                            state.user.verified === 'VERIFIED'
                              ? 'Marketplace'
                              : 'Profile & Compliance',
                          )
                        }
                      >
                        {state.user.verified === 'VERIFIED'
                          ? 'Browse seafood'
                          : 'Complete verification'}
                        <ArrowRight size={16} />
                      </Button>
                    </section>
                    <section className="panel">
                      <h2>Recent activity</h2>
                      {state.notifications.length ? (
                        state.notifications.slice(0, 4).map((n) => (
                          <div className="activity" key={n.id}>
                            <span className="event-dot" />
                            <div>
                              <b>{n.message}</b>
                              <small>{time(n.created)}</small>
                            </div>
                          </div>
                        ))
                      ) : (
                        <Empty
                          title="A fresh start"
                          text="Your updates will appear here as you verify and order."
                        />
                      )}
                    </section>
                  </div>
                  <div className="section-head">
                    <h2>Recent orders</h2>
                    <Button variant="ghost" onClick={() => go('Orders')}>
                      View all <ArrowUpRight size={16} />
                    </Button>
                  </div>
                  {orders.slice(0, 3).map((o) => (
                    <OrderRow
                      key={o.id}
                      order={o}
                      open={() => {
                        setView('Orders');
                        setExpandedOrder(o.id);
                      }}
                    />
                  ))}
                  {!orders.length && (
                    <Empty
                      title="Your first shipment starts here"
                      text="No orders yet. Browse the catalogue to explore available products."
                    />
                  )}
                </>
              )}
              {view === 'Orders' && (
                <>
                  <Title
                    tag="FROM INDIA TO YOUR DOOR"
                    title="Your orders. Every step."
                    text="Open an order’s tracking to follow its journey from reservation to delivery."
                  />
                  {orders.map((o) => (
                    <OrderTracking
                      key={o.id}
                      order={o}
                      expanded={expandedOrder === o.id}
                      toggle={() =>
                        setExpandedOrder(expandedOrder === o.id ? null : o.id)
                      }
                      cancel={() => setCancelConfirm(o.id)}
                      busy={busy}
                    />
                  ))}
                  {!orders.length && (
                    <Empty
                      title="No orders yet"
                      text="Once you confirm an order, it will appear here automatically."
                    />
                  )}
                </>
              )}
              {view === 'Profile & Compliance' && state && (
                <ComplianceWorkspace
                  user={state.user}
                  docs={docs}
                  required={required}
                  countries={Object.keys(catalog?.countries || {})}
                  busy={busy}
                  onSaveProfile={(data) =>
                    act(async () => {
                      await api('profile', data);
                      setNotice('Company profile saved. Continue with your required documents.');
                    })
                  }
                  onUpload={async (file, kind, expiry) => {
                    if (file.size > 5 * 1024 * 1024) {
                      setError('Maximum upload size is 5 MB.');
                      return false;
                    }
                    return act(async () => {
                      const content = await new Promise<string>((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve((reader.result as string).split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(file);
                      });
                      await api('documents', { kind, expiry, name: file.name, content });
                      setNotice(`${kind} uploaded securely.`);
                    });
                  }}
                  onSubmit={() =>
                    act(async () => {
                      await api('verification', {});
                      setNotice('Submitted. BlueHarbor staff will review your application.');
                    })
                  }
                />
              )}
              {view === 'Profile' && state && (
                <>
                  <Title
                    tag="COMPANY WORKSPACE"
                    title="Your business, on record."
                    text={
                      state.user.demo
                        ? 'This pre-verified demo company is ready to trade. Editing it restarts verification.'
                        : 'Changing company information restarts verification to protect your account.'
                    }
                  />
                  <form
                    className="panel form-grid"
                    key={state.user.id}
                    onSubmit={(e) => {
                      e.preventDefault();
                      const data = Object.fromEntries(
                        new FormData(e.currentTarget),
                      );
                      void act(async () => {
                        await api('profile', data);
                        setNotice(
                          'Profile saved. Verification status is now DRAFT.',
                        );
                      });
                    }}
                  >
                    {field('Full name', 'name', state.user.name)}
                    {field('Company name', 'company', state.user.company)}
                    {field(
                      'Registration number',
                      'registration',
                      state.user.registration,
                    )}
                    {field('Registered address', 'address', state.user.address)}
                    {field('Phone', 'phone', state.user.phone)}
                    <label className="field">
                      <span>Buyer country</span>
                      <NativeSelect
                        name="country"
                        defaultValue={state.user.country}
                      >
                        {Object.keys(catalog?.countries || {}).map((c) => (
                          <option key={c}>{c}</option>
                        ))}
                      </NativeSelect>
                    </label>
                    <div className="form-end">
                      <p className="muted">Signed in as {state.user.email}</p>
                      <Button disabled={busy} type="submit">
                        Save company profile
                      </Button>
                    </div>
                  </form>
                </>
              )}
              {view === 'Verification' && state && (
                <>
                  <Title
                    tag="TRUST STARTS HERE"
                    title={
                      state.user.verified === 'VERIFIED'
                        ? 'Ready to trade.'
                        : 'Ready for review.'
                    }
                    text="A transparent checklist—not a fabricated risk score."
                  />
                  <div className="status-banner">
                    <ShieldCheck />
                    <div>
                      <b>{state.user.verified.replaceAll('_', ' ')}</b>
                      <p>
                        {state.user.demo
                          ? 'This is a pre-approved local testing profile with synthetic documents—not a real verified identity.'
                          : 'Human approval is required before purchase. Email ownership and identity-provider verification are not connected.'}
                      </p>
                    </div>
                  </div>
                  <div className="verify-grid">
                    <section className="panel">
                      <h2>Company & document checklist</h2>
                      <div className="check-row">
                        <span className="event-dot" />
                        <div>
                          <b>Company information</b>
                          <p>
                            {state.user.company &&
                            state.user.registration &&
                            state.user.address
                              ? 'Required fields present'
                              : 'Company name, registration and address required'}
                          </p>
                        </div>
                        <Button variant="outline" onClick={() => go('Profile & Compliance')}>
                          Edit
                        </Button>
                      </div>
                      {required.map((kind) => {
                        const valid = docs.some(
                          (d) =>
                            d.kind === kind &&
                            d.expiry >= new Date().toISOString().slice(0, 10),
                        );
                        return (
                          <div className="check-row" key={kind}>
                            <span
                              className={valid ? 'checkmark' : 'pendingmark'}
                            >
                              {valid ? <Check size={16} /> : '–'}
                            </span>
                            <div>
                              <b>{kind}</b>
                              <p>
                                {valid
                                  ? 'Uploaded · declared expiry valid'
                                  : 'Upload an unexpired document'}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                      <Button
                        disabled={
                          busy ||
                          state.user.verified === 'UNDER_REVIEW' ||
                          state.user.verified === 'VERIFIED'
                        }
                        onClick={() =>
                          act(async () => {
                            await api('verification', {});
                            setNotice(
                              'Submitted. The admin team must review and approve your account.',
                            );
                          })
                        }
                      >
                        Submit for review <ArrowRight size={16} />
                      </Button>
                      <p className="fine">
                        File format and declared expiry are checked.
                        Authenticity, OCR and face/liveness verification are not
                        implemented. Do not upload real identity documents to
                        this POC.
                      </p>
                    </section>
                    <form className="panel" onSubmit={upload}>
                      <h2>Upload a document</h2>
                      <label className="field">
                        <span>Document type</span>
                        <NativeSelect name="kind">
                          {required.map((k) => (
                            <option key={k}>{k}</option>
                          ))}
                        </NativeSelect>
                      </label>
                      {field('Expiry date', 'expiry', '', 'date')}
                      <label className="upload">
                        <FileText />
                        <b>Choose PDF, PNG or JPG</b>
                        <small>Maximum 5 MB · private Supabase Storage</small>
                        <input
                          type="file"
                          name="file"
                          accept=".pdf,.png,.jpg,.jpeg"
                          required
                        />
                      </label>
                      <Button disabled={busy} type="submit">
                        Upload document
                      </Button>
                    </form>
                  </div>
                  <section className="ai-panel">
                    <Sparkles />
                    <div>
                      <h2>Admin-assisted verification</h2>
                      <p>
                        Your documents and company details are reviewed in the
                        admin console. AI can assist authorized staff; only
                        staff can approve your trading access.
                      </p>
                    </div>
                  </section>
                </>
              )}
              {view === 'Documentation' && (
                <>
                  <Title
                    tag="ORDER CLEARANCE"
                    title="Documents you can act on."
                    text="See what each destination needs, who owns the next step, and download released clearance files."
                  />
                  {orders.map((o) => (
                    <section className="clearance-card" key={'compliance-'+o.id}>
                      <div className="clearance-head"><div><small>{o.id} · {o.compliance?.country || o.destination}</small><h2>{o.product_name}</h2></div><span className={o.compliance?.ready ? 'clearance-ready' : 'clearance-blocked'}>{o.compliance?.ready ? 'Ready' : `${o.compliance?.blocking || 0} blockers`}</span></div>
                      <div className="clearance-progress"><span style={{width: `${o.compliance?.progress || 0}%`}} /></div>
                      <p>{o.compliance?.started || 0} of {o.compliance?.total || 0} requirements started · {o.compliance?.released || 0} released</p>
                      <div className="clearance-list">{o.compliance?.items.map((item) => <div key={item.requirement_code}><span className={'doc-state '+item.status.toLowerCase()}>{item.status.replaceAll('_',' ')}</span><div><b>{item.document_name}</b><small>{item.owner === 'BUYER' ? 'Buyer action' : item.issuer || 'BlueHarbor export desk'}{item.blocking ? ' · Dispatch blocker' : ''}</small></div>{item.document ? <a className="download" href={'/api/trade-document/'+item.document.id}><Download size={15}/> v{item.document.version}</a> : item.source_url ? <a className="download" href={item.source_url} target="_blank" rel="noreferrer">Guidance <ArrowUpRight size={14}/></a> : null}</div>)}</div>
                      {o.compliance?.ready && <a className="clearance-pack" href={'/api/clearance-pack/'+o.id}><Download size={17}/> Download verified clearance pack</a>}
                    </section>
                  ))}
                  <div className="section-head"><h2>Private company documents</h2></div>
                  {docs.map((d) => (
                    <div className="document-row" key={d.id}>
                      <FileText />
                      <div>
                        <b>{d.kind}</b>
                        <p>
                          {d.name} · {(d.size / 1024).toFixed(0)} KB · expires{' '}
                          {d.expiry}
                        </p>
                      </div>
                      <a className="download" href={'/api/document/' + d.id}>
                        <Download size={17} />
                        Download
                      </a>
                    </div>
                  ))}
                  {!docs.length && !orders.length && (
                    <Empty
                      title="No documents yet"
                      text="Upload verification files or confirm an order to populate your vault."
                    />
                  )}
                </>
              )}
              {view === 'Activity' && state && (
                <>
                  <Title
                    tag="WORKSPACE UPDATES"
                    title="Stay in the loop."
                    text="Database-backed notifications. Email delivery is not connected."
                  />
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        await api('read-notifications', {});
                      })
                    }
                  >
                    Mark all as read
                  </Button>
                  <section className="panel activity-list">
                    {state.notifications.map((n) => (
                      <div className="activity" key={n.id}>
                        <span
                          className={n.seen ? 'event-dot read' : 'event-dot'}
                        />
                        <div>
                          <b>{n.message}</b>
                          <small>{time(n.created)}</small>
                        </div>
                      </div>
                    ))}
                    {!state.notifications.length && (
                      <Empty
                        title="You’re all caught up"
                        text="New verification and order events will appear here."
                      />
                    )}
                  </section>
                </>
              )}
            </>
          )}
          <footer>
            BLUEHARBOR{' '}
            <span>India → Global markets · USD pricing · kg / MT</span>
          </footer>
        </div>
      </main>
      <Dialog
        open={!!auth}
        onOpenChange={(o) => {
          if (!o) setAuth(null);
        }}
      >
        <DialogContent className="bh-dialog">
          <DialogTitle>
            {auth === 'register' ? 'Start your buyer journey' : 'Welcome back'}
          </DialogTitle>
          <DialogDescription>
            {auth === 'register'
              ? 'Step 1 of 5 · Create a secure account. Company and document verification follow after sign-in.'
              : 'Sign in to continue compliance, browse orders, and reserve seafood exported from India.'}
          </DialogDescription>
          {catalog?.demo_available && (
            <Button
              className="demo-login-button"
              disabled={busy}
              onClick={() => void demoLogin()}
            >
              <ShieldCheck size={18} />{' '}
              {busy ? 'Signing in…' : 'Enter verified test account'}
            </Button>
          )}
          {catalog?.demo_available && (
            <p className="test-login-note">
              Testing only · Opens the pre-verified buyer without registration.
              This shortcut will be removed when production access is connected.
            </p>
          )}
          <form onSubmit={login} className="auth-form">
            {auth === 'register' && field('Full name', 'name')}
            {field('Email', 'email', '', 'email')}
            <label className="field" htmlFor="auth-password">
              <span>{auth === 'register' ? 'Password · 12–128 characters' : 'Password'}</span>
              <Input
                id="auth-password"
                name="password"
                type="password"
                required
                minLength={auth === 'register' ? 12 : undefined}
                maxLength={auth === 'register' ? 128 : undefined}
                autoComplete={
                  auth === 'register' ? 'new-password' : 'current-password'
                }
              />
            </label>
            {auth === 'register' && (
              <label className="consent" htmlFor="auth-consent">
                <Checkbox
                  id="auth-consent"
                  checked={consent}
                  onCheckedChange={(v) => setConsent(!!v)}
                />
                I agree to secure storage of my account and verification
                information for this POC.
              </label>
            )}
            {error && (
              <p role="alert" className="inline-error">
                {error}
              </p>
            )}
            <Button
              disabled={busy || (auth === 'register' && !consent)}
              type="submit"
            >
              {busy
                ? 'Please wait…'
                : auth === 'register'
                  ? 'Create account'
                  : 'Sign in'}
              <ArrowRight size={16} />
            </Button>
            <button
              type="button"
              className="text-link"
              onClick={() => {
                setError('');
                setAuth(auth === 'register' ? 'login' : 'register');
              }}
            >
              {auth === 'register'
                ? 'Already registered? Sign in'
                : 'New here? Create an account'}
            </button>
            <p className="fine">
              Confirm your email before signing in. Passwords are managed by
              Supabase Auth. Contact your administrator if you need account
              recovery.
            </p>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!product}
        onOpenChange={(o) => {
          if (!o) setProduct(null);
        }}
      >
        <DialogContent className="bh-dialog order-dialog">
          <DialogTitle>
            {review ? 'Review your order' : product?.name}
          </DialogTitle>
          <DialogDescription>
            {product?.grade} · {product?.origin}
          </DialogDescription>
          {product && (
            <>
              <div className="order-photo">
                <img
                  src={productImage(product)}
                  alt={`${product.name} species reference photograph`}
                />
                <span>
                  {product.category === 'Live fish'
                    ? 'Holding-tank collection'
                    : 'Cold-chain collection'}
                </span>
              </div>
              <p>{product.description}</p>
              <div className="origin-details">
                <span>
                  <b>Source</b>
                  {product.region || product.origin}
                </span>
                <span>
                  <b>Facility</b>
                  {product.facility || 'Exporter warehouse'}
                </span>
                <span>
                  <b>Export port</b>
                  {product.export_port || 'To be confirmed'}, India
                </span>
              </div>
              <div className="order-stock">
                <span>
                  {product.available_kg.toLocaleString()} kg available
                </span>
                <b>{money(product.cents_per_kg)} / kg</b>
              </div>
              {!review ? (
                <div className="form-grid">
                  <label className="field">
                    <span>Quantity · minimum {product.minimum_kg} kg</span>
                    <Input
                      aria-label="Quantity"
                      type="number"
                      min={product.minimum_kg / (unit === 'MT' ? 1000 : 1)}
                      step={unit === 'MT' ? 0.001 : 1}
                      value={kg / (unit === 'MT' ? 1000 : 1)}
                      onChange={(e) =>
                        setKg(
                          Math.round(
                            Number(e.target.value) * (unit === 'MT' ? 1000 : 1),
                          ),
                        )
                      }
                    />
                  </label>
                  <label className="field" htmlFor="order-unit">
                    <span>Unit</span>
                    <NativeSelect
                      id="order-unit"
                      value={unit}
                      onChange={(e) => setUnit(e.target.value)}
                    >
                      <option>kg</option>
                      <option>MT</option>
                    </NativeSelect>
                  </label>
                  <label className="field">
                    <span>Destination port</span>
                    <NativeSelect
                      value={destination}
                      onChange={(e) => setDestination(e.target.value)}
                    >
                      {catalog?.destinations.map((d) => (
                        <option key={d}>{d}</option>
                      ))}
                    </NativeSelect>
                  </label>
                  <label className="field">
                    <span>Shipping service</span>
                    <NativeSelect
                      value={service}
                      onChange={(e) => setService(e.target.value)}
                    >
                      {Object.keys(catalog?.services || {}).map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </NativeSelect>
                  </label>
                </div>
              ) : (
                <div className="summary">
                  <p>
                    <span>Seafood · {kg.toLocaleString()} kg</span>
                    <b>{money(product.cents_per_kg * kg)}</b>
                  </p>
                  <p>
                    <span>Shipping · {service}</span>
                    <b>{money(catalog?.services[service] || 0)}</b>
                  </p>
                  <p>
                    <span>Handling & documents</span>
                    <b>$500.00</b>
                  </p>
                  <p>
                    <span>Destination</span>
                    <b>{destination}</b>
                  </p>
                </div>
              )}
              <div className="order-total">
                <span>Estimated order total</span>
                <strong>{money(total)}</strong>
              </div>
              <p className="fine">
                No payment collected. Configured shipping estimates exclude
                duties, taxes and insurance. Commercial terms must be agreed
                with the exporter.
              </p>
              {error && (
                <p role="alert" className="inline-error">
                  {error}
                </p>
              )}
              {!state ? (
                <Button
                  onClick={() => {
                    setProduct(null);
                    setAuth('register');
                  }}
                >
                  Create an account to order
                </Button>
              ) : state.user.verified !== 'VERIFIED' ? (
                <Button
                  onClick={() => {
                    setProduct(null);
                    go('Profile & Compliance');
                  }}
                >
                  Complete buyer verification
                </Button>
              ) : (
                <Button
                  disabled={
                    busy ||
                    !Number.isInteger(kg) ||
                    kg < product.minimum_kg ||
                    kg > product.available_kg
                  }
                  onClick={() => {
                    if (!review) {
                      setReview(true);
                      return;
                    }
                    void act(async () => {
                      const result = await api<{ id: string }>('orders', {
                        product_id: product.id,
                        kg,
                        destination,
                        service,
                        request_key: requestKey,
                      });
                      setProduct(null);
                      setView('Orders');
                      setExpandedOrder(result.id);
                      setNotice(
                        result.id + ' confirmed. Your stock is reserved.',
                      );
                    });
                  }}
                >
                  {busy
                    ? 'Confirming…'
                    : review
                      ? 'Confirm & reserve stock'
                      : 'Review order'}
                  <ArrowRight size={16} />
                </Button>
              )}
              {review && (
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    setReview(false);
                    setRequestKey(crypto.randomUUID());
                  }}
                >
                  Edit order
                </Button>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!cancelConfirm}
        onOpenChange={(o) => {
          if (!o) setCancelConfirm(null);
        }}
      >
        <DialogContent className="bh-dialog">
          <DialogTitle>Cancel this order?</DialogTitle>
          <DialogDescription>
            The reservation will be released. You can place a new order later.
          </DialogDescription>
          <Button
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api('cancel', { id: cancelConfirm });
                setCancelConfirm(null);
                setNotice('Order cancelled and inventory released.');
              })
            }
          >
            Yes, cancel order
          </Button>
          <Button variant="outline" onClick={() => setCancelConfirm(null)}>
            Keep order
          </Button>
        </DialogContent>
      </Dialog>
      <BlueHarborGuide
        signedIn={Boolean(state)}
        verified={state?.user.verified}
        onNavigate={go}
      />
    </div>
  );
}
function Title({
  tag,
  title,
  text,
}: {
  tag: string;
  title: string;
  text: string;
}) {
  return (
    <div className="page-title">
      <p className="eyebrow">{tag}</p>
      <h1>{title}</h1>
      <p>{text}</p>
    </div>
  );
}
function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <Package size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
function OrderRow({ order: o, open }: { order: Order; open: () => void }) {
  return (
    <button className="order-row" onClick={open}>
      <span className="order-icon">
        <Package size={22} />
      </span>
      <div>
        <b>{o.product_name}</b>
        <small>
          {o.id} · {time(o.created)}
        </small>
      </div>
      <span>{(o.kg / 1000).toLocaleString()} MT</span>
      <span>{o.destination}</span>
      <b>{money(o.total)}</b>
      <span className="status-pill">{o.status}</span>
      <ArrowUpRight size={18} />
    </button>
  );
}
