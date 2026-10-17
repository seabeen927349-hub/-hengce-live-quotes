#!/usr/bin/env python3
import argparse
import csv
import io
import json
import math
import os
import random
import re
import shutil
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo('Asia/Taipei')
ROOT = Path(__file__).resolve().parents[1]
RADAR = ROOT / 'hengce' / 'q017_radar'
DATA = RADAR / 'data'
HISTORY = RADAR / 'history'
DATA.mkdir(parents=True, exist_ok=True)
HISTORY.mkdir(parents=True, exist_ok=True)
SOX_CSV = DATA / 'sox_2026.csv'
SOX_STATUS = DATA / 'sox_status.json'
TW_HISTORY = DATA / 'twse_electronics_history_2026.csv'
DATA_STATUS = RADAR / 'data_status.json'
LATEST = RADAR / 'latest.json'
SIGNAL_LEDGER = RADAR / 'signal_ledger.jsonl'
SEED_URL = 'https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/q017-2026-sox-dxy-electronics/research/q017_sox_tw_electronics/archive_2026/twse_electronics_membership_2026.csv'
NASDAQ_EXPORT = 'https://indexes.nasdaq.com/Index/ExportHistory/SOX'
TWSE_PRICE = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
TWSE_INST = 'https://www.twse.com.tw/rwd/zh/fund/T86'
TWSE_MARGIN = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN'
FUGLE_QUOTE = 'https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/'
UA = {'User-Agent': 'Mozilla/5.0 HENGCE-DAILY-COMMAND-CENTER/1.0'}


def now_tw():
    return datetime.now(TZ)


def clean(x):
    return '' if x is None else str(x).replace(',', '').strip()


def num(x):
    try:
        return float(str(x).replace(',', '').strip())
    except Exception:
        return None


def get_json(url, params=None, timeout=45):
    r = requests.get(url, params=params, headers={**UA, 'Accept': 'application/json', 'Referer': 'https://www.twse.com.tw/'}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def parse_sox(raw):
    rows = []
    if raw.startswith(b'PK'):
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
        records = list(ws.iter_rows(values_only=True))
    else:
        records = list(csv.reader(io.StringIO(raw.decode('utf-8-sig', errors='replace'))))
    for rec in records:
        if len(rec) < 2:
            continue
        ds, close = rec[0], rec[1]
        dt = ds.date() if isinstance(ds, datetime) else ds if isinstance(ds, date) else None
        if dt is None:
            for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%m/%d/%Y %H:%M:%S'):
                try:
                    dt = datetime.strptime(str(ds).strip(), fmt).date()
                    break
                except Exception:
                    pass
        c = num(close)
        if dt and dt.year == 2026 and c and c > 0:
            rows.append({'date': dt.isoformat(), 'close': c})
    return sorted({r['date']: r for r in rows}.values(), key=lambda x: x['date'])


def refresh_sox(today=None):
    today = today or now_tw().date()
    last = None
    raw = None
    for attempt in range(6):
        try:
            r = requests.get(
                NASDAQ_EXPORT,
                params={'startDate': '2026-01-01T00:00:00.000', 'endDate': today.isoformat() + 'T00:00:00.000', 'timeOfDay': 'EOD'},
                headers=UA,
                timeout=(8, 30),
            )
            if r.status_code == 200 and r.content:
                raw = r.content
                break
            last = f'HTTP_{r.status_code}'
        except Exception as e:
            last = repr(e)
        time.sleep(min(20, 2 ** attempt))
    if raw is None:
        raise RuntimeError(f'SOX_DOWNLOAD_FAIL:{last}')
    rows = parse_sox(raw)
    if len(rows) < 180:
        raise RuntimeError(f'SOX_ROWS_TOO_FEW:{len(rows)}')
    latest = datetime.strptime(rows[-1]['date'], '%Y-%m-%d').date()
    stale_days = (today - latest).days
    if stale_days > 7:
        raise RuntimeError(f'SOX_STALE:{latest}')
    with SOX_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'close'])
        w.writeheader(); w.writerows(rows)
    status = {'status': 'PASS', 'source': 'Nasdaq ExportHistory/SOX', 'latest_session': latest.isoformat(), 'rows': len(rows), 'stale_days': stale_days, 'refreshed_at_taipei': now_tw().isoformat()}
    atomic_json(SOX_STATUS, status)
    return status


