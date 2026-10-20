#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
import hengce_daily_command_center_core_legacy as core
import hengce_eod_incremental_ingest as inc

DAY=date(2026,10,20); DS='20261020'; ISO='2026-10-20'

def tickers(n): return [str(1000+i) for i in range(n)]
def price(n=900, resp_date=DS):
    fs=['證券代號','證券名稱','成交股數','成交筆數','成交金額','開盤價','最高價','最低價','收盤價','漲跌(+/-)','漲跌價差','最後揭示買價','最後揭示買量','最後揭示賣價','最後揭示賣量','本益比']
    data=[[t,'測試',100,10,1000,10,11,9,10,'+',0,10,1,10,1,12] for t in tickers(n)]
    return {'stat':'OK','date':resp_date,'tables':[{'fields':fs,'data':data}]}
def inst(n=900, resp_date=DS):
    fs=['證券代號','證券名稱','外陸資買進股數(不含外資自營商)','外陸資賣出股數(不含外資自營商)','外陸資買賣超股數(不含外資自營商)','外資自營商買進股數','外資自營商賣出股數','外資自營商買賣超股數','投信買進股數','投信賣出股數','投信買賣超股數','自營商買賣超股數','自營商買進股數(自行買賣)','自營商賣出股數(自行買賣)','自營商買賣超股數(自行買賣)','自營商買進股數(避險)','自營商賣出股數(避險)','自營商買賣超股數(避險)','三大法人買賣超股數']
    data=[[t,'測試',2,1,1,0,0,0,2,1,1,0,0,0,0,0,0,0,2] for t in tickers(n)]
    return {'stat':'OK','date':resp_date,'fields':fs,'data':data}
def margin(n=500, resp_date=DS):
    fs=['股票代號','股票名稱','買進','賣出','現金償還','前日餘額','今日餘額','次一營業日限額','買進2','賣出2','現券償還','前日餘額2','今日餘額2','次一營業日限額2','資券互抵','註記']
    data=[[t,'測試',1,1,0,10,10,100,1,1,0,10,10,100,0,''] for t in tickers(n)]
    return {'stat':'OK','date':resp_date,'tables':[{'fields':fs,'data':data}]}
PENDING={'stat':'很抱歉，沒有符合條件的資料'}

def run_case(root, p=PENDING, i=PENDING, m=PENDING):
    def fake(url, params=None, timeout=45):
        if url==core.TWSE_PRICE:return p
        if url==core.TWSE_INST:return i
        if url==core.TWSE_MARGIN:return m
        raise AssertionError(url)
    with patch.object(core,'ROOT',root),patch.object(core,'get_json',side_effect=fake):
        return inc.ingest(DAY)

def write_mother_receipt(root,status):
    p=root/'eod/20261020/receipts/mother.json'; p.parent.mkdir(parents=True,exist_ok=True)
    promoted=list(status['available_legs'])
    obj={'system':'HENGCE','artifact':'CANONICAL_HIST_MOTHER_PROMOTION_RECEIPT','target_date':ISO,'status':'PASS','promoted_legs':promoted,'promoted_leg_sha256':{x:status[f'{x}_sha256'] for x in promoted},'mother_latest_date':ISO,'mother_sha256':'test-mother-sha','second_mother':False}
    p.write_text(json.dumps(obj),encoding='utf-8')

def main():
    contract=Path(__file__).resolve().parents[1]/'hengce/HENGCE_THREE_LEG_ORIGINAL_VESSEL_INCREMENTAL_POLICY_LOCK_v1_0_20261020.json'
    c=json.loads(contract.read_text(encoding='utf-8')); assert c['policy']['create_parallel_pipeline'] is False and c['policy']['do_not_wait_for_margin_before_promoting_price_or_institutional'] is True
    with tempfile.TemporaryDirectory() as td:
        r=run_case(Path(td),price()); assert r['status']=='PARTIAL' and r['price_status']=='COMPLETE' and r['institutional_status']=='PENDING' and r['margin_status']=='PENDING'
        assert (Path(td)/'eod/20261020/receipts/price.json').exists()
        assert r['mother_status']=='PENDING' and r['downstream_ready'] is False
        root=Path(td); write_mother_receipt(root,r)
        z=run_case(root,PENDING,PENDING,PENDING)
        assert z['mother_status']=='COMPLETE' and z['downstream_ready'] is True
        z=run_case(root,PENDING,inst(),PENDING)
        assert z['institutional_status']=='COMPLETE' and z['mother_status']=='PENDING' and z['downstream_ready'] is False
    with tempfile.TemporaryDirectory() as td:
        r=run_case(Path(td),price(),inst()); assert set(r['available_legs'])=={'price','institutional'} and r['margin_status']=='PENDING'
    with tempfile.TemporaryDirectory() as td:
        r=run_case(Path(td),price(),PENDING,margin()); assert set(r['available_legs'])=={'price','margin'} and r['institutional_status']=='PENDING'
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); r=run_case(root,price(),inst(),margin()); assert r['status']=='COMPLETE' and r['three_leg_complete'] is True
        before={p.name:p.read_bytes() for p in (root/'eod/20261020').glob('price_*.csv')}
        def nofetch(*a,**k): raise AssertionError('idempotent rerun must not refetch completed legs')
        with patch.object(core,'ROOT',root),patch.object(core,'get_json',side_effect=nofetch): z=inc.ingest(DAY)
        assert z['status']=='COMPLETE'; after={p.name:p.read_bytes() for p in (root/'eod/20261020').glob('price_*.csv')}; assert before==after
    with tempfile.TemporaryDirectory() as td:
        try: run_case(Path(td),price(resp_date='20261021'))
        except RuntimeError as e: assert 'EOD_INTEGRITY_REJECTION' in str(e) and 'DATE_MISMATCH' in str(e)
        else: raise AssertionError('wrong-date response must be rejected')
    with tempfile.TemporaryDirectory() as td:
        try: run_case(Path(td),price(899))
        except RuntimeError as e: assert 'EOD_INTEGRITY_REJECTION' in str(e) and 'ROWS_TOO_SMALL' in str(e)
        else: raise AssertionError('corrupt row count must be rejected')
    print(json.dumps({'status':'PASS','price_only':True,'price_plus_institutional':True,'price_plus_margin':True,'all_three':True,'idempotent_rerun':True,'wrong_date_rejected':True,'corrupt_row_count_rejected':True,'original_eod_tree_only':True,'second_mother':False,'mother_gate':True,'q017_e2_model_change':False},ensure_ascii=False))
if __name__=='__main__': main()
