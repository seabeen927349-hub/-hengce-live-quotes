"""Synthetic governance cases only; never accesses market outcomes or holdouts."""
import importlib.metadata
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import inventory
import ledger
import scope_guard

BASE = Path(__file__).parent


def fixture(identifier='synthetic-1', previous=ledger.GENESIS, parent=None):
    obj = dict(schema_version=1, experiment_id=identifier, parent_id=parent,
               hypothesis='SYNTHETIC VALIDATOR CASE ONLY', engine='M1', code_commit='a' * 40,
               data_cutoff='2026-10-20T00:00:00+00:00', parameters={}, metrics=None,
               result='FAILED', decision='REJECT', reason='Synthetic failure retained',
               recorded_at='2026-10-22T00:00:00+00:00', previous_sha256=previous,
               record_sha256='', capital_authority=0, phase2_authorized=False)
    obj['record_sha256'] = ledger.record_hash(obj)
    return obj


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((BASE / 'evidence_inventory.json').read_text())

    def test_pinned_sources_and_inventory_are_reproducible(self):
        self.assertEqual((BASE / 'evidence_inventory.json').read_text(), inventory.encode(inventory.build()))

    def test_incomplete_eod_is_not_promoted(self):
        days = {x['target_date']: x for x in self.data['B03']['eod_days']}
        self.assertIs(days['2026-10-21']['formal_complete_day'], True)
        self.assertIs(days['2026-10-22']['formal_complete_day'], False)
        self.assertEqual(days['2026-10-22']['margin_status'], 'PENDING')
        self.assertIsNone(days['2026-10-14']['formal_complete_day'])
        self.assertEqual(self.data['B03']['formal_complete_days_explicit_true'], ['2026-10-21'])

    def test_m1_missing_numerics_and_engine_isolation(self):
        m1 = self.data['B02']['baselines']['M1']
        self.assertEqual(m1['authority'], 'RESEARCH_SHADOW_ONLY')
        self.assertEqual(m1['capital_authority'], 0)
        self.assertEqual(m1['expected_outputs'], [])
        self.assertIsNone(m1['formula_version'])
        self.assertEqual(m1['numerical_baseline'], 'ABSENT_IN_REVIEWED_EVIDENCE')

    def test_timing_and_context_are_not_execution(self):
        evidence = self.data['B05']
        self.assertEqual(len(evidence['authentic_0901_observations']), 2)
        self.assertIs(evidence['DAILY_NEXT_OPEN_RESEARCH']['intraday_0903_0905_required'], False)
        self.assertEqual(evidence['DAILY_NEXT_OPEN_RESEARCH']['status'], 'NOT_AUTHORIZED')
        self.assertEqual(evidence['INTRADAY_TIMING_RESEARCH']['daily_ohlc_substitution'], 'FORBIDDEN')
        self.assertFalse(any(evidence['current_quote_context_contract']['authority'].values()))
        self.assertTrue(all(x['first_seen_time'] == 'NOT_PROVEN' for x in self.data['B04']['artifacts']))

    def test_protected_paths_are_never_read(self):
        ev = inventory.Evidence()
        for name in ('sealed/outcomes.json', 'research/holdout.csv', 'hengce/user_trades.json'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'FORBIDDEN_EVIDENCE_READ'):
                ev.read(name)

    def test_scope_guard_rejects_model_data_and_workflow_rewrites(self):
        scope_guard.check_paths(['research/phase1_audit/governance.json', '.github/workflows/hengce-phase1-foundation.yml'])
        for path in ('scripts/hengce_e2_live.py', 'hengce/q017_radar/decision/20261022_0901.json',
                     '.github/workflows/hengce-engineering-replay.yml'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'STOP_'):
                scope_guard.check_paths([path])

    def test_coverage_counts_do_not_assert_calendar_completeness(self):
        x = inventory.csv_coverage('Date,Ticker\n2026-10-19,1111\n2026-10-21,1111\n')
        self.assertEqual(x['observed_dates'], ['2026-10-19', '2026-10-21'])
        self.assertEqual(x['completeness'], 'NOT_PROVEN_BY_ROW_COUNTS')
        self.assertEqual(x['rows_by_date']['2026-10-21'], 1)

    def test_floating_duplicate_or_missing_dependencies_rejected(self):
        text = (BASE / 'requirements-replay.txt').read_text()
        self.assertEqual(len(inventory.validate_requirements(text)), 8)
        for changed in (text.replace('==2.32.5', '>=2.32.5'), text + '\nrequests==2.32.5',
                        text.replace('requests==2.32.5', 'other==2.32.5')):
            with self.subTest(text=changed), self.assertRaises(ValueError):
                inventory.validate_requirements(changed)

    def test_replay_environment_matches_pins(self):
        for line in inventory.validate_requirements((BASE / 'requirements-replay.txt').read_text()):
            package, version = line.split('==')
            self.assertEqual(importlib.metadata.version(package), version)

    def test_governance_does_not_clear_any_blocker_or_invent_values(self):
        policy = json.loads((BASE / 'governance.json').read_text())
        self.assertEqual(policy['B10'], 'BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION')
        self.assertFalse(policy['phase2_authorized'])
        self.assertEqual(policy['B07']['existing_frozen_assumptions']['E2']['cost_roundtrip'], .008)
        self.assertTrue(all(x['value'] is None for x in policy['B07']['component_specification']))
        self.assertTrue(all(x is None for x in policy['B08']['policy_values'].values()))
        self.assertTrue(policy['B09']['immutability']['external_anchor_required'])
        self.assertFalse(policy['B09']['holdout_allocated'])

    def test_schema_fields_and_custody_states_are_explicit(self):
        experiment = json.loads((BASE / 'experiment.schema.json').read_text())
        self.assertEqual(set(experiment['required']), ledger.FIELDS)
        self.assertFalse(experiment['additionalProperties'])
        custody = json.loads((BASE / 'holdout.schema.json').read_text())
        self.assertEqual(custody['properties']['open_count']['maximum'], 1)
        self.assertEqual(len(custody['allOf']), 4)
        self.assertIn('CONSUMED', custody['properties']['state']['enum'])