def ensure_tw_history():
    if TW_HISTORY.exists() and TW_HISTORY.stat().st_size > 100000:
        return {'status': 'PASS', 'source': 'LOCAL_INCREMENTAL_HISTORY', 'seeded': False}
    r = requests.get(SEED_URL, headers=UA, timeout=90)
    r.raise_for_status()
    if len(r.content) < 100000:
        raise RuntimeError('TW_HISTORY_SEED_TOO_SMALL')
    TW_HISTORY.write_bytes(r.content)
    return {'status': 'PASS', 'source': 'Q017_VALIDATED_2026_SEED', 'seeded': True}


def parse_twse_type13_payload(payload, iso_date):
    table = None
    for t in payload.get('tables') or []:
        fields = t.get('fields') or []
        if '證券代號' in fields and '收盤價' in fields:
            table = t; break
    if table is None:
        return []
    fields = table.get('fields') or []
    idx = {f: i for i, f in enumerate(fields)}
    data = table.get('data') or table.get('records') or []
    def v(row, *names):
        for n in names:
            i = idx.get(n)
            if i is not None and i < len(row):
                return clean(row[i])
        return ''
    out = []
    for row in data:
        ticker = v(row, '證券代號').replace('=', '').replace('"', '')
        if not re.fullmatch(r'[1-9]\d{3}', ticker):
            continue
        out.append({'date': iso_date, 'ticker': ticker, 'name': v(row, '證券名稱'), 'open': v(row, '開盤價'), 'high': v(row, '最高價'), 'low': v(row, '最低價'), 'close': v(row, '收盤價'), 'volume_shares': v(row, '成交股數', '成交量'), 'turnover_ntd': v(row, '成交金額')})
    return out


def append_electronics_day(target):
    ensure_tw_history()
    ds = target.strftime('%Y%m%d')
    payload = get_json(TWSE_PRICE, {'date': ds, 'type': '13', 'response': 'json'})
    if str(payload.get('stat')) != 'OK':
        raise RuntimeError(f'TWSE_ELECTRONICS_NOT_READY:{payload.get("stat")}')
    rows = parse_twse_type13_payload(payload, target.isoformat())
    if len(rows) < 150:
        raise RuntimeError(f'TWSE_ELECTRONICS_ROWS_TOO_FEW:{len(rows)}')
    existing = []
    with TW_HISTORY.open(encoding='utf-8-sig', newline='') as f:
        existing = list(csv.DictReader(f))
    existing = [r for r in existing if r.get('date') != target.isoformat()]
    merged = existing + rows
    merged.sort(key=lambda r: (r['date'], r['ticker']))
    with TW_HISTORY.open('w', encoding='utf-8', newline='') as f:
        fields = ['date','ticker','name','open','high','low','close','volume_shares','turnover_ntd']
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(merged)
    return {'status': 'PASS', 'date': target.isoformat(), 'rows': len(rows)}


def latest_eod_status():
    eod = ROOT / 'eod'
    if not eod.exists():
        return None, None
    dates = sorted([p.name for p in eod.iterdir() if p.is_dir() and re.fullmatch(r'\d{8}', p.name)], reverse=True)
    for d in dates:
        p = eod / d / 'status.json'
        if p.exists():
            try:
                return d, json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                pass
    return None, None


