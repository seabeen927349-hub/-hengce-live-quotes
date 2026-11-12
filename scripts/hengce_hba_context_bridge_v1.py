#!/usr/bin/env python3
"""Attach existing HENGCE environment and lifelong gross turnover to HBA daily report.

Read-only research adapter; does not fetch vendors, alter original vessels or grant
selection/position/order authority. All comparisons are point-in-time safe.
"""
import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

SCHEMA = 'HENGCE_HBA_INTEGRATED_CONTEXT_RESEARCH_V1'


def load(path):
    try:
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else None
    except (ValueError, OSError):
        return None


def market_context(root, day):
    folder = root/'eod'/day.replace('-', '')
    status = load(folder/'status.json') or {}
    eod_ok = (status.get('formal_complete_day') is True and
        status.get('downstream_ready') is True and
        all(status.get(k+'_date')==day for k in ('price','institutional','margin')))
    result = {'date':day,'canonical_eod':'COMPLETE' if eod_ok else 'UNVERIFIED',
              'canonical_mother_status':status.get('mother_status')}
    if not eod_ok: return result
    x = load(folder/'market_state_finmind_context.json') or {}
    if x.get('target_date') != day or x.get('authority') != 'RESEARCH_SHADOW_DESCRIPTIVE_CONTEXT_ONLY_NO_MODEL_OR_TRADING_AUTHORITY':
        result['breadth']={'status':'MISSING_OR_UNVERIFIED'}
        return result
    b = (x.get('scopes') or {}).get('twse_all_listed_equities') or {}
    result['breadth']={'status':'SHADOW_DESCRIPTIVE_ONLY', 'advancing_count':b.get('advancing_count'),
       'declining_count':b.get('declining_count'),'observed_count':b.get('change_rate_eligible_count'),
       'declining_share':b.get('declining_share'),
       'equal_weight_change_pct_vendor':b.get('change_rate_mean_vendor_units'),
       'source_latest_timestamp':x.get('source_snapshot_latest_timestamp')}
    previous=[]
    for file in sorted((root/'eod').glob('20??????/market_state_finmind_context.json')):
        y=load(file) or {}
        d=y.get('target_date')
        if d and d<day and y.get('authority')=='RESEARCH_SHADOW_DESCRIPTIVE_CONTEXT_ONLY_NO_MODEL_OR_TRADING_AUTHORITY':
            prior=(y.get('scopes') or {}).get('twse_all_listed_equities') or {}
            if isinstance(prior.get('declining_share'),(float,int)):
                previous.append((d,prior))
    if previous:
        d,p=previous[-1]
        result['prior_breadth']={'date':d,'declining_count':p.get('declining_count'),
                                 'declining_share':p['declining_share']}
        if isinstance(b.get('declining_share'),(int,float)):
            result['declining_share_change_pp']=round(100*(b['declining_share']-p['declining_share']),2)
    return result


def read_lifelong_summary(path, day):
    if not path or not path.is_file():
        return {'status':'NOT_MOUNTED','reason':'多年研究母庫摘要未掛載，禁止以短期EOD代替'},{}
    needed={'ticker','first_date','last_date','valid_stock_days','gross_buy_shares','gross_sell_shares','net_shares'}
    stocks={}
    try:
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not needed.issubset(reader.fieldnames or []):
                return {'status':'SCHEMA_MISMATCH'},{}
            for row in reader:
                ticker=str(row['ticker'])
                if not (len(ticker)==4 and ticker.isdigit()):continue
                if row['last_date']>day:
                    return {'status':'FUTURE_DATA_REJECTED'},{}
                try:
                    buy=int(round(float(row['gross_buy_shares'])))
                    sell=int(round(float(row['gross_sell_shares'])))
                    net=int(round(float(row['net_shares'])))
                    count=int(float(row['valid_stock_days']))
                except (TypeError,ValueError,OverflowError):
                    return {'status':'INVALID_NUMERIC'},{}
                if min(buy,sell,count)<0 or abs(buy-sell-net)>max(1,int((buy+sell)*0.000001)):
                    return {'status':'AGGREGATE_INCONSISTENT'},{}
                gross=buy+sell
                stocks[ticker]={'first_date':row['first_date'],'last_date':row['last_date'],
                   'gross_buy_shares':buy,'gross_sell_shares':sell,'net_shares':net,
                   'observed_stock_days':count,
                   'net_abs_to_gross_pct':round(100*abs(net)/gross,4) if gross else None}
    except (OSError, UnicodeError):
        return {'status':'READ_FAILED'},{}
    if not stocks: return {'status':'EMPTY'},{}
    last=max(x['last_date'] for x in stocks.values())
    meta={'status':'AVAILABLE_RESEARCH_PROXY' if last==day else 'STALE_RESEARCH_SUMMARY',
          'source_file':path.name,'asof':last,
          'first_date':min(x['first_date'] for x in stocks.values()),
          'distinct_tickers':len(stocks),
          'valid_stock_days':sum(x['observed_stock_days'] for x in stocks.values()),
          'gross_buy_shares':sum(x['gross_buy_shares'] for x in stocks.values()),
          'gross_sell_shares':sum(x['gross_sell_shares'] for x in stocks.values()),
          'net_below_one_percent_count':sum(x['net_abs_to_gross_pct'] is not None and x['net_abs_to_gross_pct']<1 for x in stocks.values()),
          'note':'股票淨差小不代表完成獲利；包含多年累積交易股數，不是持股存量'}
    return meta,stocks



