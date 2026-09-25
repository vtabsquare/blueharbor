"""Postgres repository adapter retaining the existing parameterized domain queries.

No SQLite fallback. A transaction-scoped advisory lock serializes POC mutations
across API instances, protecting reservations, review revisions and quantities.
"""
import re
import secrets
from contextlib import contextmanager
import cloud_config as cfg
import cloud_http

SERIAL={'users','staff','products','events','notifications','audit','warehouses','condition_readings','stock_movements','ai_jobs','alerts','admin_audit','changes','email_outbox','discount_proposals'}
FILES={'documents':['id','user_id','kind','name','mime','content','expiry','created'],'product_images':['id','name','mime','content'],'trade_documents':['id','order_id','kind','name','mime','content','published','version','created','staff_id']}

class Row:
    def __init__(self,data):self.data=data
    def keys(self):return self.data.keys()
    def __getitem__(self,key):
        if isinstance(key,int):return list(self.data.values())[key]
        value=self.data[key]
        return cloud_http.download(value) if key=='content' and isinstance(value,str) else value
    def __iter__(self):return iter(self.data.values())
    def __len__(self):return len(self.data)

def translate(sql):
    sql=sql.strip().rstrip(';')
    if sql.upper()=='BEGIN IMMEDIATE':return 'SELECT pg_advisory_xact_lock(724811)',None
    ignore=sql.upper().startswith('INSERT OR IGNORE ')
    replace=sql.upper().startswith('INSERT OR REPLACE INTO settings'.upper())
    sql=re.sub(r'^INSERT OR (IGNORE|REPLACE) INTO','INSERT INTO',sql,flags=re.I)
    sql=re.sub(r'\browid\b','id',sql)
    sql=re.sub(r'length\((\w+\.)?content\)',lambda m:(m.group(1) or '')+'content_size',sql)
    sql=sql.replace('version=version+1','version=country_rules.version+1')
    # Quote-aware placeholder conversion; literal punctuation is not a parameter.
    pieces=re.split("('(?:''|[^'])*')",sql)
    sql=''.join(piece if i%2 else piece.replace('?','%s') for i,piece in enumerate(pieces))
    if ignore:sql+=' ON CONFLICT DO NOTHING'
    if replace:sql+=' ON CONFLICT(key) DO UPDATE SET value=excluded.value'
    match=re.match(r'INSERT INTO\s+(\w+)',sql,re.I);table=match.group(1).lower() if match else None
    returning=table in SERIAL and ' RETURNING ' not in sql.upper()
    if returning:sql+=' RETURNING id'
    return sql,table if returning else None

class Cursor:
    def __init__(self,cursor,serial=False):
        self.cursor=cursor;self.lastrowid=None
        if serial:
            row=cursor.fetchone();self.lastrowid=row['id'] if row else None
    def fetchone(self):
        data=self.cursor.fetchone();return Row(data) if data is not None else None
    def fetchall(self):return [Row(r) for r in self.cursor.fetchall()]
    def __iter__(self):return iter(self.fetchall())

class Store:
    def __init__(self,con):self.con=con;self.uploads=[]
    def execute(self,sql,params=()):
        params=list(params)
        # Match INSERT INTO table VALUES(...) or INSERT INTO table(cols) VALUES(...)
        match_positional=re.match(r'\s*INSERT INTO (documents|product_images|trade_documents) VALUES\s*\(',sql,re.I)
        match_named=re.match(r'\s*INSERT INTO (documents|product_images|trade_documents)\s*\(([^)]+)\)\s*VALUES\s*\(',sql,re.I)
        if match_positional:
            table=match_positional.group(1);fields=FILES[table]
            idx=fields.index('content');content=params[idx]
            if not isinstance(content,bytes):raise ValueError('Upload bytes required')
            path=table+'/'+secrets.token_hex(24)
            cloud_http.upload(path,content,params[fields.index('mime')]);self.uploads.append(path)
            params[idx]=path;params.append(len(content))
            sql='INSERT INTO '+table+'('+','.join(fields+['content_size'])+') VALUES('+','.join('?' for _ in params)+')'
        elif match_named:
            table=match_named.group(1);col_list=[c.strip() for c in match_named.group(2).split(',')]
            if 'content' in col_list:
                idx=col_list.index('content');content=params[idx]
                if not isinstance(content,bytes):raise ValueError('Upload bytes required')
                mime_idx=col_list.index('mime') if 'mime' in col_list else -1
                mime=params[mime_idx] if mime_idx>=0 else 'application/octet-stream'
                path=table+'/'+secrets.token_hex(24)
                cloud_http.upload(path,content,mime);self.uploads.append(path)
                params[idx]=path
                if 'content_size' not in col_list:
                    col_list.append('content_size');params.append(len(content))
                    # Add a placeholder for the new parameter
                    sql=re.sub(r'VALUES\s*\((.*)\)', lambda m: 'VALUES (' + m.group(1) + ',?)', sql, flags=re.I|re.DOTALL)
                else:
                    params[col_list.index('content_size')]=len(content)
                # Rewrite SQL with updated column list
                sql=re.sub(r'INSERT INTO '+table+r'\s*\([^)]+\)',
                    'INSERT INTO '+table+'('+','.join(col_list)+')',sql,flags=re.I)
        statement,serial=translate(sql)
        return Cursor(self.con.execute(statement,params or None),bool(serial))
    def executemany(self,sql,rows):
        for row in rows:self.execute(sql,row)
    def commit(self):self.con.commit();self.uploads.clear()
    def rollback(self):
        self.con.rollback()
        if self.uploads:
            try:cloud_http.remove(self.uploads)
            except cloud_http.CloudError:pass # Private orphan; reconcile via maintenance guide.
        self.uploads.clear()

@contextmanager
def db():
    import psycopg
    from psycopg.rows import dict_row
    cfg.validate()
    # Session pooler URI from Dashboard Connect; no browser receives this DSN.
    parsed = cloud_http.urllib.parse.urlparse(cfg.DSN)
    is_local = parsed.hostname in ('127.0.0.1', 'localhost', 'supabase-kong')
    ssl_mode = 'prefer' if is_local else 'require'
    with psycopg.connect(cfg.DSN,sslmode=ssl_mode,connect_timeout=10,prepare_threshold=None,row_factory=dict_row) as con:
        con.execute('SET search_path TO blueharbor, public')
        con.execute("SET statement_timeout TO '25s'")
        store=Store(con)
        try:yield store;store.commit()
        except Exception:store.rollback();raise
