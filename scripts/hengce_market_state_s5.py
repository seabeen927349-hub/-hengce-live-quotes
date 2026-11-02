#!/usr/bin/env python3
"""HENGCE descriptive market-state classifier.

This module has NO trading authority. It classifies a contemporaneous
9-feature market observation into one of the frozen S5 descriptive states.
Missing required evidence fails closed.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / 'hengce' / 'market_state' / 'HENGCE_MARKET_STATE_CLASSIFIER_FREEZE_v1_0_20261102.json'


def load_spec(path=DEFAULT_SPEC):
    with Path(path).open('r', encoding='utf-8') as f:
        return json.load(f)


def classify_frame(df, spec=None):
    spec = spec or load_spec()
    features = spec['features']
    missing = [c for c in features if c not in df.columns]
    if missing:
        raise ValueError(f'Missing required columns: {missing}')

    center = np.array([spec['scaler']['center_median'][f] for f in features], dtype=float)
    scale = np.array([spec['scaler']['scale_iqr'][f] for f in features], dtype=float)
    names = ['DIFFUSE_NORMAL', 'SYNCHRONIZED_STRESS']
    centroids = np.array([
        [spec['states'][s]['centroid_robust_space'][f] for f in features]
        for s in names
    ], dtype=float)

    out = df.copy()
    valid = out[features].notna().all(axis=1).to_numpy()
    states = np.array(['UNKNOWN_FAIL_CLOSED'] * len(out), dtype=object)
    d0 = np.full(len(out), np.nan)
    d1 = np.full(len(out), np.nan)
    margin = np.full(len(out), np.nan)

    if valid.any():
        X = (out.loc[valid, features].to_numpy(dtype=float) - center) / scale
        ds = np.sqrt(((X[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2))
        chosen = ds.argmin(axis=1)
        states[valid] = np.array(names, dtype=object)[chosen]
        d0[valid] = ds[:, 0]
        d1[valid] = ds[:, 1]
        small = ds.min(axis=1)
        large = ds.max(axis=1)
        margin[valid] = np.where(large > 0, (large - small) / large, 0.0)

    out['HENGCE_STATE_S5'] = states
    out['STATE_DISTANCE_DIFFUSE_NORMAL'] = d0
    out['STATE_DISTANCE_SYNCHRONIZED_STRESS'] = d1
    out['STATE_DISTANCE_MARGIN_FRACTION'] = margin
    out['MARKET_STATE_AUTHORITY'] = 'DESCRIPTIVE_ONLY_NO_TRADING_AUTHORITY'
    return out


def classify_latest_csv(input_path, output_path=None, spec_path=DEFAULT_SPEC):
    spec = load_spec(spec_path)
    df = pd.read_csv(input_path)
    if df.empty:
        raise ValueError('Empty input observation matrix')
    out = classify_frame(df.tail(1), spec)
    row = out.iloc[-1]
    result = {
        'system': 'HENGCE',
        'module': 'MARKET_ENVIRONMENT_STATE_CLASSIFIER_S5',
        'status': 'PASS' if row['HENGCE_STATE_S5'] != 'UNKNOWN_FAIL_CLOSED' else 'UNKNOWN_FAIL_CLOSED',
        'state': row['HENGCE_STATE_S5'],
        'distance_diffuse_normal': None if pd.isna(row['STATE_DISTANCE_DIFFUSE_NORMAL']) else float(row['STATE_DISTANCE_DIFFUSE_NORMAL']),
        'distance_synchronized_stress': None if pd.isna(row['STATE_DISTANCE_SYNCHRONIZED_STRESS']) else float(row['STATE_DISTANCE_SYNCHRONIZED_STRESS']),
        'distance_margin_fraction': None if pd.isna(row['STATE_DISTANCE_MARGIN_FRACTION']) else float(row['STATE_DISTANCE_MARGIN_FRACTION']),
        'authority': 'DESCRIPTIVE_ONLY_NO_TRADING_AUTHORITY',
        'trading_effect': 'NONE',
    }
    for key in ('observation_date', 'market_event_date', 'observation_timestamp'):
        if key in row.index and not pd.isna(row[key]):
            result[key] = str(row[key])
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Observation-matrix CSV containing the frozen 9 S5 features')
    ap.add_argument('--output')
    ap.add_argument('--spec', default=str(DEFAULT_SPEC))
    ap.add_argument('--latest-only', action='store_true')
    args = ap.parse_args()

    if args.latest_only:
        result = classify_latest_csv(args.input, args.output, args.spec)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'PASS' else 2

    spec = load_spec(args.spec)
    df = pd.read_csv(args.input)
    out = classify_frame(df, spec)
    if not args.output:
        raise SystemExit('--output is required unless --latest-only is used only for stdout')
    out.to_csv(args.output, index=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
