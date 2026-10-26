#!/usr/bin/env python3
"""Run the existing fail-closed HENGCE action pipeline with Q017 as the only active candidate source.

Legacy formal rows may supply previously legal geometry/formal-trigger infrastructure for
the Q017-selected ticker only; they are not candidate/selection sources in this mode.
"""
from __future__ import annotations
import hengce_unified_candidate_adapter as adapter
from hengce_unified_runner import run
from hengce_q017_formal_output import Q017_ONLY_POLICY

_ORIGINAL_BUILD = adapter.build

def build_q017_only(legacy, q017):
    if q017 is None:
        raise ValueError('Q017_CANONICAL_SOURCE_REQUIRED')
    out = _ORIGINAL_BUILD(legacy, q017)
    if out.get('q017_contract_status') != 'PASS':
        raise ValueError('Q017_CANONICAL_SOURCE_FAIL_CLOSED:' + str(out.get('q017_contract_errors')))
    rows = [r for r in out.get('rows', []) if isinstance(r, dict) and r.get('SourceProvenance') in {'Q017','BOTH'}]
    out['rows'] = rows
    out['candidate_count'] = len(rows)
    out['legacy_candidate_count'] = 0
    out['source_provenance_counts'] = {k: sum(r.get('SourceProvenance') == k for r in rows) for k in ('LEGACY','Q017','BOTH')}
    out['candidate_union_policy'] = Q017_ONLY_POLICY
    out['q017_is_only_active_candidate_source'] = True
    out['legacy_base_role'] = 'GEOMETRY_AND_FORMAL_TRIGGER_INFRASTRUCTURE_ONLY_NOT_SELECTION_SOURCE'
    return out

def main():
    adapter.build = build_q017_only
    return run()

if __name__ == '__main__':
    raise SystemExit(main())
