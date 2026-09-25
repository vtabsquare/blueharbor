import os
os.environ['SUPABASE_DB_URL']='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
os.environ['BLUEHARBOR_ROLE']='buyer'
os.environ['BLUEHARBOR_TEST_MODE']='1'
"""API integration tests use a temporary DB, never the user's application data."""
import base64
import concurrent.futures
import http.client
import json
import os
os.environ['SUPABASE_DB_URL']='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
import tempfile
import threading
import subprocess
import sys
import unittest
from pathlib import Path
import server
server.DEMO_EMAIL='demo@blueharbor.local'
server.DEMO_PASSWORD='DemoUser!2026'

class Tests(unittest.TestCase):
    def setUp(self):
        import subprocess
        from pathlib import Path
        backend_dir = Path(__file__).resolve().parent
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-c', "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = current_database();"], stdout=subprocess.DEVNULL)
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'], stdout=subprocess.DEVNULL)
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-f', str(backend_dir / '01_schema.sql')], stdout=subprocess.DEVNULL)
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-f', str(backend_dir / '02_seed_full.sql')], stdout=subprocess.DEVNULL)
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-c', "UPDATE staff SET auth_uid = (SELECT id FROM auth.users WHERE email=staff.email);"], stdout=subprocess.DEVNULL)

    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        server.DB=Path(cls.temp.name)/'test.sqlite3';server.init()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.port=cls.http.server_port
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
        import cloud_http
        try:
            users_resp = cloud_http.request('/auth/v1/admin/users', {}, 'GET', admin=True)
            for u in (users_resp.get('users') or []):
                if hasattr(cls, '_created_supabase_users') and u.get('email') in cls._created_supabase_users:
                    try: cloud_http.request('/auth/v1/admin/users/'+u['id'], {}, 'DELETE', admin=True)
                    except Exception: pass
        except Exception: pass
    def request(self,path,data=None,cookie=None,origin='http://localhost:3000'):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=15)
        headers={'Host':'localhost:3000','Origin':origin,'X-BlueHarbor':'1'}
        if cookie: headers['Cookie']=cookie
        if data is not None: headers['Content-Type']='application/json'
        c.request('GET' if data is None else 'POST','/api/'+path,None if data is None else json.dumps(data),headers)
        r=c.getresponse();raw=r.read();cookie=r.getheader('Set-Cookie');status=r.status
        result=json.loads(raw) if r.getheader('Content-Type')=='application/json' else raw
        c.close();return status,result,cookie
    def register(self,email):
        import cloud_http
        try: cloud_http.request('/auth/v1/admin/users', {'email': email, 'password': 'VeryGoodPassword123!', 'email_confirm': True, 'user_metadata': {'name': 'Test buyer'}}, 'POST', admin=True)
        except Exception: pass
        if not hasattr(self.__class__, '_created_supabase_users'): self.__class__._created_supabase_users = []
        self.__class__._created_supabase_users.append(email)
        status,_,cookie=self.request('login',{'email':email,'password':'VeryGoodPassword123!'})
        self.assertEqual(status,200);return cookie.split(';')[0]
    def approve(self,email,cookie):
        self.assertEqual(self.request('profile',{'name':'Test','company':'Test Imports','registration':'123','address':'Test port','phone':'123','country':'UAE'},cookie)[0],200)
        for kind in server.COUNTRIES['UAE']:
            self.assertEqual(self.request('documents',{'kind':kind,'name':'test.pdf','expiry':'2099-12-31','content':base64.b64encode(b'%PDF-1.4\nTest fixture only').decode()},cookie)[0],200)
        self.assertEqual(self.request('verification',{},cookie)[0],200)
        with server.db() as c: c.execute("UPDATE users SET verified='VERIFIED' WHERE email=?",(email,))
    def test_01_auth_isolation_validation(self):
        a=self.register('one@example.com');b=self.register('two@example.com')
        self.assertEqual(self.request('state')[0],401)
        self.assertEqual(self.request('state',cookie=a)[1]['user']['email'],'one@example.com')
        self.assertEqual(self.request('state',cookie=b)[1]['orders'],[])
        self.assertEqual(self.request('login',{'email':'one@example.com','password':'WrongPassword123'})[0],401)
        self.assertEqual(self.request('profile',{},a,origin='https://evil.example')[0],403)
        self.assertEqual(self.request('orders',{'product_id':1,'kg':1000,'request_key':'unverified-order1'},a)[0],403)
        self.assertEqual(self.request('verification',{},a)[0],400)
        self.assertEqual(self.request('documents',{'kind':'Trade licence','name':'x.pdf','expiry':'2099-01-01','content':base64.b64encode(b'javascript').decode()},a)[0],400)
        self.assertEqual(self.request('logout',{},a)[0],200)
        self.assertEqual(self.request('state',cookie=a)[0],401)
    def test_02_order_atomic_idempotency_cancellation(self):
        a=self.register('trade@example.com');b=self.register('other@example.com');self.approve('trade@example.com',a)
        payload={'product_id':1,'kg':1000,'request_key':'unique-order-key-123','destination':'Jebel Ali, UAE','service':'Standard'}
        status,result,_=self.request('orders',payload,a);self.assertEqual(status,200);oid=result['id']
        self.assertEqual(self.request('orders',payload,a)[1]['id'],oid)
        self.assertEqual(self.request('orders',{**payload,'kg':2000},a)[0],409)
        order=self.request('state',cookie=a)[1]['orders'][0]
        self.assertEqual(order['total'],770000)
        self.assertEqual(self.request('confirmation/'+oid,cookie=b)[0],404)
        doc=self.request('state',cookie=a)[1]['documents'][0]
        self.assertEqual(self.request('document/'+doc['id'],cookie=b)[0],404)
        self.assertEqual(self.request('confirmation/'+oid,cookie=a)[0],200)
        self.assertEqual(self.request('cancel',{'id':oid},b)[0],404)
        self.assertEqual(self.request('cancel',{'id':oid},a)[0],200)
        self.assertEqual(self.request('cancel',{'id':oid},a)[0],200)
        print('PRODUCT0:', self.request('catalog')[1]['products'][0]['name'], 'KG:', self.request('catalog')[1]['products'][0]['available_kg']); self.assertEqual(self.request('catalog')[1]['products'][0]['available_kg'],42000)
        self.assertEqual(self.request('orders',{**payload,'kg':-1,'request_key':'negative-order-key'},a)[0],400)
        self.assertEqual(self.request('orders',{**payload,'kg':1.5,'request_key':'fractional-order-key'},a)[0],400)
    def test_03_concurrent_stock(self):
        a=self.register('concurrent@example.com');self.approve('concurrent@example.com',a)
        def place(i): return self.request('orders',{'product_id':2,'kg':10000,'request_key':f'concurrent-request-{i}','destination':'Jebel Ali, UAE','service':'Economy'},a)[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(place,[1,2]))
        self.assertEqual(sorted(statuses),[200,409])
        self.assertEqual(self.request('catalog')[1]['products'][1]['available_kg'],8000)
    def test_04_persistence_and_no_fake_ai(self):
        a=self.register('persist@example.com')
        server.init()
        self.assertEqual(self.request('state',cookie=a)[1]['user']['email'],'persist@example.com')
        self.assertEqual(self.request('ai-review',{'consent':True},a)[0],403)
        self.assertEqual(self.request('profile',{'name':'A','company':'B','registration':'R','address':'X','phone':'Y','country':'Invalid'},a)[0],400)

    def test_05_demo_buyer_trades_without_onboarding(self):
        status,result,cookie=self.request('login',{'email':server.DEMO_EMAIL,'password':server.DEMO_PASSWORD})
        self.assertEqual(status,200)
        a=cookie.split(';')[0]
        self.assertTrue(result['user']['demo'])
        self.assertEqual(result['user']['verified'],'VERIFIED')
        state=self.request('state',cookie=a)[1]
        self.assertEqual(len(state['documents']),3)
        self.assertIn(b'DEMONSTRATION ONLY',self.request('document/'+state['documents'][0]['id'],cookie=a)[1])
        cat=self.request('catalog')[1]
        self.assertEqual(len(cat['tanks']),3)
        before=sum(t['available_kg'] for t in cat['tanks'] if t['product_id']==5)
        payload={'product_id':5,'kg':100,'request_key':'demo-order-real-reservation','destination':'Jebel Ali, UAE','service':'Standard'}
        status,result,_=self.request('orders',payload,a)
        self.assertEqual(status,200)
        after=sum(t['available_kg'] for t in self.request('catalog')[1]['tanks'] if t['product_id']==5)
        self.assertEqual(before-after,100)
        server.init()
        self.assertEqual(sum(t['available_kg'] for t in self.request('catalog')[1]['tanks'] if t['product_id']==5),after)
        self.assertEqual(self.request('cancel',{'id':result['id']},a)[0],200)
        self.assertEqual(sum(t['available_kg'] for t in self.request('catalog')[1]['tanks'] if t['product_id']==5),before)
        os.environ['BLUEHARBOR_DEMO']='0'
        try:
            self.assertEqual(self.request('state',cookie=a)[0],403)
            self.assertEqual(self.request('login',{'email':server.DEMO_EMAIL,'password':server.DEMO_PASSWORD})[0],403)
            self.assertFalse(self.request('catalog')[1]['demo_available'])
        finally:
            os.environ.pop('BLUEHARBOR_DEMO',None)
        self.assertEqual(self.request('profile',{'name':'Demo Edited','company':'Demo company','registration':'D','address':'D','phone':'D','country':'UAE'},a)[0],200)
        server.init()
        self.assertEqual(self.request('state',cookie=a)[1]['user']['verified'],'DRAFT')

    def test_06_catalogue_upgrade_preserves_reservations(self):
        cat=self.request('catalog')[1]
        self.assertEqual(len(cat['products']),12)
        self.assertTrue(all(p['origin']=='India' and p['export_port'] and p['region'] for p in cat['products']))
        self.assertEqual(len({p['id'] for p in cat['products']}),12)
        a=self.register('catalogue@example.com');self.approve('catalogue@example.com',a)
        payload={'product_id':12,'kg':100,'request_key':'catalogue-migration-order','destination':'Singapore','service':'Standard'}
        before=next(p['available_kg'] for p in cat['products'] if p['id']==12)
        status,result,_=self.request('orders',payload,a);self.assertEqual(status,200)
        with server.db() as c:
            c.execute("UPDATE products SET origin='Maldives' WHERE id=3")
        server.init();server.init()
        after=self.request('catalog')[1]
        self.assertEqual(len(after['products']),12)
        self.assertEqual(next(p['available_kg'] for p in after['products'] if p['id']==12),before-100)
        self.assertEqual(next(p['origin'] for p in after['products'] if p['id']==3),'India')
        self.assertEqual(self.request('state',cookie=a)[1]['orders'][0]['id'],result['id'])

    def test_07_tracking_is_persisted_and_operator_only(self):
        a=self.register('tracking@example.com');self.approve('tracking@example.com',a)
        payload={'product_id':7,'kg':500,'request_key':'tracking-stages-order-key','destination':'Rotterdam, Netherlands','service':'Standard'}
        status,result,_=self.request('orders',payload,a);self.assertEqual(status,200);oid=result['id']
        self.assertEqual(self.request('events',{'id':oid,'status':'DELIVERED'},a)[0],404)
        self.assertEqual(self.request('state',cookie=a)[1]['orders'][0]['status'],'CONFIRMED')
        env={**os.environ,'BLUEHARBOR_DB':str(server.DB)}
        def event(stage):
            return subprocess.run([sys.executable,str(server.ROOT/'backend'/'manage.py'),'event',oid,stage,'Test warehouse milestone'],env=env,capture_output=True,text=True)
        self.assertNotEqual(event('DELIVERED').returncode,0)
        for stage in ['PROCESSING','SHIPPED','DELIVERED']:
            result=event(stage);self.assertEqual(result.returncode,0,result.stderr)
            server.init()
            order=self.request('state',cookie=a)[1]['orders'][0]
            self.assertEqual(order['status'],stage)
            self.assertEqual(order['events'][-1]['title'],stage)
            self.assertTrue(order['events'][-1]['created'])
        self.assertEqual(len(order['events']),4)
        self.assertNotEqual(event('PROCESSING').returncode,0)
        self.assertEqual(self.request('cancel',{'id':oid},a)[0],409)

if __name__=='__main__': unittest.main(verbosity=2)
