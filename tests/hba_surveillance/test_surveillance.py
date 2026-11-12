import csv,json,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from hengce_hba_daily_surveillance import scan,env,stable_hash

class Surveillance(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.root=Path(self.d.name)
  for j in range(9):
   date=f'2026-10-{20+j:02d}' if j<8 else '2026-11-06'
   day=self.root/'eod'/date.replace('-','');day.mkdir(parents=True)
   (day/'status.json').write_text(json.dumps({'formal_complete_day':True,'downstream_ready':True, 'price_date':date,'institutional_date':date,'margin_date':date}))
   for typ,fields,data in [('price',['Date','Ticker','Name','Close','VolumeShares','TurnoverTWD'],[date,'1101','測試股',25+j*.5,1000000+10000*j,26000000]),('institutional',['Date','Ticker','TotalNet'],[date,'1101',30000]),('margin',['Date','Ticker','MarginBalance'],[date,'1101',1000-j*10])]:
    with (day/f'{typ}_1.csv').open('w',encoding='utf-8',newline='') as f:
     w=csv.writer(f);w.writerow(fields);w.writerow(data)
  for date,pct in [('20261023',55.0),('20261030',55.3)]:
   day=self.root/'ownership/tdcc'/date;day.mkdir(parents=True)
   with (day/'tdcc_ownership_4d.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['SnapshotDate','ObservedAtTaipei','Ticker','Big400Pct','Big1000Pct','TotalHolders']);w.writerow([date,'2026-10-31T10:00:00+08:00','1101',pct,50,2000])
 def tearDown(self):self.d.cleanup()
 def test_missing_macro_not_neutral(self):
  r=scan(self.root,'2026-11-09');self.assertEqual(r['external_environment']['label'],'資料不足');self.assertEqual(r['data_gate'],'EOD_VALID_MACRO_UNKNOWN');self.assertGreater(len(r['candidates']),0)
 def test_all_alert_evidence_kept_even_when_display_limit_zero(self):
  x=scan(self.root,'2026-11-09',limit=0)
  self.assertEqual(x['candidates'],[])
  self.assertGreater(x['total_candidates_before_limit'],0)
  self.assertEqual(len(x['all_candidates']),x['total_candidates_before_limit'])
  self.assertTrue(any(c['ticker']=='1101' for c in x['all_candidates']))
  self.assertTrue(all(c['historical_cycle_stage']=='HISTORICAL_CYCLE_UNVERIFIED' for c in x['all_candidates']))
 def test_bad_hash_not_allowed(self):
  p=self.root/'overseas_premarket/latest.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'status':'PASS_VERIFIED_VENDOR_EOD','target_tw_date':'2026-11-09','packet_sha256':'bad'}));self.assertEqual(env(self.root,'2026-11-09')['label'],'資料不足')
 def test_individual_overseas_sources_visible_without_composite(self):
  from datetime import datetime,date
  from zoneinfo import ZoneInfo
  from hengce_overseas_sox_vix_premarket_v1 import source_observation,vendor_url
  expected=date(2026,11,11);prior=date(2026,11,10)
  when=datetime(2026,11,12,8,20,tzinfo=ZoneInfo('Asia/Taipei'))
  obs=source_observation(when,'2026-11-11',
       {prior:9998.33,expected:10564.11},{prior:19.46,date(2026,11,9):19.92},
       b'PK-official-source-test'*7,b'CBOE-source-test'*12,vendor_url(when.date()))
  path=self.root/'overseas_premarket/source_status_latest.json'
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(obs))
  m=env(self.root,'2026-11-12')
  self.assertEqual(m['label'],'資料不足')
  self.assertEqual(m['status'],'資料不足')
  self.assertEqual(m['individual_sources']['sox']['latest_us_session'],'2026-11-11')
  self.assertEqual(m['individual_sources']['sox']['source_status'],'當期已更新')
  self.assertEqual(m['individual_sources']['vix']['source_status'],'官方資料待更新')
  self.assertEqual(m['individual_sources']['vix']['latest_us_session'],'2026-11-10')
  self.assertNotIn('grade',m)
  obs['sources']['sox']['latest_close']=1
  path.write_text(json.dumps(obs))
  self.assertNotIn('individual_sources',env(self.root,'2026-11-12'))
  path.write_text(json.dumps(source_observation(when,'2026-11-11',
       {prior:9998.33,expected:10564.11},{prior:19.46,date(2026,11,9):19.92},
       b'PK-official-source-test'*7,b'CBOE-source-test'*12,vendor_url(when.date()))))
  self.assertNotIn('individual_sources',env(self.root,'2026-11-13'))

 def test_stale_eod_blocked(self):
  self.assertEqual(scan(self.root,'2026-12-01')['data_gate'],'BLOCKED')
if __name__=='__main__':unittest.main()