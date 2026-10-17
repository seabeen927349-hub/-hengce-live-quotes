#!/usr/bin/env python3
import csv, math, json
from pathlib import Path
from collections import defaultdict

ROOT=Path('research/q017_sox_tw_electronics')
ARC=ROOT/'archive_2026'
RES=ROOT/'results_2026'
OUT=ROOT/'backtest_2m'
OUT.mkdir(parents=True, exist_ok=True)
START_CAP=2_000_000.0
COST=0.004


def f(x):
    try:
        s=str(x).replace(',','').strip()
        if s in ('','--','---'): return None
        return float(s)
    except: return None

# Load SOX
sox=[]
with (ARC/'sox_2026.csv').open(encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        c=f(r['close'])
        if c is not None: sox.append((r['date'],c))
sox.sort()
sox_ret={}
for i in range(1,len(sox)):
    sox_ret[sox[i][0]]=sox[i][1]/sox[i-1][1]-1
sox_dates=[d for d,_ in sox]

# Load TW electronics OHLC panel
by_ticker=defaultdict(list)
by_date=defaultdict(list)
with (ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        o,h,l,c=(f(r[k]) for k in ('open','high','low','close'))
        if None in (o,c): continue
        x={'date':r['date'],'ticker':r['ticker'],'name':r['name'],'open':o,'close':c}
        by_ticker[r['ticker']].append(x); by_date[r['date']].append(x)
for t in by_ticker: by_ticker[t].sort(key=lambda x:x['date'])

def prev_sox_date(twdate):
    # latest completed US session strictly before TW calendar date
    cand=[d for d in sox_dates if d < twdate]
    return cand[-1] if cand else None

# PIT 60-observation beta estimated on close-to-close Taiwan return vs aligned prior SOX return.
# Precompute daily aligned SOX shock for each TW date
aligned={d:sox_ret.get(prev_sox_date(d)) for d in by_date}

# per ticker rolling observations
hist=defaultdict(list)
for t,rows in by_ticker.items():
    prevc=None
    for r in rows:
        if prevc and aligned.get(r['date']) is not None:
            tr=r['close']/prevc-1
            hist[t].append((r['date'],aligned[r['date']],tr))
        prevc=r['close']

# beta before each date
beta_before={}
for t,obs in hist.items():
    sx=[]; ty=[]
    for d,sr,tr in obs:
        if len(sx)>=30:
            xx=sx[-60:]; yy=ty[-60:]
            mx=sum(xx)/len(xx); my=sum(yy)/len(yy)
            var=sum((x-mx)**2 for x in xx)
            beta=sum((x-mx)*(y-my) for x,y in zip(xx,yy))/var if var>0 else 0
            beta_before[(d,t)]=beta
        sx.append(sr);ty.append(tr)

# Build event candidates. We intentionally test a SMALL grid only, not optimize continuously.
# Rules: SOX shock threshold 1.5/2/3%; select high prior-beta stocks, equal-weight top N, buy TW open, hold H trading days, sell close.
thresholds=[0.015,0.02,0.03]
holds=[1,3,5]
topNs=[3,5,10]
sides=['UP','DOWN']

# date index for each ticker
idxmap={t:{r['date']:i for i,r in enumerate(rows)} for t,rows in by_ticker.items()}

results=[]
trades_out=[]
for side in sides:
  for th in thresholds:
    for hold in holds:
      for topN in topNs:
        capital=START_CAP; peak=capital; mdd=0; wins=0; events=0; gross_mults=[]
        monthly=defaultdict(lambda:1.0)
        # non-overlapping event portfolio so capital isn't double-counted
        busy_until='0000-00-00'
        for d in sorted(by_date):
            if d<=busy_until: continue
            shock=aligned.get(d)
            if shock is None: continue
            if side=='UP' and shock < th: continue
            if side=='DOWN' and shock > -th: continue
            cand=[]
            for r in by_date[d]:
                b=beta_before.get((d,r['ticker']))
                if b is None: continue
                cand.append((b,r))
            if not cand: continue
            # high sensitivity only; negative beta naturally excluded if enough positive names
            cand=sorted(cand,key=lambda z:z[0],reverse=True)[:topN]
            rets=[]; exits=[]
            for b,r in cand:
                rows=by_ticker[r['ticker']]; i=idxmap[r['ticker']][d]
                j=i+hold-1
                if j>=len(rows): continue
                exitr=rows[j]
                gross=exitr['close']/r['open']-1
                net=gross-COST
                rets.append(net); exits.append(exitr['date'])
            if not rets: continue
            port=sum(rets)/len(rets)
            old=capital; capital*=1+port
            peak=max(peak,capital); mdd=min(mdd,capital/peak-1)
            wins += port>0; events+=1; gross_mults.append(port)
            month=d[:7]; monthly[month]*=1+port
            busy_until=max(exits)
            trades_out.append({'side':side,'threshold':th,'hold':hold,'topN':topN,'entry':d,'exit':busy_until,'event_ret_net':port,'capital_after':capital,'n_stocks':len(rets),'sox_shock':shock})
        results.append({'side':side,'threshold':th,'hold':hold,'topN':topN,'events':events,'wins':wins,'win_rate':wins/events if events else None,'final_capital':capital,'total_return':capital/START_CAP-1,'mdd':mdd,'avg_event':sum(gross_mults)/len(gross_mults) if gross_mults else None,'monthly':json.dumps({m:v-1 for m,v in sorted(monthly.items())},ensure_ascii=False)})

# write
fields=list(results[0].keys())
with (OUT/'summary.csv').open('w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(results)
with (OUT/'event_trades.csv').open('w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=list(trades_out[0].keys()));w.writeheader();w.writerows(trades_out)

# ranking with guardrails: at least 8 events, prioritize final capital then lower MDD
valid=[r for r in results if r['events']>=8]
valid.sort(key=lambda r:(r['final_capital'],r['mdd']),reverse=True)
summary={'start_capital':START_CAP,'cost_round_trip':COST,'rules_tested':len(results),'selection':'prior-60-observation beta only, known before entry; non-overlapping events; equal-weight top N','best10':valid[:10],'note':'research screen only; if no robust positive capital curve across neighboring thresholds/holds, discard Q017 trading rule'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
