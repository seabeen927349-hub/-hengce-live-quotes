from __future__ import annotations

import json, math, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

TICKER = '6415'
NAME = '矽力*-KY'
START = pd.Timestamp('2023-10-27')
SEL_END = pd.Timestamp('2025-12-31')
OOS_START = pd.Timestamp('2026-01-01')
END = pd.Timestamp('2026-10-27')
WARMUP_START = pd.Timestamp('2023-05-01')
OUT = Path('research/silergy_6415/output_sell_v1')
OUT.mkdir(parents=True, exist_ok=True)
S = requests.Session()
S.headers.update({'User-Agent':'Mozilla/5.0 HENGCE/6415-3Y'})


def month_iter(start,end):
    y,m=start.year,start.month
    while (y,m) <= (end.year,end.month):
        yield y,m
        m += 1
        if m==13:
            y += 1; m=1


def num(x):
    s=str(x).replace(',','').strip()
    try:return float(s)
    except:return np.nan


def roc_date(s):
    y,m,d=s.split('/')
    return pd.Timestamp(int(y)+1911,int(m),int(d))


def fetch_twse():
    rows=[]; receipt=[]
    for y,m in month_iter(WARMUP_START,END):
        u='https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY'
        p={'date':f'{y}{m:02d}01','stockNo':TICKER,'response':'json'}
        payload=None; err=None
        for k in range(5):
            try:
                r=S.get(u,params=p,timeout=30); r.raise_for_status(); payload=r.json(); break
            except Exception as e:
                err=repr(e); time.sleep(1+k)
        if payload is None: raise RuntimeError(f'TWSE {y}-{m:02d}: {err}')
        data=payload.get('data',[]) or []
        receipt.append({'month':f'{y}-{m:02d}','stat':payload.get('stat'),'rows':len(data)})
        for r in data:
            if len(r)<9: continue
            rows.append({'Date':roc_date(r[0]),'Volume':num(r[1]),'Open':num(r[3]),'High':num(r[4]),'Low':num(r[5]),'Close':num(r[6])})
        time.sleep(.12)
    df=pd.DataFrame(rows).drop_duplicates('Date').sort_values('Date').reset_index(drop=True)
    df=df[(df.Date>=WARMUP_START)&(df.Date<=END)].copy()
    (OUT/'TWSE_FETCH_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    if df.empty or df.Date.max()<END: raise RuntimeError(f'incomplete max={df.Date.max() if len(df) else None}')
    return df


def fetch_dividends():
    p1=int(datetime(2023,1,1,tzinfo=timezone.utc).timestamp())
    p2=int(datetime(2026,10,28,tzinfo=timezone.utc).timestamp())
    u=f'https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}.TW'
    try:
        r=S.get(u,params={'period1':p1,'period2':p2,'interval':'1d','events':'div,splits'},timeout=30); r.raise_for_status()
        res=r.json()['chart']['result'][0]
        out=[]
        for ev in (res.get('events',{}).get('dividends',{}) or {}).values():
            dt=pd.Timestamp(datetime.fromtimestamp(int(ev['date']),tz=timezone.utc)).tz_convert('Asia/Taipei').tz_localize(None).normalize()
            out.append({'Date':str(dt.date()),'Amount':float(ev['amount'])})
        return sorted(out,key=lambda x:x['Date'])
    except Exception as e:
        return [{'error':repr(e)}]


def adjust(df,divs):
    x=df.copy()
    for c in ['Open','High','Low','Close']: x['Adj'+c]=x[c].astype(float)
    audit=[]
    for ev in [z for z in divs if 'Date' in z]:
        d=pd.Timestamp(ev['Date']); amt=float(ev['Amount'])
        prev=x[x.Date<d].tail(1)
        if prev.empty: continue
        pc=float(prev.iloc[0].Close)
        if pc<=amt or pc<=0: continue
        f=(pc-amt)/pc; mask=x.Date<d
        for c in ['Open','High','Low','Close']: x.loc[mask,'Adj'+c] *= f
        audit.append({**ev,'prev_close':pc,'factor':f})
    (OUT/'DIVIDEND_ADJUSTMENT_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return x


def events(df,lookback,damage,confirm):
    peak=df.AdjClose.rolling(lookback,min_periods=lookback).max()
    damaged=df.AdjClose <= peak*(1-damage)
    recovery=df.AdjClose > df.AdjHigh.shift(1)
    state='NORMAL'; count=0; anchor=np.nan; out=[]
    for i in range(len(df)):
        if not np.isfinite(peak.iloc[i]): continue
        if state=='NORMAL':
            if bool(damaged.iloc[i]):
                state='DAMAGED'; count=1; anchor=float(peak.iloc[i])
                if count>=confirm and i+1<len(df):
                    out.append({'Type':'SELL','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'ExecIndex':i+1,'ExecDate':str(df.iloc[i+1].Date.date()),'ExecOpen':float(df.iloc[i+1].Open),'AnchorPeak':anchor,'SignalClose':float(df.iloc[i].Close)})
                    state='WAIT_RESET'; count=0
        elif state=='DAMAGED':
            if bool(recovery.iloc[i]):
                out.append({'Type':'RECOVERY_ESCAPE','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'AnchorPeak':anchor,'SignalClose':float(df.iloc[i].Close)})
                state='NORMAL'; count=0
            elif bool(damaged.iloc[i]):
                count += 1
                if count>=confirm and i+1<len(df):
                    out.append({'Type':'SELL','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'ExecIndex':i+1,'ExecDate':str(df.iloc[i+1].Date.date()),'ExecOpen':float(df.iloc[i+1].Open),'AnchorPeak':anchor,'SignalClose':float(df.iloc[i].Close)})
                    state='WAIT_RESET'; count=0
            else:
                state='NORMAL'; count=0
        else:
            if bool(recovery.iloc[i]):
                if i+1<len(df):
                    out.append({'Type':'RESET','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'ExecIndex':i+1,'ExecDate':str(df.iloc[i+1].Date.date()),'ExecOpen':float(df.iloc[i+1].Open),'AnchorPeak':float(peak.iloc[i]),'SignalClose':float(df.iloc[i].Close)})
                state='NORMAL'; count=0
    return pd.DataFrame(out), peak, damaged, recovery, state, count


def enrich(df,ev):
    if ev.empty:return ev
    rows=[]
    for _,e in ev[ev.Type=='SELL'].iterrows():
        ex=int(e.ExecIndex); px=float(e.ExecOpen); r=e.to_dict()
        for h in [10,20,40]:
            end=ex+h
            if end>=len(df) or df.iloc[end].Date>END:
                r[f'complete{h}']=False; continue
            seg=df.iloc[ex:end+1]
            r[f'complete{h}']=True
            r[f'HoldReturn{h}']=float(df.iloc[end].Close/px-1)
            r[f'MAE{h}']=float(seg.Close.min()/px-1)
            r[f'MFE{h}']=float(seg.Close.max()/px-1)
            r[f'Deep8_{h}']=bool(seg.Close.min()<=px*.92)
            r[f'Rebound10_{h}']=bool(seg.Close.max()>=px*1.10)
            r[f'ReclaimPeak98_{h}']=bool(seg.AdjClose.max()>=float(e.AnchorPeak)*.98)
        rows.append(r)
    return pd.DataFrame(rows)


def summarize(sells,start,end):
    if sells.empty:return {'n20':0}
    x=sells.copy(); x['D']=pd.to_datetime(x.SignalDate)
    x=x[(x.D>=start)&(x.D<=end)&(x.complete20==True)]
    if x.empty:return {'n20':0}
    o={'n20':int(len(x)),'median_hold20':float(x.HoldReturn20.median()),'mean_hold20':float(x.HoldReturn20.mean()),
       'sell_better20_share':float((x.HoldReturn20<0).mean()),'deep8_20_share':float(x.Deep8_20.mean()),
       'rebound10_20_share':float(x.Rebound10_20.mean()),'reclaim_peak98_20_share':float(x.ReclaimPeak98_20.mean()),
       'median_mae20':float(x.MAE20.median()),'median_mfe20':float(x.MFE20.median())}
    for y in [2024,2025,2026]:
        z=x[x.D.dt.year==y]; o[f'n_{y}']=int(len(z)); o[f'sell_better20_share_{y}']=float((z.HoldReturn20<0).mean()) if len(z) else np.nan; o[f'median_hold20_{y}']=float(z.HoldReturn20.median()) if len(z) else np.nan
    return o


def eligible(m):
    if m.get('n20',0)<5:return False
    if m['sell_better20_share']<.60 or m['median_hold20']>=0 or m['reclaim_peak98_20_share']>.45:return False
    for y in [2024,2025]:
        if m.get(f'n_{y}',0)>=2 and m.get(f'sell_better20_share_{y}',0)<.50:return False
    return True


def main():
    raw=fetch_twse(); divs=fetch_dividends(); df=adjust(raw,divs)
    three=df[(df.Date>=START)&(df.Date<=END)].copy(); three.to_csv(OUT/'6415_3Y_TWSE.csv',index=False,encoding='utf-8-sig')
    receipt={'ticker':TICKER,'name':NAME,'rows_3y':int(len(three)),'min_date':str(three.Date.min().date()),'max_date':str(three.Date.max().date()),'duplicates':int(three.Date.duplicated().sum()),'missing_ohlc':int(three[['Open','High','Low','Close']].isna().any(axis=1).sum()),'selection_end':str(SEL_END.date()),'oos_start':str(OOS_START.date()),'price_source':'TWSE STOCK_DAY'}
    (OUT/'DATA_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')

    rows=[]; cache={}
    for lb in [40,60,90,120]:
      for d in [.08,.10,.12,.14,.16,.18,.20]:
       for c in [1,2,3]:
        ev,*_=events(df,lb,d,c); sells=enrich(df,ev); pre=summarize(sells,START,SEL_END)
        row={'lookback':lb,'damage':d,'confirm':c,**pre}; row['eligible_pre']=eligible(pre); rows.append(row); cache[(lb,d,c)]=(ev,sells)
    grid=pd.DataFrame(rows)
    neigh=[]
    for _,r in grid.iterrows():
        n=grid[(grid.index!=r.name)&(
          ((grid.lookback==r.lookback)&(grid.confirm==r.confirm)&(np.isclose(grid.damage,r.damage-.02)|np.isclose(grid.damage,r.damage+.02))) |
          ((np.isclose(grid.damage,r.damage))&(grid.confirm==r.confirm)&grid.lookback.isin([r.lookback-30,r.lookback+30,r.lookback-20,r.lookback+20])) |
          ((grid.lookback==r.lookback)&np.isclose(grid.damage,r.damage)&grid.confirm.isin([r.confirm-1,r.confirm+1]))
        )]
        neigh.append(int(n.eligible_pre.sum()))
    grid['eligible_neighbor_count']=neigh; grid['plateau_pre']=grid.eligible_pre&(grid.eligible_neighbor_count>=2)
    grid.to_csv(OUT/'SELL_GRID_PRE2026.csv',index=False)
    cand=grid[grid.plateau_pre].copy()
    if len(cand):
        cand['score']=cand.sell_better20_share*3-cand.reclaim_peak98_20_share*2-cand.rebound10_20_share-cand.median_hold20*2
        sel=cand.sort_values(['score','eligible_neighbor_count','n20'],ascending=False).iloc[0]; status='PRE2026_ELIGIBLE_PLATEAU'
    else:
        f=grid[grid.n20>=5].copy(); f['score']=f.sell_better20_share.fillna(0)*3-f.reclaim_peak98_20_share.fillna(1)*2-f.rebound10_20_share.fillna(1)-f.median_hold20.fillna(0)*2
        sel=f.sort_values(['score','n20'],ascending=False).iloc[0]; status='NO_PRE2026_ELIGIBLE_PLATEAU'
    lb=int(sel.lookback); d=float(sel.damage); c=int(sel.confirm); ev,sells=cache[(lb,d,c)]
    pre=summarize(sells,START,SEL_END); oos=summarize(sells,OOS_START,END)
    oos_ok=(oos.get('n20',0)>=3 and oos.get('sell_better20_share',0)>=.5 and oos.get('median_hold20',1)<0 and oos.get('reclaim_peak98_20_share',1)<=.5)
    authority='FREEZE_CANDIDATE' if status=='PRE2026_ELIGIBLE_PLATEAU' and oos_ok else 'NOT_FREEZE'
    ev2,peak,damaged,recovery,state,count=events(df,lb,d,c); last=df.iloc[-1]
    current={'date':str(last.Date.date()),'open':float(last.Open),'high':float(last.High),'low':float(last.Low),'close':float(last.Close),'volume':float(last.Volume),'lookback':lb,'peak_adj_close':float(peak.iloc[-1]),'damage_from_peak':float(last.AdjClose/peak.iloc[-1]-1),'sell_line':float(peak.iloc[-1]*(1-d)),'damaged_today':bool(damaged.iloc[-1]),'recovery_today':bool(recovery.iloc[-1]),'state':state,'confirm_counter':int(count)}
    spec={'ticker':TICKER,'name':NAME,'method':'buy-independent rolling-peak structural damage with recovery/reset','selected':{'lookback':lb,'damage':d,'confirm':c,'status':status},'pre2026':pre,'oos2026':oos,'current':current,'authority':authority,'governance':{'2026_used_for_selection':False,'single_stock_only':True,'no_indicator_layer':True}}
    sells.to_csv(OUT/'SELECTED_SELL_OUTCOMES_FULL3Y.csv',index=False); ev2.to_csv(OUT/'SELECTED_EVENTS_FULL3Y.csv',index=False)
    (OUT/'SPEC.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=True),encoding='utf-8')
    print(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=True))

if __name__=='__main__': main()
