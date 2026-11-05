#!/usr/bin/env python3
"""HENGCE research-only bottom discrimination query; NEVER a stock recommendation.
Historical point-time feature snapshot requires EOD; does not recreate Q017 09:01.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
from sklearn.metrics import roc_auc_score
from train_bottom_classifier import read_mother,feat_stocks,CLASSES

DEFAULT_GATE={'window_days':130,'minimum_decisive_examples':100,'minimum_event_days':20,
              'auc_min':.55,'model_prob_min':.65}


def gate_health(health_file:Path,asof:str)->dict:
    z=pd.read_csv(health_file,dtype={'Ticker':str},parse_dates=['Date','label_matured_on'])
    d=pd.Timestamp(asof)
    q=z.loc[(z.label_matured_on<d)&(z.label_matured_on>=d-pd.Timedelta(days=DEFAULT_GATE['window_days']))
       &z.label.isin(['TRUE_BOTTOM','FAKE_BOTTOM'])]
    au=None
    if (len(q)>=DEFAULT_GATE['minimum_decisive_examples'] and q.Date.nunique()>=DEFAULT_GATE['minimum_event_days'] and q.label.nunique()==2):
        au=float(roc_auc_score(q.label.eq('TRUE_BOTTOM'),q.signal_ratio))
    pass_health=au is not None and au>=DEFAULT_GATE['auc_min']
    return {'status':'PASS' if pass_health else ('FAIL' if au is not None else 'NOT_ENOUGH_MATURE_EVIDENCE'),
        'recent_mature_decisive_samples':int(len(q)),
        'recent_event_dates':int(q.Date.nunique()),
        'decisive_auc':round(au,4) if au is not None else None,
        'rule':DEFAULT_GATE}


def score(mother:Path,model_path:Path,health_file:Path,ticker:str,asof:str)->dict:
    if pd.Timestamp(asof)>pd.Timestamp('2026-11-04'):
        raise ValueError('Current frozen research artifact contains no post-2026-11-04 EOD; retraining and evidence refresh necessary')
    loaded=joblib.load(model_path)  # ONLY load this generated, trusted local file.
    actualhash=hashlib.sha256(mother.read_bytes()).hexdigest()
    if actualhash != loaded['source_sha256']:
        raise ValueError('CANONICAL_SOURCE_SHA_MISMATCH; cannot transfer pretrained model to changed vessel')
    df=feat_stocks(read_mother(mother))
    r=df.loc[(df.Ticker==str(ticker))&(df.Date==pd.Timestamp(asof))]
    if len(r)!=1:
        return {'ticker':ticker,'asof':asof,'status':'NO_VALID_COMPLETE_EOD',
            'may_recommend':False}
    row=r.iloc[0]
    raw_prob=loaded['model'].predict_proba(r[loaded['features']])[0]
    keys=list(loaded['model'].classes_)
    probs={k:round(float(raw_prob[keys.index(k)]),4) for k in CLASSES}
    health=gate_health(health_file,asof)
    in_scope=bool(row.cand_raw)
    technical= ('RESEARCH_TRUE_BOTTOM_CANDIDATE' if probs['TRUE_BOTTOM']>=loaded['threshold']
            and probs['TRUE_BOTTOM']>probs['FAKE_BOTTOM'] else
            'RESEARCH_FAKE_BOTTOM_WARNING' if probs['FAKE_BOTTOM']>=loaded['threshold']
            and probs['FAKE_BOTTOM']>probs['TRUE_BOTTOM'] else 'RESEARCH_UNCERTAIN')
    if not in_scope: decision='ABSTAIN_NOT_IN_BOTTOM_EVENT_UNIVERSE'
    elif health['status']!='PASS': decision='ABSTAIN_MODEL_HEALTH_NOT_VALIDATED'
    else:decision=technical
    return {'ticker':ticker,'asof':asof,'observation_time':'AFTER_COMPLETE_EOD_CLOSE',
        'status':decision,'technical_raw_model_class':technical,
        'in_scope':in_scope,'close':round(float(row.Close),3),
        'probabilities_exploratory_not_calibrated':probs,
        'model_health':health,'model_version':loaded['version'],
        'model_trained_without_2026_labels':True,
        'may_recommend':False,'may_trade':False,
        'notes':['Not a forecast of certain market lows. Does not restore retired Q017.',
                 'This model failed 2026 independent chronological evaluation.',
                 'Historical 09:01 observability cannot be rebuilt from daily-close features.',
                 'Health gate thresholds were devised after observed 2026 failures and are not independently validated.']}


def main():
    a=argparse.ArgumentParser();a.add_argument('--mother',required=True);a.add_argument('--model',required=True)
    a.add_argument('--health',required=True);a.add_argument('--ticker',required=True)
    a.add_argument('--asof',default='2026-11-04')
    x=a.parse_args()
    r=score(Path(x.mother),Path(x.model),Path(x.health),x.ticker,x.asof)
    print(json.dumps(r,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
