#!/usr/bin/env python3
"""Verify historical Round-2 envelopes using the original chunk assembly semantics."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "research" / "e2_profit_max" / "round2"
OUT = ROOT / "research" / "codex_full_reset_20261023" / "results" / "ROUND2_RECONSTRUCTION.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_b64_gzip(text: str) -> tuple[Any, bytes]:
    decoded = base64.b64decode(text.encode("ascii"), validate=True)
    raw = gzip.decompress(decoded)
    return json.loads(raw.decode("utf-8")), raw


def audit_group(directory: Path, pattern: str) -> dict[str, Any]:
    chunks = sorted(directory.glob(pattern))
    result: dict[str, Any] = {
        "directory": str(directory.relative_to(ROOT)),
        "pattern": pattern,
        "chunk_count": len(chunks),
        "chunks": [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p.read_bytes())}
            for p in chunks
        ],
    }
    if not chunks:
        result.update({"status": "FAILED", "error": "NO_CHUNKS"})
        return result
    try:
        joined = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
        obj, raw = decode_b64_gzip(joined)
        result.update({
            "status": "OK",
            "joined_b64_chars": len(joined),
            "decoded_json_bytes": len(raw),
            "decoded_json_sha256": sha256(raw),
            "schema": obj.get("schema") if isinstance(obj, dict) else None,
            "core": obj.get("core") if isinstance(obj, dict) else None,
            "pre_gate": obj.get("pre_gate") if isinstance(obj, dict) else None,
            "row_count": len(obj.get("r", [])) if isinstance(obj, dict) and isinstance(obj.get("r"), list) else None,
            "column_count": len(obj.get("c", [])) if isinstance(obj, dict) and isinstance(obj.get("c"), list) else None,
        })
    except Exception as exc:
        result.update({"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)[:1000]})
    return result


def audit_direct(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path.relative_to(ROOT)), "exists": path.exists()}
    if not path.exists():
        return result
    result.update({"bytes": path.stat().st_size, "sha256": sha256(path.read_bytes())})
    try:
        obj, raw = decode_b64_gzip(path.read_text(encoding="utf-8").strip())
        result.update({
            "status": "OK",
            "decoded_json_bytes": len(raw),
            "decoded_json_sha256": sha256(raw),
            "schema": obj.get("schema") if isinstance(obj, dict) else None,
            "core": obj.get("core") if isinstance(obj, dict) else None,
            "pre_gate": obj.get("pre_gate") if isinstance(obj, dict) else None,
            "row_count": len(obj.get("r", [])) if isinstance(obj, dict) and isinstance(obj.get("r"), list) else None,
            "column_count": len(obj.get("c", [])) if isinstance(obj, dict) and isinstance(obj.get("c"), list) else None,
        })
    except Exception as exc:
        result.update({"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)[:1000]})
    return result


def main() -> int:
    legacy = audit_group(R2 / "input", "r2seg_*.txt")
    shock = audit_group(R2 / "input_shock", "r2shock_*.txt")
    direct = audit_direct(R2 / "input_shock" / "payload.json.gz.b64")

    exact_match = bool(
        shock.get("status") == "OK"
        and direct.get("status") == "OK"
        and shock.get("decoded_json_sha256") == direct.get("decoded_json_sha256")
    )
    shock_contract_ok = bool(
        shock.get("status") == "OK"
        and shock.get("chunk_count") == 3
        and shock.get("schema") == 1
        and shock.get("core") == "rev1_no_teacher_K25_Top1"
        and shock.get("pre_gate") == "TW_SHOCK_m1_lt_0_m5_lte_-0.02"
        and shock.get("row_count") == 152
        and exact_match
    )
    payload = {
        "schema_version": 1,
        "stage": "A_ROUND2_RECONSTRUCTION",
        "original_runner_semantics": "concatenate chunks -> base64 decode -> gzip decompress -> JSON",
        "legacy_input": legacy,
        "shock_input": shock,
        "shock_direct_payload": direct,
        "shock_chunk_vs_direct_exact_payload_match": exact_match,
        "shock_original_contract_ok": shock_contract_ok,
        "research_interpretation": (
            "ROUND2_SHOCK_PAYLOAD_RECOVERED_AND_USABLE_AS_EXPOSED_HISTORY"
            if shock_contract_ok else "ROUND2_SHOCK_PAYLOAD_NOT_PROVEN_USABLE"
        ),
        "legacy_interpretation": (
            "LEGACY_INPUT_RECOVERED"
            if legacy.get("status") == "OK" else "LEGACY_INPUT_UNREADABLE_RETAIN_AS_FAILURE_EVIDENCE"
        ),
        "authority": {
            "research_only": True,
            "capital_authority_twd": 0,
            "broker_order_execution": False,
            "production_promotion": False,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "legacy_status": legacy.get("status"),
        "shock_status": shock.get("status"),
        "shock_rows": shock.get("row_count"),
        "shock_exact_match": exact_match,
        "shock_contract_ok": shock_contract_ok,
    }, sort_keys=True))
    return 0 if shock_contract_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
