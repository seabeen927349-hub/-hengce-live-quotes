import base64
import io
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from hengce_hba_context_bridge_v1 import card_time
from hengce_hba_decision_report import CARD_SCHEMA, write_research_cards
from hengce_hba_research_ledger import (LIVE, REPLAY, LockedArchive, canonical, key_for, sha,
                                        snapshot, store_replay, unpack)
from hengce_hba_research_outcomes import (load_inputs, sessions_after, settle_one, settlement)
from hengce_twse_calendar import load_manifest


class Conflict(Exception):
    response = {'Error': {'Code': 'PreconditionFailed'}}


class ObjectLockDouble:
    def __init__(self):
        self.objects = {}
        self.time = card_time('2026-11-18T14:00:00+08:00')
        self.mode = 'COMPLIANCE'

    def get_object_lock_configuration(self, **kwargs):
        return {'ObjectLockConfiguration': {'ObjectLockEnabled': 'Enabled',
                'Rule': {'DefaultRetention': {'Mode': self.mode, 'Years': 3}}}}

    def get_object_retention(self, **kwargs):
        return {'Retention': {'Mode': self.mode, 'RetainUntilDate': self.time+timedelta(days=1095)}}

    def put_object(self, Key, Body, Metadata, IfNoneMatch, **kwargs):
        assert IfNoneMatch == '*'
        if Key in self.objects:
            raise Conflict()
        self.objects[Key] = (Body, Metadata)
        return {'VersionId': '1'}

    def get_object(self, Key, **kwargs):
        data, metadata = self.objects[Key]
        return {'Body': io.BytesIO(data), 'Metadata': metadata, 'VersionId': '1', 'LastModified': self.time}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = {'schema': CARD_SCHEMA, 'market_date': '2026-11-17',
                    'evidence_cutoff_taipei': '2026-11-18T10:30:00+08:00',
                    'coverage': {'stocks': 1},
                    'provenance': {'eod': {}, 'tdcc': []},
                    'environment': {'taiwan_vix': {'status': 'UNVERIFIED'}, 'overseas': {'status': 'UNVERIFIED'}}}
        self.card = {'ticker': '2610', 'research': {'invalidation': {
            'status':'VERIFIED', 'downside_below_twd':90, 'upside_above_twd':108}}}

    def make(self, mode=REPLAY):
        write_research_cards(self.root, self.manifest, [self.card])
        return snapshot(self.root, 'a'*40, mode)

    def test_replay_idempotence_and_mutation_rejection(self):
        record = self.make()
        with ThreadPoolExecutor(4) as workers:
            receipts = list(workers.map(lambda _: store_replay(self.root, record), range(8)))
        first = receipts[0]
        self.assertTrue(all(r == first for r in receipts))
        self.assertIsNone(first['published_at_taipei'])
        self.assertEqual(unpack(json.loads(Path(first['path']).read_bytes()))[1]['2610'], self.card)
        Path(first['path']).write_bytes(b'replaced')
        with self.assertRaisesRegex(ValueError, 'EXISTING_RECORD_DIFFERS'):
            store_replay(self.root, record)

    def test_distinct_modes_and_no_local_prospective(self):
        replay, live = self.make(), self.make(LIVE)
        self.assertNotEqual(replay['snapshot_id'], live['snapshot_id'])
        with self.assertRaisesRegex(ValueError, 'REPLAY_ONLY'):
            store_replay(self.root, live)

    def test_future_source_rejected(self):
        proof = {'effective_date':'2026-11-17', 'status':'VERIFIED',
                 'available_at':'2026-11-18T10:31:00+08:00',
                 'mother_available_at':'2026-11-18T10:31:00+08:00'}
        self.manifest['provenance']['eod']['2026-11-17'] = {'price':proof}
        with self.assertRaisesRegex(ValueError, 'FUTURE_EOD'):
            self.make()
        self.manifest['provenance']['eod'] = {}
        self.manifest['provenance']['tdcc'] = [proof]
        with self.assertRaisesRegex(ValueError, 'FUTURE_TDCC'):
            self.make()

    def test_shard_tampering(self):
        record = self.make()
        record['objects']['cards-01.json'] = base64.b64encode(b'[]').decode()
        with self.assertRaisesRegex(ValueError, 'SHARD_SHA'):
            unpack(record)

    def test_lock_create_readback_conflict_and_expiry_independence(self):
        client = ObjectLockDouble()
        archive = LockedArchive(client, 'archive', '123456789012')
        record = self.make(LIVE)
        key = key_for(record)
        data = canonical(record)
        receipt = archive.create(key, data)
        self.assertEqual(receipt, archive.create(key, data))
        with self.assertRaisesRegex(ValueError, 'LOCKED_RECORD_DIFFERS'):
            archive.create(key, b'changed')
        for path in self.root.glob('*.json'):
            path.unlink()
        raw, _ = archive.read(key, receipt['version_id'])
        self.assertEqual(unpack(json.loads(raw))[1]['2610'], self.card)
        client.mode = 'GOVERNANCE'
        with self.assertRaisesRegex(ValueError, 'RETENTION'):
            archive.create(key, data)

    def test_intraday_formation_uses_next_open_and_reports_pending(self):
        record = self.make()
        asof = card_time('2026-11-18T14:00:00+08:00')
        result = settlement(record, None, '2610', self.root, asof)
        self.assertEqual(result['mode'], REPLAY)
        self.assertEqual(result['results']['5']['start_session'], '2026-11-19')
        self.assertTrue(all(x['status']=='PENDING' for x in result['results'].values()))
        calendar, _, _ = load_manifest()
        self.assertEqual(sessions_after(card_time('2026-11-18T08:55:00+08:00'), calendar)[0],
                         date(2026, 11, 18))

    def test_settle_actual_session_formulas_and_release_gate(self):
        calendar, _, _ = load_manifest()
        full = sessions_after(card_time('2026-11-18T10:30:00+08:00'), calendar)
        days = full[:5]
        labels = [d.isoformat() for d in days]
        prices, supplementary = {}, {}
        for day, close in zip((x.isoformat() for x in full), (105, 110, 99, 104, 108, *[108]*15)):
            proof = {'status':'VERIFIED', 'available_at':day+'T22:00:00+08:00', 'sha256':'a'*64}
            prices[day] = ({'2610':{'Open':100,'Close':close,'VolumeShares':100000}}, proof)
            supplementary[day] = {'benchmark':{**proof,'open':1000,'close':1020},
                                  'stocks':{'2610':{**proof,'trading_status':'TRADABLE','corporate_action':'NONE_VERIFIED'}}}
        policy = {'min_volume_shares':1000, 'cost_bps':{'buy_fee':10,'sell_fee':10,'sell_tax':30,'slippage_per_side':5}}
        def run(hour=23):
            return settle_one(self.card, days, prices, supplementary, policy,
                              card_time(f'{labels[-1]}T{hour:02}:00:00+08:00'))
        self.assertEqual(run(12)['status'], 'PENDING')
        self.assertEqual(run(15)['status'], 'PRICE_NOT_AVAILABLE')
        actual = run()
        self.assertEqual(actual['status'], 'SETTLED_DESCRIPTIVE')
        self.assertAlmostEqual(actual['gross_return'], .08)
        self.assertAlmostEqual(actual['gross_excess_return'], .06)
        self.assertAlmostEqual(actual['max_drawdown'], .10)
        self.assertLess(actual['illustrative_net_long_return'], .08)
        self.assertEqual(actual['range_invalidation']['date'], labels[1])
        for n in (10, 20):
            end = full[n-1].isoformat()
            horizon = settle_one(self.card, full[:n], prices, supplementary, policy,
                                 card_time(end+'T23:00:00+08:00'))
            self.assertEqual(horizon['sessions'], n)
            self.assertAlmostEqual(horizon['gross_return'], .08)
        stock = supplementary[labels[0]]['stocks']['2610']
        for field, value, expected in (
            ('trading_status','HALTED','HALTED'), ('trading_status','DELISTED','DELISTED'),
            ('corporate_action','SPLIT','CORPORATE_ACTION_OR_TRADEABILITY_BLOCKED'),
        ):
            old = stock[field]
            stock[field] = value
            self.assertEqual(run()['status'], expected)
            stock[field] = old
        policy['min_volume_shares'] = 200000
        self.assertEqual(run()['status'], 'INSUFFICIENT_VOLUME')

    def test_reference_input_sha_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'INPUT_SHA'):
            load_inputs(b'{}', sha(b'different'))
