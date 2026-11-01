#!/usr/bin/env python3
"""HENGCE literature-first gate validator.

Two modes:
  1) validate <LITERATURE_GATE.json>
  2) pr-scan --base <git-sha> --head <git-sha>

The PR scan is intentionally conservative. It allows literature/data/governance-only
work before the literature gate. It blocks changed research files that look like
model construction, signal/feature design, backtesting, tuning, ranking/selection,
entry/exit/regime rules, or candidate/version creation unless the nearest project
ancestor contains a passing LITERATURE_GATE.json.

Unknown/missing gate fields fail closed. This validator grants no downstream
production/capital/holdout authority.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "HENGCE_LITERATURE_GATE_CONTRACT_v1.json"

FORBIDDEN_PATH_TERMS = {
    "model", "models", "candidate", "candidates", "feature", "features",
    "factor", "factors", "signal", "signals", "score", "scoring",
    "rank", "ranking", "selection", "selector", "backtest", "backtests",
    "strategy", "strategies", "threshold", "thresholds", "optimizer",
    "optimization", "tuning", "entry", "exit", "regime", "version",
    "challenger", "engine"
}
FORBIDDEN_FILENAME_TERMS = FORBIDDEN_PATH_TERMS | {
    "alpha", "portfolio", "walkforward", "walk_forward", "gridsearch",
    "grid_search", "preregister", "preregistration"
}

# Work that is explicitly permitted before the literature gate.
PRE_GATE_ALLOWED_DIR_TERMS = {
    "literature", "papers", "sources", "bibliography", "evidence_map",
    "data", "raw_data", "data_acquisition", "data_cleaning", "lineage",
    "capability_audit", "governance", "docs", "documentation"
}
PRE_GATE_ALLOWED_FILE_TERMS = {
    "readme", "literature", "bibliography", "evidence", "source", "sources",
    "data_dictionary", "lineage", "manifest", "capability_audit", "governance"
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT)


def validate_gate(path: Path, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing gate file: {path}"]
    try:
        gate = load_json(path)
    except ValueError as exc:
        return [str(exc)]

    for field in contract["required_fields"]:
        if field not in gate:
            errors.append(f"missing required field: {field}")

    for field, expected in contract["pass_conditions"].items():
        if field == "full_read_count_min":
            try:
                n = int(gate.get("full_read_count", -1))
            except Exception:
                n = -1
            if n < int(expected):
                errors.append(
                    f"full_read_count={gate.get('full_read_count')!r} < minimum {expected}"
                )
            continue
        actual = gate.get(field, None)
        if actual != expected:
            errors.append(f"{field}={actual!r}; expected {expected!r}")

    for count_field in ("full_read_count", "partial_count", "found_only_count"):
        value = gate.get(count_field)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{count_field} must be non-negative integer")

    for text_field in (
        "topic_id", "topic_title", "scope_definition", "search_boundary",
        "canonical_ledger_reference", "canonical_ledger_version",
        "saturation_assessment", "reviewer", "review_date"
    ):
        value = gate.get(text_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{text_field} must be non-empty string")

    for list_field in ("unresolved_material_conflicts",):
        if not isinstance(gate.get(list_field), list):
            errors.append(f"{list_field} must be an array (empty is allowed)")

    # Explicit contamination statement is mandatory; PASS cannot hide prior modeling.
    if gate.get("no_model_or_backtest_preceded_gate") is not True:
        errors.append("prior model/backtest contamination blocks clean PASS")

    return errors


def git_changed_files(base: str, head: str) -> list[str]:
    cmd = ["git", "diff", "--name-only", f"{base}...{head}"]
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git diff failed: {exc}") from exc
    return [line.strip() for line in out.splitlines() if line.strip()]


def tokens(path: str) -> set[str]:
    normalized = path.lower().replace("-", "_").replace(".", "_")
    raw = set()
    for part in normalized.replace("/", "_").split("_"):
        if part:
            raw.add(part)
    return raw


def is_pre_gate_allowed(path: str) -> bool:
    p = Path(path)
    parts = {x.lower().replace("-", "_") for x in p.parts}
    stem_terms = tokens(p.stem)
    if parts & PRE_GATE_ALLOWED_DIR_TERMS:
        return True
    if stem_terms & PRE_GATE_ALLOWED_FILE_TERMS:
        return True
    # A gate file itself is always allowed to be created/fixed.
    if p.name == "LITERATURE_GATE.json":
        return True
    return False


def is_model_like(path: str) -> bool:
    p = Path(path)
    path_terms = tokens(path)
    stem_terms = tokens(p.stem)
    if path_terms & FORBIDDEN_PATH_TERMS:
        return True
    if stem_terms & FORBIDDEN_FILENAME_TERMS:
        return True
    # Executable research code is treated as model-like unless clearly pre-gate allowed.
    if p.suffix.lower() in {".py", ".ipynb", ".r", ".jl", ".sql"}:
        return True
    # Experiment/result/config artifacts are model-like by default.
    if p.suffix.lower() in {".yaml", ".yml", ".toml", ".json"} and p.name != "LITERATURE_GATE.json":
        return True
    return False


def nearest_gate(path: str) -> Path | None:
    p = ROOT / path
    parent = p.parent
    research_root = ROOT / "research"
    while True:
        gate = parent / "LITERATURE_GATE.json"
        if gate.exists():
            return gate
        if parent == research_root or research_root not in parent.parents:
            return None
        parent = parent.parent


def pr_scan(base: str, head: str, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    changed = git_changed_files(base, head)
    for rel in changed:
        if not rel.startswith("research/"):
            continue
        if is_pre_gate_allowed(rel):
            continue
        if not is_model_like(rel):
            # Documentation/non-executable files without model-like terms remain allowed.
            continue
        gate = nearest_gate(rel)
        if gate is None:
            errors.append(
                f"{rel}: model/research-construction change has no ancestor LITERATURE_GATE.json"
            )
            continue
        gate_errors = validate_gate(gate, contract)
        if gate_errors:
            for err in gate_errors:
                errors.append(f"{rel}: {gate.relative_to(ROOT)}: {err}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("gate")
    p_pr = sub.add_parser("pr-scan")
    p_pr.add_argument("--base", required=True)
    p_pr.add_argument("--head", required=True)
    args = parser.parse_args()

    contract = load_contract()
    if args.cmd == "validate":
        errors = validate_gate((ROOT / args.gate).resolve(), contract)
    else:
        errors = pr_scan(args.base, args.head, contract)

    if errors:
        print("HENGCE LITERATURE-FIRST GATE: BLOCKED", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 2
    print("HENGCE LITERATURE-FIRST GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
