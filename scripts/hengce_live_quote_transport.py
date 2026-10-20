#!/usr/bin/env python3
import argparse, hashlib, json, os, random, re, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Taipei')
CACHE_TTL_SECONDS=600
TRADE_IDLE_SECONDS=900
UNIVERSE_PATH=Path('hengce/live_universe.json')
CONTRACT_PATH=Path('hengce/HENGCE_LIVE_QUOTE_TRANSPORT_CONTRACT_v1_0_20261020.json')
QUOTE_DIR=Path('live/quotes')
BASE='https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/'
ROLE='QUOTE_TRANSPORT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY'
LINEAGE='LINEAGE_ONLY_NOT_AUTHORITY'
MAX_ATTEMPTS=6
BASE_SPACING_SECONDS=0.65
BACKOFF_CAP_SECONDS=20.0


def load_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha256(b): return hashlib.sha256(b).hexdigest()
def now_tw(): return datetime.now(TZ)
def phase(dt):
    if dt.weekday()>=5: return 'closed'
    m=dt.hour*60+dt.minute
    if m<540: return 'preopen'
    if m<=810: return 'open'
    return 'closed'
def parse_ts(v):
    if v in (None,''): return None
    try:
        v=float(v)
        if v>=1e14: v/=1_000_000
        elif v>=1e11: v/=1_000
        return datetime.fromtimestamp(v,TZ)
    except Exception: return None
def age(now,dt): return None if dt is None else max(0,int((now-dt).total_seconds()))
def level(v): return v[0] if isinstance(v,list) and v and isinstance(v[0],dict) else {}
def authority_fields():
    return {'transport_role':ROLE,'source_run_id_semantics':LINEAGE,'ranking_authority':False,'signal_authority':False,'capital_authority':False,'broker_order_execution':False,'legacy_v3_rank_authority':False}


def validate_contract(c):
    if c.get('module')!='HENGCE_LIVE_QUOTE_TRANSPORT': raise SystemExit('TRANSPORT_CONTRACT_MODULE_MISMATCH')
    if c.get('role')!=ROLE: raise SystemExit('TRANSPORT_CONTRACT_ROLE_MISMATCH')
    if c.get('universe_source_run_id_semantics')!=LINEAGE: raise SystemExit('TRANSPORT_CONTRACT_LINEAGE_MISMATCH')
    if c.get('legacy_v3_source_label_confers_authority') is not False: raise SystemExit('TRANSPORT_CONTRACT_V3_AUTHORITY_MUST_BE_FALSE')
    for k in ('ranking','signal','capital','broker_execution'):
        if (c.get('authority') or {}).get(k) is not False: raise SystemExit('TRANSPORT_CONTRACT_AUTHORITY_MUST_BE_FALSE:'+k)


def load_inputs():
    if not UNIVERSE_PATH.exists(): raise SystemExit('LIVE_UNIVERSE_MISSING_FAIL_CLOSED')
    if not CONTRACT_PATH.exists(): raise SystemExit('LIVE_TRANSPORT_CONTRACT_MISSING_FAIL_CLOSED')
    uraw=UNIVERSE_PATH.read_bytes(); craw=CONTRACT_PATH.read_bytes()
    u=json.loads(uraw.decode()); c=json.loads(craw.decode()); validate_contract(c)
    syms=[str(x).strip() for x in u.get('symbols',[])]
    if not syms: raise SystemExit('LIVE_UNIVERSE_EMPTY_FAIL_CLOSED')
    if len(syms)!=len(set(syms)): raise SystemExit('LIVE_UNIVERSE_DUPLICATE_SYMBOLS')
    bad=[x for x in syms if not re.fullmatch(r'[1-9]\d{3}',x)]
    if bad: raise SystemExit('LIVE_UNIVERSE_BAD_SYMBOLS:'+str(bad[:10]))
    if int(u.get('requested_count',len(syms)))!=len(syms): raise SystemExit('LIVE_UNIVERSE_COUNT_MISMATCH')
    return u,sha256(uraw),c,sha256(craw),syms


def retry_after(headers):
    if not headers: return None
    raw=headers.get('Retry-After')
    if raw in (None,''): return None
    raw=str(raw).strip()
    if raw.isdigit(): return min(float(raw),BACKOFF_CAP_SECONDS)
    try:
        dt=parsedate_to_datetime(raw)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return max(0.0,min((dt-datetime.now(timezone.utc)).total_seconds(),BACKOFF_CAP_SECONDS))
    except Exception: return None

def backoff(attempt,retry=None):
    w=min(BACKOFF_CAP_SECONDS,1.25*(2**max(0,attempt-1)))+random.uniform(.15,.55)
    if retry is not None: w=max(w,float(retry))
    return min(w,BACKOFF_CAP_SECONDS)


