"""Fail-closed regression coverage for the single HENGCE research publisher."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
import importlib.util

source=Path(__file__).resolve().parents[2]/'scripts/hengce_unified_scan_publisher.py'
spec=importlib.util.spec_from_file_location('publisher',source)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TODAY=date(2026,11,14)


def fixture():
    td=tempfile.TemporaryDirectory()
    root=Path(td.name)
    x={'schema':mod.SCHEMA,'status':mod.EXPECTED_STATUS,'system':'HENGCE',
       'model_classifier_sha256':mod.MODEL_CLS,'model_regressor_sha256':mod.MODEL_REG,
       'model_id':'v22d_daily_nowcast_liquidity_top5_v1','decision_date':'2026-11-13',
       'source_price_eod':'2026-11-13','source_tdcc_model_asof':'2026-10-30',
       'source_tdcc_research_overlay':'2026-11-06','model_first_publication_pit_verified':False,
       'formal_strategy_active':False,'buy_signal':False,'sell_signal':False,
       'broker_order_execution':False,'original_eod_receipt':'eod/20261113/status.json',
       'source_canonical_mother_sha256':'sha-ok','friday_shadow_only':True,
       'qualified_count':1,'original_781_qualified':0,
       'all_qualified':[{'rank':1,'ticker':'6446','name':'藥華藥',
             'close':1380.0,'score':0.6,'ret20':0.15,'ret5':0.08,
             'turnover20_median':3990000000,'retail_holder_date':'2026-11-06',
             'retail_holder_week_delta_pct':-2.73,'other_shares_pct':89.38}],
       'exited':[{'ticker':'1802','name':'台玻','score':0.4866,'reason':'SCORE_BELOW_0_50'}]}
    x['top5']=copy.deepcopy(x['all_qualified'])
    e={'status':'COMPLETE','target_date':'2026-11-13','mother_status':'COMPLETE',
       'three_leg_complete':True,'formal_complete_day':True,'downstream_ready':True,
       'mother_sha256':'sha-ok'}
    c={'status':'NO_ACTIVE_SELECTION_STRATEGY','active_strategy_count':0,
       'broker_order_execution':False}
    def write(path,obj):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(obj),encoding='utf-8')
    write('eod/20261113/status.json',e)
    write(mod.INPUT,x)
    write('hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json',c)
    return td,root,x,e


class Checks(unittest.TestCase):
    def test_valid_rank_and_exit(self):
        tmp,root,_,_=fixture()
        with tmp:
            out=mod.build(root,TODAY)
            self.assertEqual(out['status'],'RESEARCH_SCAN_READY')
            self.assertEqual(out['qualified_count'],1)
            self.assertEqual(out['exited'][0]['ticker'],'1802')
            self.assertEqual(out['broker_execution'],False)
            self.assertIn('台玻',mod.markdown(out))

    def test_stale_model_receipt_blocks(self):
        tmp,root,_,_=fixture()
        with tmp:
            p=root/'eod/20261116/status.json';p.parent.mkdir(parents=True)
            z=json.loads((root/'eod/20261113/status.json').read_text());z['target_date']='2026-11-16'
            p.write_text(json.dumps(z))
            out=mod.build(root,date(2026,11,16))
            self.assertEqual(out['status'],'RESEARCH_SCAN_BLOCKED')
            self.assertEqual(out['ranked'],[])

    def test_hash_tamper_blocks(self):
        tmp,root,x,_=fixture()
        with tmp:
            x['model_classifier_sha256']='unverified'
            (root/mod.INPUT).write_text(json.dumps(x))
            self.assertEqual(mod.build(root,TODAY)['reason'],'MODEL_CHECKPOINT_HASH_MISMATCH')

    def test_duplicate_stocks_block(self):
        tmp,root,x,_=fixture()
        with tmp:
            q=copy.deepcopy(x['all_qualified'][0]);q['rank']=2
            x['all_qualified'].append(q);x['qualified_count']=2;x['top5']=x['all_qualified']
            (root/mod.INPUT).write_text(json.dumps(x))
            self.assertEqual(mod.build(root,TODAY)['reason'],'DUPLICATE_OR_INVALID_TICKER')

    def test_tdcc_future_blocks(self):
        tmp,root,x,_=fixture()
        with tmp:
            x['source_tdcc_model_asof']='2026-11-12'
            (root/mod.INPUT).write_text(json.dumps(x))
            self.assertEqual(mod.build(root,TODAY)['reason'],'TDCC_LOOKAHEAD')

    def test_wrong_eod_hash_blocks(self):
        tmp,root,x,_=fixture()
        with tmp:
            x['source_canonical_mother_sha256']='wrong'
            (root/mod.INPUT).write_text(json.dumps(x))
            self.assertEqual(mod.build(root,TODAY)['reason'],'CANONICAL_MOTHER_HASH_MISMATCH')


if __name__=='__main__':unittest.main()