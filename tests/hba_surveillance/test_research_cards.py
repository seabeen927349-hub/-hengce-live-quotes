import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from hengce_hba_context_bridge_v1 import CARD_LEGS, card_eod_leg, card_tdcc, card_time
from hengce_hba_decision_report import (CARD_SCHEMA, card_flows, card_judgment,
                                         card_ownership, read_research_cards,
                                         research_cards, write_research_cards)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


class ResearchCardsTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.day = '2026-11-17'
        self.cutoff = card_time('2026-11-18T10:30:00+08:00')

    def price_source(self, payload=None, digest_override=None):
        folder = self.root/'eod/20261117'
        folder.mkdir(parents=True, exist_ok=True)
        if payload is None:
            payload = b'Date,Ticker,Name,Close,High,Low,VolumeShares,TurnoverTWD\n2026-11-17,2610,Stock,23.1,23.1,22,10,230\n'
        name = 'price_1.csv'
        (folder/name).write_bytes(payload)
        digest = digest_override or hashlib.sha256(name.encode()+b'\0'+payload+b'\0').hexdigest()
        receipt = dict(sha256=digest, rows=payload.count(b'\n')-1, source='TWSE', target_date=self.day,
                       status='COMPLETE', leg='price', files=[name],
                       promoted_at_taipei='2026-11-17T22:39:17+08:00')
        dump(folder/'receipts/price.json', receipt)
        dump(folder/'receipts/mother.json', dict(
            target_date=self.day, mother_latest_date=self.day, status='PASS', integrity_status='PASS',
            second_mother=False, updated_at_taipei='2026-11-17T22:43:42+08:00',
            mother_sha256='a'*64, promoted_leg_sha256={'price':digest}))
        dump(folder/'status.json', dict(formal_complete_day=True, downstream_ready=True,
             three_leg_complete=True, price_status='COMPLETE', price_date=self.day, mother_sha256='a'*64,
             price_sha256=digest, price_rows=receipt['rows'], price_source='TWSE'))
        return folder

    def tdcc_source(self, day, observed, corrupt=False):
        folder = self.root/'ownership/tdcc'/day
        folder.mkdir(parents=True)
        raw = b'vendor payload'
        buf = io.StringIO(newline='')
        out = csv.writer(buf)
        out.writerow(('SnapshotDate','ObservedAtTaipei','Ticker','Big400Shares','Big1000Shares','TotalShares'))
        out.writerow((day, observed, '2610', 80, 40, 100))
        summary = buf.getvalue().encode()
        (folder/'tdcc_1_5_raw.csv').write_bytes(raw)
        (folder/'tdcc_ownership_4d.csv').write_bytes(summary)
        dump(folder/'receipt.json', dict(status='COMPLETE', snapshot_date=day, source='TDCC',
             observed_at_taipei=observed, summary_rows=1, source_sha256=hashlib.sha256(raw).hexdigest(),
             summary_sha256=('0'*64 if corrupt else hashlib.sha256(summary).hexdigest())))

    def test_eod_bytes_and_promotion(self):
        self.price_source()
        rows, proof = card_eod_leg(self.root, self.day, 'price', self.cutoff)
        self.assertEqual(proof['status'], 'VERIFIED')
        self.assertEqual(rows['2610']['Close'], '23.1')
        self.assertEqual(proof['availability_kind'], 'FIRST_FORMAL_LEG_PROMOTION')

    def test_eod_before_mother_promotion(self):
        self.price_source()
        _, proof = card_eod_leg(self.root, self.day, 'price', card_time('2026-11-17T22:40:00+08:00'))
        self.assertEqual(proof['reason'], 'EOD_NOT_AVAILABLE_AT_CUTOFF')

    def test_missing_receipt(self):
        self.assertEqual(card_eod_leg(self.root, self.day, 'price', self.cutoff)[1]['status'], 'MISSING')

    def test_eod_raw_sha_mismatch(self):
        self.price_source(digest_override='0'*64)
        self.assertEqual(card_eod_leg(self.root, self.day, 'price', self.cutoff)[1]['reason'], 'EOD_SHA_MISMATCH')

    def test_duplicate_eod_ticker(self):
        folder = self.price_source()
        data = (folder/'price_1.csv').read_bytes()
        self.price_source(data+data.splitlines(keepends=True)[1])
        self.assertEqual(card_eod_leg(self.root, self.day, 'price', self.cutoff)[1]['reason'], 'DUPLICATE_TICKER')

    def test_tdcc_excludes_late_receipt(self):
        self.tdcc_source('20261113', '2026-11-18T12:00:00+08:00')
        self.tdcc_source('20261106', '2026-11-07T05:00:00+08:00')
        results = card_tdcc(self.root, date.fromisoformat(self.day), self.cutoff)
        self.assertEqual([proof['effective_date'] for _, proof in results], ['2026-11-06'])
        self.assertEqual(card_ownership(results, '2610')['change']['status'], 'MISSING')

    def test_tdcc_stale(self):
        self.tdcc_source('20261030', '2026-10-31T05:00:00+08:00')
        self.assertEqual(card_tdcc(self.root, date.fromisoformat(self.day), self.cutoff)[0][1]['reason'], 'TDCC_STALE')

    def test_tdcc_hash_mismatch(self):
        self.tdcc_source('20261113', '2026-11-14T05:00:00+08:00', corrupt=True)
        self.assertEqual(card_tdcc(self.root, date.fromisoformat(self.day), self.cutoff)[0][1]['reason'], 'TDCC_SHA_MISMATCH')

    def test_flow_does_not_fill_missing_session(self):
        dates = ['2026-11-11','2026-11-12','2026-11-13','2026-11-16','2026-11-17']
        eod = {d: {'institutional': ({'2610': {'TotalNet': '10'}}, {'status':'VERIFIED'})} for d in dates}
        self.assertEqual(card_flows(eod, dates, '2610')['5']['net_shares'], 50)
        eod[dates[2]]['institutional'] = ({}, {'status':'UNVERIFIED'})
        self.assertEqual(card_flows(eod, dates, '2610')['5']['status'], 'UNVERIFIED')

    def test_judgment_keeps_both_sides_and_conflict(self):
        card = dict(price={'trend': {'status':'VERIFIED','return_5d_pct':-3},
                           'range': {'status':'VERIFIED','low_twd':21,'high_twd':25},
                           'volume_ratio': {'status':'VERIFIED','vs_previous_5_sessions':0.5}},
                    institutional={'5':{'status':'VERIFIED','net_shares':2000,'net_buy_days':3,'net_sell_days':2}},
                    ownership={'change':{'status':'MISSING'}},
                    leverage={'MarginBalance':{'status':'VERIFIED','change_5d':{'status':'VERIFIED','change_pct':18}},
                              'ShortBalance':{'status':'VERIFIED','change_5d':{'status':'VERIFIED','change_pct':28}}})
        research = card_judgment(card)
        self.assertIn('INSTITUTIONAL_5D_NET_BUY', research['bull_case'])
        self.assertIn('MARGIN_BALANCE_5D_UP_AT_LEAST_12_PCT', research['bear_case'])
        self.assertEqual(research['strongest_counterevidence'], 'PRICE_AND_INSTITUTIONAL_FLOW_DIVERGE')
        self.assertIn('TDCC_CHANGE', research['gaps'])
        self.assertIn('SHORT_BALANCE_5D_UP_AT_LEAST_25_PCT_CHECK_ABSOLUTE_LOTS', research['bear_case'])
        self.assertEqual(research['invalidation']['downside_below_twd'], 21)

    def test_coverage_keeps_unmatched_price_universe_and_roundtrips(self):
        days = ['2026-11-10','2026-11-11','2026-11-12','2026-11-13','2026-11-16','2026-11-17']
        rows = {str(1000+i): {'Name': 'Stock', 'Close':'25', 'High':'26', 'Low':'24',
                             'VolumeShares':'50', 'TurnoverTWD':'1250'} for i in range(101)}
        eod = {d: {leg: (rows if leg == 'price' else {}, {'status':'VERIFIED'}) for leg in CARD_LEGS}
               for d in days}
        with patch('hengce_hba_context_bridge_v1.card_evidence', return_value=(days, eod, [], 'sha')):
            manifest, cards = research_cards(self.root, date.fromisoformat(self.day), self.cutoff)
        self.assertEqual(len(cards), 101)
        self.assertTrue(all(c['institutional']['5']['status']=='MISSING' for c in cards))
        self.assertTrue(all(c['v22d_selection']['status']=='UNVERIFIED' for c in cards))
        write_research_cards(self.root, manifest, cards)
        loaded, actual = read_research_cards(self.root)
        self.assertEqual(len(loaded['shards']), 2)
        self.assertEqual(list(actual.values()), cards)
        (self.root/'cards-02.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'CARD_SHARD_SHA_OR_SIZE'):
            read_research_cards(self.root)

    def test_naive_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'TIMEZONE_REQUIRED'):
            card_time('2026-11-17T12:00:00')
