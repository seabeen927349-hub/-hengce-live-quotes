#!/usr/bin/env python3
"""Deterministic past-only event detector for HENGCE v2.4.7 escape monitor.
Input contains metric histories. Detector computes empirical adverse ranks and persistence.
No manually supplied event booleans are accepted as authority.
"""
import json, math, sys, hashlib
from pathlib import Path

BASELINE=60
MIN_BASELINE=40
SEVERE=0.90
MODERATE=0.80
METRIC_CONTRACT_VERSION='HENGCE_ESCAPE_METRIC_CONTRACT_V1'
METRIC_CONTRACT_SHA256='1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281'

METRICS={
  'foreign_relative_flow_5': ('low', 'negative'),
  'trust_relative_flow_5': ('low', 'negative'),
  'dealer_relative_flow_5': ('low', 'negative'),
  'totalnet_relative_flow_5': ('low', 'negative'),
  'totalnet_relative_flow_10': ('low', 'negative'),
  'flow_breadth_negative_share': ('high', None),
  'capital_migration_strength': ('high', None),
  'source_absolute_flow_5': ('low', 'negative'),
  'broad_market_absolute_flow_5': ('low', 'negative'),
  'destination_absorption_strength': ('high', 'positive'),
  'price_damage_score_raw': ('high', None),
  'price_recovery_score_raw': ('high', None),
  'flow_reentry_score_raw': ('high', None),
  'vulnerability_crowding_score_raw': ('high', None),
  'vulnerability_leverage_score_raw': ('high', None),
  'internal_structure_score_raw': ('high', None),
  'price_flow_divergence_score_raw': ('high', None)
}

FAMILIES={
  'VULNERABILITY':['vulnerability_crowding_score_raw','vulnerability_leverage_score_raw'],
  'INTERNAL_STRUCTURE':['internal_structure_score_raw'],
  'FLOW_PROPAGATION':['foreign_relative_flow_5','trust_relative_flow_5','dealer_relative_flow_5','totalnet_relative_flow_5','totalnet_relative_flow_10'],
  'FLOW_BREADTH':['flow_breadth_negative_share'],
  'CAPITAL_MIGRATION':['capital_migration_strength','destination_absorption_strength'],
  'LEVERAGE':['vulnerability_leverage_score_raw'],
  'PRICE_DAMAGE':['price_damage_score_raw'],
  'PRICE_FLOW_DIVERGENCE':['price_flow_divergence_score_raw'],
}

def finite(x): return isinstance(x,(int,float)) and math.isfinite(float(x))

def empirical_adverse(series, idx, direction):
    start=max(0,idx-BASELINE); hist=[float(x) for x in series[start:idx] if finite(x)]
    if len(hist)<MIN_BASELINE or not finite(series[idx]): return None
    cur=float(series[idx])
    if direction=='low':
        # adverse score 1 when current is at/below almost all prior values
        rank=sum(1 for x in hist if x>=cur)/len(hist)
    else:
        rank=sum(1 for x in hist if x<=cur)/len(hist)
    return rank

def sign_ok(v, sign):
    if not finite(v): return False
    if sign=='negative': return float(v)<0
    if sign=='positive': return float(v)>0
    return True

def flags(series, direction, sign, threshold=SEVERE):
    out=[]
    for i in range(len(series)):
        a=empirical_adverse(series,i,direction)
        out.append(a is not None and a>=threshold and sign_ok(series[i],sign))
    return out

def persist(flag_series, n, window):
    if len(flag_series)<window: return False
    return sum(bool(x) for x in flag_series[-window:])>=n

def latest_score(series,direction):
    if not series: return None
    a=empirical_adverse(series,len(series)-1,direction)
    return None if a is None else 100*a

def sha(obj):
    b=json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hashlib.sha256(b).hexdigest()

