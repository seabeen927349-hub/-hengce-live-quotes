#!/usr/bin/env python3
"""HENGCE full-reset Stage A: offline corpus/PIT audit.

Research-only. No network, ranking, signals, production writes, capital authority,
or broker execution. The audit records usable and unusable historical evidence
before any model search.
"""
from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / "research" / "codex_full_reset_20261023"
RESULTS = RESET / "results"
FROZEN_BASE = "05bf0e35fb6a88473fd4f947952ef1b6875d3f88"
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


def load_json(path: Path) -> Any:
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
    if ISO_DATE_RE.fullmatch(s):
        return s
    if COMPACT_DATE_RE.fullmatch(s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return None


def first_key(row: dict[str, Any], candidates: Iterable[str]) -> str | None:
    lower = {str(k).strip().lower(): k for k in row}
    for candidate in candidates:
        if candidate in lower:
            return lower[candidate]
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
    malformed = 0
    dates: list[str] = []
    symbols: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        for row in reader:
            rows += 1
            if not row:
                malformed += 1
                continue
            date_key = first_key(row, DATE_KEYS)
            if date_key:
                d = normalized_date(row.get(date_key))
                if d:
                    dates.append(d)
            if want_symbols:
                symbol_key = first_key(row, SYMBOL_KEYS)
                if symbol_key and row.get(symbol_key) not in (None, ""):
                    symbols.add(str(row[symbol_key]).strip())
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


def collect_dates(obj: Any, limit: int = 500_000) -> tuple[list[str], int]:
    dates: list[str] = []
    visited = 0
    stack = [obj]
    while stack and visited < limit:
        item = stack.pop()
        visited += 1
        if isinstance(item, dict):
            for key, value in item.items():
                key_lower = str(key).lower()
                if key_lower in DATE_KEYS or key_lower.endswith("_date"):
                    d = normalized_date(value)
                    if d:
                        dates.append(d)
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
    return dates, visited


def event_count_hint(obj: Any) -> int | None:
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        for key in ("events", "records", "rows", "sessions", "data"):
            value = obj.get(key)
            if isinstance(value, list):
                return len(value)
        date_keys = [key for key in obj if normalized_date(key)]
        if date_keys:
            return len(date_keys)
    return None


def decode_round2(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return json.loads(gzip.decompress(raw).decode("utf-8")), "RAW_GZIP_JSON"
    stripped = raw.strip()
    if stripped.startswith(b"H4sI"):
        decoded = base64.b64decode(stripped, validate=True)
        if decoded[:2] != b"\x1f\x8b":
            raise ValueError("base64 envelope decoded but gzip magic is absent")
        return json.loads(gzip.decompress(decoded).decode("utf-8")), "BASE64_GZIP_JSON"
    return json.loads(stripped.decode("utf-8")), "JSON_TEXT"


def audit_round2_segment(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
    }
    if not path.exists():
        return out
    out.update({"bytes": path.stat().st_size, "sha256": sha256_file(path)})
    try:
        obj, encoding = decode_round2(path)
        dates, visited = collect_dates(obj)
        out.update({
            "parse_status": "OK",
            "encoding_detected": encoding,
            "top_level_type": type(obj).__name__,
            "event_count_hint": event_count_hint(obj),
            "date_min": min(dates) if dates else None,
            "date_max": max(dates) if dates else None,
            "unique_dates_seen": len(set(dates)),
            "nodes_scanned_for_dates": visited,
        })
    except Exception as exc:
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
        for key, value in obj.items():
            current = f"{path}.{key}" if path else str(key)
            if str(key).lower() in wanted and isinstance(value, (int, float)) and not isinstance(value, bool):
                hits.append({"path": current, "value": value})
            if isinstance(value, (dict, list)):
                hits.extend(recursive_metric_hits(value, current))
    elif isinstance(obj, list):
        for index, value in enumerate(obj[:2000]):
            if isinstance(value, (dict, list)):
                hits.extend(recursive_metric_hits(value, f"{path}[{index}]"))
    return hits


def audit_eod() -> list[dict[str, Any]]:
    base = ROOT / "eod"
    out: list[dict[str, Any]] = []
    if not base.exists():
        return out
    for day in sorted(path for path in base.iterdir() if path.is_dir() and path.name.isdigit()):
        row: dict[str, Any] = {
            "date": day.name,
            "path": str(day.relative_to(ROOT)),
            "file_count": len([p for p in day.rglob("*") if p.is_file()]),
        }
        status = day / "status.json"
        row["status_exists"] = status.exists()
        if status.exists():
            try:
                obj = load_json(status)
                row.update({
                    "status_sha256": sha256_file(status),
                    "three_leg_complete": obj.get("three_leg_complete"),
                    "formal_complete_day": obj.get("formal_complete_day"),
                    "downstream_ready": obj.get("downstream_ready"),
                    "status": obj.get("status"),
                })
                if isinstance(obj.get("legs"), dict):
                    row["legs"] = obj["legs"]
            except Exception as exc:
                row["status_parse_error"] = f"{type(exc).__name__}: {exc}"
        out.append(row)
    return out


def main() -> int:
    auth_path = RESET / "RESET_AUTHORIZATION.json"
    manifest_path = RESET / "CORPUS_MANIFEST.json"
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    auth = load_json(auth_path) if auth_path.exists() else {}
    auth_ok = bool(
        auth.get("research_authorized") is True
        and auth.get("production_changes_authorized") is False
        and auth.get("capital_authority_twd") == 0
        and auth.get("broker_order_execution") is False
    )
    if not auth_ok:
        failures.append({"code": "RESET_AUTHORIZATION_INVALID_OR_MISSING"})

    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    frozen_seen = manifest.get("frozen_main_commit") or manifest.get("frozen_corpus_base") or manifest.get("base_commit")
    if frozen_seen not in (None, FROZEN_BASE):
        failures.append({"code": "FROZEN_BASE_MISMATCH", "expected": FROZEN_BASE, "seen": frozen_seen})

    membership_dir = ROOT / "research" / "e2_profit_max" / "membership"
    membership_paths = sorted(membership_dir.glob("twse_electronics_membership_*.csv"))
    membership = [audit_csv(path, want_symbols=True) for path in membership_paths]
    membership_years = sorted({match.group(1) for path in membership_paths if (match := re.search(r"(20\d{2})", path.name))})
    for required_year in ("2023", "2024", "2025"):
        if required_year not in membership_years:
            failures.append({"code": "MISSING_PIT_MEMBERSHIP_YEAR", "year": required_year})
    if not membership:
        failures.append({"code": "MISSING_PIT_MEMBERSHIP"})

    macro_dir = ROOT / "research" / "e2_profit_max" / "macro"
    macro_paths = [macro_dir / "sox_daily_202212_202610.csv", macro_dir / "dxy_exact_DX-Y.NYB_202212_202610.csv"]
    macro = [audit_csv(path) for path in macro_paths]
    for item in macro:
        if not item.get("exists"):
            failures.append({"code": "MISSING_MACRO_HISTORY", "path": item["path"]})

    segment_dir = ROOT / "research" / "e2_profit_max" / "round2" / "input"
    segment_paths = sorted(segment_dir.glob("r2seg_*.txt"))
    segments = [audit_round2_segment(path) for path in segment_paths]
    if not segments:
        failures.append({"code": "ROUND2_SEGMENTS_MISSING"})
    bad_segments = [item for item in segments if item.get("parse_status") != "OK"]
    for item in bad_segments:
        failures.append({"code": "ROUND2_SEGMENT_UNREADABLE", "path": item["path"], "error": item.get("error")})

    candidate_b_path = ROOT / "research" / "e2_profit_max" / "E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json"
    candidate_b: dict[str, Any] = {"path": str(candidate_b_path.relative_to(ROOT)), "exists": candidate_b_path.exists()}
    if candidate_b_path.exists():
        try:
            candidate_b_obj = load_json(candidate_b_path)
            candidate_b.update({"sha256": sha256_file(candidate_b_path), "metric_hits": recursive_metric_hits(candidate_b_obj)})
        except Exception as exc:
            failures.append({"code": "CANDIDATE_B_VALIDATION_UNREADABLE", "error": str(exc)})
    else:
        failures.append({"code": "CANDIDATE_B_VALIDATION_MISSING"})

    eod = audit_eod()
    if not eod:
        failures.append({"code": "EOD_CORPUS_MISSING"})

    history_refs: list[dict[str, str]] = []
    def walk(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif isinstance(value, str) and (
            re.fullmatch(r"[0-9a-f]{40}", value)
            or value.startswith(("research/", "phase2/", "chatgpt/", "codex/"))
        ):
            history_refs.append({"path": path, "value": value})
    walk(manifest)

    hard_codes = {
        "RESET_AUTHORIZATION_INVALID_OR_MISSING", "FROZEN_BASE_MISMATCH",
        "MISSING_PIT_MEMBERSHIP", "MISSING_PIT_MEMBERSHIP_YEAR",
        "MISSING_MACRO_HISTORY", "ROUND2_SEGMENTS_MISSING", "EOD_CORPUS_MISSING",
    }
    hard_failures = [item for item in failures if item.get("code") in hard_codes]
    evidence_failures = [item for item in failures if item.get("code") not in hard_codes]
    admission = "BLOCKED_FOUNDATIONAL_DATA_FAILURE" if hard_failures else "ELIGIBLE_FOR_STAGE_B_SEARCH_PLAN_FREEZE"

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
        "membership_years": membership_years,
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
        "hard_failure_count": len(hard_failures),
        "historical_evidence_failure_count": len(evidence_failures),
        "warning_count": len(warnings),
        "hard_failures": hard_failures,
        "historical_evidence_failures": evidence_failures,
        "warnings": warnings,
        "model_search_admission": admission,
        "note": "Unreadable historical evidence is retained and disclosed; it is never repaired, dropped, or promoted silently.",
    }
    atomic_json(RESULTS / "DATA_LINEAGE.json", lineage)
    atomic_json(RESULTS / "DATA_COVERAGE.json", coverage)
    atomic_json(RESULTS / "DATA_QUALITY_FAILURES.json", quality)

    membership_min = [item["date_min"] for item in membership if item.get("date_min")]
    membership_max = [item["date_max"] for item in membership if item.get("date_max")]
    segment_min = [item["date_min"] for item in segments if item.get("date_min")]
    segment_max = [item["date_max"] for item in segments if item.get("date_max")]
    summary_lines = [
        "# HENGCE Full Reset — Stage A Data Audit",
        "",
        f"- Frozen corpus: `{FROZEN_BASE}`",
        f"- Reset authorization: `{'PASS' if auth_ok else 'FAIL'}`",
        f"- PIT membership years: `{', '.join(membership_years) if membership_years else 'NONE'}`",
        f"- PIT membership files: `{len(membership)}`",
        f"- PIT membership span detected: `{min(membership_min) if membership_min else 'UNKNOWN'}` → `{max(membership_max) if membership_max else 'UNKNOWN'}`",
        f"- Macro files present: `{sum(bool(item.get('exists')) for item in macro)}/{len(macro)}`",
        f"- Round-2 segments readable: `{len(segments) - len(bad_segments)}/{len(segments)}`",
        f"- Round-2 span detected: `{min(segment_min) if segment_min else 'UNKNOWN'}` → `{max(segment_max) if segment_max else 'UNKNOWN'}`",
        f"- EOD date directories audited: `{len(eod)}`",
        f"- Hard failures: `{len(hard_failures)}`",
        f"- Historical evidence failures retained: `{len(evidence_failures)}`",
        f"- Stage B admission: `{admission}`",
        "",
        "No model search was run in Stage A. No production authority was created.",
        "",
    ]
    atomic_text(RESULTS / "STAGE_A_SUMMARY.md", "\n".join(summary_lines))

    print(json.dumps({
        "stage": "A_DATA_AUDIT",
        "membership_years": membership_years,
        "round2_readable": len(segments) - len(bad_segments),
        "round2_total": len(segments),
        "eod_days": len(eod),
        "hard_failures": len(hard_failures),
        "historical_evidence_failures": len(evidence_failures),
        "admission": admission,
    }, sort_keys=True))
    return 2 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
