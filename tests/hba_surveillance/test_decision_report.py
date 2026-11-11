import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from hengce_hba_decision_report import build, markdown, original_eod_closes


class DecisionResearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.root=Path(self.d.name)
        self.day='2026-11-09'
        self.target='2026-11-10'
        p=self.root/'eod'/'20261109'
        p.mkdir(parents=True)
        (p/'status.json').write_text(json.dumps({
            'formal_complete_day':True,'downstream_ready':True,
            'price_date':self.day,'institutional_date':self.day,
            'margin_date':self.day,'price_rows':3}))
        with (p/'price_1.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['Date','Ticker','Name','Close'])
            w.writeheader()
            for t,name,close in [('3703','欣陸',22.45),('6443','元晶',27),('1416','廣豐',17.95)]:
                w.writerow({'Date':self.day,'Ticker':t,'Name':name,'Close':close})
        lock=self.root/'hengce'
        lock.mkdir()
        (lock/'HENGCE_SCAN_ONCE_CONTRACT_LATEST.json').write_text(json.dumps({
            'status':'NO_ACTIVE_SELECTION_STRATEGY','active_strategy_count':0,
            'broker_order_execution':False}))
        self.original={
            'target_tw_date':self.target,'latest_verified_eod':self.day,
            'data_gate':'EOD_VALID_MACRO_UNKNOWN','total_candidates_before_limit':3,
            'all_candidates':[
                {'ticker':'3703','stage':'行情確認（待人工評估）',
                 'day_return_pct':9.78,'five_day_return_pct':6.9,'margin_change5_pct':12.02},
                {'ticker':'6443','stage':'行情確認（待人工評估）',
                 'day_return_pct':4.05,'five_day_return_pct':14.16,'margin_change5_pct':-5.46},
                {'ticker':'1416','stage':'行情確認（待人工評估）',
                 'day_return_pct':9.79,'five_day_return_pct':32.47,'margin_change5_pct':25.15},
            ]}
        self.integrated={
            'target_tw_date':self.target,'observed_eod_date':self.day,
            'readiness':'RESEARCH_READY',
            'authority':{'new_selection':False,'trade':False},
            'market_environment':{'overseas':{'status':'資料不足'},
                                  's5':{'status':'NOT_PROVIDED'},
                                  'escape':{'status':'NOT_PROVIDED'}},
            'two_group_research':{
                'status':'VERIFIED_TWO_GROUP_RESEARCH',
                'historical_13week_continuity_verified':False,
                'multiweek_a_to_b_cycle_validated':False,
                'previous_tdcc_date':'20261030','last_tdcc_date':'20261106',
                'market_registry_total':3,'comparable_stock_count':3,
                'first_observed_taipei':'2026-11-07T04:58:23+08:00',
                'categories':{'其他持有人比重增加':2,'變化不明顯':1},
                'price_pair':{'status':'VERIFIED_REFERENCE_WEEK_PRICES',
                              'first_eod_date':'20261030','last_eod_date':'20261106'}
            },
            'two_group_market_registry':[
                {'ticker':'3703','small_shares_delta':-457520,'other_shares_delta':457520,
                 'small_holders_delta':-143,'small_share_delta_pp':-0.055577,
                 'same_week_price_return_pct':-1.4458,
                 'same_week_price_ownership_pattern':'DOWN_OTHER_SHARE_GAIN'},
                {'ticker':'6443','small_shares_delta':-2390101,'other_shares_delta':2390101,
                 'small_holders_delta':-792,'small_share_delta_pp':-0.466091,
                 'same_week_price_return_pct':10.1911,
                 'same_week_price_ownership_pattern':'UP_OTHER_SHARE_GAIN'},
                {'ticker':'1416','small_shares_delta':9673,'other_shares_delta':-9673,
                 'small_holders_delta':87,'small_share_delta_pp':0.005219,
                 'same_week_price_return_pct':26.2548,
                 'same_week_price_ownership_pattern':'FLAT_OR_UNCLASSIFIED'}
            ]
        }
    def tearDown(self):
        self.d.cleanup()
    def result(self):
        return build(self.root,self.original,self.integrated,'a'*64,'b'*64)
    def test_all_existing_research_names_preserved_without_live_buy_signals(self):
        x=self.result()
        self.assertEqual(x['status'],'RESEARCH_ADVISORY_READY')
        self.assertEqual(len(x['full_market_observations']),3)
        self.assertEqual(len(x['human_review_examples']),3)
        self.assertEqual(x['authority']['active_selection_strategy_count'],0)
        for field in ('formal_selection','ranking','signal','trading','broker_execution'):
            self.assertFalse(x['authority'][field])
        self.assertTrue(x['not_live_quotes'])
        self.assertFalse(x['historical_alpha_validated'])
        self.assertFalse(x['historical_A_B_full_cycle_today_verified'])
        self.assertNotIn('buy_signal',str(x))
    def test_different_stock_paths_have_different_explanations_and_falsifiers(self):
        x=self.result()
        cases={r['ticker']:r for r in x['human_review_examples']}
        self.assertEqual(cases['3703']['review_group'],'優先人工追蹤') # rebound warrants review; leverage remains a separate risk
        self.assertEqual(cases['6443']['review_group'],'等待價格確認')
        self.assertEqual(cases['1416']['review_group'],'風險優先覆核')
        self.assertIn('其他持有人占比增加',cases['3703']['why'])
        self.assertIn('近5日融資增加',cases['3703']['risks'])
        self.assertIn('下次已公布TDCC',cases['3703']['change_of_view'])
        self.assertIn('正式EOD',markdown(x))
        self.assertNotIn('2026-11-10盤中',markdown(x))
    def test_no_hba_shortlist_does_not_eliminate_eligible_market_observations(self):
        self.original['all_candidates']=[]
        self.original['total_candidates_before_limit']=0
        x=self.result()
        self.assertEqual(x['status'],'RESEARCH_ADVISORY_READY')
        self.assertEqual(x['research_summary']['market_covered'],3)
        self.assertEqual(x['human_review_examples'],[])
    def test_incomplete_actual_eod_fails_closed(self):
        p=self.root/'eod/20261109/status.json'
        a=json.loads(p.read_text());a['price_rows']=4;p.write_text(json.dumps(a))
        x=self.result()
        self.assertEqual(x['status'],'BLOCKED')
        self.assertEqual(x['human_review_examples'],[])
        self.assertEqual(x['full_market_observations'],[])
    def add_no_close_eod(self, *, open_='--', high='--', low='--', close='--',
                         include_ohlc=True):
        path=self.root/'eod/20261109'
        status=json.loads((path/'status.json').read_text())
        status['price_rows']=4
        (path/'status.json').write_text(json.dumps(status))
        columns=['Date','Ticker','Name','Close']
        if include_ohlc:
            columns += ['Open','High','Low']
        with (path/'price_2.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=columns)
            w.writeheader()
            row={'Date':self.day,'Ticker':'1538','Name':'正峰','Close':close}
            if include_ohlc:row.update(Open=open_,High=high,Low=low)
            w.writerow(row)
        tg=self.integrated['two_group_research']
        tg['market_registry_total']=4
        tg['comparable_stock_count']=4
        self.integrated['two_group_market_registry'].append({
            'ticker':'1538','small_shares_delta':-4001,
            'other_shares_delta':4001,'small_holders_delta':0,
            'small_share_delta_pp':-0.012387,
            'same_week_price_return_pct':None,
            'same_week_price_ownership_pattern':'PRICE_PAIR_MISSING'})

    def test_explicit_no_trade_eod_close_retained_unknown(self):
        self.add_no_close_eod()
        closes=original_eod_closes(self.root,self.day)
        self.assertEqual(len(closes),4)
        self.assertIsNone(closes['1538']['close'])
        x=self.result()
        self.assertEqual(x['status'],'RESEARCH_ADVISORY_READY',x['missing_data'])
        self.assertEqual(len(x['full_market_observations']),4)
        miss=next(r for r in x['full_market_observations'] if r['ticker']=='1538')
        self.assertIsNone(miss['latest_eod_close'])
        self.assertEqual(miss['review_group'],'兩方資料缺失')
        self.assertEqual(x['research_summary']['groups']['兩方資料缺失'],1)
        self.assertIn('3703',{r['ticker'] for r in x['human_review_examples']})
        self.assertFalse(x['authority']['broker_execution'])

    def test_malformed_no_close_with_executed_ohlc_blocks(self):
        self.add_no_close_eod(high='7.5')
        self.assertEqual(original_eod_closes(self.root,self.day),{})
        self.assertEqual(self.result()['status'],'BLOCKED')

    def test_malformed_no_close_without_ohlc_provenance_blocks(self):
        self.add_no_close_eod(include_ohlc=False)
        self.assertEqual(original_eod_closes(self.root,self.day),{})
        self.assertEqual(self.result()['status'],'BLOCKED')

    def test_future_or_mismatched_integrated_date_fails_closed(self):
        self.integrated['observed_eod_date']='2026-11-10'
        x=self.result()
        self.assertEqual(x['status'],'BLOCKED')
        self.assertEqual(x['full_market_observations'],[])
    def test_unknown_retired_strategy_contract_fails_closed(self):
        p=self.root/'hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json'
        a=json.loads(p.read_text());a['active_strategy_count']=1;p.write_text(json.dumps(a))
        self.assertEqual(self.result()['status'],'BLOCKED')
    def test_missing_tdcc_price_pair_not_substituted(self):
        self.integrated['two_group_research']['price_pair']['status']='MISSING_VERIFIED_MATCHED_WEEKLY_EOD_PRICES'
        self.assertEqual(self.result()['status'],'BLOCKED')
    def test_partial_original_hba_alerts_are_not_silently_promoted(self):
        self.original['total_candidates_before_limit']=4
        self.assertEqual(self.result()['status'],'BLOCKED')
    def test_no_future_quotes_and_no_strategy_authority_in_output(self):
        x=self.result()
        self.assertTrue(x['not_live_quotes'])
        self.assertEqual(x['research_summary']['macro'],'資料不足')
        self.assertEqual(x['research_summary']['s5'],'NOT_PROVIDED')
        self.assertEqual(x['research_summary']['escape'],'NOT_PROVIDED')
        self.assertIn('沒有買賣訊號',markdown(x))
    def test_full_repository_20261109_market_snapshot(self):
        # Verify the actual original 1,082-name market snapshot instead of
        # passing only handcrafted three-stock fixtures.
        repo=Path(__file__).resolve().parents[2]
        import hashlib
        original_file=repo/'research/hba_surveillance/latest.json'
        integrated_file=repo/'research/hba_surveillance/integrated_latest.json'
        if not original_file.is_file() or not integrated_file.is_file():
            self.skipTest('Original full-market reports are not checked out')
        orig=json.loads(original_file.read_text(encoding='utf-8'))
        integ=json.loads(integrated_file.read_text(encoding='utf-8'))
        if (orig.get('latest_verified_eod')!='2026-11-09' or
                integ.get('observed_eod_date')!='2026-11-09'):
            self.skipTest('Frozen replay date no longer matches, not a live backfill')
        x=build(repo,orig,integ,
                hashlib.sha256(original_file.read_bytes()).hexdigest(),
                hashlib.sha256(integrated_file.read_bytes()).hexdigest())
        self.assertEqual(x['status'],'RESEARCH_ADVISORY_READY',x['missing_data'])
        self.assertEqual(x['research_summary']['market_covered'],1082)
        self.assertEqual(x['research_summary']['hba_all_candidate_count'],307)
        ids={y['ticker'] for y in x['human_review_examples']}
        self.assertTrue({'3703','2406','6443','1416'}.issubset(ids))
        self.assertEqual(x['authority']['active_selection_strategy_count'],0)
        self.assertLess(len(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode('utf-8')),950000)

    def test_wrong_market_count_blocks(self):
        self.integrated['two_group_research']['comparable_stock_count']=4
        x=self.result()
        self.assertEqual(x['status'],'BLOCKED')
        self.assertEqual(x['full_market_observations'],[])

if __name__=='__main__':
    unittest.main()
