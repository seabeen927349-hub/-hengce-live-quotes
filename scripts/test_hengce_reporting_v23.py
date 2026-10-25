#!/usr/bin/env python3
from __future__ import annotations
import unittest
import hengce_three_line_resonance as resonance
import hengce_total_scoreboard as scoreboard

class ReportingV23(unittest.TestCase):
    def q(self, module='Q017_SOX_ELECTRONICS_RADAR_LOCKED', day='2026-10-22'):
        return {'system':'HENGCE','module':module,'trade_date':day,'binding_status':'PASS','market_state':'CASH','authority':'TEST',
                'decision_lock':{'cutoff_label':'09:01'},'top3':[{'ticker':'3055','name':'Q','score':1.0},{'ticker':'7795','score':.9},{'ticker':'3016','score':.8}]}
    def v(self, day='2026-10-22', ticker='3044'):
        return {'status':'PASS','screen':{'signal_date':day,'top3':[{'ticker':ticker,'name':'V','score':.8}]},'schedule':{'today_is_frozen_schedule_signal':False}}
    def w(self, day='2026-10-22', ticker='3481'):
        return {'status':'PASS_RESEARCH_SNAPSHOT','signal_date':day,'top20':[{'rank':1,'ticker':ticker,'name':'W'}],
                'economic_gate_40bp':{'pass':False}}
    def e(self):
        return {'binding_status':'PASS','engine_status':'OFF','action':'OFF','signal_asof':'2026-10-22','top1':{'ticker':'2492','name':'E'}}

    def test_schema5_trade_date_is_accepted_only_as_0901_signal_session(self):
        out=resonance.build(self.q(),self.v(),self.w())
        self.assertEqual(out['signal_date'],'2026-10-22')
        self.assertEqual(out['signal_date_resolution']['q017'],'Q017_SCHEMA5_0901_TRADE_DATE_AS_SIGNAL_SESSION')
        bad=self.q(module='SOME_OTHER_Q017_MODULE')
        with self.assertRaisesRegex(ValueError,'Q017_SIGNAL_DATE_REQUIRED'):
            resonance.build(bad,self.v(),self.w())

    def test_cross_lane_date_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'LANE_SIGNAL_DATE_MISMATCH'):
            resonance.build(self.q(),self.v('2026-10-21'),self.w())

    def test_hard_overlap_survives_topk_only_without_fabricating_soft_percentiles(self):
        out=resonance.build(self.q(),self.v(ticker='3481'),self.w(ticker='3481'))
        self.assertEqual(out['hard_overlap']['count'],1)
        self.assertEqual(out['counts']['S'],1)
        self.assertEqual(out['soft_resonance_status'],'DATA_PENDING_FULL_RANKS')
        self.assertEqual(out['rows'][0]['canonical_gate'],'CASH_BLOCKED')

    def test_scoreboard_ties_and_no_buy(self):
        prices={'3044':{'name':'健鼎','close':556},'2492':{'name':'華新科','close':368},'3055':{'name':'蔚華科','close':143},'3481':{'name':'群創','close':46.75}}
        out=scoreboard.build(self.q(),self.e(),self.v(),self.w(),prices,'2026-10-22')
        self.assertEqual(out['attention_leader']['ticker'],'3044')
        self.assertEqual(out['attention_leader']['score'],12.5)
        tied={r['ticker']:r['rank'] for r in out['top10'] if r['ticker'] in {'2492','3055','3481'}}
        self.assertEqual(len(tied),3)
        self.assertEqual(len(set(tied.values())),1)
        self.assertEqual(out['action_card']['status'],'NO_BUY')
        self.assertIsNone(out['action_card']['buy_price'])
        self.assertIsNone(out['action_card']['sell_price'])

if __name__=='__main__':
    unittest.main(argv=[__file__])