def fetch_quote(symbol,key,t):
    req=urllib.request.Request(BASE+symbol,headers={'X-API-KEY':key,'Accept':'application/json','User-Agent':'HENGCE-LIVE/3.0-TRANSPORT-NO-AUTHORITY'})
    m={'attempts':0,'rate_limit_events':0,'server_retry_events':0,'network_retry_events':0,'retry_wait_seconds':0.0}
    for attempt in range(1,MAX_ATTEMPTS+1):
        m['attempts']=attempt; t['request_attempt_count']+=1
        try:
            with urllib.request.urlopen(req,timeout=15) as r: row=json.load(r)
            if m['rate_limit_events']: t['rate_limit_recovered_count']+=1
            return row,m,None
        except urllib.error.HTTPError as e:
            if e.code in (401,403): return None,m,f'AUTH_OR_PLAN_HTTP_{e.code}'
            if e.code==429:
                m['rate_limit_events']+=1; t['rate_limit_event_count']+=1; t['rate_limit_symbols'].add(symbol)
                if attempt==MAX_ATTEMPTS:
                    t['terminal_429_count']+=1; return None,m,'RATE_LIMIT_HTTP_429'
                w=backoff(attempt,retry_after(e.headers))
            elif 500<=e.code<=599:
                m['server_retry_events']+=1; t['server_retry_event_count']+=1
                if attempt==MAX_ATTEMPTS: return None,m,f'SERVER_HTTP_{e.code}'
                w=backoff(attempt)
            else: return None,m,f'HTTP_{e.code}'
        except (urllib.error.URLError,TimeoutError,OSError) as e:
            m['network_retry_events']+=1; t['network_retry_event_count']+=1
            if attempt==MAX_ATTEMPTS: return None,m,'NETWORK_ERROR_'+type(e).__name__
            w=backoff(attempt)
        except Exception as e: return None,m,'UNEXPECTED_'+type(e).__name__+':'+str(e)
        m['retry_wait_seconds']+=w; t['total_retry_wait_seconds']+=w; time.sleep(w)
    return None,m,'UNREACHABLE_FETCH_STATE'


def old_quote(symbol):
    p=QUOTE_DIR/f'{symbol}.json'
    if not p.exists(): return None
    try: return load_json(p)
    except Exception: return None


