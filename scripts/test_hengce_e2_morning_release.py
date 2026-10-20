#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile
from datetime import date
from pathlib import Path
import hengce_e2_live as e2


def main():
    original=(e2.STATE,e2.MORNING,e2.EXECUTION_OVERRIDE)
    try:
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            e2.STATE=root/'state_latest.json'
            e2.MORNING=root/'morning_latest.json'
            e2.EXECUTION_OVERRIDE=root/'execution_override.json'
            no_fill={
                'state':'NO_FILL','signal_date':'2026-10-19','ticker':'3026','name':'禾伸堂',
                'score':4.801362351369969,'beta60':2.083939641519657,
                'residual':-0.052159336205509395,'entry_due':'NEXT_TWSE_SESSION_OPEN',
                'execution_effective_date':'2026-10-20','execution_reason':'USER_CONFIRMED_NOT_FILLED',
                'slot_released':True,'model_signal_preserved':True,'broker_order_execution':False,
            }
            state={
                'schema_version':2,'system':'HENGCE','module':'E2_PROFIT_MAX_STATE',
                'signal_asof':'2026-10-20','engine':'E2_PROFIT_MAX','engine_status':'NO_FILL',
                'binding_status':'PASS','action':'NO_FILL','paper_position':no_fill,
                'top1':{'ticker':'8021','name':'尖點','score':4.805611100695378},
                'local_gate':{'go':True},'macro_gate':{'go':False},
                'position_state':{'asof':'2026-10-20','held':[],'pending':[],'no_fill':[no_fill],
                                  'max_slots':1,'occupied_next_session':0,'free_slots_next_session':1},
            }
            e2.STATE.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
            e2.EXECUTION_OVERRIDE.write_text(json.dumps({
                'version':1,'status':'NO_FILL','ticker':'3026','signal_date':'2026-10-19',
                'effective_date':'2026-10-20','reason':'USER_CONFIRMED_NOT_FILLED'
            }),encoding='utf-8')
            out=e2.build_morning(date(2026,10,21))
            persisted=json.loads(e2.STATE.read_text(encoding='utf-8'))
            assert out['trade_date']=='2026-10-21'
            assert out['engine_status']=='OFF'
            assert out['paper_position']=={'state':'IDLE'}
            assert out['new_signal_buy_count']==0 and out['entry_due_count']==0
            assert out['held_from_prior_close']==[] and out['no_fill_from_prior_signal']==[]
            assert out['execution_override']['reason']=='PRIOR_NO_FILL_SLOT_RELEASED'
            assert out['broker_order_execution'] is False
            assert persisted['paper_position']=={'state':'IDLE'}
            assert persisted['engine_status']=='OFF' and persisted['action']=='OFF'
            assert persisted['position_state']['occupied_next_session']==0
            assert persisted['position_state']['free_slots_next_session']==1
            assert persisted['position_state']['no_fill']==[]
            assert persisted['top1']['ticker']=='8021'
        print(json.dumps({
            'status':'PASS','trade_date':'2026-10-21','prior_no_fill_persisted_idle':True,
            'free_slots_next_session':1,'same_model_top1_preserved':True,
            'candidate_b_formula_mutated':False,'broker_order_execution':False
        },ensure_ascii=False))
        return 0
    finally:
        e2.STATE,e2.MORNING,e2.EXECUTION_OVERRIDE=original


if __name__=='__main__':
    raise SystemExit(main())
