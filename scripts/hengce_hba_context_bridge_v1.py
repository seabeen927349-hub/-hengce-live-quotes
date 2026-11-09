#!/usr/bin/env python3
"""Attach existing HENGCE environment and lifelong gross turnover to HBA daily report.

Read-only research adapter; does not fetch vendors, alter original vessels or grant
selection/position/order authority. All comparisons are point-in-time safe.
"""
import argparse
import csv
import json
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
         'status':overseas.get('status','資料不足')},
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
    output['mother']=m
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
    if mother.get('status')=='AVAILABLE_RESEARCH_PROXY':
        lines.extend([f"- 期間 {mother['first_date']} 至 {mother['asof']}：{mother['distinct_tickers']:,}檔，完整買進 {mother['gross_buy_shares']:,}股，完整賣出 {mother['gross_sell_shares']:,}股",
          f"- 期末累計淨差占總買賣量小於1%：{mother['net_below_one_percent_count']:,}檔（描述性，不是買進門檻）"])
    lines+=['','## 原監測名單 × 多年資金流水（不改原信號評級）']
    for row in x['candidates']:
        h=row['historical_flow']
        details=(f"累計買{h['gross_buy_shares']:,}／賣{h['gross_sell_shares']:,}股；淨差占總量{h['net_abs_to_gross_pct']}%" if h else '多年資料未接上')
        lines.append(f"- {row['ticker']}：{row['original_stage']}；{details}")
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
