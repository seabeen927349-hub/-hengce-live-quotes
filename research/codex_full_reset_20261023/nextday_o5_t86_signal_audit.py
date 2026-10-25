#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures as cf
import json, math, statistics, time, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

import research.codex_full_reset_20261023.nextday_o3_delayed_close_overnight as o3

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_o5_t86_signal_audit_result.json'
PRIMARY_COST=o3.PRIMARY_COST
UA='Mozilla/5.0 (compatible; HENGCE-research-o5-t86-audit/1.0)'
PERIODS={'2024_DEV':o3.DEV,'2025_REUSED':o3.VAL,'2026_DIAGNOSTIC':o3.DIAG}

# Fixed BEFORE T86 outcomes are inspected. This is an orthogonal-signal audit, not
# a promoted model search. All six vetoes are simple sign/median rules.
RULES=(
 ('FOREIGN_ABOVE_MEDIAN', lambda x: x['foreign_rank']>=.50),
 ('TOTAL_ABOVE_MEDIAN', lambda x: x['total_rank']>=.50),
 ('TRUST_NONNEG', lambda x: x['trust_net']>=0),
 ('SIGN_BREADTH_2OF3', lambda x: x['sign_breadth']>=2),
 ('TOTAL_MEDIAN_AND_2OF3', lambda x: x['total_rank']>=.50 and x['sign_breadth']>=2),
 ('FOREIGN_MEDIAN_AND_TRUST_NONNEG', lambda x: x['foreign_rank']>=.50 and x['trust_net']>=0),
)


