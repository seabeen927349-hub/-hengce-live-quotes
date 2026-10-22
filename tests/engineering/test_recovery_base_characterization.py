"""Pinned unsafe behaviors, characterized before Issue #20 production changes.

Only disposable remotes and synthetic bytes; the pinned publisher is immutable.
These tests intentionally establish what the old transport allowed, not what the
new recovery boundary should allow.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_writer_races as races

BASE = '6bb5cb46a8477f2d7edf0310980791c2fb140415'


class RecoveryBaseCharacterization(unittest.TestCase):
    def fixture(self):
        f = races.WriterRaceTests(); f.setUp(); self.addCleanup(f.doCleanups)
        return f

    def legacy(self, f, root):
        path=f.root/'pinned-publisher.py'
        path.write_bytes(subprocess.check_output(['git','-C',str(races.ROOT),'show',BASE+':scripts/hengce_publish.py']))
        return subprocess.run([sys.executable,'-B',str(path),'--repo',str(root),
            '--report-dir',str(f.root/'legacy-reports')],capture_output=True,text=True)

    def test_base_allows_partial_canonical_without_alias_history_or_ledger(self):
        f=self.fixture(); p='hengce/q017_radar/decision/20261022_0901.json'
        f.commit(f.a,{p:'{"synthetic":"partial canonical only"}\n'})
        result=self.legacy(f,f.a)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(f.read_remote(p),'{"synthetic":"partial canonical only"}')

    def test_base_allows_incomplete_e2_state_without_morning_or_display(self):
        f=self.fixture(); p='hengce/e2_live/state_latest.json'
        f.commit(f.a,{p:'{"synthetic":"state write before crash"}\n'})
        result=self.legacy(f,f.a)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(f.read_remote(p),'{"synthetic":"state write before crash"}')

    def test_base_has_no_durable_fence_after_accepted_local_adoption_failure(self):
        f=self.fixture(); path='hengce/e2_live/new_state.json'
        f.commit(f.a,{path:'remote input\n'}); f.publish(f.a)
        f.commit(f.b,{races.PRIMARY:'independent captured evidence\n'})
        collision=f.b/path;collision.parent.mkdir(parents=True,exist_ok=True);collision.write_text('untracked\n')
        # Exact base already fails safely at adoption, but cannot fence a later
        # independent compute process: no durable operational marker exists.
        path=f.root/'pinned-publisher.py'
        path.write_bytes(subprocess.check_output(['git','-C',str(races.ROOT),'show',BASE+':scripts/hengce_publish.py']))
        result=subprocess.run([sys.executable,str(path),'--repo',str(f.b),'--profile','q017-primary-capture',
            '--report-dir',str(f.root/'legacy-reports')],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('ACCEPTED_PUBLICATION_LOCAL_SYNC_FAILED',result.stdout)
        self.assertEqual(f.read_remote(races.PRIMARY),'independent captured evidence')
        self.assertFalse((f.b/'.git/hengce-recovery/active.json').exists())


if __name__=='__main__': unittest.main(verbosity=2)
