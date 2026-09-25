"""Command-center regression tests with isolated data."""
import json
import unittest
from datetime import date,timedelta,datetime,timezone
import test_admin as fixtures
import server
import operations_monitor
import command_core as C

class CommandTests(unittest.TestCase):
    setUp=fixtures.AdminTests.setUp
    tearDown=fixtures.AdminTests.tearDown
    req=fixtures.AdminTests.req
    post=fixtures.AdminTests.post
    state=fixtures.AdminTests.state
    demo=fixtures.AdminTests.demo
    order=fixtures.AdminTests.order

    def propose(self,percent=50):
        ends=(date.today()+timedelta(days=1)).isoformat()
        result=self.post('discount-propose',{'lot_id':'BH-01','percent':percent,'ends_on':ends,'reason':'Staff review of upcoming stock rotation'})
        self.assertEqual(result[0],200,result[1]);return self.state()['discounts'][0]['id']

    def test_arrival_age_and_migration_preserve_unknowns(self):
        lot=next(l for l in self.state()['lots'] if l['id']=='BH-01')
        self.assertIsNone(lot['received_date']);self.assertIsNone(lot['storage_days'])
        received=(date.today()-timedelta(days=4)).isoformat()
        self.assertEqual(self.post('arrival',{'lot_id':'BH-01','received_date':received,'reason':'Warehouse receipt checked'})[0],200)
        server.init()
        lot=next(l for l in self.state()['lots'] if l['id']=='BH-01')
        self.assertEqual(lot['storage_days'],4);self.assertTrue(lot['sellable']);self.assertEqual(lot['available_kg'],42000)
        future=(date.today()+timedelta(days=1)).isoformat()
        self.assertEqual(self.post('arrival',{'lot_id':'BH-01','received_date':future,'reason':'Invalid future arrival'})[0],400)
        self.assertEqual(next(l for l in self.state()['lots'] if l['id']=='BH-01')['received_date'],received)

    def test_discount_approval_buyer_pricing_and_order_snapshot(self):
        original=self.req('catalog')[1]['products'][0]['cents_per_kg'];identifier=self.propose()
        self.assertEqual(self.req('catalog')[1]['products'][0]['cents_per_kg'],original)
        self.assertEqual(self.post('discount-decision',{'id':identifier,'status':'APPROVED','reason':'Released stock and transport timing reviewed'})[0],200)
        price=self.req('catalog')[1]['products'][0];self.assertEqual(price['cents_per_kg'],(original*50+50)//100)
        buyer=self.demo();oid=self.order(buyer)
        order=self.req('state',cookie=buyer)[1]['orders'][0];self.assertEqual(order['cents_per_kg'],price['cents_per_kg'])
        self.post('discount-decision',{'id':identifier,'status':'WITHDRAWN','reason':'Promotion ended'})
        self.assertEqual(self.req('catalog')[1]['products'][0]['cents_per_kg'],original)
        self.assertEqual(self.req('state',cookie=buyer)[1]['orders'][0]['total'],order['total'])
        self.assertEqual(oid,order['id'])

    def test_quality_hold_and_expiry_disable_promotions(self):
        identifier=self.propose();self.post('discount-decision',{'id':identifier,'status':'APPROVED','reason':'Checked'})
        self.post('quality',{'lot_id':'BH-01','quality':'HOLD','reason':'Quality evidence requires review'})
        p=self.req('catalog')[1]['products'][0];self.assertIsNone(p['promotion']);self.assertEqual(p['available_kg'],0)
        self.assertEqual(self.post('discount-propose',{'lot_id':'BH-01','percent':50,'ends_on':date.today().isoformat(),'reason':'Unsafe'})[0],409)
        with server.db() as c:
            c.execute("UPDATE lot_admin SET quality='RELEASED' WHERE lot_id='BH-01'")
            c.execute("UPDATE lots SET expiry=? WHERE id='BH-01'",((date.today()-timedelta(days=1)).isoformat(),))
        self.assertIsNone(self.req('catalog')[1]['products'][0]['promotion'])
        self.assertFalse(next(l for l in self.state()['lots'] if l['id']=='BH-01')['sellable'])

    def test_stale_promotion_permissions_and_validation(self):
        identifier=self.propose();p=self.state()['products'][0]
        self.post('product',{**p,'cents_per_kg':p['cents_per_kg']+100})
        self.assertEqual(self.post('discount-decision',{'id':identifier,'status':'APPROVED','reason':'Stale price'})[0],409)
        buyer=self.demo();self.assertEqual(self.req('admin/discount-decision',{'id':identifier,'status':'APPROVED','reason':'Forbidden'},buyer)[0],401)
        self.assertEqual(self.post('discount-propose',{'lot_id':'BH-01','percent':100,'ends_on':date.today().isoformat(),'reason':'Invalid percentage'})[0],400)
        self.assertEqual(self.post('discount-propose',{'lot_id':'BH-01','percent':50,'ends_on':'2099-01-01','reason':'After expiry'})[0],400)

    def test_worker_status_is_evidence_based(self):
        self.assertEqual(self.state()['monitor']['rules_status'],'OFFLINE')
        with server.db() as c:
            c.execute("INSERT INTO settings(key, value) VALUES('worker_heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",(json.dumps(server.now()),))
        self.assertEqual(self.state()['monitor']['rules_status'],'RUNNING')
        with server.db() as c:c.execute("INSERT INTO settings(key, value) VALUES('worker_heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",(json.dumps((datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()),))
        self.assertEqual(self.state()['monitor']['rules_status'],'OFFLINE')

    def test_stock_status_uses_saved_inventory_rules(self):
        with server.db() as c:
            operations_monitor.monitor(c)
        self.assertTrue(self.state()['monitor']['last_scan'])

if __name__=='__main__':unittest.main(verbosity=2)