def ff(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

def _open_following_temp_redirects(url,timeout=40,max_redirects=5):
    """Engineering-only hardening for TWSE's occasional 307/308 responses."""
    current=url
    for _ in range(max_redirects+1):
        req=urllib.request.Request(current,headers={'User-Agent':UA,'Accept':'application/json'})
        try:
            return urllib.request.urlopen(req,timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code not in (301,302,303,307,308):
                raise
            loc=e.headers.get('Location')
            if not loc:
                raise
            current=urllib.parse.urljoin(current,loc)
    raise RuntimeError(f'TOO_MANY_REDIRECTS:{url}')

def fetch(date):
    q=urllib.parse.urlencode({'date':date.replace('-',''),'selectType':'ALL','response':'json'})
    url='https://www.twse.com.tw/rwd/zh/fund/T86?'+q
    last=None
    for attempt in range(4):
        try:
            with _open_following_temp_redirects(url,timeout=40) as resp:
                obj=json.loads(resp.read().decode('utf-8-sig'))
            if not isinstance(obj,dict) or obj.get('stat')!='OK':
                raise RuntimeError(f"bad_stat:{obj.get('stat') if isinstance(obj,dict) else type(obj)}")
            return date,obj
        except Exception as e:
            last=e; time.sleep(.8*(attempt+1))
    raise RuntimeError(f'T86_FETCH_FAILED:{date}:{type(last).__name__}:{last}')
def find_table(obj):
    if isinstance(obj,dict):
        f=obj.get('fields'); d=obj.get('data')
        if isinstance(f,list) and isinstance(d,list) and f and f[0]=='證券代號':
            return f,d
        for v in obj.values():
            z=find_table(v)
            if z:return z
    elif isinstance(obj,list):
        for v in obj:
            z=find_table(v)
            if z:return z
    return None
def parse(obj):
    z=find_table(obj)
    if not z:raise RuntimeError('T86_TABLE_NOT_FOUND')
    fields,data=z; ix={name:i for i,name in enumerate(fields)}
    names={
      'foreign_net':'外陸資買賣超股數(不含外資自營商)',
      'trust_net':'投信買賣超股數',
      'dealer_net':'自營商買賣超股數',
      'total_net':'三大法人買賣超股數',
    }
    miss=[v for v in names.values() if v not in ix]
    if miss:raise RuntimeError('T86_FIELDS_MISSING:'+','.join(miss))
    out={}
    for row in data:
        if not isinstance(row,list) or len(row)<len(fields):continue
        t=str(row[0]).strip()
        if not (len(t)==4 and t.isdigit()):continue
        q={}; ok=True
        for k,n in names.items():
            v=ff(row[ix[n]])
            if v is None:ok=False;break
            q[k]=v
        if ok:out[t]=q
    return out
def pct_rank(pairs):
    a=sorted(pairs,key=lambda z:(z[1],z[0])); n=len(a)
    return {t:(i+.5)/n for i,(t,_) in enumerate(a)} if n else {}
def basic(rs):
    xs=[r['gross_return']-PRIMARY_COST for r in rs]; n=len(xs)
    return {
      'trades':n,'wins':sum(x>0 for x in xs),'win_rate':sum(x>0 for x in xs)/n if n else None,
      'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
      'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,
    }
def in_period(r,p):return p[0]<=r['signal_date']<=p[1]

selected=[r for r in o3.selected if o3.DEV[0]<=r['signal_date']<=o3.DIAG[1]]
dates=sorted({r['signal_date'] for r in selected})
raw_by_date={}
with cf.ThreadPoolExecutor(max_workers=4) as ex:
    futs={ex.submit(fetch,d):d for d in dates}
    for fut in cf.as_completed(futs):
        d,obj=fut.result(); raw_by_date[d]=parse(obj)

chip={}; coverage={}
for d in dates:
    tab=raw_by_date[d]; rows=[]
    for t,q in tab.items():
        s=o3.raw.stock.get((d,t)); px=o3.raw.by.get(d,{}).get(t)
        if not s or not px or s['turn20']<o3.raw.TURNMIN:continue
        turn=px['turn']; close=px['c']
        if turn<=0 or close<=0:continue
        x=dict(q)
        for k in ('foreign_net','trust_net','dealer_net','total_net'):
            x[k+'_ratio']=q[k]*close/turn
        x['sign_breadth']=sum(q[k]>0 for k in ('foreign_net','trust_net','dealer_net'))
        rows.append((t,x))
    fr=pct_rank([(t,x['foreign_net_ratio']) for t,x in rows]); tr=pct_rank([(t,x['trust_net_ratio']) for t,x in rows]); dr=pct_rank([(t,x['dealer_net_ratio']) for t,x in rows]); tor=pct_rank([(t,x['total_net_ratio']) for t,x in rows])
    for t,x in rows:
        x.update({'foreign_rank':fr[t],'trust_rank':tr[t],'dealer_rank':dr[t],'total_rank':tor[t]}); chip[(d,t)]=x
    coverage[d]={'t86_tickers':len(tab),'eligible_ranked':len(rows)}

enriched=[]; missing=[]
for r in selected:
    x=chip.get((r['signal_date'],r['ticker']))
    if not x:missing.append({'signal_date':r['signal_date'],'ticker':r['ticker']});continue
    enriched.append({**r,**x})

rule_result={}
for name,fn in RULES:
    rule_result[name]={}
    for label,p in PERIODS.items():
        base=[r for r in enriched if in_period(r,p)]; keep=[r for r in base if fn(r)]
        bm=basic(base); km=basic(keep)
        rule_result[name][label]={
          'baseline':bm,'kept':km,'coverage':km['trades']/bm['trades'] if bm['trades'] else None,
          'win_lift_pp':(km['win_rate']-bm['win_rate'])*100 if km['win_rate'] is not None and bm['win_rate'] is not None else None,
          'mean_lift_pp':(km['mean_return']-bm['mean_return'])*100 if km['mean_return'] is not None and bm['mean_return'] is not None else None,
        }
def bands(feature,label,p):
    rs=sorted([r for r in enriched if in_period(r,p)],key=lambda r:(r[feature],r['signal_date'],r['ticker'])); out=[]
    for i in range(4):
        lo=math.floor(i*len(rs)/4); hi=math.floor((i+1)*len(rs)/4); g=rs[lo:hi]
        if g:out.append({'quartile':i+1,'feature_min':min(r[feature] for r in g),'feature_max':max(r[feature] for r in g),**basic(g)})
    return out
quartiles={f:{label:bands(f,label,p) for label,p in PERIODS.items()} for f in ('foreign_rank','total_rank')}

consistent=[]
for name in dict(RULES):
    ys=rule_result[name]
    if all(ys[l]['coverage'] is not None and ys[l]['coverage']>=.40 and ys[l]['win_lift_pp'] is not None and ys[l]['win_lift_pp']>0 for l in PERIODS):
        if ys['2026_DIAGNOSTIC']['kept']['win_rate'] is not None and ys['2026_DIAGNOSTIC']['kept']['win_rate']>=.55:consistent.append(name)

res={
 'status':'T86_ORTHOGONAL_SIGNAL_PRESENT' if consistent else 'T86_NO_LOCKED_CROSS_YEAR_SIGNAL','source_o3_run':40192720652,
 'purpose':'Fast existence test before expensive full historical chip backfill. Fixed sign/median vetoes only; no rule is promoted from this audit.',
 'pit':'T86 signal-date t data only; O3 entry remains predetermined t+1 close and exit t+2 open.',
 'dates_requested':len(dates),'events_requested':len(selected),'events_enriched':len(enriched),'missing_events':missing,
 'coverage_summary':{'min_eligible_ranked':min((v['eligible_ranked'] for v in coverage.values()),default=None),'median_eligible_ranked':statistics.median([v['eligible_ranked'] for v in coverage.values()]) if coverage else None},
 'locked_rules':[name for name,_ in RULES],'rule_results':rule_result,'rank_quartiles':quartiles,'consistent_locked_rules':consistent,
 'engineering_change':'Manual follow of HTTP 301/302/303/307/308 redirects with retry; model rules unchanged.',
 'research_boundary':'Diagnostic existence test on already-exposed historical periods. It cannot establish pristine OOS performance. If signal exists, O5 must be rebuilt from full daily history with a separately locked model.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O5_T86_AUDIT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
