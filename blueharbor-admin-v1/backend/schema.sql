PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
 name TEXT NOT NULL, company TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT 'UAE',
 registration TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
 verified TEXT NOT NULL DEFAULT 'DRAFT', created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, grade TEXT NOT NULL,
 origin TEXT NOT NULL, cents_per_kg INTEGER NOT NULL CHECK(cents_per_kg>0),
 minimum_kg INTEGER NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lots (
 id TEXT PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
 available_kg INTEGER NOT NULL CHECK(available_kg>=0), reserved_kg INTEGER NOT NULL DEFAULT 0 CHECK(reserved_kg>=0),
 expiry TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), product_id INTEGER NOT NULL REFERENCES products(id),
 product_name TEXT NOT NULL, kg INTEGER NOT NULL, cents_per_kg INTEGER NOT NULL,
 shipping INTEGER NOT NULL, total INTEGER NOT NULL, destination TEXT NOT NULL, service TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'CONFIRMED', created TEXT NOT NULL, request_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
 UNIQUE(user_id,request_key)
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE TABLE IF NOT EXISTS allocations (order_id TEXT REFERENCES orders(id),lot_id TEXT REFERENCES lots(id),kg INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY,order_id TEXT REFERENCES orders(id),title TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL,name TEXT NOT NULL,
 mime TEXT NOT NULL,content BLOB NOT NULL,expiry TEXT NOT NULL,created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),message TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (identity TEXT PRIMARY KEY,count INTEGER NOT NULL,started INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS demo_accounts (user_id INTEGER PRIMARY KEY REFERENCES users(id));
CREATE TABLE IF NOT EXISTS tanks (id TEXT PRIMARY KEY,lot_id TEXT UNIQUE NOT NULL REFERENCES lots(id),zone TEXT NOT NULL);
-- Additive catalogue metadata: existing stock, users and orders stay intact.
CREATE TABLE IF NOT EXISTS product_sources (
    product_id INTEGER PRIMARY KEY REFERENCES products(id),
    region TEXT NOT NULL,
    export_port TEXT NOT NULL,
    facility TEXT NOT NULL
);
