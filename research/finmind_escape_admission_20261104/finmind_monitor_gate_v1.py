#!/usr/bin/env python3
"""Read-only HENGCE FinMind monitor evidence gate; never creates formal Escape or trading authority."""
import argparse, hashlib, json
from datetime import datetime
from pathlib import Path

SHA='1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281'

def digest(x):
    return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def require(ok,reason):
    if not ok: raise ValueError(reason)

def verify(context,status,monitor,expected_date):
    c,s,m=context,status,monitor
    require(c.get('schema')=='HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V3','BAD_CONTEXT_SCHEMA')
    require(s.get('schema')=='HENGCE_ESCAPE_FINMIND_TWSE_COMMON_SHADOW_STATUS_V3','BAD_STATUS_SCHEMA')
    require(m.get('schema')=='HENGCE_ESCAPE_INTRADAY_MONITOR_V1','BAD_MONITOR_SCHEMA')
    require(c.get('market_date')==m.get('market_date')==expected_date,'WRONG_MARKET_DATE')
    require(datetime.fromisoformat(c['generated_at_taipei']).date().isoformat()==expected_date,'WRONG_CAPTURE_DAY')
    require(c.get('generated_at_taipei')==s.get('generated_at_taipei')==m.get('generated_at_taipei'),'CAPTURE_TIMESTAMP_MISMATCH')
    require(c.get('latest_source_timestamp')==s.get('latest_source_timestamp')==m.get('latest_source_timestamp'),'SOURCE_TIMESTAMP_MISMATCH')
    for x in (c,s,m):
        require(x.get('metric_contract_sha256')==SHA,'METRIC_CONTRACT_MISMATCH')
        for k in ('feature_detector_input_authority','formal_metric_authority','trading_authority','per_security_rows_persisted','raw_finmind_rows_persisted'):
            require(x.get(k) is not True,'UNAUTHORIZED_'+k.upper())
    require(c.get('formal_escape_state_creation') is False,'ESCAPE_STATE_FORBIDDEN')
    require(s.get('formal_escape_authority') is False and m.get('formal_escape_authority') is False,'FORMAL_ESCAPE_AUTHORITY_FORBIDDEN')
    require(m.get('formal_escape_level') is None,'FORMAL_ESCAPE_LEVEL_FORBIDDEN')
    require(m.get('monitor_state')=='LIVE_CONTEXT_READY' and s.get('state')=='SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY','MONITOR_NOT_READY')
    require(s.get('healthy_transport') is True and s.get('active_universe_transport_full_coverage') is True,'TRANSPORT_NOT_READY')
    require(m.get('active_universe_transport_full_coverage') is True and s.get('unexpected_missing_count')==0,'COVERAGE_FAIL')
    require(c.get('payload_sha256')==digest({k:v for k,v in c.items() if k!='payload_sha256'}),'CONTEXT_HASH_FAIL')
    require(s.get('context_payload_sha256')==c['payload_sha256'],'STATUS_CONTEXT_HASH_FAIL')
    require(m.get('payload_sha256')==digest({k:v for k,v in m.items() if k!='payload_sha256'}),'MONITOR_HASH_FAIL')
    n=s.get('active_required_count'); valid=s.get('finmind_metric_observation_count'); stale=s.get('metric_unknown_count')
    require(all(type(z) is int and z>=0 for z in (n,valid,stale)) and valid+stale==n,'COUNT_FAIL')
    require(n==c.get('active_required_count')==m.get('active_required_count')==s.get('active_covered_count')==m.get('active_covered_count'),'UNIVERSE_COUNT_FAIL')
    require(valid==c.get('finmind_metric_observation_count')==m.get('finmind_metric_observation_count'),'VALID_COUNT_FAIL')
    require(stale==c.get('metric_unknown_count')==m.get('metric_unknown_count'),'STALE_COUNT_FAIL')
    market=c.get('market')
    require(isinstance(market,dict) and market==m.get('market'),'MARKET_MISMATCH')
    a,d,f=[market.get(k) for k in ('advance_count','decline_count','flat_count')]
    require(all(type(z) is int and z>=0 for z in (a,d,f)) and a+d+f==valid==market.get('return_observed_count'),'BREADTH_COUNT_FAIL')
    require(c.get('industry')==m.get('industry'),'INDUSTRY_MISMATCH')
    return {'system':'HENGCE','status':'PASS_INTRADAY_MONITOR_ONLY','date':expected_date,
            'captured_at_taipei':c['generated_at_taipei'],'source_timestamp':c['latest_source_timestamp'],
            'universe':n,'valid_return_rows':valid,'unknown_return_rows':stale,
            'advancing':a,'declining':d,'unchanged':f,'net_breadth':a-d,
            'equal_weight_change_rate_vendor_units':market.get('equal_weight_change_rate'),
            'context_sha256':c['payload_sha256'],'monitor_sha256':m['payload_sha256'],
            'formal_escape_level':None,'formal_escape_authority':False,'formal_selection_authority':False,
            'trading_authority':False,'formal_escape_reason':'REQUIRES_PIT_SAFE_17_METRIC_HISTORY_AND_FORMAL_GATE',
            'disclaimer':'Dated intraday research shadow, not latest close, model prediction, or trade signal'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--context',required=True);p.add_argument('--status',required=True);p.add_argument('--monitor',required=True);p.add_argument('--date',required=True)
    args=p.parse_args()
    try:
        x=verify(*[json.loads(Path(z).read_text(encoding='utf-8')) for z in (args.context,args.status,args.monitor)],args.date)
        code=0
    except Exception as e:
        x={'system':'HENGCE','status':'FAIL_CLOSED','reason':f'{type(e).__name__}:{e}','formal_escape_level':None,'trading_authority':False}
        code=2
    print(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2));return code
if __name__=='__main__':raise SystemExit(main())
