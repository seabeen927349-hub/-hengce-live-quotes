#!/usr/bin/env python3
"""HENGCE full-reset Stage A: offline corpus / PIT data audit.

Research-only.  This program does not fetch data, rank securities, create signals,
write production state, or grant any trading authority.  It inventories the frozen
research corpus and records what is usable (or broken) before any model search.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / "research" / "codex_full_reset_20261023"
RESULTS = RESET / "results"
FROZEN_BASE = "05bf0e35fb6a88473fd4f947952ef1b6875d3f88"

MEMBERSHIP_FILES = [
    "electronics_membership_pit_2023.csv",
    "electronics_membership_pit_2024.csv",
    "electronics_membership_pit_2025.csv",
    "electronics_membership_pit_2026_ytd.csv",
]
MACRO_FILES = [
    "sox_20220101_20261017.csv",
    "dxy_usdx_20220101_20261017.csv",
]
DATE_KEYS = (
    "date", "trade_date", "trading_date", "signal_date", "membership_date",
    "session_date", "asof_date", "as_of_date", "effective_date",
)
SYMBOL_KEYS = ("ticker", "symbol", "stock_id", "stock_no", "code")
ISO_DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
COMPACT_DATE_RE = re.compile(r"^20\d{6}$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def normalized_date(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if ISO_DATE_RE.match(s):
        return s
    if COMPACT_DATE_RE.match(s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return None


def first_key(row: dict[str, Any], candidates: Iterable[str]) -> str | None:
    lower = {str(k).strip().lower(): k for k in row}
    for c in candidates:
        if c in lower:
            return lower[c]
    return None


def audit_csv(path: Path, want_symbols: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
    }
    if not path.exists():
        return out
    out.update({"bytes": path.stat().st_size, "sha256": sha256_file(path)})
    rows = 0
    dates: list[str] = []
    symbols: set[str] = set()
    headers: list[str] = []
    malformed = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        for row in reader:
            rows += 1
            if not row:
                malformed += 1
                continue
            dk = first_key(row, DATE_KEYS)
            d = normalized_date(row.get(dk)) if dk else None
            if d:
                dates.append(d)
            if want_symbols:
                sk = first_key(row, SYMBOL_KEYS)
                if sk and row.get(sk) not in (None, ""):
                    symbols.add(str(row[sk]).strip())
    out.update({
        "rows": rows,
        "headers": headers,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "unique_dates": len(set(dates)),
        "unique_symbols": len(symbols) if want_symbols else None,
        "malformed_rows": malformed,
    })
    return out


def _collect_dates(obj: Any, limit: int = 250_000) -> tuple[list[str], int]:
    dates: list[str] = []
    visited = 0
    stack = [obj]
    while stack and visited < limit:
        item = stack.pop()
        visited += 1
        if isinstance(item, dict):
            for k, v in item.items():
                kl = str(k).lower()
                if kl in DATE_KEYS or kl.endswith("_date"):
                    d = normalized_date(v)
                    if d:
                        dates.append(d)
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(item, list):
            stack.extend(item)
    return dates, visited


def _event_count(obj: Any) -> int | None:
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        for key in ("events", "records", "rows", "sessions", "data"):
            v = obj.get(key)
            if isinstance(v, list):
                return len(v)
        # Common Round-2 envelope: date-indexed records.
        date_keys = [k for k in obj if normalized_date(k)]
        if date_keys:
            return len(date_keys)
    return None


def audit_round2_segment(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
    }
    if not path.exists():
        return out
    raw_prefix = path.read_bytes()[:4]
    out.update({
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "gzip_magic": raw_prefix[:2] == b"\x1f\x8b",
    })
    try:
        if out["gzip_magic"]:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                obj = json.load(f)
        else:
            obj = json_load(path)
        dates, visited = _collect_dates(obj)
        out.update({
            "parse_status": "OK",
            "top_level_type": type(obj).__name__,
            "event_count_hint": _event_count(obj),
            "date_min": min(dates) if dates else None,
            "date_max": max(dates) if dates else None,
            "unique_dates_seen": len(set(dates)),
            "nodes_scanned_for_dates": visited,
        })
    except Exception as exc:  # Evidence must retain corruption instead of hiding it.
        out.update({
            "parse_status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        })
    return out


def recursive_metric_hits(obj: Any, path: str = "") -> list[dict[str, Any]]:
    wanted = {
        "events", "qualified", "executed", "overlap_skipped", "wins", "losses",
        "gross_sum", "cost_sum", "net_sum", "win_rate", "avg_net", "average_net",
    }
    hits: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if str(k).lower() in wanted and isinstance(v, (int, float)) and not isinstance(v, bool):
                hits.append({"path": p, "value": v})
            if isinstance(v, (dict, list)):
                hits.extend(recursive_metric_hits(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:1000]):
            if isinstance(v, (dict, list)):
                hits.extend(recursive_metric_hits(v, f"{path}[{i}]"))
    return hits


def audit_eod() -> list[dict[str, Any]]:
    base = ROOT / "eod"
    out: list[dict[str, Any]] = []
    if not base.exists():
        return out
    for day in sorted(p for p in base.iterdir() if p.is_dir() and p.name.isdigit()):
        row: dict[str, Any] = {"date": day.name, "path": str(day.relative_to(ROOT))}
        status = day / "status.json"
        row["status_exists"] = status.exists()
        if status.exists():
            try:
                obj = json_load(status)
                row.update({
                    "status_sha256": sha256_file(status),
                    "three_leg_complete": obj.get("three_leg_complete"),
                    "formal_complete_day": obj.get("formal_complete_day"),
                    "downstream_ready": obj.get("downstream_ready"),
                    "status": obj.get("status"),
                    "leg_status": {
                        key: (obj.get(key) if isinstance(obj.get(key), str) else None)
                        for key in ("price", "institutional", "margin")
                    },
                })
                # Preserve compact leg evidence even when schema is nested/different.
                if isinstance(obj.get("legs"), dict):
                    row["legs"] = obj["legs"]
            except Exception as exc:
                row["status_parse_error"] = f"{type(exc).__name__}: {exc}"
        row["files"] = len([p for p in day.rglob("*") if p.is_file()])
        out.append(row)
    return out


def main() -> int:
    auth_path = RESET / "RESET_AUTHORIZATION.json"
    manifest_path = RESET / "CORPUS_MANIFEST.json"
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    auth = json_load(auth_path) if auth_path.exists() else {}
    auth_ok = bool(
        auth.get("research_authorized") is True
        and auth.get("production_changes_authorized") is False
        and auth.get("capital_authority_twd") == 0
        and auth.get("broker_order_execution") is False
    )
    if not auth_ok:
        failures.append({"code": "RESET_AUTHORIZATION_INVALID_OR_MISSING", "path": str(auth_path.relative_to(ROOT))})

    manifest = json_load(manifest_path) if manifest_path.exists() else {}
    frozen_base_seen = manifest.get("frozen_main_commit") or manifest.get("frozen_corpus_base") or manifest.get("base_commit")
    if frozen_base_seen not in (None, FROZEN_BASE):
        failures.append({"code": "FROZEN_BASE_MISMATCH", "expected": FROZEN_BASE, "seen": frozen_base_seen})

    mem_dir = ROOT / "research" / "e2_profit_max" / "membership"
    membership = [audit_csv(mem_dir / name, want_symbols=True) for name in MEMBERSHIP_FILES]
    for item in membership:
        if not item.get("exists"):
            failures.append({"code": "MISSING_PIT_MEMBERSHIP", "path": item["path"]})
        elif not item.get("date_min") or not item.get("date_max"):
            warnings.append({"code": "MEMBERSHIP_DATE_COLUMN_UNRESOLVED", "path": item["path"]})

    macro_dir = ROOT / "research" / "e2_profit_max" / "macro"
    macro = [audit_csv(macro_dir / name) for name in MACRO_FILES]
    for item in macro:
        if not item.get("exists"):
            failures.append({"code": "MISSING_MACRO_HISTORY", "path": item["path"]})

    seg_dir = ROOT / "research" / "e2_profit_max" / "round2" / "input"
    segments = [audit_round2_segment(seg_dir / f"r2seg_{i:02d}.txt") for i in range(1, 15)]
    bad_segments = [x for x in segments if x.get("parse_status") != "OK"]
    for item in bad_segments:
        failures.append({
            "code": "ROUND2_SEGMENT_UNREADABLE",
            "path": item["path"],
            "error": item.get("error"),
        })

    candidate_b_path = ROOT / "research" / "e2_profit_max" / "E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json"
    candidate_b: dict[str, Any] = {"path": str(candidate_b_path.relative_to(ROOT)), "exists": candidate_b_path.exists()}
    if candidate_b_path.exists():
        try:
            b = json_load(candidate_b_path)
            candidate_b.update({
                "sha256": sha256_file(candidate_b_path),
                "metric_hits": recursive_metric_hits(b),
            })
        except Exception as exc:
            failures.append({"code": "CANDIDATE_B_VALIDATION_UNREADABLE", "error": str(exc)})
    else:
        failures.append({"code": "CANDIDATE_B_VALIDATION_MISSING"})

    eod = audit_eod()
    if not eod:
        failures.append({"code": "EOD_CORPUS_MISSING"})

    history_refs = []
    if isinstance(manifest, dict):
        # Keep the manifest itself authoritative; summarize discoverable commit/ref-looking strings.
        def walk(v: Any, p: str = "") -> None:
            if isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{p}.{k}" if p else str(k))
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{p}[{i}]")
            elif isinstance(v, str) and (re.fullmatch(r"[0-9a-f]{40}", v) or v.startswith(("research/", "phase2/", "chatgpt/", "codex/"))):
                history_refs.append({"path": p, "value": v})
        walk(manifest)

    lineage = {
        "schema_version": 1,
        "stage": "A_DATA_AUDIT",
        "frozen_corpus_base": FROZEN_BASE,
        "reset_authorization_sha256": sha256_file(auth_path) if auth_path.exists() else None,
        "corpus_manifest_sha256": sha256_file(manifest_path) if manifest_path.exists() else None,
        "history_refs": history_refs,
        "authority": {
            "research_only": True,
            "signal_authority": False,
            "ranking_authority": False,
            "capital_authority_twd": 0,
            "broker_order_execution": False,
            "production_promotion": False,
        },
    }
    coverage = {
        "schema_version": 1,
        "stage": "A_DATA_AUDIT",
        "membership": membership,
        "macro": macro,
        "round2_segments": segments,
        "round2_segment_count": len(segments),
        "round2_readable_count": len(segments) - len(bad_segments),
        "candidate_b_baseline_evidence": candidate_b,
        "eod": eod,
    }
    quality = {
        "schema_version": 1,
        "stage": "A_DATA_AUDIT",
        "critical_failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "model_search_admission": "BLOCKED_DATA_AUDIT_FAILURE" if failures else "ELIGIBLE_FOR_STAGE_B_SEARCH_PLAN_FREEZE",
        "note": "Failures are retained as evidence. This audit never repairs, backfills, or silently drops corrupt inputs.",
    }

    atomic_json(RESULTS / "DATA_LINEAGE.json", lineage)
    atomic_json(RESULTS / "DATA_COVERAGE.json", coverage)
    atomic_json(RESULTS / "DATA_QUALITY_FAILURES.json", quality)

    min_dates = [x.get("date_min") for x in membership if x.get("date_min")]
    max_dates = [x.get("date_max") for x in membership if x.get("date_max")]
    seg_dates_min = [x.get("date_min") for x in segments if x.get("date_min")]
    seg_dates_max = [x.get("date_max") for x in segments if x.get("date_max")]
    summary = f"""# HENGCE Full Reset — Stage A Data Audit\n\n"
    summary += f"- Frozen corpus: `{FROZEN_BASE}`\n"
    summary += f"- Reset authorization: `{'PASS' if auth_ok else 'FAIL'}`\n"
    summary += f"- PIT membership files present: `{sum(bool(x.get('exists')) for x in membership)}/{len(membership)}`\n"
    summary += f"- PIT membership date span detected: `{min(min_dates) if min_dates else 'UNKNOWN'}` → `{max(max_dates) if max_dates else 'UNKNOWN'}`\n"
    summary += f"- Macro files present: `{sum(bool(x.get('exists')) for x in macro)}/{len(macro)}`\n"
    summary += f"- Round-2 segments readable: `{len(segments) - len(bad_segments)}/{len(segments)}`\n"
    summary += f"- Round-2 date span detected: `{min(seg_dates_min) if seg_dates_min else 'UNKNOWN'}` → `{max(seg_dates_max) if seg_dates_max else 'UNKNOWN'}`\n"
    summary += f"- EOD date directories audited: `{len(eod)}`\n"
    summary += f"- Critical data-quality failures: `{len(failures)}`\n"
    summary += f"- Warnings: `{len(warnings)}`\n"
    summary += f"- Stage B admission: `{quality['model_search_admission']}`\n\n"
    summary += "No model search was run in Stage A. No production authority was created.\n"
    atomic_text(RESULTS / "STAGE_A_SUMMARY.md", summary)

    print(json.dumps({
        "stage": "A_DATA_AUDIT",
        "membership_files": len(membership),
        "macro_files": len(macro),
        "round2_readable": len(segments) - len(bad_segments),
        "round2_total": len(segments),
        "eod_days": len(eod),
        "critical_failures": len(failures),
        "warnings": len(warnings),
        "admission": quality["model_search_admission"],
    }, sort_keys=True))
    # Known corrupt historical evidence is a research result, not a CI infrastructure crash.
    # CI fails only for missing/invalid reset authority or absent foundational corpus classes.
    hard_codes = {"RESET_AUTHORIZATION_INVALID_OR_MISSING", "MISSING_PIT_MEMBERSHIP", "MISSING_MACRO_HISTORY", "EOD_CORPUS_MISSING"}
    return 2 if any(x.get("code") in hard_codes for x in failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
