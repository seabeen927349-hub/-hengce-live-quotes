from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path('research/nanmao_8150/output/8150_3y_twse_canonical.csv')
OUT = Path('research/nanmao_8150/output_damage_recovery_v3')
OUT.mkdir(parents=True, exist_ok=True)

SEL_START = pd.Timestamp('2023-10-27')
SEL_END = pd.Timestamp('2025-12-31')
OOS_START = pd.Timestamp('2026-01-01')
END = pd.Timestamp('2026-10-27')
CAPITAL = 1_000_000.0
HALF_COST = 0.002

LOOKBACKS = [40, 60, 90]
DAMAGES = [0.08, 0.10, 0.12, 0.14]
PATIENCE = [2, 3, 5]


def load_data():
    df = pd.read_csv(BASE)
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


def state_events(df, lookback, damage, patience):
    peak = df.AdjClose.rolling(lookback, min_periods=lookback).max()
    damaged = df.AdjClose <= peak * (1-damage)
    recovery = df.AdjClose > df.AdjHigh.shift(1)

    state = 'NORMAL'
    age = 0
    anchor_peak = np.nan
    events = []
    for i in range(len(df)):
        if not np.isfinite(peak.iloc[i]):
            continue
        if state == 'NORMAL':
            if bool(damaged.iloc[i]):
                state = 'DAMAGED'
                age = 1
                anchor_peak = float(peak.iloc[i])
                if age >= patience and i+1 < len(df):
                    events.append({'Type':'SELL','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'ExecIndex':i+1,
                                   'ExecDate':str(df.iloc[i+1].Date.date()),'ExecOpen':float(df.iloc[i+1].Open),
                                   'AnchorPeak':anchor_peak,'SignalClose':float(df.iloc[i].Close)})
                    state = 'WAIT_RESET'
        elif state == 'DAMAGED':
            if bool(recovery.iloc[i]):
                events.append({'Type':'RECOVERY_ESCAPE','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),
                               'ExecIndex':None,'ExecDate':None,'ExecOpen':None,'AnchorPeak':anchor_peak,
                               'SignalClose':float(df.iloc[i].Close)})
                state = 'NORMAL'
                age = 0
            else:
                age += 1
                if age >= patience and i+1 < len(df):
                    events.append({'Type':'SELL','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'ExecIndex':i+1,
                                   'ExecDate':str(df.iloc[i+1].Date.date()),'ExecOpen':float(df.iloc[i+1].Open),
                                   'AnchorPeak':anchor_peak,'SignalClose':float(df.iloc[i].Close)})
                    state = 'WAIT_RESET'
                    age = 0
        else:  # WAIT_RESET
            if bool(recovery.iloc[i]):
                if i+1 < len(df):
                    events.append({'Type':'RESET','SignalIndex':i,'SignalDate':str(df.iloc[i].Date.date()),'ExecIndex':i+1,
                                   'ExecDate':str(df.iloc[i+1].Date.date()),'ExecOpen':float(df.iloc[i+1].Open),
                                   'AnchorPeak':float(peak.iloc[i]),'SignalClose':float(df.iloc[i].Close)})
                state = 'NORMAL'
                age = 0

    return pd.DataFrame(events), peak, damaged, recovery, state, age


def enrich_sell_outcomes(df, events):
    sells = events[events.Type=='SELL'].copy()
    if sells.empty:
        return sells
    rows=[]
    for _,e in sells.iterrows():
        i=int(e.SignalIndex); ex=int(e.ExecIndex); px=float(e.ExecOpen)
        r=e.to_dict()
        for h in [10,20,40]:
            end=ex+h
            if end>=len(df) or df.iloc[end].Date>END:
                r[f'complete{h}']=False
                continue
            seg=df.iloc[ex:end+1]
            r[f'complete{h}']=True
            r[f'HoldReturn{h}']=float(df.iloc[end].Close/px-1)
            r[f'MAE{h}']=float(seg.Close.min()/px-1)
            r[f'MFE{h}']=float(seg.Close.max()/px-1)
            r[f'Deep8_{h}']=bool(seg.Close.min()<=px*0.92)
            r[f'Rebound10_{h}']=bool(seg.Close.max()>=px*1.10)
            r[f'ReclaimPeak98_{h}']=bool(seg.AdjClose.max()>=float(e.AnchorPeak)*0.98)
        rows.append(r)
    return pd.DataFrame(rows)


