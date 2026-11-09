import csv,json,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from hengce_hba_context_bridge_v1 import build,read_lifelong_summary

class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for date,down,up in [('2026-11-05',857,167),('2026-11-06',953,105)]:
   p=self.root/'eod'/date.replace('-','');p.mkdir(parents=True)
   (p/'status.json').write_text(json.dumps({'formal_complete_day':True,'downstream_ready':True,
    'price_date':date,'institutional_date':date,'margin_date':date,'mother_status':'COMPLETE'}))
   (p/'market_state_finmind_context.json').write_text(json.dumps({'target_date':date,
    'authority':'RESEARCH_SHADOW_DESCRIPTIVE_CONTEXT_ONLY_NO_MODEL_OR_TRADING_AUTHORITY',
    'scopes':{'twse_all_listed_equities':{'advancing_count':up,'declining_count':down,
    'change_rate_eligible_count':1085,'declining_share':down/1085}}}))
  (self.root/'escape_live').mkdir()
  (self.root/'escape_live/twse_common_status.json').write_text(json.dumps({'generated_at_taipei':'2026-11-03T16:38:44+08:00','errors':['HTTP_403: Forbidden']}))
  (self.root/'escape_live/intraday_monitor.json').write_text(json.dumps({'market_date':'2026-11-06','source':'FinMind taiwan_stock_tick_snapshot','monitor_state':'LIVE_CONTEXT_READY','active_universe_transport_full_coverage':True,'formal_escape_authority':False,'formal_eod_authority':False,'active_required_count':1088,'finmind_metric_observation_count':1085,'metric_unknown_count':3}))
  self.summary=self.root/'summary.csv'
  with self.summary.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['ticker','first_date','last_date','valid_stock_days','gross_buy_shares','gross_sell_shares','net_shares'])
   w.writeheader();w.writerow(dict(ticker='2330',first_date='2018-01-02',last_date='2026-11-06',
    valid_stock_days=3,gross_buy_shares=200,gross_sell_shares=180,net_shares=20))
  self.original={'target_tw_date':'2026-11-09','latest_verified_eod':'2026-11-06',
    'data_gate':'EOD_VALID_MACRO_UNKNOWN','candidates':[{'ticker':'2330','stage':'觀察'}],
    'external_environment':{'label':'資料不足','status':'資料不足'}}
 def tearDown(self):self.tmp.cleanup()
 def test_increment_only_after_original_eod_receipt_and_never_rewrites_cache(self):
  # 2026-11-09 is the next weekday following the 2026-11-06 frozen mother.
  day='2026-11-09';folder=self.root/'eod/20261109'
  folder.mkdir(parents=True)
  (folder/'status.json').write_text(json.dumps({
   'formal_complete_day':True,'downstream_ready':True,'mother_status':'COMPLETE',
   'price_date':day,'institutional_date':day,'margin_date':day,
   'price_sha256':'p','institutional_sha256':'i','margin_sha256':'m',
   'price_rows':1,'institutional_rows':1
  }))
  (folder/'receipts').mkdir()
  (folder/'receipts/mother.json').write_text(json.dumps({
   'target_date':day,'mother_latest_date':day,'status':'PASS',
   'second_mother':False,'promoted_legs':['price','institutional','margin'],
   'promoted_leg_sha256':{'price':'p','institutional':'i','margin':'m'}
  }))
  with (folder/'price_2.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['Date','Ticker']);w.writeheader();w.writerow({'Date':day,'Ticker':'2330'})
  fields=['Date','Ticker','ForeignBuy','ForeignSell','ForeignDealerBuy','ForeignDealerSell',
          'TrustBuy','TrustSell','DealerProprietaryBuy','DealerProprietarySell',
          'DealerHedgeBuy','DealerHedgeSell']
  with (folder/'institutional_2.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow({
     'Date':day,'Ticker':'2330','ForeignBuy':100,'ForeignSell':50,
     'ForeignDealerBuy':10,'ForeignDealerSell':5,'TrustBuy':20,'TrustSell':15,
     'DealerProprietaryBuy':30,'DealerProprietarySell':25,
     'DealerHedgeBuy':40,'DealerHedgeSell':35
  })
  baseline=self.summary.read_bytes()
  from hengce_hba_context_bridge_v1 import fold_verified_original_eod
  m,stocks=read_lifelong_summary(self.summary,day)
  self.assertEqual(m['status'],'STALE_RESEARCH_SUMMARY')
  a,new=fold_verified_original_eod(self.root,day,m,stocks)
  self.assertEqual(a['status'],'AVAILABLE_RESEARCH_PROXY')
  self.assertEqual(a['incremental_eod_dates'],[day])
  self.assertEqual(a['incremental_valid_stock_days'],1)
  self.assertEqual(new['2330']['gross_buy_shares'],400)
  self.assertEqual(new['2330']['gross_sell_shares'],310)
  self.assertEqual(new['2330']['net_shares'],90)
  self.assertEqual(new['2330']['observed_stock_days'],4)
  again,new_again=fold_verified_original_eod(self.root,day,m,stocks)
  self.assertEqual(again['gross_buy_shares'],a['gross_buy_shares'])
  self.assertEqual(new_again,new)
  self.assertEqual(self.summary.read_bytes(),baseline)
  self.original['latest_verified_eod']=day
  integrated=build(self.root,self.original,self.summary)
  self.assertEqual(integrated['readiness'],'RESEARCH_READY')
  self.assertTrue(integrated['candidates'][0]['historical_flow_available'])
  self.assertEqual(integrated['mother']['incremental_valid_stock_days'],1)
  receipt=json.loads((folder/'receipts/mother.json').read_text())
  receipt['promoted_leg_sha256']['institutional']='BAD'
  (folder/'receipts/mother.json').write_text(json.dumps(receipt))
  blocked=build(self.root,self.original,self.summary)
  self.assertEqual(blocked['mother']['status'],'STALE_RESEARCH_SUMMARY')
  self.assertEqual(blocked['readiness'],'EOD_READY_LONG_TERM_MISSING')

 def test_gap_with_no_canonical_market_day_fails_closed(self):
  from hengce_hba_context_bridge_v1 import fold_verified_original_eod
  m,stocks=read_lifelong_summary(self.summary,'2026-11-10')
  meta,_=fold_verified_original_eod(self.root,'2026-11-10',m,stocks)
  self.assertEqual(meta['status'],'STALE_RESEARCH_SUMMARY')
  self.assertIn('2026-11-09',meta['reason'])

 def test_cross_day_breadth_and_old_403(self):
  x=build(self.root,self.original,self.summary)
  self.assertEqual(x['readiness'],'RESEARCH_READY')
  self.assertEqual(x['market_environment']['canonical']['prior_breadth']['declining_count'],857)
  self.assertEqual(x['market_environment']['canonical']['breadth']['declining_count'],953)
  self.assertEqual(x['market_environment']['fugle_whole_market_batch']['status'],'HISTORICAL_403')
  self.assertEqual(x['market_environment']['full_market_intraday_monitor']['primary_source'],'FinMind taiwan_stock_tick_snapshot')
  self.assertEqual(x['market_environment']['full_market_intraday_monitor']['status'],'OBSERVED_SAME_SESSION_SHADOW')
  self.assertEqual(x['market_environment']['full_market_intraday_monitor']['valid_metric_count'],1085)
  self.assertFalse(x['authority']['trade'])
 def test_integrated_bridge_uses_full_hba_evidence_not_top15_only(self):
  self.original['total_candidates_before_limit']=2
  self.original['all_candidates']=[{'ticker':'2330','stage':'觀察'}, {'ticker':'6782','stage':'準備監控'}]
  x=build(self.root,self.original,self.summary)
  self.assertEqual([c['ticker'] for c in x['candidates']],['2330','6782'])
  self.assertEqual(x['candidate_coverage']['source'],'ORIGINAL_HBA_FULL_REGISTRY')
  self.assertFalse(x['candidate_coverage']['truncated'])
  self.assertFalse(x['candidates'][1]['historical_flow_available'])
  self.assertFalse(x['authority']['new_selection'])
 def test_monitor_mismatched_day_does_not_become_current(self):
  x=json.loads((self.root/'escape_live/intraday_monitor.json').read_text());x['market_date']='2026-11-05';(self.root/'escape_live/intraday_monitor.json').write_text(json.dumps(x))
  y=build(self.root,self.original,self.summary)
  self.assertEqual(y['market_environment']['full_market_intraday_monitor']['status'],'NO_MATCHING_FINMIND_SHADOW')
 def test_lifelong_gross_not_net_only(self):
  m,x=read_lifelong_summary(self.summary,'2026-11-06')
  self.assertEqual(m['status'],'AVAILABLE_RESEARCH_PROXY')
  self.assertEqual(x['2330']['net_abs_to_gross_pct'],round(20/380*100,4))
 def test_no_mother_not_fake_proof(self):
  x=build(self.root,self.original)
  self.assertEqual(x['readiness'],'EOD_READY_LONG_TERM_MISSING')
  self.assertEqual(x['mother']['status'],'NOT_MOUNTED')
 def test_future_lookahead_forbidden(self):
  self.assertEqual(read_lifelong_summary(self.summary,'2026-11-05')[0]['status'],'FUTURE_DATA_REJECTED')
  self.original['latest_verified_eod']='2026-11-10'
  self.assertEqual(build(self.root,self.original,self.summary)['readiness'],'BLOCKED')
 def test_missing_formal_eod_blocks(self):
  p=self.root/'eod/20261106/status.json';x=json.loads(p.read_text());x['downstream_ready']=False;p.write_text(json.dumps(x))
  self.assertEqual(build(self.root,self.original,self.summary)['readiness'],'BLOCKED')
if __name__=='__main__':unittest.main()