def fold_verified_original_eod(root, day, mother, stocks):
    """Fold post-cache formal EOD days into the existing *in-memory* research proxy.

    The frozen nine-year mother summary on disk is immutable here; the original
    eod/YYYYMMDD institutional + price legs supply only newer verified rows.
    Missing days, bad provenance or missing numeric legs fail closed.
    """
    if mother.get('status') not in ('AVAILABLE_RESEARCH_PROXY','STALE_RESEARCH_SUMMARY'):
        return mother, stocks
    base = mother.get('asof')
    if not isinstance(base,str) or base >= day:
        return mother, stocks
    def stale(reason):
        return dict(mother, status='STALE_RESEARCH_SUMMARY',
                    reason=reason, expected_eod=day, source_base_asof=base), stocks

    # Never skip a potentially open weekday without canonical session proof.
    pending = []
    d = date.fromisoformat(base) + timedelta(days=1)
    until = date.fromisoformat(day)
    while d <= until:
        if d.weekday() < 5:
            pending.append(d.isoformat())
        d += timedelta(days=1)
    if not pending:
        return stale('NO_NEW_VERIFIED_MARKET_SESSION')
    totals = {t:dict(v) for t,v in stocks.items()}
    raw_fields = ('ForeignBuy','ForeignSell','ForeignDealerBuy','ForeignDealerSell',
                  'TrustBuy','TrustSell','DealerProprietaryBuy','DealerProprietarySell',
                  'DealerHedgeBuy','DealerHedgeSell')
    increments = 0
    for trade_day in pending:
        folder = root/'eod'/trade_day.replace('-','')
        status = load(folder/'status.json') or {}
        receipt = load(folder/'receipts/mother.json') or {}
        if not (status.get('formal_complete_day') is True and
                status.get('downstream_ready') is True and
                status.get('mother_status') == 'COMPLETE' and
                all(status.get(leg+'_date')==trade_day for leg in ('price','institutional','margin')) and
                receipt.get('target_date')==trade_day and
                receipt.get('mother_latest_date')==trade_day and
                receipt.get('status') in ('PASS','COMPLETE') and
                receipt.get('second_mother') is False and
                set(receipt.get('promoted_legs') or ()) == {'price','institutional','margin'}):
            return stale('GAP_OR_UNVERIFIED_CANONICAL_DAY:'+trade_day)
        hashes = receipt.get('promoted_leg_sha256') or {}
        if any(hashes.get(leg)!=status.get(leg+'_sha256') or not hashes.get(leg)
               for leg in ('price','institutional','margin')):
            return stale('ORIGINAL_EOD_LEG_HASH_MISMATCH:'+trade_day)
        # Read the original published bytes, not any new vendor endpoint.
        def rows_for(leg):
            paths = sorted(folder.glob(leg+'_[1-9].csv'))
            if not paths:
                raise ValueError(leg.upper()+'_FILES_MISSING')
            seen=set()
            out={}
            for p in paths:
                with p.open('r',encoding='utf-8-sig',newline='') as f:
                    reader=csv.DictReader(f)
                    required={'Date','Ticker'} | (set(raw_fields) if leg=='institutional' else set())
                    if not required.issubset(reader.fieldnames or []):
                        raise ValueError(leg.upper()+'_SCHEMA_MISMATCH')
                    for row in reader:
                        ticker=str(row['Ticker'])
                        if row['Date']!=trade_day or len(ticker)!=4 or not ticker.isdigit() or ticker in seen:
                            raise ValueError(leg.upper()+'_DATE_TICKER_INVALID')
                        seen.add(ticker)
                        out[ticker]=row
            reported=status.get(leg+'_rows')
            if isinstance(reported,int) and len(out)!=reported:
                raise ValueError(leg.upper()+'_ROW_COUNT_MISMATCH')
            return out
        try:
            prices = rows_for('price')
            inst = rows_for('institutional')
        except (OSError,UnicodeError,csv.Error,ValueError) as exc:
            return stale('EOD_ORIGINAL_SOURCE_INVALID:'+trade_day+':'+str(exc)[:90])
        valid_on_day = 0
        for ticker, row in inst.items():
            if ticker not in prices:
                continue
            try:
                # Distinguish zero from missing; do not infer a buy/sell leg.
                nums=[]
                for field in raw_fields:
                    raw=str(row.get(field) or '').strip().replace(',','')
                    if not raw or not raw.isdecimal():
                        raise ValueError('MISSING_OR_INVALID_T86_LEG')
                    nums.append(int(raw))
            except ValueError:
                continue
            buy=sum(nums[::2])
            sell=sum(nums[1::2])
            prev=totals.get(ticker)
            if prev and prev['last_date']>=trade_day:
                continue
            if prev:
                x=prev
                x['gross_buy_shares']+=buy
                x['gross_sell_shares']+=sell
                x['net_shares']=x['gross_buy_shares']-x['gross_sell_shares']
                x['observed_stock_days']+=1
                x['last_date']=trade_day
            else:
                x={'first_date':trade_day,'last_date':trade_day,
                   'gross_buy_shares':buy,'gross_sell_shares':sell,
                   'net_shares':buy-sell,'observed_stock_days':1}
                totals[ticker]=x
            gross=x['gross_buy_shares']+x['gross_sell_shares']
            x['net_abs_to_gross_pct']=round(100*abs(x['net_shares'])/gross,4) if gross else None
            valid_on_day+=1
        if valid_on_day==0:
            return stale('NO_VALID_INTERSECTING_T86_PRICE_ROWS:'+trade_day)
        increments+=valid_on_day
    # Descriptive gross total, not a historical phase/selection assertion.
    updated=dict(mother, status='AVAILABLE_RESEARCH_PROXY', asof=day,
                 distinct_tickers=len(totals), valid_stock_days=sum(x['observed_stock_days'] for x in totals.values()),
                 gross_buy_shares=sum(x['gross_buy_shares'] for x in totals.values()),
                 gross_sell_shares=sum(x['gross_sell_shares'] for x in totals.values()),
                 net_below_one_percent_count=sum(x['net_abs_to_gross_pct'] is not None and x['net_abs_to_gross_pct']<1 for x in totals.values()),
                 original_cache_asof=base, incremental_eod_dates=pending,
                 incremental_valid_stock_days=increments,
                 source_scope='EXISTING_VERIFIED_EOD_PRICE_AND_T86_FOLD_NO_SECOND_MOTHER')
    return updated, totals



