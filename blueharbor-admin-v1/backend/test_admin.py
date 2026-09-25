"""End-to-end API checks against isolated temporary data, no live user records."""
import base64
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ['BLUEHARBOR_ADMIN_PASSWORD']='LocalTestAdmin!2026'
os.environ['BLUEHARBOR_TEST_MODE']='1'
import server
import operations_monitor

import time
class AdminTests(unittest.TestCase):
    _test_counter = 0
    def setUp(self):
        AdminTests._test_counter += 1
        self._run_id = f'{int(time.time())}.{AdminTests._test_counter}'
        self._created_supabase_users = []
        import subprocess
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'], stdout=subprocess.DEVNULL)
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-f', '01_schema.sql'], stdout=subprocess.DEVNULL)
        subprocess.run(['psql', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres', '-f', '02_seed_full.sql'], stdout=subprocess.DEVNULL)
        self.temp=tempfile.TemporaryDirectory();server.DB=Path(self.temp.name)/'test.sqlite3';server.init()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.port=self.http.server_port
        import realtime_bus
        self.stop_worker=threading.Event()
        realtime_bus.start(self.stop_worker)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
        status,result,cookie=self.req('admin/login',{'email':'admin@blueharbor.local','password':'LocalTestAdmin!2026'})
        self.assertEqual(status,200);self.admin=cookie.split(';')[0]
    def tearDown(self):
        self.stop_worker.set()
        self.http.shutdown();self.http.server_close();self.temp.cleanup()
        import cloud_http, json
        for email in self._created_supabase_users:
            try:
                import urllib.request
                import cloud_config as cfg
                # Delete Supabase Auth test user to allow re-registration in future runs
                users_resp = cloud_http.request('/auth/v1/admin/users?email='+email, {}, 'GET', admin=True)
                for u in (users_resp.get('users') or []):
                    if u.get('email') == email:
                        cloud_http.request('/auth/v1/admin/users/'+u['id'], {}, 'DELETE', admin=True)
            except Exception:
                pass
    def req(self,path,data=None,cookie='',origin='http://localhost:3000'):
        con=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        headers={'Host':'localhost:3000','Origin':origin,'X-BlueHarbor':'1','Cookie':cookie}
        if data is not None:headers['Content-Type']='application/json'
        con.request('GET' if data is None else 'POST','/api/'+path,json.dumps(data) if data is not None else None,headers)
        response=con.getresponse();raw=response.read();value=json.loads(raw) if response.getheader('Content-Type')=='application/json' else raw
        result=(response.status,value,response.getheader('Set-Cookie'));con.close();return result
    def post(self,path,data):return self.req('admin/'+path,data,self.admin)
    def state(self):return self.req('admin/state',cookie=self.admin)[1]
    def buyer(self,email=None):
        if email is None:email=f'buyer.{self._run_id}@example.com'
        self._created_supabase_users.append(email)
        status,_,_=self.req('register',{'email':email,'password':'TestBuyerPassword!2026','name':'Test Buyer','consent':True});self.assertEqual(status,200)
        status,_,cookie=self.req('login',{'email':email,'password':'TestBuyerPassword!2026'})
        self.assertEqual(status,200)
        cookie=cookie.split(';')[0];uid=self.req('state',cookie=cookie)[1]['user']['id'];return uid,cookie
    def submit(self,uid,cookie):
        self.req('profile',{'name':'Test Buyer','company':'Test Imports','registration':'REG-123','address':'Test address','phone':'123','country':'UAE'},cookie)
        for kind in server.COUNTRIES['UAE']:
            status,_,_=self.req('documents',{'kind':kind,'name':'test.pdf','expiry':'2099-01-01','content':base64.b64encode(b'%PDF-1.4\nTest fixture only').decode()},cookie);self.assertEqual(status,200)
        self.assertEqual(self.req('verification',{},cookie)[0],200)
    def approve(self,uid):
        detail=self.req('admin/buyer/'+str(uid),cookie=self.admin)[1]
        for doc in detail['documents']:self.assertEqual(self.post('document-review',{'id':doc['id'],'status':'APPROVED','reason':'Test officer checked fixture'})[0],200)
        detail=self.req('admin/buyer/'+str(uid),cookie=self.admin)[1]
        self.assertEqual(self.post('verification',{'user_id':uid,'revision':detail['case']['revision'],'status':'VERIFIED','reason':'Officer approval for local test'})[0],200)
    def demo(self):
        status,_,cookie=self.req('login',{'email':'demo@blueharbor.local','password':'DemoPassword!2026'});self.assertEqual(status,200);return cookie.split(';')[0]
    def order(self,cookie,pid=1,kg=1000):
        result=self.req('orders',{'product_id':pid,'kg':kg,'request_key':'new-order-request-key-'+str(pid),'destination':'Jebel Ali, UAE','service':'Standard'},cookie)
        self.assertEqual(result[0],200,result[1]);return result[1]['id']
    def test_staff_roles_cookie_isolation_and_session_revocation(self):
        uid,buyer=self.buyer()
        self.assertEqual(self.req('admin/state',cookie=buyer)[0],401)
        self.assertEqual(self.req('state',cookie=self.admin)[0],401)
        for role in ['VERIFIER','OPERATIONS']:
            email=role.lower()+'@example.com'
            self.assertEqual(self.post('staff',{'email':email,'name':role,'password':'StaffPassword!2026','role':role,'active':1})[0],200)
            status,_,cookie=self.req('admin/login',{'email':email,'password':'StaffPassword!2026'});self.assertEqual(status,200);cookie=cookie.split(';')[0]
            snapshot=self.req('admin/state',cookie=cookie)[1]
            if role=='OPERATIONS':
                self.assertEqual(snapshot['buyers'],[])
                self.assertEqual(self.req('admin/buyer/'+str(uid),cookie=cookie)[0],403)
            else:
                self.assertEqual(snapshot['orders'],[])
                self.assertEqual(self.req('admin/adjust-stock',{'lot_id':'BH-01','delta':-1,'expected_available':42000,'reason':'Not authorized'},cookie)[0],403)
            self.assertEqual(self.req('admin/settings',{},cookie)[0],403)
        staff=self.state()['team'][1]
        self.assertEqual(self.post('staff',{**staff,'active':0})[0],200)
        self.assertEqual(self.post('staff',{'id':1,'name':'Local','email':'admin@blueharbor.local','active':0,'role':'ADMIN'})[0],400)
        self.assertEqual(self.req('admin/settings',{},self.admin,origin='https://evil.example')[0],403)
    def test_verification_review_revision_and_buyer_sync(self):
        uid,buyer=self.buyer();self.assertTrue(any(b['id']==uid for b in self.state()['buyers']))
        self.submit(uid,buyer);detail=self.req('admin/buyer/'+str(uid),cookie=self.admin)[1];rev=detail['case']['revision']
        self.assertEqual(self.post('verification',{'user_id':uid,'revision':rev,'status':'VERIFIED','reason':'Too early'})[0],409)
        self.approve(uid)
        self.assertEqual(self.req('state',cookie=buyer)[1]['user']['verified'],'VERIFIED')
        self.assertEqual(self.post('verification',{'user_id':uid,'revision':rev,'status':'REJECTED','reason':'Stale'})[0],409)
        oid=self.order(buyer)
        detail=self.req('admin/buyer/'+str(uid),cookie=self.admin)[1]
        self.assertEqual(self.post('verification',{'user_id':uid,'revision':detail['case']['revision'],'status':'SUSPENDED','reason':'Officer review required'})[0],200)
        self.assertEqual(self.req('orders',{'product_id':1,'kg':1000,'request_key':'another-unique-order','destination':'Jebel Ali, UAE','service':'Standard'},buyer)[0],403)
        self.assertTrue(self.req('state',cookie=buyer)[1]['notifications'])
        self.assertIn(oid,[o['id'] for o in self.state()['orders']])
    def test_product_publication_pricing_and_stock_hold(self):
        p=self.state()['products'][0]
        self.assertEqual(self.post('product',{**p,'published':0})[0],200)
        self.assertNotIn(p['id'],[x['id'] for x in self.req('catalog')[1]['products']])
        buyer=self.demo()
        self.assertEqual(self.req('orders',{'product_id':1,'kg':1000,'request_key':'hidden-product-key','destination':'Jebel Ali, UAE','service':'Standard'},buyer)[0],400)
        self.post('product',{**p,'published':1,'cents_per_kg':600})
        oid=self.order(buyer)
        self.assertEqual(self.req('state',cookie=buyer)[1]['orders'][0]['total'],850000)
        self.post('product',{**p,'published':1,'cents_per_kg':700})
        self.assertEqual(self.req('state',cookie=buyer)[1]['orders'][0]['total'],850000)
        self.assertEqual(self.post('quality',{'lot_id':'BH-01','quality':'HOLD','reason':'Quality review'})[0],200)
        self.assertEqual(self.req('catalog')[1]['products'][0]['available_kg'],0)
        self.assertEqual(self.post('order-status',{'id':oid,'status':'PROCESSING','reason':'Attempt blocked dispatch'})[0],409)
        self.assertEqual(self.post('adjust-stock',{'lot_id':'BH-01','expected_available':41000,'delta':-42000,'reason':'Too much'})[0],409)
        self.assertEqual(self.post('adjust-stock',{'lot_id':'BH-01','expected_available':42000,'delta':1,'reason':'Stale adjustment'})[0],409)
    def test_inventory_receipt_transfer_capacity_and_monitor(self):
        self.assertEqual(self.post('warehouse',{'name':'Kochi','location':'Kochi, India','kind':'Cold store'})[0],200)
        lot={'id':'NEW-LOT','product_id':7,'quantity':500,'warehouse_id':2,'production_date':'2026-01-01','expiry':'2099-01-01','reason':'Receipt reference'}
        self.assertEqual(self.post('lot',lot)[0],200)
        self.assertEqual(self.post('transfer',{'lot_id':'NEW-LOT','warehouse_id':1,'reason':'Relocation'})[0],200)
        self.assertEqual(self.post('tank',{'tank_id':'Tank A-01','lot_id':'LIVE-A1','zone':'Marine','capacity_kg':100,'status':'ACTIVE','reason':'Too small'})[0],400)
        self.assertEqual(self.post('reading',{'tank_id':'Tank A-01','temperature':25.5,'oxygen':6.2,'reason':'Manual meter check'})[0],200)
        self.assertEqual(self.post('adjust-stock',{'lot_id':'BH-01','expected_available':42000,'delta':-41500,'reason':'Audited stock count'})[0],200)
        with server.db() as c:operations_monitor.monitor(c)
        alerts=self.state()['alerts'];self.assertTrue(any(a['kind']=='LOW_STOCK' for a in alerts));self.assertTrue(any(a['kind']=='LARGE_ADJUSTMENT' for a in alerts))
        server.init();self.assertEqual(next(l['available_kg'] for l in self.state()['lots'] if l['id']=='BH-01'),500)
    def test_order_tracking_and_private_pdfs(self):
        buyer=self.demo();oid=self.order(buyer)
        self.post('order-hold',{'id':oid,'on_hold':1,'reason':'Internal-only hold note'})
        self.assertEqual(self.post('order-status',{'id':oid,'status':'PROCESSING','reason':'Not yet'})[0],409)
        self.post('order-hold',{'id':oid,'on_hold':0,'reason':'Checks complete'})
        self.assertEqual(self.post('shipment',{'id':oid,'origin_port':'Chennai','vessel':'Test vessel','eta':'2099-01-01','reason':'Shipment assigned'})[0],200)
        for stage in ('PROCESSING','SHIPPED','DELIVERED'):self.assertEqual(self.post('order-status',{'id':oid,'status':stage,'reason':'Recorded '+stage})[0],200)
        state=self.req('state',cookie=buyer)[1];self.assertEqual(state['orders'][0]['status'],'DELIVERED');self.assertEqual(state['orders'][0]['shipment']['vessel'],'Test vessel')
        self.assertNotIn('Internal-only',json.dumps(state))
        self.assertEqual(self.post('generate-document',{'order_id':oid,'kind':'Informational invoice'})[0],200)
        doc=self.state()['documents'][0]
        self.assertTrue(self.req('admin/trade-document/'+doc['id'],cookie=self.admin)[1].startswith(b'%PDF-1.4'))
        self.assertEqual(self.req('trade-document/'+doc['id'],cookie=buyer)[0],404)
        self.assertEqual(self.post('publish-document',{'id':doc['id'],'published':1})[0],200)
        self.assertEqual(self.req('trade-document/'+doc['id'],cookie=buyer)[0],200)
        _,other=self.buyer('other@example.com');self.assertEqual(self.req('trade-document/'+doc['id'],cookie=other)[0],404)
        self.assertEqual(len(self.req('state',cookie=buyer)[1]['orders'][0]['documents']),1)
    def test_rules_change_live_pricing_csv_and_no_sensitive_report(self):
        uid,buyer=self.buyer();self.submit(uid,buyer);self.approve(uid)
        self.assertEqual(self.post('country',{'country':'UAE','requirements':server.COUNTRIES['UAE']+['New required document']})[0],200)
        self.assertEqual(self.req('state',cookie=buyer)[1]['user']['verified'],'ADDITIONAL_INFORMATION_REQUIRED')
        self.assertIn('New required document',self.req('catalog')[1]['countries']['UAE'])
        self.assertEqual(self.post('shipping',{'name':'Priority','cents':12300})[0],200)
        self.assertEqual(self.req('catalog')[1]['services']['Priority'],12300)
        cfg=self.state()['settings'];self.post('settings',{**cfg,'handling_cents':65000})
        self.assertEqual(self.req('catalog')[1]['handling_cents'],65000)
        report=self.req('admin/report',cookie=self.admin);self.assertEqual(report[0],200);self.assertNotIn(b'password',report[1].lower())
    def test_new_product_image_and_buyer_exposure(self):
        p={**self.state()['products'][0],'id':None,'name':'New shrimp','image':'','published':1}
        self.assertEqual(self.post('product',p)[0],400)
        p.update(photo_content=base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode(),photo_name='product.png')
        self.assertEqual(self.post('product',p)[0],200)
        product=self.req('catalog')[1]['products'][-1];self.assertTrue(product['image'].startswith('/api/product-image/'))
        self.assertEqual(self.req(product['image'].removeprefix('/api/'))[0],200)
        self.assertNotIn('photo_content',json.dumps(self.state()['audit']))

    def test_sse_live_invalidation_does_not_expose_private_data(self):
        buyer=self.demo()
        con=http.client.HTTPConnection('127.0.0.1',self.port,timeout=8)
        con.request('GET','/api/stream',headers={'Host':'localhost:3000','Cookie':buyer})
        response=con.getresponse();self.assertEqual(response.status,200)
        lines=[]
        for _ in range(4):lines.append(response.fp.readline().decode())
        self.assertIn('event: ready\n',lines)
        p=self.state()['products'][0];self.post('product',{**p,'cents_per_kg':650})
        received=[]
        for _ in range(6):
            line=response.fp.readline().decode();received.append(line)
            if line=='data: changed\n':break
        self.assertIn('event: refresh\n',received)
        self.assertNotIn('buyer',str(received));self.assertNotIn('company',str(received))
        con.close();response.close();time.sleep(2.2)

    def test_optional_email_and_backup(self):
        uid,_=self.buyer();self.post('notify',{'user_id':uid,'message':'Private in-app notice'})
        self.assertEqual(self.state()['emails'][0]['status'],'NOT_CONNECTED')
        import local_email,maintenance,sqlite3
        with patch.dict(os.environ,{'BLUEHARBOR_SMTP_HOST':'smtp.example.invalid','BLUEHARBOR_SMTP_FROM':'sender@example.com'}):
            cfg=self.state()['settings'];self.post('settings',{**cfg,'email_enabled':True})
            self.post('notify',{'user_id':uid,'message':'Opt-in SMTP fixture'})
            with patch.object(local_email.smtplib,'SMTP_SSL') as smtp:
                local_email.process_one();self.assertTrue(smtp.return_value.send_message.called)
            self.assertEqual(self.state()['emails'][0]['status'],'SENT')
        path=maintenance.backup()
        self.assertTrue(path.is_file() and path.stat().st_size > 100)

if __name__=='__main__':unittest.main(verbosity=2)
