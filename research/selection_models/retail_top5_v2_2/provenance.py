"""Pinned bundled-reference checks and deterministic replay, never trading authority."""
import hashlib
import io
import gzip
import zlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT/'reference'/'bundled_contract.json'
CONTRACT_SHA256 = '2cbe2ce3ab857a20460a6554c465cdfe0c7e31ae027f2cb70ad6680c87349dd3'
DEFAULT_DAILY = ROOT/'price_seed_through_20261106.csv.gz'
DEFAULT_CHIPS = ROOT/'chip_seed_through_20261106.csv.gz'
CODE_FILES = ('screen.py','validation.py','provenance.py','freeze.py','rank_whole_lot.py','select_stocks.py','strategy.py')
AUTHORITY = 'NO_TRADING_AUTHORITY'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def code_hashes():
    return {name:digest((ROOT/name).read_bytes()) for name in CODE_FILES}


def load_contract(path=DEFAULT_CONTRACT):
    raw = Path(path).read_bytes()
    if digest(raw) != CONTRACT_SHA256:
        raise ValueError('REFERENCE_CONTRACT_MISMATCH: 非本版固定基準；不能自行縮減母體或認定官方核准')
    return json.loads(raw)


def validate_coverage(daily, chips, contract):
    for frame, key, label in [(daily,'daily_universe','DAILY'),(chips,'chip_universe','CHIP')]:
        if frame.duplicated(['Date','Ticker']).any():
            raise ValueError(f'{label}_DUPLICATE_KEYS')
        actual = {pd.Timestamp(day).strftime('%Y-%m-%d'):set(g.Ticker)
                  for day,g in frame.groupby('Date')}
        expected = contract[key]
        if set(actual) != set(expected):
            raise ValueError(f'{label}_DATE_COVERAGE_MISMATCH: 缺漏或額外日期')
        for day, tickers in expected.items():
            target = set(tickers)
            if actual[day] != target:
                missing = sorted(target-actual[day])
                extra = sorted(actual[day]-target)
                raise ValueError(f'{label}_UNIVERSE_MISMATCH {day}: missing={len(missing)} extra={len(extra)}')


def load_inputs(daily_path=DEFAULT_DAILY, chip_path=DEFAULT_CHIPS, contract_path=DEFAULT_CONTRACT):
    from screen import read_daily, read_chips
    contract = load_contract(contract_path)
    # Read immutable in-memory snapshots: hashes and calculations use the same bytes.
    daily_raw, chip_raw = Path(daily_path).read_bytes(), Path(chip_path).read_bytes()
    def parse(raw,reader,label):
        try:
            data=gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw
            return reader(io.BytesIO(data))
        except (EOFError,gzip.BadGzipFile,zlib.error,pd.errors.ParserError,
                pd.errors.EmptyDataError,UnicodeError,ValueError) as exc:
            raise ValueError(f'DATA_INPUT_ERROR batch={contract["batch_id"]} input={label} sha256={digest(raw)} error={type(exc).__name__}: {exc}') from None
    daily, chips = parse(daily_raw,read_daily,'daily'),parse(chip_raw,read_chips,'chips')
    validate_coverage(daily, chips, contract)
    if digest(daily_raw) != contract['daily_sha256'] or digest(chip_raw) != contract['chip_sha256']:
        raise ValueError('SOURCE_SHA256_MISMATCH: 原始資料或批次版本不同，需獨立核對新基準')
    return daily, chips, contract


def compute_lanes(daily, chips, decision, contract):
    from screen import screen, eligible_stocks
    from strategy import TOP_N
    from validation import decision_data
    lanes = {}
    for lag in (14,21):
        d,c,last = decision_data(daily,chips,decision,lag,contract=contract)
        rows = eligible_stocks(d,c,lag,decision=pd.Timestamp(decision))
        rows = rows.sort_values(['liquidity','ticker'],ascending=[False,True])
        pairs=screen(d,c,lag,decision=pd.Timestamp(decision))
        lanes[str(lag)] = dict(chip_date=str(last.date()),
                              candidates=json.loads(rows.to_json(orient='records',date_format='iso')),
                              top5=rows.ticker.head(TOP_N).tolist(),
                              research_pairs=json.loads(pairs.to_json(orient='records',date_format='iso')))
    return lanes


def verify_record(frozen, daily_path=DEFAULT_DAILY, chip_path=DEFAULT_CHIPS, contract_path=DEFAULT_CONTRACT):
    if frozen.get('version') != 'retail_forward_v2_2':
        raise ValueError('LEGACY_OR_UNKNOWN_FREEZE: 請用V2.2重新產生演練封存')
    from strategy import PARAMETERS
    if frozen.get('strategy') != PARAMETERS:
        raise ValueError('FREEZE_STRATEGY_MISMATCH')
    if frozen.get('kind') != 'rehearsal':
        raise ValueError('OFFICIAL_EVIDENCE_UNAVAILABLE: 未接正式存證及風控，拒絕prospective封存')
    if frozen.get('authority') != AUTHORITY or frozen.get('verification_scope') != 'BUNDLED_REFERENCE_ONLY':
        raise ValueError('INVALID_AUTHORITY_LABEL')
    if frozen.get('official_publication_verified') is not False or frozen.get('integrity') != 'RECOMPUTABLE_NOT_SIGNED' or frozen.get('intended_fill') is not None:
        raise ValueError('INVALID_EVIDENCE_LABEL')
    if frozen.get('contract_sha256') != CONTRACT_SHA256:
        raise ValueError('FREEZE_CONTRACT_HASH_MISMATCH')
    if frozen.get('code_sha256') != code_hashes():
        raise ValueError('FREEZE_CODE_HASH_MISMATCH')
    daily,chips,contract = load_inputs(daily_path,chip_path,contract_path)
    if frozen.get('price_sha256') != contract['daily_sha256'] or frozen.get('chip_sha256') != contract['chip_sha256']:
        raise ValueError('FREEZE_SOURCE_HASH_MISMATCH')
    lanes = compute_lanes(daily,chips,frozen['decision'],contract)
    if frozen.get('lanes') != lanes:
        raise ValueError('FREEZE_REPLAY_MISMATCH: 候選或指標與重算結果不同')
    count = int(daily.Date.eq(pd.Timestamp(frozen['decision'])).sum())
    if frozen.get('price_rows') != count:
        raise ValueError('FREEZE_PRICE_ROWS_MISMATCH')
    return lanes