def read_existing_two_group_tdcc(root, target, observed_eod):
    """Audit small-holder (grades 1-3) vs all-other REAL shares from the original TDCC vessel.

    This is a descriptive, read-only sidecar. It never changes the HBA's frozen
    short-window formula, its original candidate registry, or a trading signal.
    """
    import hashlib
    import re
    from datetime import datetime
    from zoneinfo import ZoneInfo

    meta={'status':'NOT_AVAILABLE','role':'RESEARCH_ONLY_NO_SELECTION_OR_TRADING',
          'small_definition':'TDCC grades 1-3, 1 to 10000 shares',
          'other_definition':'grade 17 total minus grades 1-3 shares',
          'source':'EXISTING_TDCC_1_5_RAW_AND_RECEIPTS',
          'target_tw_date':target,'price_date':observed_eod,
          'last_tdcc_date':None,'first_observed_taipei':None,
          'historical_13week_continuity_verified':False,
          'no_future_data':True,'stock_count':0,'comparable_stock_count':0,
          'exclusions':{},'categories':{},
          'authority':{'selection':False,'rank':False,'trade':False,'capital':False}}
    if not isinstance(target,str) or not isinstance(observed_eod,str) or observed_eod>target:
        return dict(meta,status='INVALID_TIME'), {}
    price_folder=root/'eod'/observed_eod.replace('-','')
    prices=set()
    try:
        for p in sorted(price_folder.glob('price_*.csv')):
            with p.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    ticker=str(row.get('Ticker') or '').strip()
                    if row.get('Date')==observed_eod and re.fullmatch(r'[1-9]\d{3}',ticker):
                        prices.add(ticker)
    except (OSError, UnicodeError, csv.Error):
        return dict(meta,status='INVALID_EOD_PRICE_VESSEL'), {}
    if not prices:
        return dict(meta,status='NO_VERIFIED_EOD_PRICE_ROWS'), {}
    meta['stock_count']=len(prices)
    tdcc_root=root/'ownership'/'tdcc'
    available=[]
    for folder in sorted(tdcc_root.glob('20??????')):
        snap=folder.name
        try:
            snap_date=date.fromisoformat(snap[:4]+'-'+snap[4:6]+'-'+snap[6:])
        except ValueError:
            continue
        if snap_date > date.fromisoformat(target) or snap_date > date.fromisoformat(observed_eod):
            continue
        receipt=load(folder/'receipt.json') or {}
        if receipt.get('status')!='COMPLETE' or receipt.get('snapshot_date')!=snap:
            continue
        if receipt.get('source')!='https://opendata.tdcc.com.tw/getOD.ashx?id=1-5':
            continue
        obs=str(receipt.get('observed_at_taipei') or '')
        try:
            observed=datetime.fromisoformat(obs)
            if observed.tzinfo is None:continue
            at_tw=observed.astimezone(ZoneInfo('Asia/Taipei'))
        except ValueError:
            continue
        if at_tw.date()>date.fromisoformat(target) or observed>datetime.now(ZoneInfo('Asia/Taipei')):
            continue
        raw=folder/'tdcc_1_5_raw.csv'
        if not raw.is_file():
            continue
        try:
            payload=raw.read_bytes()
        except OSError:
            continue
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=receipt.get('source_sha256'):
            continue
        grades={}
        bad=set()
        try:
            with raw.open(encoding='utf-8-sig',newline='') as f:
                rd=csv.DictReader(f)
                needed={'資料日期','證券代號','持股分級','人數','股數'}
                if not needed.issubset(rd.fieldnames or []):
                    continue
                for row in rd:
                    ticker=str(row.get('證券代號') or '').strip()
                    if ticker not in prices:
                        continue
                    if row.get('資料日期')!=snap:
                        bad.add(ticker)
                        continue
                    try:
                        grade=int(str(row['持股分級']).strip())
                        people=int(str(row['人數']).strip().replace(',',''))
                        shares=int(str(row['股數']).strip().replace(',',''))
                    except (ValueError, TypeError, OverflowError):
                        bad.add(ticker)
                        continue
                    if not (1<=grade<=17) or min(people,shares)<0:
                        bad.add(ticker)
                        continue
                    g=grades.setdefault(ticker,{})
                    if grade in g:
                        bad.add(ticker)
                    g[grade]=(people,shares)
        except (OSError,UnicodeError,csv.Error):
            continue
        validated={}
        for ticker,g in grades.items():
            if ticker in bad or not all(i in g for i in range(1,16)) or 17 not in g:
                continue
            total=g[17][1]
            adj=g.get(16,(0,0))[1]
            total15=sum(g[k][1] for k in range(1,16))
            small_shares=sum(g[k][1] for k in range(1,4))
            if total<=0 or small_shares>total or abs(total15-total)!=abs(adj):
                continue
            validated[ticker]={
               'small_holders':sum(g[k][0] for k in range(1,4)),
               'small_shares':small_shares,
               'other_shares':total-small_shares,
               'total_shares':total}
        available.append((snap,obs,digest,validated))
    if len(available)<2:
        return dict(meta,status='INSUFFICIENT_VERIFIED_TDCC_SNAPSHOTS',
                    validated_snapshot_count=len(available)),{}
    old,cur=available[-2:]
    old_date=date(int(old[0][:4]),int(old[0][4:6]),int(old[0][6:]))
    cur_date=date(int(cur[0][:4]),int(cur[0][4:6]),int(cur[0][6:]))
    gap=(cur_date-old_date).days
    age=(date.fromisoformat(target)-cur_date).days
    if not 5<=gap<=10 or age>14:
        return dict(meta,status='GAPPED_OR_STALE_TDCC_SNAPSHOTS',
                    last_tdcc_date=cur[0],last_gap_days=gap,age_days=age),{}
    meta.update(status='VERIFIED_TWO_GROUP_RESEARCH',last_tdcc_date=cur[0],
                previous_tdcc_date=old[0],first_observed_taipei=cur[1],
                verified_raw_sha256={old[0]:old[2],cur[0]:cur[2]},
                days_between_snapshots=gap,age_days=age,
                representative_scope='ALL_MATCHED_TWSE_EOD_PRICE_ROWS',
                share_change_threshold_pp_for_description=0.05,
                caveat='The 0.05pp descriptive grouping is not a validated trade threshold; accounts may cross grades.')
    groups={'其他持有人比重增加':0,'散戶持股比重增加':0,'變化不明顯':0}
    excluded={'MISSING_OR_INVALID_TDCC_GRADES':0,'SHARE_CAPITAL_CHANGE_GT_1PCT':0}
    result={}
    for ticker in sorted(prices):
        x=old[3].get(ticker);y=cur[3].get(ticker)
        if not x or not y:
            excluded['MISSING_OR_INVALID_TDCC_GRADES']+=1
            continue
        cap=100*(y['total_shares']/x['total_shares']-1)
        if abs(cap)>1:
            excluded['SHARE_CAPITAL_CHANGE_GT_1PCT']+=1
            continue
        small_share_pp=100*(y['small_shares']/y['total_shares']-
                            x['small_shares']/x['total_shares'])
        direction=('散戶持股比重增加' if small_share_pp>=0.05 else
                   '其他持有人比重增加' if small_share_pp<=-0.05 else
                   '變化不明顯')
        groups[direction]+=1
        small_change=y['small_shares']-x['small_shares']
        people_change=y['small_holders']-x['small_holders']
        result[ticker]={
          'status':'COMPARABLE','snapshot_date':cur[0],
          'first_observed_taipei':cur[1],
          'previous_snapshot_date':old[0],
          'small_holders':y['small_holders'],
          'small_shares':y['small_shares'],'other_shares':y['other_shares'],
          'total_shares':y['total_shares'],
          'small_holders_delta':people_change,
          'small_shares_delta':small_change,
          'other_shares_delta':y['other_shares']-x['other_shares'],
          'small_share_delta_pp':round(small_share_pp,6),
          'other_share_delta_pp':round(-small_share_pp,6),
          'capital_delta_pct':round(cap,6),
          'holder_shares_disagree':small_change*people_change<0,
          'two_group_direction':direction,
          'price_relation':'PRICE_PATH_REQUIRES_SEPARATE_VALIDATED_EOD_COMPARISON',
          'ownership_is_legal_identity':False,
          'trade_authority':False}
    meta['comparable_stock_count']=len(result)
    meta['exclusions']=excluded
    meta['categories']=groups
    meta['people_and_shares_disagree_count']=sum(r['holder_shares_disagree'] for r in result.values())
    meta['actual_small_shares_up_count']=sum(r['small_shares_delta']>0 for r in result.values())
    meta['actual_small_shares_down_count']=sum(r['small_shares_delta']<0 for r in result.values())
    if len(available)>=3:
        prev=available[-3]
        prev_date=date(int(prev[0][:4]),int(prev[0][4:6]),int(prev[0][6:]))
        if 5<=(old_date-prev_date).days<=10:
            up=down=0
            for ticker,r in result.items():
                z=prev[3].get(ticker);x=old[3].get(ticker)
                if not z or not x or abs(100*(x['total_shares']/z['total_shares']-1))>1:continue
                prior_delta=x['small_shares']-z['small_shares']
                up+=int(prior_delta>0 and r['small_shares_delta']>0)
                down+=int(prior_delta<0 and r['small_shares_delta']<0)
            meta['two_consecutive_observed_intervals']={
                'first':prev[0]+'..'+old[0],'second':old[0]+'..'+cur[0],
                'small_shares_up_both':up,'small_shares_down_both':down,
                'not_a_full_2026_13week_panel':True}
    return meta,result




