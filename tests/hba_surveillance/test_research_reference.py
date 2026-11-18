import base64
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from hengce_hba_context_bridge_v1 import card_time
from hengce_hba_research_ledger import canonical, sha
from hengce_hba_research_outcomes import VERSION, load_inputs
from hengce_hba_research_reference import KINDS, OFFICIAL, official_sessions


class OfficialReferenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.key = self.root/'key.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'Ed25519', '-out', str(self.key)], check=True)
        public = subprocess.check_output(['openssl', 'pkey', '-in', str(self.key), '-pubout'], text=True)
        self.day = '2026-11-18'
        self.publication = card_time(self.day+'T16:00:00+08:00')
        self.asof = card_time(self.day+'T17:00:00+08:00')
        origin = 'https://www.twse.com.tw/fixture/'
        policy = {'version': VERSION, 'benchmark': 'TAIEX', 'min_volume_shares': 1000,
                  'cost_bps': dict(buy_fee=10, sell_fee=10, sell_tax=30, slippage_per_side=5)}
        self.trust = {'schema': 'HENGCE_TWSE_REFERENCE_TRUST_V1',
                      'approved_policy_sha256': [sha(canonical(policy))],
                      'collectors': {'approved': {'public_key_pem': public,
                          'valid_from': '2026-01-01T00:00:00+08:00', 'valid_until': '2027-01-01T00:00:00+08:00',
                          'endpoints': {kind: [origin+kind] for kind in KINDS}}}}
        raw, packets = {}, {}
        for kind, claims in zip(KINDS, ({'open': 100, 'close': 101}, {'2610':'TRADABLE'}, {'2610':'NO_ACTION'})):
            blob = canonical({'test_fixture': kind, 'records': claims})
            digest = sha(blob)
            raw[digest] = base64.b64encode(blob).decode()
            receipt = dict(schema=OFFICIAL, publisher='TWSE', dataset=kind, effective_date=self.day,
                           key_id='approved', source=origin+kind+'?date=20261118',
                           announced_at_taipei=self.day+'T14:20:00+08:00',
                           first_observed_at_taipei=self.day+'T14:30:00+08:00',
                           raw_sha256=digest, claims_sha256=sha(canonical(claims)))
            (self.root/'receipt').write_bytes(canonical(receipt))
            sig = subprocess.check_output(['openssl', 'pkeyutl', '-sign', '-rawin',
                                          '-inkey', str(self.key), '-in', str(self.root/'receipt')])
            packets[kind] = dict(receipt=receipt, claims=claims, signature=base64.b64encode(sig).decode())
        self.bundle = dict(schema=OFFICIAL, policy=policy, raw_objects=raw, official_sessions={self.day:packets})

    def test_signed_original_and_claims_bind_all_three_datasets(self):
        data = canonical(self.bundle)
        with patch('hengce_hba_research_outcomes.load_trust', return_value=self.trust):
            _, sessions = load_inputs(data, sha(data), publication=self.publication, asof=self.asof)
        row = sessions[self.day]
        self.assertEqual(row['benchmark']['close'], 101)
        self.assertEqual(row['stocks']['2610']['corporate_action'], 'NONE_VERIFIED')
        self.assertEqual(row['benchmark']['available_at'], self.publication.isoformat())
        self.assertNotEqual(row['stocks']['2610']['sha256'], row['stocks']['2610']['corporate_action_proof']['sha256'])

    def test_raw_missing_or_changed_and_normalized_tampering(self):
        taiex = self.bundle['official_sessions'][self.day]['taiex']
        key = taiex['receipt']['raw_sha256']
        for value in (None, base64.b64encode(b'fake').decode()):
            altered = copy.deepcopy(self.bundle)
            if value is None:
                del altered['raw_objects'][key]
            else:
                altered['raw_objects'][key] = value
            with self.assertRaisesRegex(ValueError, 'RAW_OR_CLAIMS_SHA'):
                official_sessions(altered, self.publication, self.asof, self.trust)
        taiex['claims']['close'] = 999
        with self.assertRaisesRegex(ValueError, 'RAW_OR_CLAIMS_SHA'):
            official_sessions(self.bundle, self.publication, self.asof, self.trust)

    def test_forged_signature_unapproved_host_and_future_availability(self):
        receipt = self.bundle['official_sessions'][self.day]['taiex']['receipt']
        for field, value, error in (
            ('announced_at_taipei', self.day+'T14:21:00+08:00', 'SIGNATURE'),
            ('source', 'https://www.twse.com.tw.example/fixture/taiex', 'SOURCE_UNAPPROVED'),
            ('first_observed_at_taipei', self.day+'T16:30:00+08:00', 'TIME_INVALID'),
            ('key_id', 'self-signed', 'SIGNER_UNTRUSTED'),
        ):
            original = receipt[field]
            receipt[field] = value
            with self.assertRaisesRegex(ValueError, error):
                official_sessions(self.bundle, self.publication, self.asof, self.trust)
            receipt[field] = original
        with self.assertRaisesRegex(ValueError, 'TIME_INVALID'):
            official_sessions(self.bundle, self.publication, card_time(self.day+'T15:00:00+08:00'), self.trust)

    def test_legacy_synthetic_or_incomplete_records_cannot_settle_live(self):
        fake = canonical({'policy':self.bundle['policy'], 'sessions':{}})
        with patch('hengce_hba_research_outcomes.load_trust', return_value=self.trust):
            with self.assertRaisesRegex(ValueError, 'OFFICIAL_REFERENCE_BUNDLE_REQUIRED'):
                load_inputs(fake, sha(fake), publication=self.publication, asof=self.asof)
        del self.bundle['official_sessions'][self.day]['corporate_actions']
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_OFFICIAL_REFERENCE_SET'):
            official_sessions(self.bundle, self.publication, self.asof, self.trust)
        with self.assertRaisesRegex(ValueError, 'NO_APPROVED'):
            official_sessions(self.bundle, self.publication, self.asof, {})

    def test_unapproved_cost_policy_rejected(self):
        self.bundle['policy']['cost_bps']['sell_tax'] = 0
        with self.assertRaisesRegex(ValueError, 'UNAPPROVED_SETTLEMENT_POLICY'):
            official_sessions(self.bundle, self.publication, self.asof, self.trust)
