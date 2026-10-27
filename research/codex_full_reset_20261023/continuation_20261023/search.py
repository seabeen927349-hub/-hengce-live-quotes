"""Bounded research continuation. Never imported by a production producer.

This batch has no training/parameter selection and no pristine holdout. The old
completed study and journal are immutable inputs; this batch has its own journal.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import stage_c_rule_search as prior
from reset_ledger import AUTHORITY, TrialLedger, digest

PLAN = HERE / 'PLAN.json'
OUTPUT = HERE / 'results'
KINDS = ('SKIP5_MOMENTUM', 'TREND_PULLBACK', 'LOW_VOL_TREND')


def dump(path, obj):
    # Results are immutable per batch: no successful or failed attempt overwritten.
    with path.open('x') as stream:
        json.dump(obj, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def valid(row):
    if row is None:
        return False
    prices = (row.open, row.high, row.low, row.close)
    return (all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in prices)
            and row.low <= min(row.open, row.close) <= max(row.open, row.close) <= row.high
            and type(row.turnover) in (int, float) and math.isfinite(row.turnover) and row.turnover >= 0)


def features(history, threshold):
    """Caller supplies ONLY the 61 rows at/before the signal session."""
    if len(history) != 61 or not all(valid(r) for r in history):
        return None
    closes = [r.close for r in history]
    changes = [b / a - 1 for a, b in zip(closes, closes[1:])]
    if any(abs(r) > threshold for r in changes):
        return None
    if statistics.mean(r.turnover for r in history[-20:]) < 50_000_000:
        return None
    vol = statistics.stdev(changes[-21:-1])
    slow = closes[-1] / closes[0] - 1
    trend = slow > 0 and closes[-1] > statistics.mean(closes[-60:])
    skip = closes[-6] / closes[0] - 1
    pullback = -(closes[-1] / closes[-4] - 1)
    return {
        'SKIP5_MOMENTUM': skip if skip > 0 else None,
        'TREND_PULLBACK': pullback if trend and pullback > 0 else None,
        'LOW_VOL_TREND': -vol if trend and vol > 0 else None,
    }


def signal_cache(dates, rows, threshold):
    cache = {}
    for i, day in enumerate(dates):
        if i < 60:
            continue
        eligible = {}
        for ticker in sorted(rows[day]):
            f = features([rows[d].get(ticker) for d in dates[i-60:i+1]], threshold)
            if f is not None:
                eligible[ticker] = f
        cache[day] = {
            'universe': sorted(eligible),
            **{kind: sorted((t for t in eligible if eligible[t][kind] is not None),
                           key=lambda t: (-eligible[t][kind], t)) for kind in KINDS},
        }
    return cache


def outcome(tickers, signal_i, horizon, dates, rows, threshold):
    entry_i, exit_i = signal_i + 1, signal_i + 1 + horizon
    event = {'signal_date': dates[signal_i], 'entry_date': dates[entry_i],
             'exit_date': dates[exit_i], 'tickers': tickers}
    errors = []
    for ticker in tickers:
        for j in range(entry_i, exit_i+1):
            r, prev = rows[dates[j]].get(ticker), rows[dates[j-1]].get(ticker)
            reason = None
            if not valid(r) or not valid(prev):
                reason = 'MISSING_OR_INVALID_OHLC'
            elif j == entry_i and r.high == r.low:
                reason = 'LIMIT_LOCKED_OR_UNFILLABLE_ENTRY'
            elif abs(r.close / prev.close - 1) > threshold:
                reason = 'UNPROVEN_PRICE_DISCONTINUITY'
            if reason:
                errors.append({'ticker': ticker, 'date': dates[j], 'reason': reason})
                break
    if errors:
        return {**event, 'status': 'CENSORED', 'reasons': errors}
    path = [[dates[j], statistics.mean(rows[dates[j]][t].close / rows[dates[entry_i]][t].open
                                      for t in tickers)] for j in range(entry_i, exit_i+1)]
    return {**event, 'status': 'COMPLETE', 'gross_return': path[-1][1] - 1,
            'daily_gross_nav': path}


def evaluate(kind, horizon, threshold, dates, rows, cache):
    model, benchmark = [], []
    for year in (2023, 2024, 2025):
        free = -1
        for i, day in enumerate(dates):
            if not day.startswith(str(year)) or i < free or day not in cache:
                continue
            chosen = cache[day][kind][:10]
            exit_i = i + 1 + horizon
            if len(chosen) != 10 or exit_i >= len(dates) or not dates[exit_i].startswith(str(year)):
                continue
            # Freeze signal-time identities; no future outcome can change them.
            model.append(outcome(chosen, i, horizon, dates, rows, threshold))
            benchmark.append(outcome(cache[day]['universe'], i, horizon, dates, rows, threshold))
            free = exit_i + 1  # censored outcomes reserve the exact same interval
    return model, benchmark


def metrics(events):
    result = {}
    for label, years in [('2023', ('2023',)), ('2024', ('2024',)), ('2025', ('2025',)),
                         ('2024_2025', ('2024', '2025'))]:
        all_events = [e for e in events if e['signal_date'][:4] in years]
        complete = [e for e in all_events if e['status'] == 'COMPLETE']
        censored = len(all_events) - len(complete)
        result[label] = {
            'intended_baskets': len(all_events), 'censored_baskets': censored,
            'return_identified': bool(all_events) and not censored,
            'censor_reasons': dict(Counter(r['reason'] for e in all_events for r in e.get('reasons', []))),
            'cost_scenarios': {},
        }
        for cost in (.008, .012, .016):
            m = prior.summarize_events(complete, cost)
            if not complete:
                m['compounded_return'] = None
                m['max_drawdown'] = None
            m['interpretation'] = 'COMPLETE_CASE_ONLY_NOT_IDENTIFIED_TOTAL' if censored else 'HYPOTHETICAL_RAW_PRICE_RETURN'
            m['remove_best_return'] = prior.remove_best_return(complete, cost) if complete else None
            m['total_return_lower_bound'] = -1.0 if censored else m['compounded_return']
            result[label]['cost_scenarios'][str(cost)] = m
    return result


def screen(model, benchmark):
    reasons = []
    both = model['2024_2025']
    m = both['cost_scenarios']['0.012']
    b = benchmark['2024_2025']
    if both['censored_baskets']:
        reasons.append('MODEL_RETURN_NOT_IDENTIFIED')
    if m['complete_trades'] < 20:
        reasons.append('INSUFFICIENT_BASKETS')
    for year in ('2024', '2025'):
        y = model[year]['cost_scenarios']['0.016']
        if y['complete_trades'] < 5 or y['compounded_return'] is None or y['compounded_return'] <= 0:
            reasons.append('YEAR_NOT_POSITIVE_OR_INSUFFICIENT_' + year)
    if m['remove_best_return'] is None or m['remove_best_return'] <= 0:
        reasons.append('BEST_BASKET_DEPENDENT_OR_NONPOSITIVE')
    if m['max_drawdown'] is None or m['max_drawdown'] < -.35:
        reasons.append('DRAWDOWN_OR_MISSING')
    if not b['return_identified'] or not both['return_identified']:
        reasons.append('BENCHMARK_COMPARISON_NOT_IDENTIFIED')
    elif m['compounded_return'] <= b['cost_scenarios']['0.012']['compounded_return']:
        reasons.append('NO_MATCHED_BENCHMARK_EXCESS')
    return reasons


def audit(directory=OUTPUT):
    """Offline retained-byte/metric audit; does not regenerate any signal."""
    summary = json.loads((directory/'SUMMARY.json').read_text())
    plan = json.loads(PLAN.read_text())
    for name, expected in summary['provenance']['file_hashes'].items():
        if prior.sha256_file(HERE/name) != expected:
            raise ValueError('EVIDENCE_OR_CODE_HASH_MISMATCH:' + name)
    if prior.sha256_file(HERE.parent/'results/stage_c/EXPERIMENT_LEDGER.jsonl') != plan['parent_ledger_sha256']:
        raise ValueError('PARENT_LEDGER_CHANGED')
    previous, ids, started, terminal, retained = '0'*64, set(), set(), set(), {}
    for line in (directory/'LEDGER.jsonl').read_text().splitlines():
        r = json.loads(line)
        h = r.pop('record_hash')
        if (r['previous_hash'] != previous or digest(r) != h or r['record_id'] in ids
                or r['authority'] != AUTHORITY or r['provenance'] != summary['provenance']):
            raise ValueError('JOURNAL_INTEGRITY_FAILURE')
        previous = h
        ids.add(r['record_id'])
        if r['status'] == 'STARTED':
            started.add(r['experiment_id'])
        if r['status'] == 'EVALUATED':
            terminal.add(r['experiment_id'])
            result = json.loads((directory/r['result_file']).read_text())
            if (prior.sha256_file(directory/r['result_file']) != r['result_sha256']
                    or metrics(result['events']) != result['metrics'] or result['authority'] != AUTHORITY
                    or result['trial'] != r['experiment_id']):
                raise ValueError('RESULT_HASH_OR_ARITHMETIC_FAILURE')
            retained[r['experiment_id']] = result
    if started != terminal or len(terminal) != 24 or previous != summary['ledger_tip']:
        raise ValueError('BUDGET_OR_TERMINAL_MISMATCH')
    potential = []
    for kind in KINDS:
        for horizon in (5, 20):
            passed = True
            for q in (.15, .10):
                key = f'{kind}_H{horizon}_Q{q}'
                model = retained[key+'_MODEL']['metrics']
                benchmark = retained[key+'_MATCHED_BENCHMARK']['metrics']
                expected = {'model': model, 'benchmark': benchmark,
                            'screen_rejection_reasons': screen(model, benchmark)}
                if summary['trials'][key] != expected:
                    raise ValueError('SUMMARY_CLASSIFICATION_MISMATCH')
                passed = passed and not expected['screen_rejection_reasons']
            if passed:
                potential.append(f'{kind}_H{horizon}')
    if (summary['historical_potential'] != potential or summary['accepted_models'] != []
            or summary['production_authorized'] is not False or summary['authority'] != AUTHORITY):
        raise ValueError('SUMMARY_AUTHORITY_OR_POTENTIAL_MISMATCH')
    print(json.dumps({'audit': 'PASS', 'evaluations': len(terminal), 'ledger_tip': previous}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    if args.audit:
        audit()
        return
    plan = json.loads(PLAN.read_text())
    # Remote commit anchor must predate historical evaluation; refuse dirty code.
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=prior.ROOT, text=True).strip()
    for file in (PLAN, Path(__file__).resolve()):
        rel = file.relative_to(prior.ROOT).as_posix()
        if subprocess.check_output(['git', 'show', head+':'+rel], cwd=prior.ROOT) != file.read_bytes():
            raise ValueError('PREREGISTRATION_NOT_COMMITTED')
    if prior.sha256_file(HERE.parent/'results/stage_c/EXPERIMENT_LEDGER.jsonl') != plan['parent_ledger_sha256']:
        raise ValueError('PARENT_LEDGER_DRIFT')
    mother = HERE.parent/'results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
    prior.validate_mother_receipt(mother, mother.parent/'TWSE_MOTHER_RECEIPT.json')
    if prior.sha256_file(mother) != plan['mother_sha256']:
        raise ValueError('PLAN_MOTHER_MISMATCH')
    dates, rows = prior.load_mother(mother)
    prior.verify_mother_membership(dates, rows)
    OUTPUT.mkdir(exist_ok=False)
    hashes = {name: prior.sha256_file(HERE/name) for name in
              ('PLAN.json', 'search.py', '../stage_c_rule_search.py', '../reset_ledger.py',
               '../stage_b_build_twse_year.py')}
    provenance = {'study': plan['study'], 'preregistered_commit': head, 'file_hashes': hashes,
                  'mother_sha256': plan['mother_sha256'], 'parent_ledger_sha256': plan['parent_ledger_sha256']}
    trials = {}
    with TrialLedger(OUTPUT/'LEDGER.jsonl', provenance) as ledger:
        for threshold in (.15, .10):
            cache = signal_cache(dates, rows, threshold)
            for kind in KINDS:
                for horizon in (5, 20):
                    pair = []
                    for source in ('MODEL', 'MATCHED_BENCHMARK'):
                        trial = f'{kind}_H{horizon}_Q{threshold}_{source}'
                        ledger.append({'record_id': trial+':STARTED', 'experiment_id': trial, 'status': 'STARTED'})
                    try:
                        pair = evaluate(kind, horizon, threshold, dates, rows, cache)
                        calculated = [metrics(e) for e in pair]
                        for source, events, m in zip(('MODEL', 'MATCHED_BENCHMARK'), pair, calculated):
                            trial = f'{kind}_H{horizon}_Q{threshold}_{source}'
                            file = trial+'.json'
                            dump(OUTPUT/file, {'trial': trial, 'authority': AUTHORITY, 'events': events, 'metrics': m})
                            ledger.append({'record_id': trial+':EVALUATED', 'experiment_id': trial, 'status': 'EVALUATED',
                                           'result_file': file, 'result_sha256': prior.sha256_file(OUTPUT/file)})
                        trials[f'{kind}_H{horizon}_Q{threshold}'] = {'model': calculated[0], 'benchmark': calculated[1],
                                                                 'screen_rejection_reasons': screen(*calculated)}
                    except Exception as exc:
                        for source in ('MODEL', 'MATCHED_BENCHMARK'):
                            trial = f'{kind}_H{horizon}_Q{threshold}_{source}'
                            if trial+':EVALUATED' not in ledger.ids:
                                ledger.append({'record_id': trial+':FAILED', 'experiment_id': trial, 'status': 'FAILED',
                                               'reason': type(exc).__name__+':'+str(exc)})
                        raise
        potential = [f'{k}_H{h}' for k in KINDS for h in (5, 20)
                     if all(not trials[f'{k}_H{h}_Q{q}']['screen_rejection_reasons'] for q in (.15, .10))]
        dump(OUTPUT/'SUMMARY.json', {'provenance': provenance, 'authority': AUTHORITY, 'evaluations': 24,
             'parent_evaluations': 8505, 'cumulative_evaluations': 8529, 'ledger_tip': ledger.previous,
             'historical_potential': potential, 'accepted_models': [], 'production_authorized': False,
             'status': 'HISTORICAL_POTENTIAL_ONLY_NOT_ACCEPTED' if potential else 'NO_NEW_POTENTIAL_UNDER_REGISTERED_SCREEN',
             'trials': trials})
    audit()


if __name__ == '__main__':
    main()
