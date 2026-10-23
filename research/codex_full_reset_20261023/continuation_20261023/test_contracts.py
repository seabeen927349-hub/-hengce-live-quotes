"""Entirely synthetic; running CI never launches a historical model trial."""
import copy
from datetime import date, timedelta
import json
import math
from pathlib import Path
import tempfile
import unittest

import search as s


class Contracts(unittest.TestCase):
    def history(self):
        return [s.prior.Row(str(i), '2330', 'fixture', 100+i, 102+i, 99+i,
                            101+i, 1000, 100_000_000) for i in range(61)]

    def lane(self):
        days = [(date(2024, 1, 1)+timedelta(days=i)).isoformat() for i in range(10)]
        rows = {d: {str(t): s.prior.Row(d, str(t), 'fixture', 100, 110, 90, 105, 1000,
                                        100_000_000) for t in range(11)} for d in days}
        cache = {days[0]: {'SKIP5_MOMENTUM': [str(t) for t in range(11)],
                           'universe': [str(t) for t in range(11)]}}
        return days, rows, cache

    def test_known_skip_score_and_signal_history_only(self):
        rows = self.history()
        result = s.features(rows, .15)
        self.assertAlmostEqual(result['SKIP5_MOMENTUM'], rows[-6].close / rows[0].close-1)
        rows[-1].close = rows[-1].open
        self.assertEqual(result['SKIP5_MOMENTUM'], s.features(rows, .15)['SKIP5_MOMENTUM'])

    def test_malformed_or_nonfinite_history_fails_closed(self):
        for value in (None, math.nan, math.inf, -1, 0, True):
            rows = self.history()
            rows[4].close = value
            self.assertIsNone(s.features(rows, .15))
        rows = self.history()
        rows[0] = None
        self.assertIsNone(s.features(rows, .15))
        self.assertIsNone(s.features(self.history()[1:], .15))

    def test_discontinuity_is_not_an_adjustment(self):
        rows = self.history()
        rows[-1].close *= 2
        rows[-1].high = rows[-1].close
        self.assertIsNone(s.features(rows, .15))

    def test_bad_future_does_not_replace_selected_ticker(self):
        days, rows, cache = self.lane()
        rows[days[1]]['0'].open = None
        model, benchmark = s.evaluate('SKIP5_MOMENTUM', 5, .15, days, rows, cache)
        self.assertEqual(len(model), 1)
        self.assertEqual(model[0]['status'], 'CENSORED')
        self.assertEqual(model[0]['tickers'], [str(t) for t in range(10)])
        self.assertNotIn('10', model[0]['tickers'])
        self.assertEqual(benchmark[0]['status'], 'CENSORED')

    def test_censored_interval_cannot_spawn_replacement_basket(self):
        days, rows, cache = self.lane()
        cache.update({d: cache[days[0]] for d in days[1:]})
        rows[days[1]]['0'].open = None
        model, _ = s.evaluate('SKIP5_MOMENTUM', 5, .15, days, rows, cache)
        self.assertEqual(len(model), 1)

    def test_year_crossing_trade_is_purged(self):
        days, rows, cache = self.lane()
        shifted = [(date(2024, 12, 28)+timedelta(days=i)).isoformat() for i in range(10)]
        rows = {new: rows[old] for old, new in zip(days, shifted)}
        cache = {shifted[0]: cache[days[0]]}
        self.assertEqual(s.evaluate('SKIP5_MOMENTUM', 5, .15, shifted, rows, cache), ([], []))

    def test_locked_entry_censored(self):
        days, rows, _ = self.lane()
        row = rows[days[1]]['0']
        row.open = row.close = row.high = row.low = 105
        event = s.outcome(['0'], 0, 5, days, rows, .15)
        self.assertEqual(event['status'], 'CENSORED')
        self.assertEqual(event['reasons'][0]['reason'], 'LIMIT_LOCKED_OR_UNFILLABLE_ENTRY')

    def test_cost_applied_once_and_unknown_not_cash(self):
        days, rows, _ = self.lane()
        event = s.outcome(['0'], 0, 5, days, rows, .15)
        m = s.metrics([event])['2024']['cost_scenarios']['0.012']
        self.assertAlmostEqual(m['compounded_return'], .05-.012)
        self.assertAlmostEqual(m['max_drawdown'], -.012/1.05)
        rows[days[2]].pop('0')
        unknown = s.outcome(['0'], 0, 5, days, rows, .15)
        m = s.metrics([unknown])['2024']
        self.assertFalse(m['return_identified'])
        self.assertIsNone(m['cost_scenarios']['0.012']['compounded_return'])
        self.assertEqual(m['cost_scenarios']['0.012']['total_return_lower_bound'], -1)

    def test_signal_cache_is_prefix_causal_and_ties_deterministic(self):
        days = [(date(2024, 1, 1)+timedelta(days=i)).isoformat() for i in range(65)]
        rows = {d: {t: s.prior.Row(d,t,'fixture',100+i,102+i,99+i,101+i,1000,100_000_000)
                    for t in ('2454', '2330')} for i,d in enumerate(days)}
        prefix = s.signal_cache(days[:61], rows, .15)
        self.assertEqual(prefix[days[60]]['SKIP5_MOMENTUM'], ['2330', '2454'])
        changed = copy.deepcopy(rows)
        for d in days[61:]:
            changed[d].clear()
        self.assertEqual(s.signal_cache(days, changed, .15)[days[60]], prefix[days[60]])

    def test_immutable_evidence_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'result.json'
            s.dump(p, {'value': 1})
            with self.assertRaises(FileExistsError):
                s.dump(p, {'value': 2})
            self.assertEqual(json.loads(p.read_text()), {'value': 1})

    def test_missing_samples_or_unknown_benchmark_never_passes(self):
        days, rows, _ = self.lane()
        event = s.outcome(['0'], 0, 5, days, rows, .15)
        model = s.metrics([event])
        benchmark = s.metrics([])
        reasons = s.screen(model, benchmark)
        self.assertIn('INSUFFICIENT_BASKETS', reasons)
        self.assertIn('BENCHMARK_COMPARISON_NOT_IDENTIFIED', reasons)

    def test_plan_is_research_only_and_budget_finite(self):
        plan = json.loads(s.PLAN.read_text())
        self.assertEqual(plan['authority'], s.AUTHORITY)
        self.assertEqual(plan['total_evaluation_budget'], 24)
        self.assertEqual(plan['model_configs'], len(s.KINDS)*2)


if __name__ == '__main__':
    unittest.main()