def detect(packet):
    if packet.get('metric_contract_version') != METRIC_CONTRACT_VERSION or packet.get('metric_contract_sha256') != METRIC_CONTRACT_SHA256:
        return {'status':'UNVERIFIED','reason':'METRIC_CONTRACT_MISMATCH','required_version':METRIC_CONTRACT_VERSION,'required_sha256':METRIC_CONTRACT_SHA256}
    gate=packet.get('data_gate',{})
    for k in ('freshness_pass','integrity_pass','pit_pass','universe_pass'):
        if not gate.get(k,False):
            return {'status':'UNVERIFIED','reason':f'GATE_FAIL:{k}'}
    hist=packet.get('metrics_history',{})
    missing=[m for m in METRICS if m not in hist or not isinstance(hist[m],list)]
    if missing:
        return {'status':'UNVERIFIED','reason':'MISSING_METRIC_HISTORY','missing':missing}
    lengths={len(hist[m]) for m in METRICS}
    if len(lengths)!=1 or next(iter(lengths))<MIN_BASELINE+6:
        return {'status':'UNVERIFIED','reason':'MISALIGNED_OR_TOO_SHORT_HISTORY','lengths':sorted(lengths)}
    scores={m:latest_score(hist[m],METRICS[m][0]) for m in METRICS}
    severe_flags={m:flags(hist[m],*METRICS[m],threshold=SEVERE) for m in METRICS}
    moderate_flags={m:flags(hist[m],*METRICS[m],threshold=MODERATE) for m in METRICS}
    ev={}
    for c in ('foreign','trust','dealer'):
        ev[f'{c}_negative_flow_confirmed']=persist(severe_flags[f'{c}_relative_flow_5'],3,5)
    ev['totalnet_negative_flow_confirmed']=persist(severe_flags['totalnet_relative_flow_5'],3,5)
    ev['flow_breadth_confirmed']=persist(severe_flags['flow_breadth_negative_share'],3,5)
    ev['capital_migration_confirmed']=persist(severe_flags['capital_migration_strength'],3,5)
    ev['medium_window_flow_confirmed']=persist(moderate_flags['totalnet_relative_flow_10'],4,6)
    ev['source_absolute_withdrawal_confirmed']=persist(severe_flags['source_absolute_flow_5'],3,5)
    ev['broad_market_absolute_withdrawal_confirmed']=persist(severe_flags['broad_market_absolute_flow_5'],3,5)
    ev['destination_absorption_confirmed']=persist(severe_flags['destination_absorption_strength'],3,5)
    ev['broad_price_damage_confirmed']=persist(severe_flags['price_damage_score_raw'],3,5)
    ev['price_recovery_confirmed']=persist(severe_flags['price_recovery_score_raw'],3,5)
    ev['flow_reentry_confirmed']=persist(severe_flags['flow_reentry_score_raw'],3,5)
    ev['vulnerability_crowding_confirmed']=persist(moderate_flags['vulnerability_crowding_score_raw'],3,5)
    ev['vulnerability_leverage_confirmed']=persist(moderate_flags['vulnerability_leverage_score_raw'],3,5)
    ev['internal_structure_confirmed']=persist(moderate_flags['internal_structure_score_raw'],3,5)
    ev['price_flow_divergence_confirmed']=persist(moderate_flags['price_flow_divergence_score_raw'],3,5)
    # five consecutive recovery observations, not merely 3-of-5
    r=[a and b for a,b in zip(severe_flags['price_recovery_score_raw'],severe_flags['flow_reentry_score_raw'])]
    ev['recovery_5_consecutive_confirmed']=len(r)>=5 and all(r[-5:])
    fam={}
    for f,ms in FAMILIES.items():
        vals=[scores[m] for m in ms if scores[m] is not None]
        fam[f]=None if not vals else sum(vals)/len(vals)
    return {
      'status':'PASS_DETECTOR',
      'detector_version':'HENGCE_ESCAPE_FEATURE_DETECTOR_V1',
      'baseline_sessions':BASELINE,'minimum_baseline_sessions':MIN_BASELINE,
      'severe_adverse_percentile':SEVERE,'moderate_adverse_percentile':MODERATE,
      'events':ev,'family_scores':fam,'metric_adverse_scores':scores,
      'metrics_history_hash':sha(hist),
      'manual_event_input_accepted':False,
      'metric_contract_version':METRIC_CONTRACT_VERSION,
      'metric_contract_sha256':METRIC_CONTRACT_SHA256
    }

def main():
    if len(sys.argv)!=2:
        print(json.dumps({'status':'USAGE','usage':'detector.py INPUT.json'})); return 2
    packet=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print(json.dumps(detect(packet),ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
