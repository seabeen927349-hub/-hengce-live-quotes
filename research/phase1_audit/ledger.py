"""Offline append-only evidence validator. No storage, experiment or holdout access."""
import hashlib
import json
import re
from datetime import datetime

GENESIS = '0' * 64
FIELDS = {'schema_version', 'experiment_id', 'parent_id', 'hypothesis', 'engine', 'code_commit',
          'data_cutoff', 'parameters', 'metrics', 'result', 'decision', 'reason', 'recorded_at',
          'previous_sha256', 'record_sha256', 'capital_authority', 'phase2_authorized'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def record_hash(record):
    return hashlib.sha256(canonical({k: v for k, v in record.items() if k != 'record_sha256'})).hexdigest()


def validate_ledger(records):
    """Internal consistency only; authenticity needs independently retained anchors."""
    previous, seen = GENESIS, set()
    for record in records:
        if set(record) != FIELDS:
            raise ValueError('INVALID_FIELDS')
        if record['schema_version'] != 1 or type(record['schema_version']) is not int:
            raise ValueError('INVALID_SCHEMA')
        if any(not isinstance(record[k], str) or not record[k].strip() for k in (
                'experiment_id', 'hypothesis', 'reason', 'recorded_at', 'data_cutoff')):
            raise ValueError('MISSING_AUDIT_TEXT')
        if record['experiment_id'] in seen:
            raise ValueError('DUPLICATE_ID')
        if record['parent_id'] is not None and record['parent_id'] not in seen:
            raise ValueError('PARENT_NOT_EARLIER')
        if not isinstance(record['code_commit'], str) or not re.fullmatch('[0-9a-f]{40}', record['code_commit']):
            raise ValueError('INVALID_COMMIT')
        try:
            stamp = datetime.fromisoformat(record['recorded_at'])
            cutoff = datetime.fromisoformat(record['data_cutoff'])
        except ValueError as exc:
            raise ValueError('INVALID_TIMESTAMP') from exc
        if stamp.tzinfo is None or cutoff.tzinfo is None or cutoff > stamp:
            raise ValueError('NONCAUSAL_OR_NAIVE_TIMESTAMP')
        if record['engine'] not in ('Q017', 'E2', 'M1'):
            raise ValueError('MIXED_OR_UNKNOWN_ENGINE')
        if record['capital_authority'] != 0 or type(record['capital_authority']) is not int or record['phase2_authorized'] is not False:
            raise ValueError('AUTHORITY_FORBIDDEN')
        if record['result'] not in ('PROPOSED', 'FAILED', 'COMPLETED', 'ABORTED') or record['decision'] not in ('PENDING', 'ACCEPT', 'REJECT'):
            raise ValueError('INVALID_OUTCOME')
        if record['result'] in ('FAILED', 'ABORTED') and record['decision'] != 'REJECT':
            raise ValueError('FAILED_EXPERIMENT_MUST_BE_RETAINED_AS_REJECT')
        if record['result'] == 'PROPOSED' and record['decision'] != 'PENDING':
            raise ValueError('PROPOSAL_HAS_NO_RESULT')
        if not isinstance(record['parameters'], dict) or not (record['metrics'] is None or isinstance(record['metrics'], dict)):
            raise ValueError('INVALID_PARAMETERS_OR_METRICS')
        canonical(record)  # Reject non-JSON / NaN / infinities recursively.
        if record['previous_sha256'] != previous or record['record_sha256'] != record_hash(record):
            raise ValueError('BROKEN_HASH_CHAIN')
        previous = record['record_sha256']
        seen.add(record['experiment_id'])
    return {'record_count': len(records), 'head_sha256': previous}


def validate_extension(old, new, trusted_checkpoint):
    """Caller must obtain checkpoint from independent trusted storage, not the ledger."""
    if validate_ledger(old) != trusted_checkpoint:
        raise ValueError('TRUSTED_CHECKPOINT_MISMATCH')
    if len(new) < len(old) or new[:len(old)] != old:
        raise ValueError('APPEND_ONLY_VIOLATION')
    return validate_ledger(new)