def price_pair_for_same_tdcc_weeks(root, old_snapshot, new_snapshot):
    """Verified EOD closes matching the actual TDCC reference dates, never a future close."""
    def closes(snapshot):
        if not isinstance(snapshot,str) or len(snapshot)!=8 or not snapshot.isdigit():
            return None
        day=snapshot[:4]+'-'+snapshot[4:6]+'-'+snapshot[6:8]
        folder=root/'eod'/snapshot
        status=load(folder/'status.json') or {}
        if not (status.get('formal_complete_day') is True and
                status.get('downstream_ready') is True and
                all(status.get(leg+'_date')==day for leg in ('price','institutional','margin'))):
            return None
        prices={}
        files=sorted(folder.glob('price_*.csv'))
        if not files:return None
        try:
            for file in files:
                with file.open(encoding='utf-8-sig',newline='') as f:
                    reader=csv.DictReader(f)
                    if not {'Date','Ticker','Close'}.issubset(reader.fieldnames or ()):
                        return None
                    for row in reader:
                        t=str(row.get('Ticker') or '')
                        if row.get('Date')!=day or len(t)!=4 or not t.isdigit():continue
                        try:
                            p=float(str(row['Close']).replace(',',''))
                            if 0<p<float('inf'):prices[t]=p
                        except (ValueError,TypeError):pass
        except (OSError,UnicodeError,csv.Error):
            return None
        return prices or None
    a=closes(old_snapshot)
    b=closes(new_snapshot)
    if not a or not b:
        return {'status':'MISSING_VERIFIED_MATCHED_WEEKLY_EOD_PRICES'},{}
    changes={t:100*(v/a[t]-1) for t,v in b.items() if t in a and a[t]>0}
    return {'status':'VERIFIED_REFERENCE_WEEK_PRICES',
            'first_eod_date':old_snapshot,'last_eod_date':new_snapshot,
            'data_role':'RETROSPECTIVE_SAME_WEEK_PAIR_NOT_TRADE_SIGNAL'},changes


