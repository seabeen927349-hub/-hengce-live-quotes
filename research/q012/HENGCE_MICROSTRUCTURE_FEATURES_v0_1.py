#!/usr/bin/env python3
import argparse, json, math
from collections import defaultdict, deque
from datetime import datetime, timezone

WINDOWS=(30,60,300)
EPS=1e-12

def micros_to_sec(us): return float(us)/1_000_000.0

def book_features(p):
    bids=p.get('bids') or []
    asks=p.get('asks') or []
    if not bids or not asks: return None
    bs=sum(float(x.get('size') or 0) for x in bids[:5])
    aS=sum(float(x.get('size') or 0) for x in asks[:5])
    bb=float(bids[0]['price']); ba=float(asks[0]['price'])
    b1=float(bids[0].get('size') or 0); a1=float(asks[0].get('size') or 0)
    mid=(bb+ba)/2
    micro=(ba*b1+bb*a1)/max(b1+a1,EPS)
    obi=(bs-aS)/max(bs+aS,EPS)
    return dict(mid=mid,microprice=micro,obi5=obi,bid5=bs,ask5=aS,best_bid=bb,best_ask=ba)

def aggressor(p):
    price=p.get('price'); bid=p.get('bid'); ask=p.get('ask')
    if price is None: return 0
    if ask is not None and float(price)>=float(ask): return 1
    if bid is not None and float(price)<=float(bid): return -1
    return 0

def load(paths):
    rows=[]
    for fp in paths:
        with open(fp,encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                r=json.loads(line); p=r.get('payload',{})
                t=p.get('time')
                if t is None: continue
                rows.append((micros_to_sec(t),r.get('channel'),p,r.get('validContinuous',True)))
    rows.sort(key=lambda x:x[0])
    return rows

def compute(rows):
    latest_book={}
    trades=deque()
    out=[]
    for t,ch,p,valid in rows:
        sym=p.get('symbol')
        if not sym or not valid: continue
        if ch=='books':
            bf=book_features(p)
            if bf: latest_book[sym]=(t,bf)
            continue
        if ch!='trades' or sym not in latest_book: continue
        side=aggressor(p); size=float(p.get('size') or 0)
        trades.append((t,sym,side,size))
        cutoff=t-max(WINDOWS)
        while trades and trades[0][0]<cutoff: trades.popleft()
        bt,bf=latest_book[sym]
        rec={'time':t,'symbol':sym,**bf,'trade_price':float(p.get('price') or math.nan),'trade_size':size,'aggressor':side}
        for w in WINDOWS:
            xs=[x for x in trades if x[1]==sym and x[0]>=t-w]
            buy=sum(sz for _,_,sd,sz in xs if sd>0); sell=sum(sz for _,_,sd,sz in xs if sd<0)
            tot=buy+sell
            rec[f'ati_{w}s']=(buy-sell)/max(tot,EPS)
            rec[f'aggr_vol_{w}s']=tot
            rec[f'net_aggr_{w}s']=buy-sell
        out.append(rec)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--out', required=True)
    args=ap.parse_args()
    rows=compute(load(args.files))
    with open(args.out,'w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'OK','rows':len(rows),'out':args.out}))
if __name__=='__main__': main()
