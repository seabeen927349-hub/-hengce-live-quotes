#!/usr/bin/env python3
from __future__ import annotations

import json, time, urllib.parse, urllib.request

DATES = ('20240103','20250103','20261022')
BASE = 'https://www.twse.com.tw/rwd/zh'
ENDPOINTS = {
    'T86': ('fund/T86', {'selectType':'ALL'}),
    'MI_MARGN': ('marginTrading/MI_MARGN', {'selectType':'ALL'}),
    'TWT93U': ('marginTrading/TWT93U', {}),
}
UA = 'Mozilla/5.0 (compatible; HENGCE-research-o5-probe/1.0)'


def fetch(url):
    req=urllib.request.Request(url, headers={'User-Agent':UA,'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw=resp.read()
    return json.loads(raw.decode('utf-8-sig'))


def table_summaries(obj):
    out=[]
    if isinstance(obj,dict):
        if isinstance(obj.get('fields'),list) and isinstance(obj.get('data'),list):
            fields=obj.get('fields') or []; data=obj.get('data') or []
            sample=None
            for row in data:
                if isinstance(row,list) and row and str(row[0]).strip()=='2330':
                    sample=row[:min(len(row),20)]; break
            if sample is None and data:
                sample=data[0][:min(len(data[0]),20)] if isinstance(data[0],list) else data[0]
            out.append({'title':obj.get('title'),'fields':fields,'rows':len(data),'sample':sample})
        for k,v in obj.items():
            if k not in ('fields','data'):
                out.extend(table_summaries(v))
    elif isinstance(obj,list):
        for v in obj:
            if isinstance(v,(dict,list)):
                out.extend(table_summaries(v))
    return out

results={}
for date in DATES:
    results[date]={}
    for name,(path,extra) in ENDPOINTS.items():
        q={'date':date,'response':'json',**extra}
        url=f"{BASE}/{path}?{urllib.parse.urlencode(q)}"
        try:
            obj=fetch(url)
            results[date][name]={
                'ok': True,
                'stat': obj.get('stat') if isinstance(obj,dict) else None,
                'date': obj.get('date') if isinstance(obj,dict) else None,
                'tables': table_summaries(obj)[:8],
            }
        except Exception as e:
            results[date][name]={'ok':False,'error':f'{type(e).__name__}:{e}'}
        time.sleep(.4)
print('O5_CHIP_PROBE='+json.dumps(results,ensure_ascii=False,separators=(',',':')))
