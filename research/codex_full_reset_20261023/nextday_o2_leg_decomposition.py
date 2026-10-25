#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import defaultdict
from pathlib import Path
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as o2

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_o2_leg_decomposition_result.json'
COSTS=(0.0,0.002)
PERIODS={
 '2024_DEV':('2024-01-01','2024-12-31'),
 '2025_REUSED_VALIDATION':('2025-01-01','2025-12-31'),
 '2026_DIAGNOSTIC':('2026-01-01','2026-10-22'),
}

def safe_ret(a,b):
    return b/a-1 if a and b and a>0 and b>0 else None

def enrich(r):
    d=r['signal_date']; i=o2.di[d]
    ed=o2.dates[i+1]; xd=o2.dates[i+2]
    s=o2.by[d][r['ticker']]; e=o2.by[ed][r['ticker']]; x=o2.by[xd][r['ticker']]
    z=dict(r)
    z.update({
      'signal_close_to_entry_open':safe_ret(s['c'],e['o']),
      'entry_open_to_entry_close':safe_ret(e['o'],e['c']),
      'entry_close_to_exit_open':safe_ret(e['c'],x['o']),
      'exit_open_to_exit_close':safe_ret(x['o'],x['c']),
      'entry_open_to_exit_open':safe_ret(e['o'],x['o']),
      'entry_close_to_exit_close':safe_ret(e['c'],x['c']),
      'entry_open_to_exit_close':safe_ret(e['o'],x['c']),
    })
    return z

rows=[enrich(r) for r in o2.selected]
all_rows=[enrich(r) for r in o2.scored if r['signal_date']>='2024-01-01']
LEGS=('signal_close_to_entry_open','entry_open_to_entry_close','entry_close_to_exit_open','exit_open_to_exit_close')
STRATS=('entry_open_to_entry_close','entry_close_to_exit_open','entry_open_to_exit_open','entry_close_to_exit_close','entry_open_to_exit_close')

def stat(vals,cost=0.0):
    xs=[x-cost for x in vals if x is not None and math.isfinite(x)]
    if not xs:return {'n':0}
    return {
      'n':len(xs),'wins':sum(x>0 for x in xs),'win_rate':sum(x>0 for x in xs)/len(xs),
      'mean':statistics.mean(xs),'median':statistics.median(xs),'worst':min(xs),'best':max(xs),
    }

def summarize(rs):
    return {
      'trades':len(rs),
      'gross_legs':{k:stat([r[k] for r in rs],0.0) for k in LEGS},
      'strategy_windows':{k:{str(c):stat([r[k] for r in rs],c) for c in COSTS} for k in STRATS},
    }

def split(rs,p): return [r for r in rs if p[0]<=r['signal_date']<=p[1]]

by_year={k:summarize(split(rows,p)) for k,p in PERIODS.items()}
all_by_year={k:summarize(split(all_rows,p)) for k,p in PERIODS.items()}

# Family decomposition on selected O2 only. Diagnostic: no family is promoted from this audit.
fams=defaultdict(list)
for r in rows:fams[r['family']].append(r)
family_summary={f:summarize(rs) for f,rs in sorted(fams.items())}

# Identify which owned leg contributes most negative arithmetic return, using only selected 2024 development.
dev=split(rows,PERIODS['2024_DEV'])
owned_leg_means={k:stat([r[k] for r in dev])['mean'] for k in ('entry_open_to_entry_close','entry_close_to_exit_open','exit_open_to_exit_close')}
worst_owned_leg=min(owned_leg_means,key=owned_leg_means.get) if owned_leg_means else None

res={
 'status':'DIAGNOSTIC_ONLY_NO_MODEL_SELECTION',
 'source_model':'O2 strict-nextday reversal analog tail-risk model',
 'source_status':o2.res['status'],
 'purpose':'Before adding another selection rule, decompose exactly where O2 return is earned/lost and compare executable exit windows.',
 'definitions':{
   'signal_close_to_entry_open':'unowned gap from signal-day close to executable next open',
   'entry_open_to_entry_close':'t+1 open -> t+1 close; same-session trade after signal',
   'entry_close_to_exit_open':'t+1 close -> t+2 open; pure overnight leg (requires a separate close-entry implementation)',
   'exit_open_to_exit_close':'t+2 open -> t+2 close; second-session intraday leg',
   'entry_open_to_exit_open':'t+1 open -> t+2 open; executable overnight window',
   'entry_close_to_exit_close':'t+1 close -> t+2 close; close-to-next-close window',
   'entry_open_to_exit_close':'current O-series definition: t+1 open -> t+2 close',
 },
 'cost_note':'20bp is applied as a simple round-trip stress to each strategy window, not to individual path legs.',
 'selected_o2':by_year,
 'all_o2_daily_scored_picks':all_by_year,
 'selected_family_summary':family_summary,
 '2024_owned_leg_means':owned_leg_means,
 '2024_worst_owned_leg':worst_owned_leg,
 'research_boundary':'Diagnostic only. Results must not be presented as a new holdout-qualified model; 2025/2026 were already exposed in the broader project.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('LEG_AUDIT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
