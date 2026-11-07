#!/usr/bin/env python3
"""Diagnose one failing FinMind TDCC 2023 tier snapshot, no licensed raw output."""
import os,json,urllib.parse,urllib.request,collections
d='2023-04-21'
q=urllib.parse.urlencode({'dataset':'TaiwanStockHoldingSharesPer','start_date':d})
req=urllib.request.Request('https://api.finmindtrade.com/api/v4/data?'+q,headers={'Authorization':'Bearer '+os.environ['FINMIND_TOKEN']})
with urllib.request.urlopen(req,timeout=180) as r:o=json.load(r)
assert o.get('status')==200 and isinstance(o.get('data'),list)
bad=[]
for x in o['data']:
    try:p=float(x['percent']);n=int(x['people']);u=int(x['unit'])
    except Exception:bad.append({'ticker':x.get('stock_id'),'level':x.get('HoldingSharesLevel'),'reason':'bad_numeric'});continue
    lv=str(x['HoldingSharesLevel'])
    adj='差異數調整' in lv
    if n<0 or (not adj and (p<0 or p>100 or u<0)):
        bad.append({'ticker':x.get('stock_id'),'level':lv,'percent':p,'people':n,'unit':u,'reason':'outside_tier_gate'})
print('HENGCE_TDCC_2023_DIAG',json.dumps({'date':d,'total_rows':len(o['data']),'bad_count':len(bad),'examples':bad[:25]},ensure_ascii=False))