def sell_summary(sells,start,end):
    if sells.empty:return {'n20':0}
    x=sells.copy(); x['SignalDateTS']=pd.to_datetime(x.SignalDate)
    x=x[(x.SignalDateTS>=start)&(x.SignalDateTS<=end)&(x.complete20==True)]
    if x.empty:return {'n20':0}
    out={'n20':len(x),'median_hold20':float(x.HoldReturn20.median()),'sell_better20_share':float((x.HoldReturn20<0).mean()),
         'deep8_20_share':float(x.Deep8_20.mean()),'rebound10_20_share':float(x.Rebound10_20.mean()),
         'reclaim_peak98_20_share':float(x.ReclaimPeak98_20.mean()),'median_mae20':float(x.MAE20.median()),'median_mfe20':float(x.MFE20.median())}
    for yr in [2024,2025,2026]:
        y=x[x.SignalDateTS.dt.year==yr]
        out[f'n_{yr}']=len(y)
        out[f'sell_better20_share_{yr}']=float((y.HoldReturn20<0).mean()) if len(y) else np.nan
        out[f'median_hold20_{yr}']=float(y.HoldReturn20.median()) if len(y) else np.nan
    return out


def lifecycle_trades(df,events,start,end):
    ev=events.copy(); ev['SignalDateTS']=pd.to_datetime(ev.SignalDate)
    ev=ev[(ev.SignalDateTS>=start)&(ev.SignalDateTS<=end)].sort_values('SignalIndex')
    holding=False; entry_px=None; entry_date=None; shares=0; rows=[]
    for _,e in ev.iterrows():
        typ=e.Type
        if typ=='RESET' and not holding:
            ex=int(e.ExecIndex)
            if ex>=len(df) or df.iloc[ex].Date>end: continue
            px=float(e.ExecOpen); lots=int(CAPITAL//(px*1000))
            if lots<1:continue
            holding=True; entry_px=px; entry_date=df.iloc[ex].Date; shares=lots*1000
        elif typ=='SELL' and holding:
            ex=int(e.ExecIndex)
            if ex>=len(df) or df.iloc[ex].Date>end:continue
            px=float(e.ExecOpen); exit_date=df.iloc[ex].Date
            costs=(entry_px+px)*shares*HALF_COST
            pnl=(px-entry_px)*shares-costs
            rows.append({'EntryDate':str(entry_date.date()),'Entry':entry_px,'ExitDate':str(exit_date.date()),'Exit':px,
                         'Shares':shares,'PnL':pnl})
            holding=False; entry_px=None; entry_date=None; shares=0
    return pd.DataFrame(rows), {'holding':holding,'entry':entry_px,'entry_date':str(entry_date.date()) if holding else None,'shares':shares}


def life_summary(t):
    if t.empty:return {'n':0,'pnl':0.0,'wr':np.nan,'pf':np.nan,'mdd':0.0,'remove_best1':np.nan}
    p=t.PnL.astype(float); wins=p[p>0].sum(); losses=-p[p<0].sum(); pf=wins/losses if losses>0 else np.inf
    cum=p.cumsum(); mdd=float((cum-cum.cummax()).min())
    return {'n':len(p),'pnl':float(p.sum()),'wr':float((p>0).mean()),'pf':float(pf),'mdd':mdd,
            'remove_best1':float(p.sum()-p.max()) if len(p)>1 else np.nan}


def eligible(m):
    if m.get('n20',0)<5:return False
    if m['sell_better20_share']<0.60:return False
    if m['median_hold20']>=0:return False
    if m['reclaim_peak98_20_share']>0.45:return False
    for y in [2024,2025]:
        if m.get(f'n_{y}',0)>=2 and m.get(f'sell_better20_share_{y}',0)<0.50:return False
    return True


def main():
    df=load_data(); rows=[]; cache={}
    for lb in LOOKBACKS:
        for d in DAMAGES:
            for p in PATIENCE:
                ev,*_=state_events(df,lb,d,p); sells=enrich_sell_outcomes(df,ev); pre=sell_summary(sells,SEL_START,SEL_END)
                lt,_=lifecycle_trades(df,ev,SEL_START,SEL_END); lm=life_summary(lt)
                row={'lookback':lb,'damage':d,'patience':p,**pre,**{f'life_{k}':v for k,v in lm.items()}}
                row['eligible_pre']=eligible(pre)
                rows.append(row); cache[(lb,d,p)]=(ev,sells)
    grid=pd.DataFrame(rows)
    neigh=[]
    for _,r in grid.iterrows():
        n=grid[(grid.index!=r.name)&(((grid.lookback==r.lookback)&(grid.patience==r.patience)&
             (np.isclose(grid.damage,r.damage-.02)|np.isclose(grid.damage,r.damage+.02)))|
             ((np.isclose(grid.damage,r.damage))&(grid.patience==r.patience)&grid.lookback.isin([r.lookback-20,r.lookback+20,r.lookback-30,r.lookback+30]))|
             ((grid.lookback==r.lookback)&np.isclose(grid.damage,r.damage)&grid.patience.isin([r.patience-1,r.patience+1,r.patience-2,r.patience+2])))]
        neigh.append(int(n.eligible_pre.sum()))
    grid['eligible_neighbor_count']=neigh; grid['plateau_pre']=grid.eligible_pre&(grid.eligible_neighbor_count>=2)
    cand=grid[grid.plateau_pre].copy()
    if len(cand):
        cand['score']=cand.sell_better20_share*3-cand.reclaim_peak98_20_share*2-cand.rebound10_20_share-cand.median_hold20*2
        sel=cand.sort_values(['score','eligible_neighbor_count','n20'],ascending=False).iloc[0]; status='PRE2026_ELIGIBLE_PLATEAU'
    else:
        f=grid[grid.n20>=5].copy(); f['score']=f.sell_better20_share.fillna(0)*3-f.reclaim_peak98_20_share.fillna(1)*2-f.rebound10_20_share.fillna(1)-f.median_hold20.fillna(0)*2
        sel=f.sort_values(['score','n20'],ascending=False).iloc[0]; status='NO_PRE2026_ELIGIBLE_PLATEAU'
    lb=int(sel.lookback); d=float(sel.damage); p=int(sel.patience)
    ev,sells=cache[(lb,d,p)]
    pre=sell_summary(sells,SEL_START,SEL_END); oos=sell_summary(sells,OOS_START,END)
    pretr,prestate=lifecycle_trades(df,ev,SEL_START,SEL_END); oostr,oosstate=lifecycle_trades(df,ev,OOS_START,END)
    prelife=life_summary(pretr); ooslife=life_summary(oostr)
    oos_ok=(oos.get('n20',0)>=3 and oos.get('sell_better20_share',0)>=.5 and oos.get('median_hold20',1)<0 and oos.get('reclaim_peak98_20_share',1)<=.5)
    authority='FREEZE_CANDIDATE' if status=='PRE2026_ELIGIBLE_PLATEAU' and oos_ok else 'NOT_FREEZE'

    # Current structural state by replay.
    _,peak,damaged,recovery,state,age=state_events(df,lb,d,p)
    last=df.iloc[-1]
    current={'date':str(last.Date.date()),'close':float(last.Close),'state':state,'damage_now':float(last.AdjClose/peak.iloc[-1]-1),
             'peak':float(peak.iloc[-1]),'damage_line':float(peak.iloc[-1]*(1-d)),'recovery_today':bool(recovery.iloc[-1]),'age':int(age)}

    grid.to_csv(OUT/'GRID_PRE2026.csv',index=False); ev.to_csv(OUT/'SELECTED_EVENTS_FULL3Y.csv',index=False); sells.to_csv(OUT/'SELECTED_SELL_OUTCOMES.csv',index=False)
    pretr.to_csv(OUT/'LIFECYCLE_PRE2026.csv',index=False); oostr.to_csv(OUT/'LIFECYCLE_OOS2026.csv',index=False)
    spec={'ticker':'8150','mechanism':'damage -> recovery proof (Close > prior High) or failure -> SELL; after SELL first recovery proof -> RESET',
          'selected':{'lookback':lb,'damage':d,'patience':p,'status':status},'pre2026_sell':pre,'oos2026_sell':oos,
          'pre2026_lifecycle':prelife,'oos2026_lifecycle':ooslife,'current':current,'authority':authority,
          'governance':{'2026_used_for_selection':False,'single_stock_only':True,'no_indicator_layer':True}}
    (OUT/'SPEC.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=True),encoding='utf-8')
    print(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=True))

if __name__=='__main__':main()
