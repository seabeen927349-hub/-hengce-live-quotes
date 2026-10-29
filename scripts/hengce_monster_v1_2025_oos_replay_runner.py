#!/usr/bin/env python3
"""Scope-correct runner for the isolated Monster V1 OOS reconstruction."""
import pandas as pd
import hengce_monster_v1_2025_oos_replay as m

def compare_2026_only(events, validation_end):
    e=events[(events['Date']>=pd.Timestamp('2026-01-01')) & (events['Date']<=pd.Timestamp(validation_end))]
    got=set((d.strftime('%Y-%m-%d'),str(t)) for d,t in zip(e['Date'],e['Ticker']))
    tp=len(got & m.FROZEN_SET); extra=sorted(got-m.FROZEN_SET); missing=sorted(m.FROZEN_SET-got)
    return {'n_got':len(got),'n_frozen':len(m.FROZEN_SET),'tp':tp,'extra_n':len(extra),'missing_n':len(missing),
            'exact':got==m.FROZEN_SET,'extra':extra,'missing':missing}

m.compare=compare_2026_only
m.main()
