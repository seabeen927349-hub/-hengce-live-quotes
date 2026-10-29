#!/usr/bin/env python3
"""Scope-correct, rate-limited runner for the isolated Monster V1 OOS reconstruction.

Research transport only. The model/frozen thresholds are untouched. This runner
only serializes official TWSE calls so the original HENGCE vessel is not rate-limited.
"""
import time
import pandas as pd
import hengce_monster_v1_2025_oos_replay as m

# Transport-only throttle around the exact existing original-vessel HTTP function.
_orig_get_json = m.vessel.core.get_json
_last_call = [0.0]

def throttled_get_json(*args, **kwargs):
    last_err = None
    for attempt in range(6):
        gap = time.monotonic() - _last_call[0]
        if gap < 0.75:
            time.sleep(0.75-gap)
        try:
            out = _orig_get_json(*args, **kwargs)
            _last_call[0] = time.monotonic()
            return out
        except Exception as e:
            last_err = e
            _last_call[0] = time.monotonic()
            # Empty/non-JSON/rate-limited responses are transport failures only.
            time.sleep(min(30.0, 3.0 * (2 ** attempt)))
    raise last_err

m.vessel.core.get_json = throttled_get_json

# Force one original-vessel day at a time; no parallel pressure on TWSE.
_orig_fetch_range = m.fetch_range

def serial_fetch_range(start, end, workers):
    return _orig_fetch_range(start, end, 1)

m.fetch_range = serial_fetch_range

def compare_2026_only(events, validation_end):
    e=events[(events['Date']>=pd.Timestamp('2026-01-01')) & (events['Date']<=pd.Timestamp(validation_end))]
    got=set((d.strftime('%Y-%m-%d'),str(t)) for d,t in zip(e['Date'],e['Ticker']))
    tp=len(got & m.FROZEN_SET); extra=sorted(got-m.FROZEN_SET); missing=sorted(m.FROZEN_SET-got)
    return {'n_got':len(got),'n_frozen':len(m.FROZEN_SET),'tp':tp,'extra_n':len(extra),'missing_n':len(missing),
            'exact':got==m.FROZEN_SET,'extra':extra,'missing':missing}

m.compare=compare_2026_only
m.main()
