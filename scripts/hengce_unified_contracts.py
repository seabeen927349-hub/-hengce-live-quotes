"""Shared boundary checks for the single HENGCE runtime; no model computation."""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

ZERO_AUTHORITY = {"capital_authority_twd": 0, "broker_order_execution": False,
                  "PROMOTE_TO_PRODUCTION": "FORBIDDEN"}
TICKER_KEYS = ('Ticker', 'ticker', 'Symbol', 'symbol', 'StockNo', 'stock_no', '證券代號')
GEOMETRY_KEYS = (
    ('BreakoutLower', 'breakout_lower', 'breakout_low', 'BreakoutLow', 'breakout_zone_low', 'BreakoutZoneLow'),
    ('BreakoutUpper', 'breakout_upper', 'breakout_high', 'BreakoutHigh', 'breakout_zone_high', 'BreakoutZoneHigh'),
    ('NoChase', 'no_chase', 'NoChasePrice', 'no_chase_price'),
    ('Invalidation', 'InvalidationPrice', 'invalid', 'invalid_price', 'StructureInvalidation'),
)

def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def ticker(row):
    values = set()
    for key in TICKER_KEYS:
        if row.get(key) is None:
            continue
        value = row[key]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError('INVALID_TICKER_TYPE')
        value = str(value).strip().upper()
        if value.startswith('TWSE:'):
            value = value[5:]
        if value.endswith('.TW'):
            value = value[:-3]
        if not re.fullmatch(r'[A-Z0-9]{1,12}', value):
            raise ValueError('INVALID_TICKER')
        values.add(value)
    if len(values) > 1:
        raise ValueError('CONFLICTING_TICKER_ALIASES')
    return next(iter(values), '')


def geometry(row):
    values = []
    for keys in GEOMETRY_KEYS:
        present = [finite(row[k]) for k in keys if row.get(k) is not None]
        if not present or None in present or len(set(present)) != 1:
            return None
        values.append(present[0])
    lower, upper, chase, invalid = values
    return tuple(values) if 0 < invalid < lower <= upper <= chase else None


def strict_loads(data):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('DUPLICATE_JSON_KEY:' + key)
            out[key] = value
        return out
    def constant(value):
        raise ValueError('NONFINITE_JSON:' + value)
    def floating(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('NONFINITE_JSON:' + value)
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def aware(value):
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('NAIVE_TIMESTAMP')
    return dt


def session_metadata(obj, now, *, live=False):
    """No calendar guessing: producers must bind artifacts to this action session."""
    if not isinstance(obj, dict):
        raise ValueError('INPUT_NOT_OBJECT')
    session = obj.get('valid_for_trade_date', obj.get('trade_date'))
    if session != now.date().isoformat():
        raise ValueError('STALE_OR_UNBOUND_SESSION')
    generated = aware(obj.get('generated_at_taipei', obj.get('generated_at')))
    age = (now - generated).total_seconds()
    # Daily formal/context artifacts may be generated earlier in the same session;
    # this is an admission bound, not a new trading/calendar rule.
    if generated.astimezone(now.tzinfo).date() != now.date() or age < -30:
        raise ValueError('INVALID_GENERATION_SESSION')
    if live and age > 480:
        raise ValueError('STALE_LIVE_SNAPSHOT')
