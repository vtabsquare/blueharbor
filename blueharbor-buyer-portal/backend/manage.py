"""Local owner-only management CLI; not exposed to buyer HTTP clients."""
import argparse
from server import init, db, audit, notify, now, valid_verification

def main():
    p=argparse.ArgumentParser(description='Local POC operator. Run only as the database owner.')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('buyers')
    a=sub.add_parser('approve'); a.add_argument('email')
    a=sub.add_parser('event'); a.add_argument('order_id'); a.add_argument('status',choices=['PROCESSING','SHIPPED','DELIVERED']); a.add_argument('note')
    args=p.parse_args(); init()
    with db() as c:
        if args.command=='buyers':
            for u in c.execute('SELECT email,company,verified FROM users'): print(dict(u))
        elif args.command=='approve':
            u=c.execute('SELECT * FROM users WHERE email=?',(args.email.lower(),)).fetchone()
            if not u or u['verified']!='UNDER_REVIEW' or not valid_verification(c,u): p.error('Buyer must have submitted complete, valid documents for review.')
            c.execute("UPDATE users SET verified='VERIFIED' WHERE id=?",(u['id'],))
            audit(c,u['id'],'operator_approved','Local database owner reviewed buyer'); notify(c,u['id'],'Your buyer account has been approved.'); print('Approved. This is a local POC decision, not external identity assurance.')
        else:
            c.execute('BEGIN IMMEDIATE')
            o=c.execute('SELECT * FROM orders WHERE id=?',(args.order_id,)).fetchone()
            transitions={'CONFIRMED':'PROCESSING','PROCESSING':'SHIPPED','SHIPPED':'DELIVERED'}
            if not o or transitions.get(o['status'])!=args.status: p.error('Invalid order transition.')
            if not args.note.strip(): p.error('A tracking note is required.')
            c.execute('UPDATE orders SET status=? WHERE id=?',(args.status,o['id']))
            if args.status=='SHIPPED':
                for a in c.execute('SELECT * FROM allocations WHERE order_id=?',(o['id'],)).fetchall(): c.execute('UPDATE lots SET reserved_kg=reserved_kg-? WHERE id=?',(a['kg'],a['lot_id']))
            c.execute('INSERT INTO events(order_id,title,note,created) VALUES(?,?,?,?)',(o['id'],args.status,args.note,now()))
            audit(c,o['user_id'],'operator_tracking',o['id']); notify(c,o['user_id'],f'{o["id"]}: {args.status}'); print('Tracking updated.')

if __name__=='__main__': main()