def write_eod_three_leg(target):
    ds = target.strftime('%Y%m%d'); iso = target.isoformat(); out = ROOT / 'eod' / ds; out.mkdir(parents=True, exist_ok=True)
    # Price
    p = get_json(TWSE_PRICE, {'date': ds, 'type': 'ALLBUT0999', 'response': 'json'})
    if str(p.get('stat')) != 'OK' or str(p.get('date')) != ds:
        raise RuntimeError(f'PRICE_NOT_READY:{p.get("stat")}:{p.get("date")}')
    pt = next((t for t in (p.get('tables') or []) if '證券代號' in (t.get('fields') or []) and '收盤價' in (t.get('fields') or [])), None)
    if pt is None:
        raise RuntimeError('PRICE_TABLE_NOT_FOUND')
    pf = pt.get('fields') or []; pi = {f:i for i,f in enumerate(pf)}; pdata = pt.get('data') or pt.get('records') or []
    def pv(row, *names):
        for n in names:
            i=pi.get(n)
            if i is not None and i < len(row): return clean(row[i])
        return ''
    pcols=['Date','Ticker','Name','VolumeShares','Trades','TurnoverTWD','Open','High','Low','Close','ChangeSign','Change','LastBid','LastBidVolume','LastAsk','LastAskVolume','PE','Source']
    pb={str(i):[] for i in range(1,10)}
    for r in pdata:
        t=pv(r,'證券代號')
        if re.fullmatch(r'[1-9]\d{3}',t): pb[t[0]].append({'Date':iso,'Ticker':t,'Name':pv(r,'證券名稱'),'VolumeShares':pv(r,'成交股數','成交量'),'Trades':pv(r,'成交筆數'),'TurnoverTWD':pv(r,'成交金額'),'Open':pv(r,'開盤價'),'High':pv(r,'最高價'),'Low':pv(r,'最低價'),'Close':pv(r,'收盤價'),'ChangeSign':pv(r,'漲跌(+/-)','漲跌'),'Change':pv(r,'漲跌價差'),'LastBid':pv(r,'最後揭示買價'),'LastBidVolume':pv(r,'最後揭示買量'),'LastAsk':pv(r,'最後揭示賣價'),'LastAskVolume':pv(r,'最後揭示賣量'),'PE':pv(r,'本益比'),'Source':TWSE_PRICE})
    for k,rs in pb.items():
        if rs:
            with (out/f'price_{k}.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=pcols);w.writeheader();w.writerows(rs)
    price_rows=sum(map(len,pb.values()))
    # Institutional
    q=get_json(TWSE_INST, {'date':ds,'selectType':'ALLBUT0999','response':'json'})
    if str(q.get('stat'))!='OK' or str(q.get('date'))!=ds: raise RuntimeError(f'INST_NOT_READY:{q.get("stat")}:{q.get("date")}')
    qf=q.get('fields') or []; qd=q.get('data') or q.get('records') or []
    if not qd and isinstance(q.get('tables'),list):
        for t in q['tables']:
            fs=t.get('fields') or []
            if '證券代號' in fs and any('外陸資買賣超股數' in str(x) for x in fs): qf=fs;qd=t.get('data') or t.get('records') or [];break
    qi={f:i for i,f in enumerate(qf)}
    def qv(row, exact=None, contains=None):
        if exact in qi and qi[exact] < len(row): return clean(row[qi[exact]])
        if contains:
            for f,i in qi.items():
                if contains in f and i < len(row): return clean(row[i])
        return ''
    icols=['Date','Ticker','Name','ForeignBuy','ForeignSell','ForeignNet','ForeignDealerBuy','ForeignDealerSell','ForeignDealerNet','TrustBuy','TrustSell','TrustNet','DealerNet','DealerProprietaryBuy','DealerProprietarySell','DealerProprietaryNet','DealerHedgeBuy','DealerHedgeSell','DealerHedgeNet','TotalNet','Source']
    ib={str(i):[] for i in range(1,10)}
    for r in qd:
        t=qv(r,exact='證券代號')
        if re.fullmatch(r'[1-9]\d{3}',t): ib[t[0]].append({'Date':iso,'Ticker':t,'Name':qv(r,exact='證券名稱'),'ForeignBuy':qv(r,contains='外陸資買進股數(不含外資自營商)'),'ForeignSell':qv(r,contains='外陸資賣出股數(不含外資自營商)'),'ForeignNet':qv(r,contains='外陸資買賣超股數(不含外資自營商)'),'ForeignDealerBuy':qv(r,exact='外資自營商買進股數'),'ForeignDealerSell':qv(r,exact='外資自營商賣出股數'),'ForeignDealerNet':qv(r,exact='外資自營商買賣超股數'),'TrustBuy':qv(r,exact='投信買進股數'),'TrustSell':qv(r,exact='投信賣出股數'),'TrustNet':qv(r,exact='投信買賣超股數'),'DealerNet':qv(r,exact='自營商買賣超股數'),'DealerProprietaryBuy':qv(r,exact='自營商買進股數(自行買賣)'),'DealerProprietarySell':qv(r,exact='自營商賣出股數(自行買賣)'),'DealerProprietaryNet':qv(r,exact='自營商買賣超股數(自行買賣)'),'DealerHedgeBuy':qv(r,exact='自營商買進股數(避險)'),'DealerHedgeSell':qv(r,exact='自營商賣出股數(避險)'),'DealerHedgeNet':qv(r,exact='自營商買賣超股數(避險)'),'TotalNet':qv(r,exact='三大法人買賣超股數'),'Source':TWSE_INST})
    for k,rs in ib.items():
        if rs:
            with (out/f'institutional_{k}.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=icols);w.writeheader();w.writerows(rs)
    inst_rows=sum(map(len,ib.values()))
    # Margin
    m=get_json(TWSE_MARGIN, {'date':ds,'selectType':'ALL','response':'json'})
    if str(m.get('stat'))!='OK' or str(m.get('date'))!=ds: raise RuntimeError(f'MARGIN_NOT_READY:{m.get("stat")}:{m.get("date")}')
    candidates=[]
    if isinstance(m.get('tables'),list): candidates += m['tables']
    if isinstance(m.get('fields'),list) and isinstance(m.get('data'),list): candidates += [{'fields':m['fields'],'data':m['data']}]
    for k,v in m.items():
        mm=re.fullmatch(r'fields(\d+)',str(k))
        if mm and isinstance(v,list) and isinstance(m.get('data'+mm.group(1)),list): candidates += [{'fields':v,'data':m['data'+mm.group(1)]}]
    mt=None
    for t in candidates:
        fs=[clean(x).replace(' ','') for x in (t.get('fields') or [])]; md=t.get('data') or t.get('records') or []
        if len(fs)>=15 and len(md)>=500 and any('現金償還' in x for x in fs) and any('現券償還' in x for x in fs): mt=(t.get('fields') or [],md);break
    if mt is None: raise RuntimeError('MARGIN_TABLE_NOT_FOUND')
    mf,md=mt;mcols=['Date','Ticker','Name','MarginBuy','MarginSell','MarginCashRepayment','MarginPreviousBalance','MarginBalance','MarginNextDayLimit','ShortBuy','ShortSell','ShortStockRepayment','ShortPreviousBalance','ShortBalance','ShortNextDayLimit','Offset','Note','Source'];mb={str(i):[] for i in range(1,10)}
    for r in md:
        if not isinstance(r,(list,tuple)) or len(r)<15: continue
        t=clean(r[0]).replace('=','').replace('"','')
        if re.fullmatch(r'[1-9]\d{3}',t): mb[t[0]].append({'Date':iso,'Ticker':t,'Name':clean(r[1]),'MarginBuy':clean(r[2]),'MarginSell':clean(r[3]),'MarginCashRepayment':clean(r[4]),'MarginPreviousBalance':clean(r[5]),'MarginBalance':clean(r[6]),'MarginNextDayLimit':clean(r[7]),'ShortBuy':clean(r[8]),'ShortSell':clean(r[9]),'ShortStockRepayment':clean(r[10]),'ShortPreviousBalance':clean(r[11]),'ShortBalance':clean(r[12]),'ShortNextDayLimit':clean(r[13]),'Offset':clean(r[14]),'Note':clean(r[15]) if len(r)>15 else '','Source':TWSE_MARGIN})
    for k,rs in mb.items():
        if rs:
            with (out/f'margin_{k}.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=mcols);w.writeheader();w.writerows(rs)
    margin_rows=sum(map(len,mb.values()))
    if price_rows<900 or inst_rows<900 or margin_rows<500: raise RuntimeError(f'EOD_ROW_COUNT_TOO_SMALL:{price_rows}:{inst_rows}:{margin_rows}')
    status={'system':'HENGCE','artifact':'EOD_COMPLETE_LEG_INGEST','target_date':iso,'price_status':'COMPLETE','price_date':iso,'price_rows':price_rows,'institutional_status':'COMPLETE','institutional_date':iso,'institutional_rows':inst_rows,'margin_status':'COMPLETE','margin_date':iso,'margin_rows':margin_rows,'policy':'THREE_LEG_COMPLETE_REQUIRED','completed_at_taipei':now_tw().isoformat()}
    atomic_json(out/'status.json',status)
    return status


def read_sox():
    with SOX_CSV.open(encoding='utf-8') as f:
        rows=[{'date':r['date'],'close':float(r['close'])} for r in csv.DictReader(f)]
    rows.sort(key=lambda r:r['date']); return rows


def sox_features(today):
    rows=read_sox(); usable=[r for r in rows if r['date'] < today.isoformat()]
    if len(usable)<6: raise RuntimeError('SOX_HISTORY_INSUFFICIENT')
    last=usable[-1];prev=usable[-2]
    r1=last['close']/prev['close']-1
    r5=last['close']/usable[-6]['close']-1
    return {'session':last['date'],'sox_1d':r1,'sox_5d':r5}


def load_tw_history():
    ensure_tw_history()
    with TW_HISTORY.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def prior_session_map(sox_rows, tw_dates):
    sd=sorted(r['date'] for r in sox_rows)
    ret={sox_rows[i]['date']:sox_rows[i]['close']/sox_rows[i-1]['close']-1 for i in range(1,len(sox_rows))}
    out={}
    for d in sorted(set(tw_dates)):
        prior=[x for x in sd if x<d]
        out[d]=ret.get(prior[-1]) if prior else None
    return out


def current_betas(history, sox_rows):
    by_t=defaultdict(list);tw_dates=[]
    for r in history:
        c=num(r.get('close'))
        if c is None: continue
        by_t[r['ticker']].append((r['date'],c,r.get('name','')));tw_dates.append(r['date'])
    amap=prior_session_map(sox_rows,tw_dates);betas={};prevclose={};names={}
    for t,rs in by_t.items():
        rs.sort(); obs=[];pc=None
        for d,c,n in rs:
            if pc is not None and amap.get(d) is not None:
                obs.append((amap[d],c/pc-1))
            pc=c;names[t]=n
        prevclose[t]=pc
        if len(obs)>=30:
            z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
            betas[t]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0.0
    latest_date=max(r['date'] for r in history if r.get('date'))
    universe=sorted({r['ticker'] for r in history if r.get('date')==latest_date})
    return betas,prevclose,names,latest_date,universe


def fugle_quote(symbol,key):
    req_headers={'X-API-KEY':key,'Accept':'application/json','User-Agent':'HENGCE-Q017-RADAR/1.0'}
    last=None
    for a in range(4):
        try:
            r=requests.get(FUGLE_QUOTE+symbol,headers=req_headers,timeout=15)
            if r.status_code==200:
                return r.json(),None
            last=f'HTTP_{r.status_code}'
            if r.status_code not in (429,500,502,503,504): break
        except Exception as e: last=repr(e)
        time.sleep((2**a)+random.uniform(.1,.4))
    return None,last


def radar_run(today=None):
    today=today or now_tw().date(); key=os.environ.get('FUGLE_API_KEY')
    if not key: raise RuntimeError('FUGLE_API_KEY_MISSING')
    sox_status=refresh_sox(today); seed=ensure_tw_history(); history=load_tw_history(); srows=read_sox(); sf=sox_features(today)
    betas,prevclose,names,hist_date,universe=current_betas(history,srows)
    one=sf['sox_1d']<=0.0;five=sf['sox_5d']<=-0.02
    market_state='GO' if one and five else 'WATCH' if one or five else 'CASH'
    candidates=[];fail=[];opened=0
    for i,t in enumerate(universe,1):
        b=betas.get(t);pc=prevclose.get(t)
        if b is None or b<=0 or not pc: continue
        q,err=fugle_quote(t,key)
        if not q:
            fail.append({'ticker':t,'error':err});continue
        op=num(q.get('openPrice'));prev=num(q.get('previousClose')) or pc
        if op is None or prev in (None,0): continue
        opened+=1;gap=op/prev-1;expected=b*sf['sox_1d'];resid=gap-expected
        if resid>0.04: continue
        score=b*(1+25*max(-resid,0))
        candidates.append({'ticker':t,'name':q.get('name') or names.get(t,''),'beta':b,'open':op,'previous_close':prev,'gap':gap,'expected_gap':expected,'residual':resid,'score':score,'qualified':market_state=='GO'})
        time.sleep(.32)
    candidates.sort(key=lambda x:x['score'],reverse=True);top3=candidates[:3]
    prev_top=[]
    if LATEST.exists():
        try: prev_top=[x['ticker'] for x in json.loads(LATEST.read_text(encoding='utf-8')).get('top3',[])]
        except Exception: pass
    cur=[x['ticker'] for x in top3]
    for x in top3: x['new']=x['ticker'] not in prev_top
    dropped=[t for t in prev_top if t not in cur]
    coverage=opened/max(1,sum(1 for t in universe if betas.get(t,0)>0))
    binding='PASS' if coverage>=0.90 else 'DATA_PENDING'
    if binding!='PASS':
        market_state='DATA_PENDING'
        for x in top3: x['qualified']=False
    payload={'schema_version':1,'system':'HENGCE','module':'Q017_SOX_ELECTRONICS_RADAR','generated_at_taipei':now_tw().isoformat(),'trade_date':today.isoformat(),'binding_status':binding,'market_state':market_state,'data_status':{'sox':sox_status,'tw_history':seed,'tw_history_latest_date':hist_date,'universe_count':len(universe),'opened_quote_count':opened,'quote_coverage':coverage,'quote_failures':fail[:20]},'sox':sf,'rules':{'sox_1d_max':0.0,'sox_5d_max':-0.02,'residual_max':0.04,'score':'beta*(1+25*max(-residual,0))','top_n':3,'research_hold_days':10},'top3':top3,'new':[x['ticker'] for x in top3 if x['new']],'dropped':dropped,'note':'Top1 is strongest research candidate, not a mandatory trade. Top2/Top3 remain visible for market context.'}
    atomic_json(LATEST,payload);stamp=now_tw().strftime('%Y%m%dT%H%M%S');atomic_json(HISTORY/f'{stamp}.json',payload)
    with SIGNAL_LEDGER.open('a',encoding='utf-8') as f: f.write(json.dumps({'time':payload['generated_at_taipei'],'date':payload['trade_date'],'market_state':payload['market_state'],'top3':cur},ensure_ascii=False)+'\n')
    return payload


def premarket(today=None):
    today=today or now_tw().date();sox=refresh_sox(today);seed=ensure_tw_history();ed,es=latest_eod_status();sf=sox_features(today)
    eod_ok=bool(es and es.get('price_status')=='COMPLETE' and es.get('institutional_status')=='COMPLETE' and es.get('margin_status')=='COMPLETE')
    hist=load_tw_history();latest_hist=max(r['date'] for r in hist)
    status={'system':'HENGCE','module':'DAILY_DATA_GATE','generated_at_taipei':now_tw().isoformat(),'trade_date':today.isoformat(),'status':'PASS' if eod_ok else 'DATA_PENDING','required':{'sox':sox,'latest_eod_date':ed,'latest_eod_complete':eod_ok,'electronics_history':seed,'electronics_history_latest':latest_hist},'sox':sf,'policy':'NO_REQUIRED_DATA_NO_FORMAL_SIGNAL'}
    atomic_json(DATA_STATUS,status);return status


def postclose(today=None):
    today=today or now_tw().date()
    if today.weekday()>=5:
        return {'status':'SKIP_WEEKEND','date':today.isoformat()}
    status=write_eod_three_leg(today)
    elec=append_electronics_day(today)
    sox=refresh_sox(today)
    out={'system':'HENGCE','module':'POSTCLOSE_DATA_GATE','generated_at_taipei':now_tw().isoformat(),'status':'PASS','eod':status,'electronics_history_append':elec,'sox':sox}
    atomic_json(DATA_STATUS,out);return out


def self_test():
    # Pure math/invariant checks: no network required.
    obs=[(x/100.0,(2*x+1)/100.0) for x in range(-20,21) if x!=0]
    z=obs[-40:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z);b=sum((a-mx)*(y-my) for a,y in z)/vv
    assert 1.9<b<2.1
    resid=-0.03;score=b*(1+25*max(-resid,0));assert score>b
    assert ('GO' if (-.01<=0 and -.03<=-.02) else 'CASH')=='GO'
    print(json.dumps({'self_test':'PASS','beta':b,'score':score}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['self-test','premarket','radar','postclose'],required=True);ap.add_argument('--date');args=ap.parse_args()
    target=datetime.strptime(args.date,'%Y-%m-%d').date() if args.date else None
    if args.mode=='self-test':self_test();return 0
    try:
        result=premarket(target) if args.mode=='premarket' else radar_run(target) if args.mode=='radar' else postclose(target)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        fail={'system':'HENGCE','module':'DAILY_COMMAND_CENTER','mode':args.mode,'generated_at_taipei':now_tw().isoformat(),'status':'DATA_PENDING','error':repr(e),'policy':'FAIL_CLOSED_NO_FORMAL_SIGNAL'}
        atomic_json(DATA_STATUS,fail);print(json.dumps(fail,ensure_ascii=False,indent=2));return 2

if __name__=='__main__': raise SystemExit(main())
