"""All fixtures synthetic; no history/model replay or API dependency here."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import v2 as v


class V2Contracts(unittest.TestCase):
    def terms(self,**kw):
        return {'status':'PROVEN','cash_per_old_share':'0','free_shares_per_old_share':'0',
                'paid_subscription_per_old_share':'0',**kw}
    def test_mixed_cash_stock(self):
        r=v.diagnose(self.terms(cash_per_old_share='4',free_shares_per_old_share='.2',cash_payment_date='2025-08-29',new_share_saleable_date='2025-09-01'),'2025-08-01','PROVEN')
        self.assertIn('CASH_RECEIVABLE_NOT_PAID',r['states']);self.assertIn('STOCK_ENTITLEMENT_NOT_SALEABLE',r['states'])
        self.assertFalse(r['cash_reinvestment_allowed']);self.assertFalse(r['undelivered_share_sale_allowed'])
    def test_delayed_stock_delivery(self):
        t=self.terms(free_shares_per_old_share='.3',new_share_saleable_date='2025-09-01')
        self.assertFalse(v.diagnose(t,'2025-08-31','PROVEN')['undelivered_share_sale_allowed'])
        self.assertTrue(v.diagnose(t,'2025-09-01','PROVEN')['undelivered_share_sale_allowed'])
    def test_paid_subscription_requires_cash_deadline(self):
        r=v.diagnose(self.terms(paid_subscription_per_old_share='.1'),'2025-01-01','PROVEN')
        self.assertIn('SUBSCRIPTION_TERMS_INCOMPLETE',r['block_reasons']);self.assertFalse(r['cash_reinvestment_allowed'])
    def test_cash_reduction_class_and_receivable(self):
        self.assertEqual(v.classify('退還股款','TWTAUU'),'CAPITAL_REDUCTION_CASH_RETURN')
        self.assertIn('PAYMENT_DATE_UNKNOWN',v.diagnose(self.terms(cash_per_old_share='5'),'2025-01-01','PROVEN')['block_reasons'])
    def test_no_cash_reduction_does_not_guess_numeric_terms(self):
        self.assertEqual(v.classify('彌補虧損','TWTAUU'),'CAPITAL_REDUCTION_LOSS_ABSORPTION')
        self.assertIn('UNKNOWN_CASH_PER_OLD_SHARE',v.diagnose({},'2025-01-01','PROVEN')['block_reasons'])
    def test_conversion_identity_and_delivery(self):
        t=self.terms(conversion=True,old_security_id='OLD',new_security_id='NEW')
        self.assertIn('CONVERSION_SALEABLE_DATE_UNKNOWN',v.diagnose(t,'2025-08-25','PROVEN')['block_reasons'])
        t['new_share_saleable_date']='2025-08-25'
        self.assertIn('OLD_SECURITY_CONVERTED',v.diagnose(t,'2025-08-25','PROVEN')['states'])
    def test_suspension_spanning_exit_blocks_price(self):
        r=v.diagnose(self.terms(),'2025-08-20','PROVEN',suspended=True)
        self.assertIn('SUSPENSION_NO_TRADABLE_PRICE',r['states']);self.assertFalse(r['cash_reinvestment_allowed'])
    def test_unknown_delivery_and_payment_never_immediate(self):
        r=v.diagnose(self.terms(cash_per_old_share='4',free_shares_per_old_share='.2'),'2025-01-01','PROVEN')
        self.assertIn('PAYMENT_DATE_UNKNOWN',r['block_reasons']);self.assertIn('DELIVERY_DATE_UNKNOWN',r['block_reasons'])
    def test_current_master_rejected(self):
        with self.assertRaisesRegex(ValueError,'CURRENT_MASTER'):v.identity_proof('CURRENT_OLD','CURRENT_NEW','CURRENT_SECURITY_MASTER')
        with self.assertRaises(ValueError):v.identity_proof(None,None,'HISTORICAL_EFFECTIVE_DATED_DOCUMENT')
    def detail(self,ticker='2330'):
        return json.dumps({'stat':'ok','fields':v.v1n.DETAIL_FIELDS,'data':[[ticker,'fixture','4 元／股','','200 股','0 股','0 股','0 元／股','0 股','0 股','0 股','0 股']]}).encode()
    def test_detail_mismatch(self):
        with self.assertRaisesRegex(ValueError,'DETAIL_EVENT_MISMATCH'):v.parse_detail(self.detail('2454'),{'ticker':'2330'})
    def test_conflicting_terms_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'CONFLICTING_OFFICIAL_TERMS'):v.merge_terms({'cash_per_old_share':'4'},{'cash_per_old_share':'5'})
        self.assertEqual(v.merge_terms({'cash_per_old_share':'4'},{'cash_per_old_share':None})['cash_per_old_share'],'4')
    def test_lower_limit_buy_sell_semantics(self):
        a=v.fill_evidence('BUY',True,True,'10000');b=v.fill_evidence('SELL',True,True,'10000')
        self.assertNotEqual(a['interpretation'],b['interpretation']);self.assertEqual(a['fill_status'],'UNKNOWN');self.assertEqual(b['fill_status'],'UNKNOWN')
    def test_daily_volume_not_allocation(self):
        for volume in ('0','9999999999',None):self.assertEqual(v.fill_evidence('BUY',True,True,volume)['fill_status'],'UNKNOWN')
    def test_parent_history_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'history').write_bytes(b'FAILED\nREJECTED\n')
            inventory={'history':v.sha(root/'history')};v.assert_hashes(root,inventory)
            (root/'history').write_bytes(b'SUCCESS\n')
            with self.assertRaisesRegex(ValueError,'PARENT_BYTE_CHANGED'):v.assert_hashes(root,inventory)
    def test_zero_trial_and_authority(self):
        r=v.diagnose(self.terms(),'2025-01-01','PROVEN')
        self.assertFalse(r['adjusted_pnl_computed']);self.assertEqual(r['authority']['capital_authority_twd'],0)
        self.assertFalse(r['authority']['broker_order_execution']);self.assertFalse(r['authority']['production_promotion'])
    def test_entry_action_is_not_prior_share_entitlement(self):
        event={'ticker':'2330','effective_date':'2025-01-02'};w={'tickers':['2330'],'entry_date':'2025-01-02','exit_date':'2025-01-10'}
        self.assertEqual(v.intersects(event,w),'ENTRY')
        event['effective_date']='2025-01-10';self.assertEqual(v.intersects(event,w),'EXIT')
        event['effective_date']='2025-01-11';self.assertIsNone(v.intersects(event,w))
    def test_duplicate_evidence_assertion_rejected_prefix_retained(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            with v.TrialLedger(p,{'synthetic':True}) as l:l.append({'record_id':'assertion','status':'UNKNOWN'})
            prefix=p.read_bytes()
            with v.TrialLedger(p,{'synthetic':True}) as l:
                with self.assertRaises(ValueError):l.append({'record_id':'assertion','status':'PROVEN'})
            self.assertEqual(prefix,p.read_bytes())


if __name__=='__main__':unittest.main()
