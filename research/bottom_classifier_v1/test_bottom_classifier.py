"""Audits research-only evidence, data lineage, and a high-risk historical example."""
from pathlib import Path
import json, pandas as pd
BASE=Path(__file__).parent
j=json.loads((BASE/'evidence_report.json').read_text())
h=json.loads((BASE/'health_gate_evidence.json').read_text())
assert j['status']=='RESEARCH_ONLY_NOT_TRADEABLE'
assert j['event_count']==39115
assert j['winner']=='forest'
assert j['training_provenance']['train']=='events before 2022-11-25'
assert j['results']['test_2025']['true_vs_false_auc']>.6
assert j['results']['diagnostic_2026']['true_vs_false_auc']<.5
assert h['asof_2026_10_21']['gate']=='FAIL'
assert h['asof_2026_10_21']['rolling_auc']<.55
assert sum(z['events'] for z in h['by_year'] if z['year']==2026 and z['strategy']=='approved')==0
assert all(not z['observation_at'].startswith('09:01') for z in j['case_studies'])
assert len([z for z in j['case_studies'] if z['ticker']=='8150' and z['date']=='2026-10-21'])==1
p=pd.read_csv(BASE/'health_matured_events.csv',parse_dates=['Date','label_matured_on'])
assert p.label_matured_on.gt(p.Date).all()
assert p.Date.max().year==2026
print('RESEARCH_GUARDS_PASS: model rejected for live use; 2026 bottom discrimination invalid; 8150 abstained')
