'use client';
/* Local optimized reference assets; no external image-optimizer service needed. */
/* oxlint-disable next/no-img-element */

import { useState } from 'react';
import {
  ArrowUpRight,
  ArrowRight,
  Search,
  ShieldCheck,
  Waves,
  Package,
  Fish,
  MapPin,
  Anchor,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';

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
type Tank = {
  id: string;
  zone: string;
  product_id: number;
  available_kg: number;
  reserved_kg: number;
  name: string;
};
type Props = {
  products: Product[];
  tanks: Tank[];
  onProduct: (p: Product) => void;
  onDemo: () => void;
  demoAvailable: boolean;
  signedIn: boolean;
  busy: boolean;
};
const imageNames = [
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
export function productImage(p: { id: number; image?: string }) {
  if (p.image && /^\/(catalog\/|api\/product-image\/)/.test(p.image))
    return p.image;
  return '/catalog/' + (imageNames[p.id - 1] || 'asian-sea-bass') + '.jpg';
}
const price = (n: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n / 100);

export default function SeafoodMarketplace({
  products,
  tanks,
  onProduct,
  onDemo,
  demoAvailable,
  signedIn,
  busy,
}: Props) {
  const [category, setCategory] = useState('All seafood');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('Featured');
  const [tankId, setTankId] = useState<string | null>(null);
  const tank = tanks.find((t) => t.id === tankId);
  const filtered = products.filter(
    (p) =>
      (category === 'All seafood' || p.category === category) &&
      `${p.name} ${p.grade} ${p.origin} ${p.region} ${p.export_port}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  if (sort === 'Price: low to high')
    filtered.sort((a, b) => a.cents_per_kg - b.cents_per_kg);
  if (sort === 'Stock: high to low')
    filtered.sort((a, b) => b.available_kg - a.available_kg);
  const volume = tanks.reduce((s, t) => s + t.available_kg, 0);
  return (
    <>
      <section className="exchange-hero" aria-label="India seafood marketplace">
        <img
          src="/ocean-tanks.png"
          alt="Illustrative ocean scene with schooling fish"
          fetchPriority="high"
        />
        <div className="exchange-hero-copy">
          <p className="hero-kicker">
            <span />
            INDIA’S SEAFOOD EXCHANGE
          </p>
          <h1>
            From Indian waters.
            <br />
            <em>To your world.</em>
          </h1>
          <p>
            Explore available seafood, reserve your quantity,
            <br className="desktop-only" /> and follow every step of your
            shipment.
          </p>
        </div>
        <div className="exchange-hero-stock">
          <Waves size={26} />
          <small>LIVE HOLDING INVENTORY</small>
          <strong>
            {(volume / 1000).toLocaleString()} <span>MT</span>
          </strong>
          <p>{tanks.length} tanks · Chennai, India</p>
          <a href="#warehouse-tanks">
            Explore holding tanks <ArrowRight size={16} />
          </a>
        </div>
        <span className="hero-image-note">Ocean illustration</span>
      </section>
      <div className="export-strip">
        <span>
          <MapPin size={17} /> Sourced in India
        </span>
        <span>
          <ShieldCheck size={17} /> Verified buyer access
        </span>
        <span>
          <Anchor size={17} /> International destinations
        </span>
      </div>
      <section id="fish-catalogue" className="fish-collection">
        <div className="collection-heading">
          <div>
            <p className="eyebrow">THE MARKETPLACE</p>
            <h2>
              Find your next catch.<span>{products.length} products</span>
            </h2>
          </div>
          <span className="collection-price-note">
            USD / MT · Export pricing
          </span>
        </div>
        <div className="collection-controls">
          <fieldset className="collection-tabs" aria-label="Filter products">
            {[
              'All seafood',
              'Live fish',
              'Shrimp',
              'Fish',
              'Cephalopods',
              'Crab',
            ].map((c) => (
              <button
                key={c}
                className={category === c ? 'selected' : ''}
                aria-pressed={category === c}
                onClick={() => setCategory(c)}
              >
                {c === 'Live fish' && <Waves size={16} />}{' '}
                {c === 'Fish'
                  ? 'Frozen fish'
                  : c === 'Cephalopods'
                    ? 'Squid & cuttlefish'
                    : c}
              </button>
            ))}
          </fieldset>
          <div className="collection-tools">
            <div className="collection-search">
              <Search size={18} />
              <Input
                value={query}
                aria-label="Search seafood or Indian source location"
                placeholder="Species, location or port…"
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <NativeSelect
              value={sort}
              aria-label="Sort products"
              onChange={(e) => setSort(e.target.value)}
            >
              {['Featured', 'Price: low to high', 'Stock: high to low'].map(
                (s) => (
                  <option key={s}>{s}</option>
                ),
              )}
            </NativeSelect>
          </div>
        </div>
        <div className="results-line" aria-live="polite">
          <span>{filtered.length} products available to explore</span>
          <span>
            <i className="dot" /> Stock refreshes every 15 seconds
          </span>
        </div>
        <div className="seafood-cards">
          {filtered.map((p) => (
            <button
              key={p.id}
              className={`seafood-card species-${p.id}`}
              onClick={() => onProduct(p)}
              aria-label={`View ${p.name}, ${p.available_kg.toLocaleString()} kilograms available`}
            >
              <div className="seafood-photo">
                <img
                  src={productImage(p)}
                  alt={`${p.name} species reference photograph`}
                  loading="lazy"
                />
                <span className="stock-lozenge">
                  <span className="dot" />
                  {p.available_kg
                    ? `${(p.available_kg / 1000).toLocaleString()} MT available`
                    : 'Out of stock'}
                </span>
                <span className="photo-caption">Species reference</span>
                <span className="product-open">
                  <ArrowUpRight size={22} />
                </span>
              </div>
              <div className="seafood-info">
                <div className="seafood-origin">
                  <span>
                    <MapPin size={14} />
                    {p.region || p.origin}
                  </span>
                  {p.category === 'Live fish' ? (
                    <Waves size={17} />
                  ) : (
                    <Package size={17} />
                  )}
                </div>
                <h3>{p.name}</h3>
                <p>{p.grade}</p>
                <div className="product-route">
                  <Anchor size={14} />
                  {p.export_port || 'Origin port'}, India{' '}
                  <ArrowRight size={14} /> Global
                </div>
                <div className="seafood-price">
                  <div>
                    <b>{price(p.cents_per_kg * 1000)}</b>
                    <span> / MT</span>
                    <small>Min. {p.minimum_kg.toLocaleString()} kg</small>
                  </div>
                  <span className="trade-label">
                    View & order <ArrowRight size={16} />
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
        {!filtered.length && (
          <div className="empty">
            <Fish size={28} />
            <h3>No seafood matches your search</h3>
            <p>Try another species or source location.</p>
            <Button
              variant="outline"
              onClick={() => {
                setCategory('All seafood');
                setQuery('');
              }}
            >
              Clear filters
            </Button>
          </div>
        )}
      </section>
      <section
        className="tank-showroom"
        id="warehouse-tanks"
        aria-label="Warehouse holding tanks"
      >
        <div className="showroom-image">
          <img
            src="/fish-warehouse.png"
            alt="Illustrative warehouse with blue aquaculture holding tanks"
            loading="lazy"
          />
          <span>
            <Waves size={16} /> Warehouse illustration
          </span>
        </div>
        <div className="showroom-content">
          <div className="showroom-title">
            <div>
              <p className="eyebrow">CHENNAI · LIVE HOLDING</p>
              <h2>A closer look at your source.</h2>
            </div>
          </div>
          <p>Select a tank to see available and reserved stock.</p>
          <div className="tank-options">
            {tanks.map((t) => (
              <button
                key={t.id}
                onClick={() => setTankId(tankId === t.id ? null : t.id)}
                className={tankId === t.id ? 'selected' : ''}
                aria-pressed={tankId === t.id}
              >
                <span className="tank-water">
                  <Waves size={18} />
                </span>
                <span>
                  <b>{t.id}</b>
                  <small>{t.name}</small>
                </span>
                <strong>
                  {(t.available_kg / 1000).toLocaleString()}
                  <small> MT</small>
                </strong>
              </button>
            ))}
          </div>
          {tank && (
            <div className="tank-selection">
              <span>
                {tank.zone} · {tank.available_kg.toLocaleString()} kg available
                · {tank.reserved_kg.toLocaleString()} kg reserved
              </span>
              <Button
                size="sm"
                onClick={() => {
                  const p = products.find((p) => p.id === tank.product_id);
                  if (p) onProduct(p);
                }}
              >
                View fish <ArrowUpRight size={16} />
              </Button>
              <small>
                Orders allocate eligible lots by expiry, not exclusively from
                the selected tank.
              </small>
            </div>
          )}
        </div>
      </section>
      <p className="catalogue-footnote">
        Catalogue locations, prices and volumes are seeded test data. Species
        photographs are references, not images of the offered lots. Live-fish
        transport requires exporter confirmation.{' '}
        <a href="/catalog/credits.html" target="_blank" rel="noreferrer">
          Photo credits & licenses
        </a>
      </p>
      {!signedIn && demoAvailable && (
        <section className="demo-invitation">
          <ShieldCheck size={28} />
          <div>
            <h3>Explore as a verified buyer.</h3>
            <p>
              One-click testing access. No registration or document upload
              needed.
            </p>
          </div>
          <Button disabled={busy} onClick={onDemo}>
            Enter test account <ArrowRight size={17} />
          </Button>
        </section>
      )}
    </>
  );
}
