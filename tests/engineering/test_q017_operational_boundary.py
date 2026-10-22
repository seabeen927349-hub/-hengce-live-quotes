"""Byte-exact model freeze with only the explicit Issue #20 I/O insertion.

This is not a blanket exception for compute_decision or for a production file.
All original bytes, including that function's original body, remain frozen.
"""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASE='6bb5cb46a8477f2d7edf0310980791c2fb140415'
PATH='scripts/hengce_q017_observation_lock_v5.py'
INSERTIONS=(
    ('import hengce_q017_decision_lock_v4 as v4\n',
     'from hengce_recovery_transaction import current_request\n'),
    ('    today=today or core.now_tw().date();op=obs_path(today)\n',
     "    current_request('q017-recovery','compute',today.isoformat(),core.now_tw())\n"),
    ("    if not op.exists():raise RuntimeError('NO_IMMUTABLE_0901_OBSERVATION')\n",
     "    p=decision_path(today)\n"
     "    if p.exists():\n"
     "        stored=json.loads(p.read_text(encoding='utf-8'))\n"
     "        validate_decision(stored,today)\n"
     "        return stored  # Existing validated immutable decision wins; no rerank or projection repair.\n"),
)


def permitted_source(before):
    after=before
    for anchor,insertion in INSERTIONS:
        if after.count(anchor)!=1:raise ValueError('UNKNOWN_OPERATIONAL_SOURCE_CONTRACT')
        after=after.replace(anchor,anchor+insertion)
    return after


def verify(before,after):
    if after!=before and after!=permitted_source(before):
        raise ValueError('FROZEN_Q017_BYTES_CHANGED_OUTSIDE_EXACT_ISSUE20_IO_INSERTION')


class FrozenQ017OperationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+PATH]).decode()
        cls.allowed=permitted_source(cls.before)

    def test_current_source_has_only_exact_authorized_io_insertion(self):
        verify(self.before,(ROOT/PATH).read_text())

    def test_unchanged_original_and_exact_io_insertion_are_allowed(self):
        verify(self.before,self.before);verify(self.before,self.allowed)

    def test_formula_or_threshold_edit_is_rejected(self):
        for token,replacement in [('score=b*(1+25*max(-res,0))','score=b*(1+26*max(-res,0))'),
                                  ('if res>0.04:continue','if res>0.05:continue')]:
            self.assertIn(token,self.allowed)
            with self.assertRaises(ValueError):verify(self.before,self.allowed.replace(token,replacement))

    def test_any_other_compute_body_change_is_rejected(self):
        token="obs=json.loads(op.read_text(encoding='utf-8'));out=build_decision_from_observation(obs)"
        self.assertIn(token,self.allowed)
        with self.assertRaises(ValueError):verify(self.before,self.allowed.replace(token,token+';out.clear()'))

    def test_widened_admission_or_unvalidated_existing_decision_is_rejected(self):
        for changed in (self.allowed.replace("today.isoformat(),core.now_tw()","'',core.now_tw()"),
                        self.allowed.replace('        validate_decision(stored,today)\n','')):
            with self.assertRaises(ValueError):verify(self.before,changed)


if __name__=='__main__':unittest.main(verbosity=2)
