import json, sys, tempfile, unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).parents[1]))
import unified_decision as u

MODEL=json.loads((Path(__file__).parents[1]/'frozen_continuation_model.json').read_text())

def synthetic():
 dates=pd.bdate_range('2026-05-01',periods=101)
 px=np.r_[np.full(80,100.),np.linspace(130.,145.,20),80.]
 df=pd.DataFrame({'Date':dates,'Ticker':'TEST','Open':px,'High':px+2,'Low':px-2,'Close':px,'Volume':10000,'Turnover':np.maximum(px,1)*10000})
 c=df.Close; tr=pd.concat([df.High-df.Low,(df.High-c.shift()).abs(),(df.Low-c.shift()).abs()],axis=1).max(axis=1)
 df['atr20']=tr.rolling(20,min_periods=20).mean();df['ma20']=c.rolling(20,min_periods=20).mean();df['ma30']=c.rolling(30,min_periods=30).mean();df['r5']=c/c.shift(5)-1;df['r10']=c/c.shift(10)-1;df['r20']=c/c.shift(20)-1;df['turnover5_to20']=df.Turnover.rolling(5,min_periods=5).mean()/df.Turnover.rolling(20,min_periods=20).mean();df['prior60high']=c.shift().rolling(60,min_periods=60).max();df['median_turnover20']=df.Turnover.rolling(20,min_periods=20).median();df['tradable']=True
 return df

class UnifiedTests(unittest.TestCase):
 def test_research_never_order(self):
  p={'Ticker':'TEST','entry_date':'2026-05-01','entry_price':100,'initial_atr20':3,'shares':1000,'entry_quality':.91,'entry_retail_score':.65}
  bars={'TEST':synthetic()};d=u.position_review(bars,p,bars['TEST'].Date.iloc[-1].strftime('%Y-%m-%d'),MODEL)
  self.assertEqual(d['state'],'SELL_REVIEW')
  self.assertEqual(d['authorized_lots'],0)
  self.assertIsNone(d['next_open_execution_price'])
  self.assertTrue(d['stop_trigger']['trigger_date']<=bars['TEST'].Date.iloc[-1].strftime('%Y-%m-%d'))
 def test_missing_basis_fails_closed(self):
  d=u.position_review({'TEST':synthetic()},{'Ticker':'TEST','shares':1000},'2026-08-31',MODEL)
  self.assertEqual(d['state'],'HOLD_DATA_REQUIRED')
 def test_checkpoint_uses_last_finished_checkpoint(self):
  g=synthetic();p={'Ticker':'TEST','entry_date':g.Date.iloc[60].strftime('%Y-%m-%d'),'entry_price':100,'initial_atr20':3,'shares':1000,'entry_quality':.91,'entry_retail_score':.65}
  r=u.checkpoint({'TEST':g},p,g.Date.iloc[85].strftime('%Y-%m-%d'),MODEL)
  self.assertEqual(r['checkpoint_day'],20)
  self.assertEqual(r['checkpoint_date'],g.Date.iloc[79].strftime('%Y-%m-%d'))
 def test_reentry_wait_and_breakout(self):
  g=synthetic();rec={'Ticker':'TEST','exit_fill_date':g.Date.iloc[75].strftime('%Y-%m-%d')}
  early=g.Date.iloc[78].strftime('%Y-%m-%d')
  self.assertIsNone(u.reentry_review({'TEST':g},rec,early))
  day=g.Date.iloc[82].strftime('%Y-%m-%d')
  self.assertEqual(u.reentry_review({'TEST':g},rec,day)['state'],'REENTRY_REVIEW')
 def test_no_forward_lookahead_signal(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'f.csv';pd.DataFrame([dict(date='2026-11-06',Ticker='TEST',unadjusted_score_week_end_le10_count_decline_1pct=.7,**{'mfe240':8})]).to_csv(path,index=False)
   d=u.load_forecast(path,'2026-11-06');self.assertNotIn('mfe240',d.columns)
 def test_forecast_missing_date_fails(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'f.csv';pd.DataFrame([dict(date='2026-11-05',Ticker='TEST',unadjusted_score_week_end_le10_count_decline_1pct=.7)]).to_csv(path,index=False)
   with self.assertRaises(ValueError):u.load_forecast(path,'2026-11-06')
 def test_duplicate_forecasts_fail(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'f.csv';pd.DataFrame([dict(date='2026-11-06',Ticker='TEST',unadjusted_score_week_end_le10_count_decline_1pct=.7)]*2).to_csv(path,index=False)
   with self.assertRaises(ValueError):u.load_forecast(path,'2026-11-06')
 def test_strict_provenance_rejects_unverified(self):
  with self.assertRaises(ValueError):u.verify_asof_availability(None,'a','b','2026-11-06',strict=True)
 def test_model_score_valid_prob(self):
  f={k:0.01 for k in u.FEATURES};f['checkpoint_day']=10;f['initial_q']=.9;f['initial_retail_score']=.55;f['turnover5_to20']=1.1
  score,state=u.model_score(MODEL,f);self.assertTrue(0<=score<=1);self.assertIn(state,('WEAK','MIXED','STRONG'))
 def test_entry_gates_ranking(self):
  g=synthetic();q=g.iloc[82].copy();q['r20']=.11;q['r5']=.06;q['median_turnover20']=20000000;q['atr20']=3.;q['tradable']=True;g.loc[g.index[-1],:]=q
  asof=g.Date.iloc[-1].strftime('%Y-%m-%d')
  scores=pd.DataFrame([{'Ticker':'TEST','date':asof,'p':.8}]);p,n=u.entry_candidates({'TEST':g},scores,asof)
  # As-of must match last bar, preventing reuse of older prices.
  self.assertEqual(n,1);self.assertEqual(p[0]['Ticker'],'TEST')
 def test_timestamped_forecast_accepts_valid_asof(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'pred.csv'
   x={'Ticker':'TEST','PredictionAt':'2026-11-06T19:00:00+08:00','FeatureAvailableAt':'2026-11-06T18:00:00+08:00','ModelTrainedThrough':'2026-11-05T23:00:00+08:00','CalibrationAvailableAt':'2026-11-06T17:00:00+08:00','TargetSnapshot':'2026-11-13','Probability':.71,'ModelVersion':'r1'}
   pd.DataFrame([x]).to_csv(path,index=False)
   d=u.load_forecast(path,'2026-11-06')
   self.assertEqual(len(d),1);self.assertEqual(d.iloc[0].p,.71)
 def test_timestamped_forecast_rejects_future_feature(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'pred.csv'
   x={'Ticker':'TEST','PredictionAt':'2026-11-06T19:00:00+08:00','FeatureAvailableAt':'2026-11-06T20:00:00+08:00','ModelTrainedThrough':'2026-11-05T23:00:00+08:00','CalibrationAvailableAt':'2026-11-06T17:00:00+08:00','TargetSnapshot':'2026-11-13','Probability':.71,'ModelVersion':'r1'}
   pd.DataFrame([x]).to_csv(path,index=False)
   with self.assertRaises(ValueError):u.load_forecast(path,'2026-11-06')
 def test_reentry_is_not_order(self):
  g=synthetic();rec={'Ticker':'TEST','exit_fill_date':g.Date.iloc[75].strftime('%Y-%m-%d')}
  row=u.reentry_review({'TEST':g},rec,g.Date.iloc[82].strftime('%Y-%m-%d'))
  self.assertEqual(row['authorized_lots'],0)

if __name__=='__main__':unittest.main()