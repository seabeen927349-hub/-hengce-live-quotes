#!/usr/bin/env python3
import json, argparse
import numpy as np
import pandas as pd


def load_spec(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_frame(df, spec):
    features = spec["features"]
    missing = [c for c in features if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    center = np.array([spec["scaler"]["center_median"][f] for f in features], dtype=float)
    scale = np.array([spec["scaler"]["scale_iqr"][f] for f in features], dtype=float)
    names = ["DIFFUSE_NORMAL", "SYNCHRONIZED_STRESS"]
    centroids = np.array([
        [spec["states"][s]["centroid_robust_space"][f] for f in features]
        for s in names
    ], dtype=float)

    out = df.copy()
    valid = out[features].notna().all(axis=1).to_numpy()
    states = np.array(["UNKNOWN_FAIL_CLOSED"] * len(out), dtype=object)
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

    out["HENGCE_STATE_S5"] = states
    out["STATE_DISTANCE_DIFFUSE_NORMAL"] = d0
    out["STATE_DISTANCE_SYNCHRONIZED_STRESS"] = d1
    out["STATE_DISTANCE_MARGIN_FRACTION"] = margin
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    spec = load_spec(args.spec)
    df = pd.read_csv(args.input)
    out = classify_frame(df, spec)
    out.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
