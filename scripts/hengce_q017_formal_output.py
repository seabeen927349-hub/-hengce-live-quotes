"""Q017 schema-5 output boundary. Latest pointers never grant authority.

The daily canonical research/candidate bridge has a different contract. It may
not replace immutable 09:01 evidence or introduce its ranking into formal output.
"""
from pathlib import Path

from hengce_unified_contracts import aware, strict_loads

Q017_ONLY_POLICY = 'Q017_ONLY_REUSE_LEGACY_GEOMETRY_NO_LEGACY_CANDIDATES'


def current_decision(now, root=None):
    # Keep policy imports usable by minimal, fail-closed installed routers.
    import hengce_q017_authority_guard_v5 as guard
    now = now.astimezone(guard.v5.TZ)
    radar = Path(root) / 'hengce/q017_radar' if root is not None else guard.RADAR
    path = radar / 'decision' / (now.strftime('%Y%m%d') + '_0901.json')
    decision = strict_loads(path.read_bytes())
    if not isinstance(decision, dict) or decision.get('trade_date') != now.date().isoformat():
        raise ValueError('CURRENT_SCHEMA5_DECISION_REQUIRED')
    try:
        ok, reason = guard.validate_decision_payload(decision, radar=radar)
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError, RuntimeError) as exc:
        raise ValueError('MALFORMED_SCHEMA5_EVIDENCE:' + str(exc)) from exc
    if not ok:
        raise ValueError(reason)
    if aware(decision.get('generated_at_taipei')) > now:
        raise ValueError('FUTURE_DECISION_NOT_AVAILABLE')
    return decision


def require_q017_publication(display, base, now, root=None):
    """Additional authority gate after the complete transaction/UI validation.

    This never computes scores or supplies geometry. An old mixed publication
    cannot acquire authority by changing a policy label or a latest pointer.
    """
    if display.get('binding_status') != 'PASS':
        raise ValueError(display.get('reason') or 'UNBOUND_PUBLICATION')
    if (base.get('candidate_union_policy') != Q017_ONLY_POLICY or
            base.get('q017_is_only_active_candidate_source') is not True or
            base.get('q017_contract_status') != 'PASS'):
        raise ValueError('Q017_ONLY_PUBLICATION_REQUIRED')
    decision = current_decision(now, root)
    if (base.get('q017_observation_snapshot_sha256') != decision['observation_snapshot_sha256'] or
            base.get('q017_decision_snapshot_sha256') != decision['decision_snapshot_sha256']):
        raise ValueError('PUBLICATION_NOT_BOUND_TO_SCHEMA5_DECISION')
    ranked = {row['ticker']: (rank, row) for rank, row in enumerate(decision['top3'], 1)}
    previous_rank = 0
    for row in display['rows']:
        evidence = ranked.get(row.get('Ticker'))
        if row.get('SourceProvenance') not in {'Q017', 'BOTH'} or evidence is None:
            raise ValueError('NON_Q017_FORMAL_ROW')
        rank, source = evidence
        if rank <= previous_rank:
            raise ValueError('PUBLICATION_Q017_ORDER_CHANGED')
        previous_rank = rank
        if row.get('Q017Score') != source['score'] or row.get('Q017Rank') != rank:
            raise ValueError('PUBLICATION_Q017_RANK_OR_SCORE_CHANGED')
        if row.get('FinalAction') in {'REVIEW_ENTRY', 'REVIEW_PROBE'} and (
                decision['market_state'] != 'GO' or source.get('qualified') is not True):
            raise ValueError('Q017_CASH_CANNOT_CREATE_ENTRY')
    return decision