def run_fetch():
    key=os.environ.get('FUGLE_API_KEY')
    if not key: raise SystemExit('FUGLE_API_KEY missing')
    u,usha,c,csha,syms=load_inputs()
    uv=u.get('version'); ud=u.get('target_date'); ur=u.get('source_run_id'); av=u.get('source_action_board_version')
    legacy='HENGCE_V3' in str(ur or '')
    print('HENGCE LIVE UNIVERSE',len(syms),uv,ur,'provenance_scope=transport-only')
    QUOTE_DIR.mkdir(parents=True,exist_ok=True)
    snap=now_tw(); sid=snap.strftime('%Y%m%dT%H%M%S%z'); exp=snap+timedelta(seconds=CACHE_TTL_SECONDS)
    records=[]; failures=[]; ok=0
    t={'request_attempt_count':0,'rate_limit_event_count':0,'rate_limit_symbols':set(),'rate_limit_recovered_count':0,'terminal_429_count':0,'server_retry_event_count':0,'network_retry_event_count':0,'total_retry_wait_seconds':0.0}
    for symbol in syms:
        row,m,err=fetch_quote(symbol,key,t)
        if err is None:
            try:
                if not isinstance(row,dict): raise RuntimeError('INVALID_RESPONSE')
                if str(row.get('symbol'))!=symbol: raise RuntimeError('SYMBOL_MISMATCH')
                name=row.get('name')
                if not name: raise RuntimeError('NAME_MISSING')
                total=row.get('total') or {}; last=row.get('lastTrade') or {}; trial=row.get('lastTrial') or {}; halt=row.get('tradingHalt') or {}
                bid=level(row.get('bids')); ask=level(row.get('asks')); qt=parse_ts(row.get('lastUpdated')); tt=parse_ts(last.get('time'))
                price=row.get('lastPrice') if row.get('lastTrade') is None else last.get('price')
                price=last.get('price') if last.get('price') is not None else row.get('lastPrice')
                prev=row.get('previousClose'); chg=pct=None
                if price is not None and prev not in (None,0): chg=round(float(price)-float(prev),4); pct=round((float(price)/float(prev)-1)*100,4)
                qdate=row.get('date'); is_trial=bool(row.get('isTrial',False)); ta=age(snap,tt)
                rec={'schema_version':2,'snapshot_id':sid,'symbol':symbol,'company_name':name,'price':price,'previous_close':prev,'reference_price':row.get('referencePrice'),'open':row.get('openPrice'),'high':row.get('highPrice'),'low':row.get('lowPrice'),'avg_price':row.get('avgPrice'),'change':chg,'change_percent':pct,'volume':total.get('tradeVolume'),'trade_value':total.get('tradeValue'),'transactions':total.get('transaction'),'volume_at_bid':total.get('tradeVolumeAtBid'),'volume_at_ask':total.get('tradeVolumeAtAsk'),'best_bid':bid.get('price'),'best_bid_size':bid.get('size'),'best_ask':ask.get('price'),'best_ask_size':ask.get('size'),'last_trade_time':tt.isoformat() if tt else None,'trade_age_seconds':ta,'trade_idle_warning':ta is not None and ta>TRADE_IDLE_SECONDS,'source_last_price':row.get('lastPrice'),'source_last_updated':qt.isoformat() if qt else None,'quote_age_seconds':age(snap,qt),'is_trial':is_trial,'trial_price':row.get('lastPrice') if is_trial else None,'last_trial_price':trial.get('price'),'is_halted':bool(halt.get('isHalted',False)),'is_limit_up_price':bool(row.get('isLimitUpPrice',False)),'is_limit_down_price':bool(row.get('isLimitDownPrice',False)),'is_delayed_open':bool(row.get('isDelayedOpen',False)),'is_delayed_close':bool(row.get('isDelayedClose',False)),'quote_date':qdate,'stale_at_publish':qdate!=snap.date().isoformat(),'fetch_ok':True,'fetched_at_taipei':snap.isoformat(),'cache_expires_at_taipei':exp.isoformat(),'market_phase':phase(snap),'source':'Fugle MarketData','universe_version':uv,'universe_source_run_id':ur,'source_action_board_version':av,'transport_fetch_attempts':m['attempts'],'transport_rate_limit_events':m['rate_limit_events'],'transport_server_retry_events':m['server_retry_events'],'transport_network_retry_events':m['network_retry_events'],'transport_retry_wait_seconds':round(m['retry_wait_seconds'],3),**authority_fields()}
                records.append(rec); ok+=1
                (QUOTE_DIR/f'{symbol}.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
                print('OK',symbol,name,price,'attempts',m['attempts'])
            except Exception as e: err=str(e)
        if err is not None:
            failures.append({'symbol':symbol,'error':err,'attempts':m['attempts'],'rate_limit_events':m['rate_limit_events'],'retry_wait_seconds':round(m['retry_wait_seconds'],3)})
            old=old_quote(symbol)
            if old:
                old.update(authority_fields()); old.update({'fetch_ok':False,'stale_at_publish':True,'fetch_error':err,'last_fetch_attempt_taipei':snap.isoformat(),'transport_fetch_attempts':m['attempts'],'transport_rate_limit_events':m['rate_limit_events'],'transport_server_retry_events':m['server_retry_events'],'transport_network_retry_events':m['network_retry_events'],'transport_retry_wait_seconds':round(m['retry_wait_seconds'],3)})
                records.append(old)
            print('FAIL',symbol,err,'attempts',m['attempts'])
        time.sleep(BASE_SPACING_SECONDS)
    if ok==0: raise SystemExit('ALL_REQUESTS_FAILED')
    fc=len(failures); hs='PASS' if fc==0 else 'DEGRADED'; rls=sorted(t['rate_limit_symbols'])
    payload={'schema_version':2,'service':'HENGCE LIVE QUOTES','snapshot_id':sid,'generated_at_taipei':snap.isoformat(),'cache_expires_at_taipei':exp.isoformat(),'cache_ttl_seconds':CACHE_TTL_SECONDS,'market_phase':phase(snap),**authority_fields(),'transport_contract_version':c.get('contract_version'),'transport_contract_sha256':csha,'transport_health_status':hs,'fully_healthy':fc==0 and ok==len(syms),'degraded':fc>0,'fresh_success_ratio':round(ok/len(syms),6),'retry_policy':{'max_attempts':MAX_ATTEMPTS,'base_spacing_seconds':BASE_SPACING_SECONDS,'respect_retry_after':True,'backoff_cap_seconds':BACKOFF_CAP_SECONDS},'request_attempt_count':t['request_attempt_count'],'rate_limit_event_count':t['rate_limit_event_count'],'rate_limit_symbol_count':len(rls),'rate_limit_symbols':rls,'rate_limit_recovered_count':t['rate_limit_recovered_count'],'terminal_429_count':t['terminal_429_count'],'server_retry_event_count':t['server_retry_event_count'],'network_retry_event_count':t['network_retry_event_count'],'total_retry_wait_seconds':round(t['total_retry_wait_seconds'],3),'universe_policy':'DAILY_ACTION_BOARD_ROWS_HARD_BIND','universe_version':uv,'universe_target_date':ud,'universe_source_run_id':ur,'source_action_board_version':av,'legacy_source_label_detected':legacy,'universe_sha256':usha,'requested_count':len(syms),'success_count':ok,'failure_count':fc,'stale_count':sum(bool(x.get('stale_at_publish')) for x in records),'trial_count':sum(bool(x.get('is_trial')) for x in records),'halted_count':sum(bool(x.get('is_halted')) for x in records),'failures':failures,'data':records}
    status={k:v for k,v in payload.items() if k!='data'}; status['healthy']=ok>0
    Path('latest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('live/active.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('live/status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print('HENGCE SNAPSHOT',hs,ok,'/',len(syms),'429_events',t['rate_limit_event_count'],'429_recovered',t['rate_limit_recovered_count'],'terminal_429',t['terminal_429_count'])


def validate_latest():
    u,usha,c,csha,syms=load_inputs(); latest=load_json('latest.json')
    actual=[str(x.get('symbol')) for x in latest.get('data',[])]; failed={str(x.get('symbol')) for x in latest.get('failures',[])}
    if latest.get('requested_count')!=len(syms): raise SystemExit('requested_count mismatch')
    if latest.get('universe_source_run_id')!=u.get('source_run_id'): raise SystemExit('universe source run mismatch')
    if latest.get('universe_sha256')!=usha: raise SystemExit('universe sha mismatch')
    if latest.get('transport_contract_sha256')!=csha: raise SystemExit('transport contract sha mismatch')
    if latest.get('transport_contract_version')!=c.get('contract_version'): raise SystemExit('transport contract version mismatch')
    if latest.get('transport_role')!=ROLE or latest.get('source_run_id_semantics')!=LINEAGE: raise SystemExit('transport provenance mismatch')
    for k in ('ranking_authority','signal_authority','capital_authority','broker_order_execution','legacy_v3_rank_authority'):
        if latest.get(k) is not False: raise SystemExit(k+' must remain false')
    if 'HENGCE_V3' in str(u.get('source_run_id') or '') and latest.get('legacy_source_label_detected') is not True: raise SystemExit('legacy V3 lineage detection missing')
    if '2033' not in syms or '6415' not in syms: raise SystemExit('continuity/reentry regression symbol absent')
    silent=[x for x in syms if x not in actual and x not in failed]
    if silent: raise SystemExit('silent missing symbols:'+str(silent[:10]))
    tf=sum(1 for x in latest.get('failures',[]) if x.get('error')=='RATE_LIMIT_HTTP_429')
    if latest.get('terminal_429_count')!=tf: raise SystemExit('terminal 429 telemetry mismatch')
    if int(latest.get('rate_limit_recovered_count',0))>int(latest.get('rate_limit_symbol_count',0)): raise SystemExit('429 recovered count invalid')
    if int(latest.get('rate_limit_event_count',0))<int(latest.get('terminal_429_count',0)): raise SystemExit('429 event count invalid')
    hs='PASS' if int(latest.get('failure_count',0))==0 else 'DEGRADED'
    if latest.get('transport_health_status')!=hs: raise SystemExit('transport health status mismatch')
    for r in latest.get('data',[]):
        for k in ('ranking_authority','signal_authority','capital_authority','broker_order_execution','legacy_v3_rank_authority'):
            if r.get(k) is not False: raise SystemExit('row authority violation '+str(r.get('symbol'))+':'+k)
    print('HENGCE LIVE TRANSPORT HARD-LOCK VERIFIED',latest.get('requested_count'),latest.get('success_count'),latest.get('failure_count'),hs,'429_events',latest.get('rate_limit_event_count'),'429_recovered',latest.get('rate_limit_recovered_count'),'terminal_429',latest.get('terminal_429_count'))


def self_test():
    _,_,c,_,syms=load_inputs(); validate_contract(c)
    assert len(syms)==len(set(syms)); assert retry_after({'Retry-After':'3'})==3.0; assert retry_after({'Retry-After':'999'})==BACKOFF_CAP_SECONDS
    a=authority_fields(); assert all(a[k] is False for k in ('ranking_authority','signal_authority','capital_authority','broker_order_execution','legacy_v3_rank_authority'))
    print(json.dumps({'self_test':'PASS','transport_role':ROLE,'source_run_id_semantics':LINEAGE,'legacy_v3_rank_authority':False,'max_attempts':MAX_ATTEMPTS,'respect_retry_after':True,'backoff_cap_seconds':BACKOFF_CAP_SECONDS},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=('fetch','validate','self-test'),default='fetch'); m=ap.parse_args().mode
    {'fetch':run_fetch,'validate':validate_latest,'self-test':self_test}[m]()
