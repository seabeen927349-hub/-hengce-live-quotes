import csv, hashlib, importlib.util, io, json, tempfile, unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

P=Path(__file__).resolve().parents[2]/'scripts'/'hengce_retail_top5_vessel_bridge.py'
spec=importlib.util.spec_from_file_location('bridge',P)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.decision=date(2026,11,6)
        self.names=[f'{1000+i:04d}' for i in range(900)]
        days=[];d=self.decision
        while len(days)<21:
            if d.weekday()<5:days.append(d)
            d-=timedelta(days=1)
        for d in days:
            p=self.root/'eod'/d.strftime('%Y%m%d');(p/'receipts').mkdir(parents=True)
            with (p/'price_1.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(['Date','Ticker','VolumeShares','TurnoverTWD','Close'])
                for t in self.names:w.writerow([d.isoformat(),t,1500000,100000000,100])
            sh=b.eod_digest([p/'price_1.csv'])
            (p/'receipts'/'price.json').write_text(json.dumps({'status':'COMPLETE','leg':'price','target_date':d.isoformat(),'files':['price_1.csv'],'sha256':sh,'rows':900}))
            (p/'status.json').write_text(json.dumps({'target_date':d.isoformat(),'price_date':d.isoformat(),'price_status':'COMPLETE','downstream_ready':True,'mother_status':'COMPLETE','second_mother':False,'price_sha256':sh}))
        for ds in ['20261008','20261015','20261022']:
            p=self.root/'ownership'/'tdcc'/ds;p.mkdir(parents=True)
            txt=io.StringIO();w=csv.writer(txt);w.writerow(['資料日期','證券代號','持股分級','人數','股數'])
            for t in self.names:
                for g in (1,2,3):w.writerow([ds,t,g,100,10000*g])
            raw=txt.getvalue().encode('utf-8-sig');(p/'tdcc_1_5_raw.csv').write_bytes(raw)
            observed=date(int(ds[:4]),int(ds[4:6]),int(ds[6:]))+timedelta(days=1)
            (p/'receipt.json').write_text(json.dumps({'snapshot_date':ds,'observed_at_taipei':observed.isoformat()+'T09:00:00+08:00',
                'status':'COMPLETE','source_owner':'TDCC','model_authority_created':False,'source_sha256':b.sha(raw)}))
            proot=self.root/'ownership'/'tdcc'/'provenance'/'first_observed';proot.mkdir(parents=True,exist_ok=True)
            (proot/(b.sha(raw)+'.json')).write_text(json.dumps({
              'payload_sha256':b.sha(raw), 'snapshot_reference_date':f'{ds[:4]}-{ds[4:6]}-{ds[6:]}',
              'provenance_source_authority':'CANONICAL_VESSEL_RESPONSE_ONLY','official_published_at':None,
              'ownership_and_provenance_share_exact_response_bytes':True,
              'first_observed_at_taipei':observed.isoformat()+'T09:00:00+08:00'}))
    def test_verified_sources_schema_but_zero_authority(self):
        out,day,week=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'SOURCE_DATA_PREPARED_RESEARCH_ONLY',out['blockers'])
        self.assertEqual(len(day),21*900)
        self.assertEqual(len(week),3*900)
        self.assertEqual(day[0][1],'1000');self.assertEqual(week[-1][2],300)
        self.assertEqual(out['capital_authority_twd'],0)
        self.assertFalse(out['broker_execution'])
    def test_missing_eod_blocked(self):
        p=self.root/'eod'/'20261106'/'status.json';p.unlink()
        out,_,_=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'BLOCKED')
        self.assertTrue(any('EOD_INVALID' in q for q in out['blockers']))
    def test_receipt_hash_tamper_blocked(self):
        p=self.root/'eod'/'20261106'/'price_1.csv';p.write_bytes(p.read_bytes()+b' ') 
        out,_,_=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'BLOCKED');self.assertTrue(any('SHA_MISMATCH' in q for q in out['blockers']))
    def test_tdcc_no_first_observed_proof_blocked(self):
        p=self.root/'ownership'/'tdcc'/'20261022'/'tdcc_1_5_raw.csv'
        proof=self.root/'ownership'/'tdcc'/'provenance'/'first_observed'/(b.sha(p.read_bytes())+'.json')
        proof.unlink()
        out,_,_=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'BLOCKED')
        self.assertTrue(any('FIRST_OBSERVED_PROOF_ABSENT' in q for q in out['blockers']))
    def test_tdcc_unavailable_blocked(self):
        (self.root/'ownership'/'tdcc'/'20261022'/'receipt.json').unlink()
        out,_,_=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'BLOCKED')
        self.assertTrue(any('TDCC_INVALID' in q for q in out['blockers']))
    def test_tdcc_future_observed_blocked(self):
        p=self.root/'ownership'/'tdcc'/'20261022'/'receipt.json';x=json.loads(p.read_text());x['observed_at_taipei']='2026-11-07T12:00:00+08:00';p.write_text(json.dumps(x))
        out,_,_=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'BLOCKED')
        self.assertTrue(any('NOT_KNOWN' in q for q in out['blockers']))
    def test_auxiliary_not_substituted(self):
        x=b.aux_status(self.root,self.decision)
        self.assertEqual(x['finmind']['status'],'UNAVAILABLE_OR_STALE')
        self.assertEqual(x['fugle']['status'],'UNAVAILABLE_OR_STALE')
        out,_,_=b.audit(self.root,self.decision)
        self.assertEqual(out['status'],'SOURCE_DATA_PREPARED_RESEARCH_ONLY')
if __name__=='__main__':unittest.main()