"""Deterministic stock monitoring and email delivery; no AI model integration."""
import json
import threading
import time
from datetime import date, datetime, timedelta, timezone

import admin_core as A


def monitor(c):
    cfg = A.settings(c)
    today = date.today()
    active = set()

    def alert(key, kind, severity, title, evidence, recommendation):
        active.add(key)
        old = c.execute('SELECT * FROM alerts WHERE alert_key=?', (key,)).fetchone()
        if not old:
            c.execute('INSERT INTO alerts(alert_key,kind,severity,title,evidence,recommendation,created,updated) VALUES(?,?,?,?,?,?,?,?)', (key, kind, severity, title, evidence, recommendation, A.S.now(), A.S.now()))
            A.change(c)
        elif old['evidence'] != evidence or old['state'] == 'RESOLVED':
            c.execute("UPDATE alerts SET evidence=?,recommendation=?,state=CASE WHEN state='RESOLVED' THEN 'OPEN' ELSE state END,updated=? WHERE id=?", (evidence, recommendation, A.S.now(), old['id']))
            A.change(c)

    products = c.execute("SELECT p.id product_id,p.name,a.reorder_kg,COALESCE(SUM(CASE WHEN l.expiry>=? AND la.quality='RELEASED' THEN l.available_kg ELSE 0 END),0) available_kg FROM products p JOIN product_admin a ON a.product_id=p.id LEFT JOIN lots l ON l.product_id=p.id LEFT JOIN lot_admin la ON la.lot_id=l.id GROUP BY p.id,p.name,a.reorder_kg", (today.isoformat(),)).fetchall()
    for product in products:
        if product['available_kg'] <= product['reorder_kg']:
            alert('low:' + str(product['product_id']), 'LOW_STOCK', 'HIGH' if product['available_kg'] == 0 else 'MEDIUM', product['name'] + ' needs attention', f"{product['available_kg']} kg sellable; reorder threshold {product['reorder_kg']} kg.", 'Review open orders and replenishment. No purchase has been placed.')
    for row in c.execute('SELECT l.*,a.quality FROM lots l JOIN lot_admin a ON a.lot_id=l.id'):
        days = (date.fromisoformat(row['expiry']) - today).days
        if row['available_kg'] + row['reserved_kg'] and days <= cfg['expiry_days']:
            alert('expiry:' + row['id'], 'EXPIRY', 'HIGH' if days < 0 else 'MEDIUM', row['id'] + (' expired' if days < 0 else ' approaching expiry'), f"Expiry {row['expiry']}; {row['available_kg']} available / {row['reserved_kg']} reserved kg.", 'Review allocated orders and quality disposition. Expired stock is excluded from new reservations.')
        if row['reserved_kg'] and (row['quality'] != 'RELEASED' or days < 0):
            alert('hold:' + row['id'], 'ALLOCATED_HOLD', 'HIGH', 'Reserved stock needs review: ' + row['id'], f"{row['reserved_kg']} kg reserved; quality {row['quality']}; expiry {row['expiry']}.", 'Review affected orders before processing or dispatch.')
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    for row in c.execute("SELECT * FROM stock_movements WHERE kind='ADJUSTMENT' AND ABS(available_delta)>=1000 AND created>=?", (cutoff,)):
        alert('adjust:' + str(row['id']), 'LARGE_ADJUSTMENT', 'MEDIUM', 'Large adjustment: ' + row['lot_id'], f"Movement {row['id']}: {row['available_delta']} kg. Reason: {row['reason']}", 'Check receipt or count evidence with warehouse staff.')
    for old in c.execute("SELECT * FROM alerts WHERE state!='RESOLVED'").fetchall():
        if old['alert_key'] not in active:
            c.execute("UPDATE alerts SET state='RESOLVED',resolution='Condition no longer present in latest scan',updated=? WHERE id=?", (A.S.now(), old['id']))
            A.change(c)
    c.execute("INSERT OR REPLACE INTO settings VALUES('last_monitor',?)", (json.dumps(A.S.now()),))
    c.execute("INSERT OR REPLACE INTO settings VALUES('monitor_error','\"\"')")


def start_worker():
    stop = threading.Event()

    def scan():
        next_monitor = 0
        while not stop.is_set():
            try:
                with A.S.db() as c:
                    c.execute("INSERT OR REPLACE INTO settings VALUES('worker_heartbeat',?)", (json.dumps(A.S.now()),))
                    cfg = A.settings(c)
                    if time.time() >= next_monitor:
                        monitor(c)
                        next_monitor = time.time() + cfg['monitor_seconds']
                        A.change(c, 'catalog-refresh')
                    c.execute("INSERT OR REPLACE INTO settings VALUES('next_monitor',?)", (json.dumps(datetime.fromtimestamp(next_monitor, timezone.utc).isoformat()),))
            except Exception as exc:
                try:
                    with A.S.db() as c:
                        c.execute("INSERT OR REPLACE INTO settings VALUES('monitor_error',?)", (json.dumps(type(exc).__name__ + ': monitoring failed; check the local backend.'),))
                except Exception:
                    pass
            stop.wait(2)

    def email():
        from local_email import process_one as deliver_email
        while not stop.is_set():
            try:
                deliver_email()
            except Exception:
                pass
            stop.wait(2)

    for name, target in [('monitor', scan), ('email', email)]:
        threading.Thread(target=target, name='blueharbor-' + name, daemon=True).start()
    return stop
