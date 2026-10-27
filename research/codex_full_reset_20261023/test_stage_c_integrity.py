"""Synthetic temporal and trial-retention regressions. No historical model runs."""
import unittest
from pathlib import Path
import tempfile
import stage_c_rule_search as c

class Integrity(unittest.TestCase):
    def fixture(self):
        dates=['2023-12-28','2023-12-29','2024-01-02','2024-01-03']
        rows={d:{t:c.Row(d,t,t,100,101,99,100,1000,100000,scores={}) for t in ('2330','2454')} for d in dates}
        config=c.Config('RAW_REVERSAL','NEG_R1',0,1,1,'ALL')
        ranks={(config.score,0,dates[0]):['2330','2454']}
        return dates,rows,config,ranks
    def test_fold_outcomes_must_finish_inside_fold(self):
        dates,rows,config,ranks=self.fixture()
        _,events=c.simulate(config,'2023-01-01','2023-12-31',.012,dates,{d:i for i,d in enumerate(dates)},rows,{d:{'market':{},'sox':None} for d in dates},ranks)
        self.assertEqual(events,[])
    def test_missing_future_of_first_pick_never_selects_second(self):
        dates,rows,config,ranks=self.fixture();rows[dates[1]]['2330'].open=None
        _,events=c.simulate(config,dates[0],dates[-1],.012,dates,{d:i for i,d in enumerate(dates)},rows,{d:{'market':{},'sox':None} for d in dates},ranks)
        self.assertEqual(events,[])
    def test_ledger_append_preserves_prefix_and_failures(self):
        from reset_ledger import TrialLedger
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            with TrialLedger(p,{'run':'synthetic'}) as ledger:
                ledger.append({'record_id':'trial-a','status':'FAILED'})
            first=p.read_bytes()
            with TrialLedger(p,{'run':'synthetic-2'}) as ledger:
                ledger.append({'record_id':'trial-b','status':'REJECTED'})
                with self.assertRaises(ValueError):ledger.append({'record_id':'trial-a','status':'PASS'})
            self.assertTrue(p.read_bytes().startswith(first))
    def test_ledger_tampering_detected(self):
        from reset_ledger import TrialLedger
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            with TrialLedger(p,{}) as ledger: ledger.append({'record_id':'a','status':'FAILED'})
            p.write_text(p.read_text().replace('FAILED','PASSED'))
            with self.assertRaises(ValueError):
                with TrialLedger(p,{}) as ledger:pass
    def test_orphan_trial_is_retained_as_aborted(self):
        from reset_ledger import TrialLedger
        import json
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            with TrialLedger(p,{}) as ledger:ledger.append({'record_id':'a:STARTED','experiment_id':'a','status':'STARTED'})
            prefix=p.read_bytes()
            with TrialLedger(p,{}) as ledger:pass
            self.assertTrue(p.read_bytes().startswith(prefix))
            self.assertEqual(json.loads(p.read_text().splitlines()[-1])['status'],'ABORTED')
    def test_drawdown_includes_intra_trade_close(self):
        event={'exit_date':'2024-01-03','gross_return':.1,'daily_gross_nav':[['2024-01-02',.5],['2024-01-03',1.1]]}
        metrics=c.summarize_events([event],.012)
        self.assertEqual(metrics['max_drawdown'],-.5)
        self.assertEqual(metrics['trade_endpoint_max_drawdown'],0)
    def test_insolvency_never_resurrects_nav(self):
        self.assertEqual(c.product_return([-1.1,-1.1,100]),-1)
    def test_multiple_testing_and_insufficient_blocks(self):
        self.assertEqual(c.quarterly_signflip([])['status'],'INSUFFICIENT_SAMPLE')
        result=c.holm_adjust({'a':{'p_value':.01},'b':{'p_value':.04},'c':{'p_value':.9}})
        self.assertAlmostEqual(result['a']['holm_adjusted_p'],.03)
        self.assertAlmostEqual(result['b']['holm_adjusted_p'],.08)
    def test_synthetic_full_attempt_produces_retained_evidence(self):
        from unittest.mock import patch
        import json
        import sys
        dates,rows,config,ranks=self.fixture()
        context={d:{'market':{},'sox':None} for d in dates}
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'stage_c'
            with patch.object(c,'OUT',out),patch.object(sys,'argv',['search','--mother','synthetic','--mother-receipt','synthetic']),patch.object(c,'validate_mother_receipt',return_value={}),patch.object(c,'verify_pinned_file'),patch.object(c,'verify_mother_membership'),patch.object(c,'load_mother',return_value=(dates,rows)),patch.object(c,'prepare_features',return_value=({},context,{d:i for i,d in enumerate(dates)})),patch.object(c,'build_rank_cache',return_value=ranks),patch.object(c,'configs',return_value=[config]),patch.object(c,'FAMILY_SCORES',{'RAW_REVERSAL':('NEG_R1',)}),patch.object(c,'sha256_file',return_value='0'*64):
                import contextlib,io
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(c.main(),0)
            decisions=list(out.glob('runs/*/WINNER_OR_NO_WINNER.json'))
            self.assertEqual(len(decisions),1)
            self.assertEqual(json.loads(decisions[0].read_text())['status'],'NO_ROBUST_WINNER')
            ledger=[json.loads(x) for x in (out/'EXPERIMENT_LEDGER.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['status']=='NO_TRADE' for x in ledger))
            self.assertEqual(ledger[-1]['status'],'RUN_COMPLETED')
    def test_missing_receipt_never_allows_search(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises((ValueError,RuntimeError,FileNotFoundError)):
                c.validate_mother_receipt(Path(td)/'mother.gz',None)

if __name__=='__main__':unittest.main(argv=[__file__])
