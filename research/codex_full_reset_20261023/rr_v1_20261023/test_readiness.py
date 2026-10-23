"""Synthetic/offline evidence tests; no model inputs or simulations."""
import copy
import json
import unittest
from unittest.mock import patch

import readiness as r


class ReadinessTests(unittest.TestCase):
    def test_bom_and_unordered_dates_inventory(self):
        got = r.csv_summary(b'\xef\xbb\xbfdate,ticker\n2026-01-05,2330\n2026-01-02,2330\n', ticker_column='ticker')
        self.assertEqual((got['rows'], got['date_min'], got['date_max']), (2, '2026-01-02', '2026-01-05'))

    def test_duplicate_key_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SOURCE_KEY'):
            r.csv_summary(b'date,ticker\n2026-01-02,2330\n2026-01-02,2330\n', ticker_column='ticker')

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            r.csv_summary(b'date\n2026-02-30\n')

    def test_duplicate_header_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_HEADERS'):
            r.csv_summary(b'date,date\n2026-01-02,2026-01-02\n')

    def test_ragged_rejected(self):
        for raw in (b'date,ticker\n2026-01-02\n', b'date,ticker\n2026-01-02,2330,extra\n'):
            with self.assertRaisesRegex(ValueError, 'RAGGED_SOURCE'):
                r.csv_summary(raw, ticker_column='ticker')

    def test_missing_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'MISSING_KEY_COLUMN'):
            r.csv_summary(b'other\na\n')

    def test_empty_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'EMPTY_SOURCE'):
            r.csv_summary(b'date,ticker\n', ticker_column='ticker')

    def test_preferred_share_not_silently_discarded(self):
        got = r.csv_summary(b'date,ticker\n2026-01-02,8112A\n', ticker_column='ticker')
        self.assertEqual(got['non_four_digit_ticker_rows'], {'8112A': 1})

    def test_comparison_separates_format_from_value(self):
        seed = b'date,ticker,close\n2026-01-02,2330,"1,000"\n'
        same = b'date,ticker,close\n2026-01-02,2330,1000\n'
        diff = b'date,ticker,close\n2026-01-02,2330,1001\n'
        key = 'different_values_after_thousands_separator_normalization'
        self.assertEqual(r.compare_seed(seed, same)[key], [])
        self.assertEqual(r.compare_seed(seed, diff)[key], [['2026-01-02', '2330']])

    def test_missing_seed_key_is_retained_as_gap(self):
        seed = b'date,ticker\n2026-01-02,2330\n2026-01-02,8112A\n'
        current = b'date,ticker\n2026-01-02,2330\n'
        self.assertEqual(r.compare_seed(seed, current)['missing_keys'], [['2026-01-02', '8112A']])

    def test_schema_difference_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SCHEMA_MISMATCH'):
            r.compare_seed(b'date,ticker\n2026-01-02,2330\n', b'date,other\n2026-01-02,2330\n')

    def test_blocked_result_never_invents_zero_trades_or_returns(self):
        prereg = {'frozen_config': r.CONFIG, 'authority': r.AUTH}
        with patch.object(r, 'blob', return_value=r.encoded(prereg)), patch.object(r, 'inventory', return_value={'synthetic': True}):
            out = r.generate()
        result = json.loads(out['RR_V1_RESULT.json'])
        self.assertEqual(out['RR_V1_EVENTS.jsonl'], b'')
        self.assertEqual(result['status'], 'BLOCKED_DATA_READINESS')
        self.assertEqual(result['new_model_evaluations'], 0)
        for key in ('intended_baskets', 'complete_baskets', 'censored_baskets', 'regime_occurrences'):
            self.assertIsNone(result[key])
        for case in result['cost_cases']:
            self.assertIsNone(case['compounded_return'])
            self.assertIsNone(case['max_drawdown'])
        self.assertEqual(result['authority'], r.AUTH)
        self.assertFalse(result['prospective_claim'])

    def test_config_or_authority_tampering_rejected(self):
        for target in ('config', 'authority'):
            p = {'frozen_config': copy.deepcopy(r.CONFIG), 'authority': copy.deepcopy(r.AUTH)}
            if target == 'config':
                p['frozen_config']['top_n'] = 3
            else:
                p['authority']['capital_authority_twd'] = 1
            with patch.object(r, 'blob', return_value=r.encoded(p)):
                with self.assertRaisesRegex(ValueError, 'CONTRACT_MISMATCH'):
                    r.generate()

    def test_out_of_scope_parent_mutation_rejected(self):
        with patch.object(r, 'git', return_value=b'scripts/hengce_e2_live.py\n'):
            with self.assertRaisesRegex(ValueError, 'OUT_OF_SCOPE_CHANGE'):
                r.check_scope()

    def test_evidence_tampering_rejected(self):
        with patch.object(r, 'check_scope'), patch.object(r, 'generate', return_value={'test.json': b'original'}), patch.object(r.Path, 'read_bytes', return_value=b'modified'):
            with self.assertRaisesRegex(ValueError, 'REPRODUCTION_MISMATCH'):
                r.audit()


if __name__ == '__main__':
    unittest.main()
