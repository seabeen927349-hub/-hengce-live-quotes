#!/usr/bin/env python3
"""Offline adversarial contract regressions (no market-data requests)."""
import copy
from datetime import datetime
import unittest
import hengce_unified_candidate_adapter as adapter
import hengce_unified_action_board as board
from hengce_unified_contracts import ticker, geometry, strict_loads

NOW = datetime.fromisoformat('2026-10-23T10:00:00+08:00')

def fixtures():
    legacy = {'run_id': 'TEST', 'formal_scan_allowed': True, 'trade_date': '2026-10-23',
              'generated_at': NOW.isoformat(), 'rows': [
        {'Ticker': '2330', 'AlphaScore': .9, 'FormalEntryTrigger': True,
         'BreakoutLower': 100, 'BreakoutUpper': 105, 'NoChase': 110, 'InvalidationPrice': 90}]}
    live = {'snapshot_id': 'S1', 'generated_at_taipei': NOW.isoformat(), 'stale_count': 0,
            'data': [{'symbol': '2330', 'price': 103, 'high': 104, 'quote_date': '2026-10-23'}]}
    context = {'MarketContextState': 'NORMAL', 'NewCapitalPolicy': 'NORMAL'}
    return legacy, live, context

class Boundaries(unittest.TestCase):
    def test_ticker_formats(self):
        self.assertEqual(ticker({'Ticker': '2330.TW', 'symbol': 'TWSE:2330'}), '2330')
        with self.assertRaises(ValueError): ticker({'Ticker': '2330', 'symbol': '2454'})
    def test_strict_json(self):
        for data in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}']:
            with self.assertRaises(ValueError): strict_loads(data)
    def test_no_geometry_no_entry(self):
        legacy, live, ctx = fixtures()
        del legacy['rows'][0]['BreakoutLower']
        result = board.build(adapter.build(legacy), live, ctx, trade_date='2026-10-23', now=NOW)
        self.assertEqual(result['rows'][0]['FinalAction'], 'ABSTAIN')
    def test_unknown_context_no_entry(self):
        legacy, live, ctx = fixtures()
        ctx['MarketContextState'] = 'UNRECOGNIZED'
        result = board.build(adapter.build(legacy), live, ctx, trade_date='2026-10-23', now=NOW)
        self.assertEqual(result['binding_status'], 'FAIL_CLOSED')
        self.assertTrue(all(r['FinalAction'] == 'ABSTAIN' for r in result['rows']))
    def test_conflicting_duplicate_rejected(self):
        legacy, _, _ = fixtures()
        other = copy.deepcopy(legacy['rows'][0]); other['AlphaScore'] = .1
        legacy['rows'].append(other)
        with self.assertRaises(ValueError): adapter.build(legacy)
    def test_invalid_geometry(self):
        legacy, _, _ = fixtures()
        row = legacy['rows'][0]
        for field, value in [('NoChase', float('inf')), ('BreakoutLower', True), ('InvalidationPrice', 106)]:
            bad = dict(row); bad[field] = value
            self.assertIsNone(geometry(bad))
    def test_no_numeric_contract_coercion(self):
        from unittest.mock import patch
        from test_hengce_unified_q017 import canonical_q017
        q = canonical_q017()
        with patch.object(adapter, 'VERIFIED_Q017_PRODUCERS', frozenset({'0' * 40})):
            self.assertTrue(adapter.validate_q017_contract(q)[0])
            for value in (1.9, True, '1'):
                q['canonical_q017_contract']['top_n'] = value
                self.assertFalse(adapter.validate_q017_contract(q)[0])
    def test_duplicate_live_rejected(self):
        legacy, live, ctx = fixtures()
        live['data'].append(dict(live['data'][0], price=106))
        result = board.build(adapter.build(legacy), live, ctx, trade_date='2026-10-23', now=NOW)
        self.assertEqual(result['binding_status'], 'FAIL_CLOSED')

if __name__ == '__main__': unittest.main()