def build(root, original, summary=None):
    target=original.get('target_tw_date')
    day=original.get('latest_verified_eod')
    output={'schema':SCHEMA,'target_tw_date':target,'observed_eod_date':day,
      'authority':{'formal_escape':False,'new_selection':False,'trade':False,'capital':False},
      'readiness':'BLOCKED','market_environment':{},'mother':{},'candidates':[],
      'capital_cycle_claim_gate':{'status':'HISTORICAL_CYCLE_UNVERIFIED',
        'historical_phase_claim_authorized':False,
        'short_window_alerts_are_historical_phases':False,
        'gross_total_summary_is_longitudinal_event_path':False,
        'governance':'governance/HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.json',
        'reason':'累計gross總和與最近5日/兩週警報均不足以判定多年播種、施肥或收割'}}
    if not isinstance(day,str) or not isinstance(target,str) or not day or day>target:
        output['reason']='原HBA無可核對的歷史EOD時間；不得使用未來資料';return output
    e=market_context(root,day)
    fugle=load(root/'escape_live/twse_common_status.json') or {}
    recorded=str(fugle.get('generated_at_taipei') or '')[:10]
    denied=any('HTTP_403' in str(err) for err in (fugle.get('errors') or []))
    finmind=load(root/'escape_live/finmind_twse_common_status.json') or {}
    monitor=load(root/'escape_live/intraday_monitor.json') or {}
    monitor_date=str(monitor.get('market_date') or '')
    full_coverage=monitor.get('active_universe_transport_full_coverage') is True
    finmind_source=monitor.get('source')=='FinMind taiwan_stock_tick_snapshot'
    matched_monitor=(finmind_source and monitor_date==day and full_coverage and
                     monitor.get('monitor_state')=='LIVE_CONTEXT_READY' and
                     monitor.get('formal_escape_authority') is False and
                     monitor.get('formal_eod_authority') is False)
    overseas=original.get('external_environment') or {}
    output['market_environment']={'canonical':e,'overseas':{'label':overseas.get('label','資料不足'),
         'status':overseas.get('status','資料不足'),
         'official_source_observation':overseas.get('individual_sources'),
         'observation_role':'SOURCE_ONLY_NOT_GOVERNED_COMPOSITE_FORECAST' if overseas.get('individual_sources') else 'NOT_AVAILABLE',
         'preopen_individual_sources':overseas.get('individual_sources_preopen'),
         'postopen_individual_sources':overseas.get('individual_sources_postopen')},
         's5':{'status':'NOT_PROVIDED','reason':'未取得原凍結9特徵的正式分類憑證，不能由下跌家數擅自推定'},
         'escape':{'status':'NOT_PROVIDED','reason':'只接受既有狀態機結果，不能自行製造L0至L6'},
         'full_market_intraday_monitor':{
            'primary_source':'FinMind taiwan_stock_tick_snapshot',
            'observed_market_date':monitor_date or None,
            'status':'OBSERVED_SAME_SESSION_SHADOW' if matched_monitor else 'NO_MATCHING_FINMIND_SHADOW',
            'transport_full_coverage':full_coverage if matched_monitor else None,
            'active_required_count':monitor.get('active_required_count') if matched_monitor else None,
            'valid_metric_count':monitor.get('finmind_metric_observation_count') if matched_monitor else None,
            'unknown_metric_count':monitor.get('metric_unknown_count') if matched_monitor else None,
            'authority':'DESCRIPTIVE_PRICE_LIQUIDITY_ONLY_NO_FORMAL_ESCAPE_OR_EOD',
            'note':'GitHub紀錄中的全股盤中監控使用FinMind；資料可能是歷史觀測，不能視為查詢當下即時行情'},
         'fugle_whole_market_batch':{'last_attempt_date':recorded or None,
            'status':'HISTORICAL_403' if denied and recorded !=day else
                     'CURRENT_403' if denied else 'NO_CURRENT_VERIFIED_BATCH_SNAPSHOT',
            'note':'個股報價可用不代表全上市批次端點有權限；不阻斷canonical EOD'},
         'finmind_shadow':{'status':finmind.get('state','NOT_AVAILABLE'),
            'latest_source_timestamp':finmind.get('latest_source_timestamp'),
            'role':'INTRADAY_PRICE_LIQUIDITY_SHADOW_ONLY'}}
    m,stocks=read_lifelong_summary(summary,day)
    m,stocks=fold_verified_original_eod(root,day,m,stocks)
    output['mother']=m
    # Research annotation only: the original HBA thresholds, tiers and registry stay frozen.
    # Raw TDCC grade 1-3 shares cannot be inferred from TotalHolders or Big400Pct.
    tg_meta,tg_stocks=read_existing_two_group_tdcc(root,target,day)
    output['two_group_research']=tg_meta
    # Full-market research registry: independent of original 307 short-window HBA alerts.
    # Price is paired with the same two reference TDCC weeks, NOT current-day EOD.
    price_meta, price_changes=price_pair_for_same_tdcc_weeks(
        root,tg_meta.get('previous_tdcc_date'),tg_meta.get('last_tdcc_date'))
    tg_meta['price_pair']=price_meta
    patterns={'UP_OTHER_SHARE_GAIN':0,'UP_SMALL_SHARE_GAIN':0,
              'DOWN_SMALL_SHARE_GAIN':0,'DOWN_OTHER_SHARE_GAIN':0,
              'FLAT_OR_UNCLASSIFIED':0,'PRICE_PAIR_MISSING':0}
    market_registry=[]
    for ticker,row in sorted(tg_stocks.items()):
        # Avoid repeating all constant provenance and audit labels 1,000+ times.
        # Full receipt/date/coverage/provenance is retained in two_group_research;
        # all numerically meaningful stock-level shares and changes remain here.
        rec={k:row[k] for k in (
            'small_holders','small_shares','other_shares',
            'small_holders_delta','small_shares_delta','other_shares_delta',
            'small_share_delta_pp','two_group_direction')}
        rec['ticker']=ticker
        delta=price_changes.get(ticker)
        rec['same_week_price_return_pct']=round(delta,4) if delta is not None else None
        small=row['small_share_delta_pp']
        if delta is None: pattern='PRICE_PAIR_MISSING'
        elif delta>0 and small<=-0.05:pattern='UP_OTHER_SHARE_GAIN'
        elif delta>0 and small>=0.05:pattern='UP_SMALL_SHARE_GAIN'
        elif delta<0 and small>=0.05:pattern='DOWN_SMALL_SHARE_GAIN'
        elif delta<0 and small<=-0.05:pattern='DOWN_OTHER_SHARE_GAIN'
        else:pattern='FLAT_OR_UNCLASSIFIED'
        patterns[pattern]+=1
        rec['same_week_price_ownership_pattern']=pattern
        market_registry.append(rec)
    tg_meta['market_registry_stock_fields']='ticker,small_holders,small_shares,other_shares,small_holders_delta,small_shares_delta,other_shares_delta,small_share_delta_pp,two_group_direction,same_week_price_return_pct,same_week_price_ownership_pattern'
    tg_meta['derived_per_stock_fields']='total_shares=small_shares+other_shares; holder_shares_disagree=(small_holders_delta*small_shares_delta<0); selection_authority=false at output.authority'
    tg_meta['per_stock_provenance_ref']='two_group_research.verified_raw_sha256 and first_observed_taipei'
    tg_meta['price_share_pattern_counts']=patterns
    tg_meta['market_registry_total']=len(market_registry)
    tg_meta['multiweek_a_to_b_cycle_validated']=False
    output['two_group_market_registry']=market_registry
    tg_index={x['ticker']:x for x in market_registry}
    # Consume the existing HBA full evidence list, not its top-15 display subset.
    full=original.get('all_candidates')
    has_full=isinstance(full,list)
    observed=full if has_full else (original.get('candidates') or [])+(original.get('exit_alerts') or [])
    observed=[row for row in observed if isinstance(row,dict)]
    total=original.get('total_candidates_before_limit')
    output['candidate_coverage']={
        'source':'ORIGINAL_HBA_FULL_REGISTRY' if has_full else 'LEGACY_HBA_DISPLAY_SUBSET',
        'original_total':total if isinstance(total,int) else None,
        'represented':len(observed),
        'truncated':bool(isinstance(total,int) and len(observed)<total),
        'authority':'SHORT_WINDOW_SURVEILLANCE_ONLY_NO_SELECTION_OR_TRADING',
    }
    for item in observed:
        ticker=str(item.get('ticker'))
        output['candidates'].append({'ticker':ticker,'original_stage':item.get('stage'),
           'original_stage_scope':'SHORT_WINDOW_SURVEILLANCE_ONLY',
           'historical_cycle_stage':'HISTORICAL_CYCLE_UNVERIFIED',
           'historical_phase_claim_authorized':False,
           'historical_flow':stocks.get(ticker),
           'historical_flow_available':ticker in stocks,
           'two_group':tg_index.get(ticker),
           'two_group_available':ticker in tg_index,
           'original_decision_readiness':item.get('decision_readiness')})
    if e['canonical_eod']=='COMPLETE' and original.get('data_gate')!='BLOCKED':
        output['readiness']='RESEARCH_READY' if m['status']=='AVAILABLE_RESEARCH_PROXY' else 'EOD_READY_LONG_TERM_MISSING'
    return output