class LedgerTests(unittest.TestCase):
    def test_append_and_failed_experiment_retention(self):
        first = fixture()
        second = fixture('synthetic-2', first['record_sha256'], first['experiment_id'])
        checkpoint = ledger.validate_ledger([first])
        self.assertEqual(ledger.validate_extension([first], [first, second], checkpoint)['record_count'], 2)

    def test_tampering_and_wrong_hashes_rejected(self):
        first = fixture()
        for key, value in [('reason', 'tampered'), ('previous_sha256', 'a' * 64), ('record_sha256', 'b' * 64)]:
            modified = {**first, key: value}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'HASH_CHAIN'):
                ledger.validate_ledger([modified])

    def test_rehash_cannot_rewrite_or_truncate_anchored_history(self):
        first = fixture()
        second = fixture('synthetic-2', first['record_sha256'])
        old = [first, second]
        modified = {**first, 'reason': 'rewritten'}
        modified['record_sha256'] = ledger.record_hash(modified)
        with self.assertRaisesRegex(ValueError, 'APPEND_ONLY'):
            ledger.validate_extension(old, [modified], ledger.validate_ledger(old))
        with self.assertRaisesRegex(ValueError, 'CHECKPOINT'):
            ledger.validate_extension([modified], [modified], ledger.validate_ledger([first]))
        with self.assertRaisesRegex(ValueError, 'APPEND_ONLY'):
            ledger.validate_extension(old, [first], ledger.validate_ledger(old))

    def test_unknown_parent_duplicate_or_mixed_engines_rejected(self):
        first = fixture()
        for modified in ({**first, 'parent_id': 'missing'}, {**first, 'engine': 'Q017+E2'}):
            with self.assertRaises(ValueError):
                ledger.validate_ledger([modified])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            ledger.validate_ledger([first, first])

    def test_authority_time_outcome_and_nonfinite_rejected(self):
        first = fixture()
        for key, value in [('capital_authority', 1), ('capital_authority', False),
                           ('phase2_authorized', True), ('decision', 'ACCEPT'),
                           ('recorded_at', '2026-10-19T00:00:00Z'),
                           ('recorded_at', '2026-10-22T00:00:00'),
                           ('metrics', {'profit': float('nan')}), ('metrics', {'profit': float('inf')})]:
            modified = {**first, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                ledger.validate_ledger([modified])


if __name__ == '__main__':
    unittest.main(verbosity=2)
