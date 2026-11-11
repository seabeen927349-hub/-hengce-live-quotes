#!/usr/bin/env python3
"""HENGCE V2.4-U: read-only, as-of unified research decisions.

Does NOT modify orders, production router or state; all outputs have authorized_lots=0.
Requires a verified daily forecast feed for production-quality point-in-time use;
historical V2.2-D feed is insufficient to claim live data provenance.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd

VERSION='HENGCE_V24U_RESEARCH_0_1'
PRICE_FIELDS=['Date','Ticker','Open','High','Low','Close','Volume','Turnover']
PRED_FIELDS=['date','Ticker','unadjusted_score_week_end_le10_count_decline_1pct']
FUTURE_COLS={'label','target_pct','targetN','y','mfe240','forward_gain30','forward_60_mfe','exit_reason','net_return_pct','future_label'}
FEATURES=['gain_from_entry','r5','r10','above_ma20','turnover5_to20','drawdown_from_peak','above_prior60high','atr_pct','initial_q','initial_retail_score','checkpoint_day']
BUY_FEE=.001425;SELL_FEE=.001425;SELL_TAX=.003;SLIP=.001

def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for buf in iter(lambda:f.read(8<<20),b''):h.update(buf)
 return h.hexdigest()

def ensure(cond,msg):
 if not cond:raise ValueError(msg)

def read_bars(path,asof,history_start=None,tickers=None):
 out=[]
 for block in pd.read_csv(path,usecols=PRICE_FIELDS,dtype={'Ticker':str,'Date':str,'Open':str,'High':str,'Low':str,'Close':str,'Volume':str,'Turnover':str},chunksize=220000):
  block=block[block.Date.le(asof)]
  if tickers is not None:block=block[block.Ticker.isin(tickers)]
  if history_start:block=block[block.Date.ge(history_start)]
  if len(block):out.append(block)
 ensure(out,'No EOD <= asof')
 d=pd.concat(out,ignore_index=True)
 d['Ticker']=d.Ticker.str.strip();d['Date']=pd.to_datetime(d.Date,errors='raise')
 ensure(not d.duplicated(['Ticker','Date']).any(),'Duplicate price bars')
 for c in PRICE_FIELDS[2:]:d[c]=pd.to_numeric(d[c],errors='coerce')
 ensure(not d[PRICE_FIELDS[2:]].lt(0).any().any(),'Negative OHLC/volume')
 ensure(not np.isinf(d[PRICE_FIELDS[2:]].to_numpy(dtype=float)).any(),'Infinite OHLC/volume')
 d=d.sort_values(['Ticker','Date']).reset_index(drop=True)
 pieces=[]
 for _,g in d.groupby('Ticker',sort=False):
  g=g.copy().reset_index(drop=True)
  c=g.Close.where(g.Close.gt(0)); prev=c.shift(1)
  g['tradable']=(g.Open.gt(0)&g.Close.gt(0)&g.Volume.gt(0)&g.Turnover.gt(0))
  tr=pd.concat([(g.High-g.Low),(g.High-prev).abs(),(g.Low-prev).abs()],axis=1).max(axis=1)
  tr=tr.where(prev.notna() & g.High.gt(0) & g.Low.gt(0))
  g['atr20']=tr.rolling(20,min_periods=20).mean()
  g['ma20']=c.rolling(20,min_periods=20).mean()
  g['ma30']=c.rolling(30,min_periods=30).mean()
  g['r5']=c/c.shift(5)-1
  g['r10']=c/c.shift(10)-1
  g['r20']=c/c.shift(20)-1
  g['median_turnover20']=g.Turnover.rolling(20,min_periods=20).median()
  g['turnover5_to20']=g.Turnover.rolling(5,min_periods=5).mean()/g.Turnover.rolling(20,min_periods=20).mean()
  g['prior60high']=c.shift(1).rolling(60,min_periods=60).max()
  pieces.append(g)
 return {t:g for t,g in ((x.Ticker.iloc[0],x) for x in pieces)}

def load_forecast(path,asof):
 """Accept V2.2-D legacy scores or V2.3 timestamped scores, never future labels."""
 head=pd.read_csv(path,nrows=0).columns.tolist()
 if set(PRED_FIELDS).issubset(head):
  # Legacy retrospective source; availability not independently certified.
  d=pd.read_csv(path,usecols=PRED_FIELDS,dtype={'Ticker':str,'date':str})
  d=d[d.date==asof].copy()
  ensure(len(d)>0,'No daily forecasts on asof date: cannot substitute prior week silently')
  d.Ticker=d.Ticker.str.strip()
  ensure(not d.duplicated(['Ticker','date']).any(),'Duplicate daily forecast')
  d['p']=pd.to_numeric(d[PRED_FIELDS[2]],errors='raise')
  ensure(d.p.notna().all() and d.p.between(0,1).all(),'Invalid forecast score')
  return d[['Ticker','date','p']]
 req=['Ticker','PredictionAt','FeatureAvailableAt','ModelTrainedThrough','CalibrationAvailableAt','TargetSnapshot','Probability','ModelVersion']
 ensure(set(req).issubset(head),'Forecast needs V22D or timestamped V23 schema')
 pred=pd.read_csv(path,usecols=req,dtype={'Ticker':str})
 ensure(len(pred)>0,'Empty V23 forecast')
 for col in ['PredictionAt','FeatureAvailableAt','ModelTrainedThrough','CalibrationAvailableAt']:
  ensure(pred[col].astype(str).str.contains(r'(?:Z|[+-]\d\d:\d\d)$',regex=True).all(),f'Timestamp offset missing: {col}')
  pred[col]=pd.to_datetime(pred[col],utc=True,errors='raise')
 ensure(pred.ModelVersion.notna().all() and pred.ModelVersion.astype(str).str.strip().ne('').all(),'Missing model version')
 ensure((pred.FeatureAvailableAt<=pred.PredictionAt).all(),'Future feature')
 ensure((pred.CalibrationAvailableAt<=pred.PredictionAt).all(),'Future calibration')
 ensure((pred.ModelTrainedThrough<pred.PredictionAt).all(),'Model trained after prediction')
 target=pd.to_datetime(pred.TargetSnapshot,errors='raise')
 ensure(target.dt.tz is None,'Target snapshot must be local YYYY-MM-DD')
 delta=(target.dt.date-pred.PredictionAt.dt.tz_convert('Asia/Taipei').dt.date).map(lambda x:x.days)
 ensure(delta.between(1,7).all(),'Target snapshot outside next 1-7 days')
 pred['date']=pred.PredictionAt.dt.tz_convert('Asia/Taipei').dt.strftime('%Y-%m-%d')
 pred=pred[pred.date==asof].copy()
 ensure(len(pred)>0,'Missing asof V23 forecast')
 cutoff=pd.Timestamp(asof).tz_localize('Asia/Taipei')+pd.Timedelta(hours=22)
 pred=pred[pred.PredictionAt<=cutoff]
 ensure(len(pred)>0,'No forecast available by 22:00 Taiwan time')
 pred=pred.sort_values('PredictionAt').groupby('Ticker').tail(1)
 pred['p']=pd.to_numeric(pred.Probability,errors='raise')
 ensure(pred.p.notna().all() and pred.p.between(0,1).all(),'Invalid Probability')
 return pred[['Ticker','date','p']]

def verify_asof_availability(manifest_path,prices_path,forecast_path,asof,strict=False):
 """Manifest checks source identities and availability. No manifest => clearly unverified."""
 base={'status':'UNVERIFIED_RESEARCH_SOURCE','time_verified':False,'full_candidate_coverage_verified':False}
 if not manifest_path:
  ensure(not strict,'Strict provenance needs manifest');return base
 m=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
 for field,path in [('price_sha256',prices_path),('forecast_sha256',forecast_path)]:
  ensure(m.get(field)==digest(path),f'SHA mismatch: {field}')
 base['sha_verified']=True
 base['status']='MANIFEST_MATCHED_RESEARCH'
 if m.get('asof')!=asof:raise ValueError('Manifest asof must match requested date')
 # Stronger verification requires explicit independent evidence, not just fields filled in.
 base['time_verified']=m.get('timestamp_evidence')=='INDEPENDENTLY_VERIFIED'
 base['full_candidate_coverage_verified']=m.get('full_candidate_coverage_verified') is True
 if strict:ensure(base['time_verified'] and base['full_candidate_coverage_verified'],'PIT availability/coverage not certified')
 return base

def entry_candidates(bars,forecast,asof,topk=5):
 rows=[]
 for r in forecast.itertuples(index=False):
  g=bars.get(r.Ticker)
  if g is None or g.iloc[-1].Date.strftime('%Y-%m-%d')!=asof:continue
  q=g.iloc[-1]
  if not(q.tradable and np.isfinite(q.atr20) and q.atr20>0 and np.isfinite(q.r20) and np.isfinite(q.r5) and np.isfinite(q.median_turnover20)):continue
  if q.r20<.05 or q.r5<0 or q.median_turnover20<10000000 or float(r.p)<.5:continue
  rows.append(dict(Ticker=r.Ticker,score=float(r.p),r20=float(q.r20),r5=float(q.r5),median_turnover20=float(q.median_turnover20),atr20=float(q.atr20),close=float(q.Close),date=asof))
 rows=sorted(rows,key=lambda r:(-r['median_turnover20'],r['Ticker']))
 for i,row in enumerate(rows):row['rank']=i+1
 return rows[:topk],len(rows)

def model_score(model,features):
 ensure(model['feature_order']==FEATURES,'Unexpected model feature order')
 v=np.array([features[k] for k in FEATURES],dtype=float)
 ensure(np.isfinite(v).all(),'Nonfinite lifecycle feature')
 scale=np.array(model['scaler_scale'],dtype=float)
 ensure((scale>0).all(),'Invalid scaler')
 logit=float(((v-np.array(model['scaler_mean']))/scale)@np.array(model['logistic_coef'])+model['logistic_intercept'])
 score=1/(1+math.exp(-max(-500,min(500,logit))))
 state='STRONG' if score>=model['high_cutoff'] else ('WEAK' if score<=model['low_cutoff'] else 'MIXED')
 return score,state

def checkpoint(bars,position,asof,model):
 # Values at most recent validated 5/10/20/40-day checkpoint only. Do not pretend
 # the frozen model was trained on all daily ages.
 g=bars.get(position['Ticker'])
 if g is None:return None
 ed=pd.Timestamp(position['entry_date'])
 matches=np.flatnonzero(g.Date.to_numpy()==np.datetime64(ed))
 if len(matches)!=1:return None
 start=int(matches[0]); end=int(np.flatnonzero(g.Date.to_numpy()<=np.datetime64(asof))[-1])
 age=end-start+1
 cp=max((d for d in (5,10,20,40) if d<=age),default=None)
 if cp is None:return None
 i=start+cp-1;s=g.iloc[i];piece=g.iloc[start:i+1];buy=position['entry_price']
 f={'gain_from_entry':s.Close/buy-1,'r5':s.r5,'r10':s.r10,'above_ma20':s.Close/s.ma20-1,'turnover5_to20':s.turnover5_to20,'drawdown_from_peak':s.Close/max(piece.Close.max(),buy)-1,'above_prior60high':s.Close/s.prior60high-1,'atr_pct':s.atr20/s.Close,'initial_q':position.get('entry_quality'),'initial_retail_score':position.get('entry_retail_score'),'checkpoint_day':cp}
 try:sc,st=model_score(model,f)
 except (TypeError,ValueError,ZeroDivisionError):return None
 return {'checkpoint_day':cp,'checkpoint_date':s.Date.strftime('%Y-%m-%d'),'score_uncalibrated':round(sc,6),'strength_state':st,'valid_as_of':s.Date.strftime('%Y-%m-%d'),'latest_market_day':g.iloc[end].Date.strftime('%Y-%m-%d')}

def position_review(bars,pos,asof,model):
 t=pos.get('Ticker');base={'Ticker':t,'state':'HOLD_DATA_REQUIRED','research_action':'COMPLETE_POSITION_BASIS','authorized_lots':0,'reason':'Missing verified fill/ATR/entry date','next_open_execution_price':None}
 req=['Ticker','entry_date','entry_price','initial_atr20','shares']
 if any(k not in pos or pos[k] is None or (isinstance(pos[k],str) and not pos[k].strip()) for k in req):return base
 try:
  p={**pos,'entry_price':float(pos['entry_price']),'initial_atr20':float(pos['initial_atr20']),'shares':int(pos['shares'])}
  ensure(p['entry_price']>0 and p['initial_atr20']>0 and p['shares']>0,'Invalid position numbers')
  ensure(p['entry_date']<=asof,'Position date after asof')
  g=bars.get(t)
  ensure(g is not None,'Missing position ticker')
  hist=g[(g.Date>=pd.Timestamp(p['entry_date']))&(g.Date<=pd.Timestamp(asof))]
  ensure(not hist.empty and hist.iloc[0].Date.strftime('%Y-%m-%d')==p['entry_date'],'Missing entry-date bar')
  ensure(hist.iloc[-1].Date.strftime('%Y-%m-%d')==asof,'No asof EOD for position')
  stop=p['entry_price']-2*p['initial_atr20'];ensure(stop>0,'Nonpositive initial stop')
  peak=p['entry_price'];trail=-float('inf');activated=False;hit=None
  for x in hist.itertuples(index=False):
   if not np.isfinite(x.Close) or x.Close<=0:continue
   peak=max(peak,float(x.Close))
   if peak>=p['entry_price']*1.20:activated=True
   if activated and np.isfinite(x.atr20) and x.atr20>0:trail=max(trail,peak-4*float(x.atr20))
   if x.Close<=stop or (activated and x.Close<=trail):
    hit={'trigger_date':x.Date.strftime('%Y-%m-%d'),'reason':'INITIAL_STOP_2ATR' if x.Close<=stop else 'TRAIL_4ATR_AFTER_20PCT'}
    break
  close=float(hist.iloc[-1].Close)
  cp=checkpoint(bars,p,asof,model)
  return dict(base, state='SELL_REVIEW' if hit else 'HOLD_REVIEW',research_action='VERIFY_EXIT_AT_NEXT_OPEN' if hit else 'MONITOR_HOLD',reason=(hit['reason'] if hit else 'NO_EXIT_TRIGGER'),last_close=close,initial_stop=round(stop,4),trailing_stop=round(trail,4) if activated and np.isfinite(trail) else None,stop_trigger=hit,peak_close=round(peak,4),unrealized_change_pct=round(100*(close/p['entry_price']-1),3),continuation=cp,shares=p['shares'],hold_data_complete=True)
 except (ValueError,TypeError,KeyError,IndexError) as exc:
  return dict(base,reason=str(exc))

def reentry_review(bars,exit_record,asof):
 t=exit_record.get('Ticker');g=bars.get(t)
 if g is None:return None
 date=exit_record.get('exit_fill_date')
 if not date or date>=asof:return None
 hist=g[g.Date<=pd.Timestamp(asof)].reset_index(drop=True)
 exit_indexes=np.flatnonzero(hist.Date.to_numpy()==np.datetime64(date))
 if len(exit_indexes)!=1:return None
 elapsed=len(hist)-1-int(exit_indexes[0])
 if elapsed<5:return None
 q=hist.iloc[-1]
 if not (q.tradable and np.isfinite(q.prior60high) and np.isfinite(q.ma30) and q.Close>q.prior60high and q.Close>q.ma30):return None
 return {'Ticker':t,'state':'REENTRY_REVIEW','research_action':'REVIEW_NEXT_OPEN_REENTRY','authorized_lots':0,'trigger_close':float(q.Close),'prior60high':float(q.prior60high),'ma30':float(q.ma30),'sessions_since_last_exit':elapsed,'next_open_execution_price':None,'reason':'CLOSE_BREAKS_PRIOR60HIGH_AND_ABOVE_MA30'}

def decide(prices,forecasts,asof,model_file,positions_file=None,exits_file=None,manifest_file=None,strict=False,topk=5):
 ensure(dt.date.fromisoformat(asof)<=dt.date.today()+dt.timedelta(days=1),'Future asof prohibited')
 audit=verify_asof_availability(manifest_file,prices,forecasts,asof,strict)
 model=json.loads(Path(model_file).read_text(encoding='utf-8'))
 forecast=load_forecast(forecasts,asof)
 positions=json.loads(Path(positions_file).read_text()) if positions_file else []
 exits=json.loads(Path(exits_file).read_text()) if exits_file else []
 ensure(isinstance(positions,list) and isinstance(exits,list),'Positions/exits must be JSON arrays')
 universe=set(forecast.Ticker.astype(str))|{p.get('Ticker') for p in positions}|{e.get('Ticker') for e in exits}
 universe.discard(None)
 entry_dates=[p.get('entry_date') for p in positions if p.get('entry_date')]
 oldest=min(entry_dates) if entry_dates else asof
 history_start=min((dt.date.fromisoformat(asof)-dt.timedelta(days=850)).isoformat(),(dt.date.fromisoformat(oldest)-dt.timedelta(days=120)).isoformat())
 bars=read_bars(prices,asof,history_start=history_start,tickers=universe)
 picks,n_qual=entry_candidates(bars,forecast,asof,topk=topk)
 held=[p.get('Ticker') for p in positions]
 ensure(all(isinstance(t,str) and len(t)>0 for t in held),'Position ticker invalid')
 ensure(len(held)==len(set(held)),'Duplicate open holding ticker')
 rows=[position_review(bars,p,asof,model) for p in positions]
 seen=set(held)
 for x in reversed(exits):
  t=x.get('Ticker')
  if not t or t in seen:continue
  seen.add(t)
  r=reentry_review(bars,x,asof)
  if r:rows.append(r)
 for p in picks:
  if p['Ticker'] in seen:continue
  seen.add(p['Ticker'])
  rows.append({'Ticker':p['Ticker'],'state':'ENTRY_REVIEW','research_action':'REVIEW_NEXT_OPEN_BUY','authorized_lots':0,'reason':'DAILY_FORECAST_AND_V22_PRICE_LIQUIDITY_GATES','reference_close':p['close'],'initial_stop_if_filled':None,'planned_initial_stop_formula':'ACTUAL_FILLED_PRICE - 2 * SIGNAL_DAY_ATR20','signal_day_atr20':p['atr20'],'median_turnover20':p['median_turnover20'],'score_uncalibrated':p['score'],'rank':p['rank'],'next_open_execution_price':None})
 # Presence of a previously exited symbol never creates an ordinary new order.
 freshness=(dt.date.today()-dt.date.fromisoformat(asof)).days
 return {'schema':'HENGCE_V24U_DECISION_V1','version':VERSION,'authority':'RESEARCH_ONLY_NO_ORDER','authorized_lots':0,'formal_strategy_active':False,'source_asof':asof,'generated_date_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'latest_available_bar':max(g.Date.iloc[-1] for g in bars.values()).strftime('%Y-%m-%d'),'is_today_live_decision':False,'stale_for_current_use':freshness>2,'forecast_provenance':audit,'positions_supplied':len(positions),'qualified_candidates':n_qual,'top5_unadjusted':[x['Ticker'] for x in picks],'decision_count':len(rows),'decisions':rows,'operational_notes':['RESEARCH_RECOMMENDATIONS_NOT_ORDERS','NEXT_OPEN_PRICE_UNKNOWN_UNTIL_EXECUTION','PARTIAL_MARKET_AND_TDCC_TIME_CERTIFICATION','WINNER_SCORE_UNCALIBRATED_EXPLORATORY','NO_CAPITAL_ALLOCATION_OR_BROKER_LINK']}

def render_report(result):
 """Human-readable advisory, with unknown execution price visibly preserved."""
 lines=[f"# 衡策 V2.4-U 統一研究決策｜{result['source_asof']}",
        '',f"**狀態：{result['authority']}；正式策略未啟用；授權張數 0。**",
        '',f"資料最後日期：{result['latest_available_bar']}；今天可用：{'否' if result['stale_for_current_use'] else '仍需核對來源與報價'}。",
        f"資料來源：{result['forecast_provenance']['status']}；時間驗證：{result['forecast_provenance']['time_verified']}。",
        f"符合條件候選 {result['qualified_candidates']} 檔；前五研究候選：{', '.join(result['top5_unadjusted']) or '無'}。",'',
        '| 代號 | 統一狀態 | 參考收盤 | 初始風險線 | 買後續強 | 理由 |',
        '|---|---|---:|---:|---|---|']
 for x in result['decisions']:
  cp=x.get('continuation') or {}
  price=x.get('reference_close',x.get('last_close',x.get('trigger_close')))
  stop=x.get('initial_stop')
  lines.append('| '+ ' | '.join([str(x['Ticker']),x['state'],str(round(price,3)) if price is not None else '—',str(stop) if stop is not None else '待實際成交價',cp.get('strength_state','—')+(f"({cp.get('checkpoint_date')})" if cp else ''),x['reason']])+' |')
 lines+=['','**買賣價說明：** 進場訊號只知道當日收盤與 ATR，下一交易日開盤買價未知；實際成交後初始風險線＝成交價−2×訊號日ATR20。賣出為收盤觸發、下一個有效開盤價待確認，不能假設以觸發價成交。','','**限制：** 集保每日戶數是估計、分數未校準；歷史來源可得時間未獨立核驗，並非今日即時選股或券商下單指令。']
 return '\n'.join(lines)+'\n'

def main():
 ap=argparse.ArgumentParser(description='Read-only unified V2.4 entry/hold/exit/reentry decision engine')
 ap.add_argument('--prices',required=True);ap.add_argument('--forecasts',required=True)
 ap.add_argument('--model',default=str(Path(__file__).with_name('frozen_continuation_model.json')))
 ap.add_argument('--asof',required=True);ap.add_argument('--positions');ap.add_argument('--exits')
 ap.add_argument('--manifest');ap.add_argument('--strict-provenance',action='store_true')
 ap.add_argument('--topk',type=int,default=5);ap.add_argument('--out',required=True)
 a=ap.parse_args();ensure(1<=a.topk<=50,'topk out of range')
 result=decide(a.prices,a.forecasts,a.asof,a.model,a.positions,a.exits,a.manifest,a.strict_provenance,a.topk)
 out=Path(a.out);ensure(not out.exists(),'Output file exists; refuse overwrite');out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 report=out.with_suffix('.md');ensure(not report.exists(),'Report file exists; refuse overwrite')
 report.write_text(render_report(result),encoding='utf-8')
 print(json.dumps({'status':'RESEARCH_OUTPUT_CREATED','asof':result['source_asof'],'candidates':result['qualified_candidates'],'top5':result['top5_unadjusted'],'decision_count':result['decision_count'],'authority':'NO_ORDER','file':str(out)},ensure_ascii=False))
if __name__=='__main__':main()