def markdown(x):
    market=x['market_environment'].get('canonical',{})
    breadth=market.get('breadth',{})
    mother=x.get('mother',{})
    lines=[f"# 衡策每日整合雷達（唯讀）｜{x.get('target_tw_date')}",'',
     f"- 實際可核驗收盤日：**{x.get('observed_eod_date')}**｜狀態：**{x['readiness']}**",
     f"- 原始EOD三腿：{market.get('canonical_eod','資料不足')}",
     f"- 收盤環境：上漲 {breadth.get('advancing_count','?')}／下跌 {breadth.get('declining_count','?')}（有效 {breadth.get('observed_count','?')} 檔）",
     f"- 前一筆廣度觀測：{(market.get('prior_breadth') or {}).get('date','資料不足')}",
     f"- 全上市監控（FinMind）：{x['market_environment'].get('full_market_intraday_monitor',{}).get('status')}（盤中影子，非正式EOD）",
     f"- Fugle全市場批次（非主要監控）：{x['market_environment'].get('fugle_whole_market_batch',{}).get('status')}",
     '- S5及Escape正式級別：缺來源憑證時保持「資料不足」，不自行新增評級',
     f"- 多年資金紀錄：{mother.get('status','資料不足')}",
     '- **多年播種／施肥／收割：歷史階段未判定**。累計買賣總和與短期偵查警示不能代替完整逐日資金＋集保時序稽核。','']
    tg=x.get('two_group_research') or {}
    lines.extend(['','## 散戶與其他所有持有人：原始實股側錄（不改原HBA分層）',
        f"- 研究側錄狀態：{tg.get('status','資料不足')}；集保週：{tg.get('last_tdcc_date') or '無'}；最早可知收件：{tg.get('first_observed_taipei') or '未核對'}",
        f"- 對應正式EOD上市股票 {tg.get('stock_count',0):,} 檔；股本穩定可比較 {tg.get('comparable_stock_count',0):,} 檔",
        f"- 其他端占比增加 {tg.get('categories',{}).get('其他持有人比重增加',0):,}；散戶端占比增加 {tg.get('categories',{}).get('散戶持股比重增加',0):,}；變化不明顯 {tg.get('categories',{}).get('變化不明顯',0):,}（0.05pp僅分組觀察，不是選股門檻）",
        '- 散戶＝集保1至3級距實股及人數；其他＝集保總股數扣除散戶實股。股數移動與人數不等價。',
        '- 只核驗相鄰有效集保週；2026完整13週歷史未接續時，禁止推估多年或13週連續籌碼階段。',
        '- 原HBA 5日訊號及其排序僅保留作原始警報；不得把下列側錄誤認為正式買進順位。'])
    patterns=tg.get('price_share_pattern_counts') or {}
    lines.extend([
        f"- 同週股價／兩方持股：{(tg.get('price_pair') or {}).get('status','資料不足')}；上漲其他占比增加 {patterns.get('UP_OTHER_SHARE_GAIN',0):,}、上漲散戶占比增加 {patterns.get('UP_SMALL_SHARE_GAIN',0):,}、下跌散戶承接 {patterns.get('DOWN_SMALL_SHARE_GAIN',0):,}、下跌其他增加 {patterns.get('DOWN_OTHER_SHARE_GAIN',0):,}。",
        '- 一週價籌配對不是已確認的跨週A/B完整循環；不得轉為正式選股順位。',
    ])
    if mother.get('status')=='AVAILABLE_RESEARCH_PROXY':
        lines.extend([f"- 期間 {mother['first_date']} 至 {mother['asof']}：{mother['distinct_tickers']:,}檔，完整買進 {mother['gross_buy_shares']:,}股，完整賣出 {mother['gross_sell_shares']:,}股",
          f"- 期末累計淨差占總買賣量小於1%：{mother['net_below_one_percent_count']:,}檔（描述性，不是買進門檻）"])
    lines+=['','## 原監測名單 × 多年資金流水（不改原信號評級）']
    for row in x['candidates']:
        h=row['historical_flow']
        details=(f"累計買{h['gross_buy_shares']:,}／賣{h['gross_sell_shares']:,}股；淨差占總量{h['net_abs_to_gross_pct']}%" if h else '多年資料未接上')
        g=row.get('two_group')
        actual=(f"；10張以下實股變化{g['small_shares_delta']:+,}股、其他實股變化{g['other_shares_delta']:+,}股；{g['two_group_direction']}" if g else '；兩方實股不可比或未核驗')
        lines.append(f"- {row['ticker']}：原短期分層{row['original_stage']}；{details}{actual}")
    lines+=['','本輸出為研究附加觀測，沒有下單或資金調度權限。']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--hba-input',type=Path,default=Path('research/hba_surveillance/latest.json'))
    p.add_argument('--mother-summary',type=Path,default=None)
    p.add_argument('--out',type=Path,default=Path('research/hba_surveillance/integrated_latest.json'))
    a=p.parse_args()
    original=load(a.root/a.hba_input)
    if not original:raise SystemExit('FAIL_CLOSED: existing HBA latest.json missing')
    result=build(a.root,original,a.mother_summary)
    out=a.root/a.out;out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    out.with_suffix('.md').write_text(markdown(result),encoding='utf-8')
    print(json.dumps({'readiness':result['readiness'],'observed_eod_date':result.get('observed_eod_date'),
       'mother_status':result['mother'].get('status')},ensure_ascii=False))

if __name__=='__main__':main()
