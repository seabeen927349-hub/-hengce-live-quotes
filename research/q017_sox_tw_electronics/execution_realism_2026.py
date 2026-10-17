#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'executable_hold_timing_surface_2026'/'summary.json';OUT=ROOT/'execution_realism_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY:raise SystemExit('FUGLE_API_KEY missing')
src=json.loads(SRC.read_text(encoding='utf-8'));events=src['best_events']

def f(x):
 try:return float(x)
 except:return None
def fetch(symbol,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{symbol}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-REALISM/1.1'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return json.load(r).get('data',[])
  except Exception:
   if a==4:raise
   time.sleep(2**a)
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
aug=[]
for e in events:
 rows=fetch(e['ticker'],e['entry']);target=dt(e['entry_time']);hit=next((x for x in rows if dt(x.get('date')) and dt(x['date'])>=target),None)
 if not hit:raise SystemExit(f'NO_ENTRY_CANDLE:{e["entry"]}:{e["ticker"]}')
 # Fugle official docs: listed stock minute-candle volume is BOARD LOTS (張), 1 lot = 1000 shares.
 lots=f(hit.get('volume')) or 0
 z=dict(e);z['entry_candle_time']=hit['date'];z['entry_candle_volume_lots']=lots;z['entry_candle_volume_shares']=int(round(lots*1000));z['entry_candle_high']=f(hit.get('high'));z['entry_candle_low']=f(hit.get('low'));aug.append(z);time.sleep(.15)

rows=[];details={}
# share_proxy allows integer shares but uses regular-market volume only as a liquidity proxy; boardlot is the executable regular-lot case.
for mode in ('share_proxy','boardlot'):
 for part in (.01,.05,.10,.20,1.0):
  for slip in (0,.001,.002,.003):
   for cost in (.004,.006,.008,.010):
    cap=START;wins=0;tr=[]
    for e in aug:
     px=e['entry_price']*(1+slip);vol_shares=max(0,int(e['entry_candle_volume_shares']))
     desired=math.floor(cap/px)
     if mode=='boardlot':desired=(desired//1000)*1000
     maxq=math.floor(vol_shares*part)
     if mode=='boardlot':maxq=(maxq//1000)*1000
     q=min(desired,maxq)
     if q<=0:
      tr.append({'entry':e['entry'],'ticker':e['ticker'],'shares':0,'minute_volume_lots':e['entry_candle_volume_lots'],'capital':cap,'skipped':'LIQUIDITY_OR_LOT'});continue
     gross=e['exit_close']/px-1;net=gross-cost;pnl=q*px*net;cap+=pnl;wins+=net>0
     tr.append({'entry':e['entry'],'ticker':e['ticker'],'shares':q,'minute_volume_lots':e['entry_candle_volume_lots'],'minute_volume_shares':vol_shares,'participation_used':q/vol_shares if vol_shares else None,'entry_px_stressed':px,'exit_close':e['exit_close'],'net_ret_on_invested':net,'pnl':pnl,'capital':cap})
    rec={'mode':mode,'participation_cap':part,'slippage':slip,'roundtrip_cost':cost,'final':cap,'ret':cap/START-1,'executed':sum(x.get('shares',0)>0 for x in tr),'wins':wins}
    rows.append(rec);details[(mode,part,slip,cost)]=tr
rows.sort(key=lambda x:x['final'],reverse=True)
def pick(mode,part=.10,slip=.002,cost=.006):return next(r for r in rows if r['mode']==mode and r['participation_cap']==part and r['slippage']==slip and r['roundtrip_cost']==cost)
anchors={'share_proxy_practical':pick('share_proxy'),'boardlot_practical':pick('boardlot')}
summary={'objective':'stress best executable 2026 rule for discrete sizing, correctly unit-converted entry-minute liquidity, slippage, and costs','volume_unit_contract':'Fugle listed-stock minute volume is board lots; converted x1000 to shares','entry_rule':src['best'],'tested':len(rows),'best':rows[0],'practical_anchors':anchors,'top20':rows[:20],'events_with_volume':aug}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'best_details.json').write_text(json.dumps(details[(rows[0]['mode'],rows[0]['participation_cap'],rows[0]['slippage'],rows[0]['roundtrip_cost'])],ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
