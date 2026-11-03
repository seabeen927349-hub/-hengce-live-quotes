#!/usr/bin/env python3
"""Append-only hash-chain writer for HENGCE escape black box.
Never overwrites an observation. Revisions are new RECONCILIATION records.
"""
import argparse, hashlib, json
from pathlib import Path

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_obj(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()

def read_last(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    last = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = json.loads(line)
    return last

def existing_keys(path):
    out = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[r["record_key"]] = r
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("packet")
    ap.add_argument("--phase", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--supersedes-record-hash")
    a = ap.parse_args()
    ledger = Path(a.ledger)
    packet = json.loads(Path(a.packet).read_text(encoding="utf-8"))
    trade_date = packet.get("trade_date")
    if not trade_date:
        raise SystemExit("trade_date required")
    phase = a.phase
    if phase not in {"INTRADAY", "CLOSE_PRELIM", "EOD_FORMAL", "OWNERSHIP_WEEKLY", "NEXT_DAY_RECONCILIATION"}:
        raise SystemExit("invalid phase")
    key = f"{trade_date}|{phase}|{a.run_id}"
    if key in existing_keys(ledger):
        raise SystemExit("record_key already exists; overwrite forbidden")
    prev = read_last(ledger)
    body = {
        "record_key": key,
        "observed_at_taipei": packet.get("asof_taipei"),
        "trade_date": trade_date,
        "phase": phase,
        "run_id": a.run_id,
        "source_hashes": packet.get("source_hashes", {}),
        "universe_hash": packet.get("universe_hash"),
        "raw_feature_hash": packet.get("raw_feature_hash") or sha256_obj(packet.get("raw_features", {})),
        "state_output": packet.get("state_output"),
        "data_gate": packet.get("data_gate"),
        "missing_data": packet.get("missing_data", []),
        "false_alarm_tracking": packet.get("false_alarm_tracking", {}),
        "previous_record_hash": prev.get("record_hash") if prev else None,
        "supersedes_record_hash": a.supersedes_record_hash,
    }
    body["record_hash"] = sha256_obj(body)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({
        "status": "APPENDED",
        "record_key": key,
        "record_hash": body["record_hash"],
        "previous_record_hash": body["previous_record_hash"]
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
