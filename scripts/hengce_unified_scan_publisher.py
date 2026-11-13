#!/usr/bin/env python3
"""Publish HENGCE's ONE verified V2.2D/10-lot research report.

This is a receipt consumer, not an alternative estimator. Only a verified
original-checkpoint score receipt can update the ranked report. Incomplete
model/EOD/TDCC input fails closed. Does not run orders or modify vessels.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
INPUT = Path('research/retail_top5/unified_scan/latest.json')
OUTPUT_JSON = Path('research/retail_top5/unified_scan/report_latest.json')
OUTPUT_MD = Path('research/retail_top5/unified_scan/report_latest.md')
MODEL_CLS = 'db47b6f2276150610972d50a8f2b1a9d816eb89fc415d41db5c81b12c1c94a97'
MODEL_REG = '8e6931fa9b4ca4324db3b24feb47312bbcbdb9030388e00ab5e8f2e36b014c06'
SCHEMA = 'HENGCE_UNIFIED_V22D_TWSE_10LOT_RESEARCH_V1'
EXPECTED_STATUS = 'VERIFIED_HISTORICAL_REPLAY_RESEARCH_ONLY'


def read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None


def fmtpct(v, multiple=1):
    return f'{v * multiple:+.2f}%'


def last_verified_eod(root):
    dated=[]
    for p in (root/'eod').glob('20??????/status.json'):
        try:
            d=dt.date.fromisoformat(p.parent.name[:4]+'-'+p.parent.name[4:6]+'-'+p.parent.name[6:8])
        except ValueError:
            continue
        s=read(p)
        if s and s.get('target_date')==d.isoformat() and s.get('status')=='COMPLETE' and s.get('three_leg_complete') is True and s.get('formal_complete_day') is True and s.get('mother_status')=='COMPLETE' and s.get('downstream_ready') is True:
            dated.append((d,s))
    return max(dated,key=lambda z:z[0]) if dated else (None,None)


def validate_rows(source):
    rows=source.get('all_qualified')
    if not isinstance(rows,list) or not rows or len(rows)!=source.get('qualified_count') or len(rows)>3000:
        return False,'INVALID_QUALIFIED_COUNT'
    if source.get('top5') != rows[:5]:
        return False,'TOP5_NOT_MAIN_RANK_SUBSET'
    seen=set(); last_turnover=None; last_ticker=None
    for rank,row in enumerate(rows,1):
        if not isinstance(row,dict) or row.get('rank')!=rank:
            return False,'RANK_NOT_CONTIGUOUS'
        tick=row.get('ticker')
        if not isinstance(tick,str) or len(tick)!=4 or not tick.isdigit() or tick.startswith('91') or tick in seen:
            return False,'DUPLICATE_OR_INVALID_TICKER'
        seen.add(tick)
        for field in ('close','score','ret20','ret5','turnover20_median','retail_holder_week_delta_pct','other_shares_pct'):
            val=row.get(field)
            if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val):
                return False,'MISSING_OR_NONFINITE_'+field
        if not (row['close']>0 and 0.5<=row['score']<=1 and row['ret20']>=0.05 and row['ret5']>=0 and row['turnover20_median']>=10000000 and 0<=row['other_shares_pct']<=100):
            return False,'ORIGINAL_GATE_VIOLATION'
        if row.get('retail_holder_date')!=source.get('source_tdcc_research_overlay'):
            return False,'UNVERIFIED_TDCC_OVERLAY_DATE'
        turnover=row['turnover20_median']
        if last_turnover is not None and (turnover>last_turnover or (turnover==last_turnover and tick<last_ticker)):
            return False,'RANKING_ORDER_VIOLATION'
        last_turnover=turnover;last_ticker=tick
    return True,'PASS'


def build(root, today=None):
    today=today or dt.datetime.now(TZ).date()
    eod_date,eod=last_verified_eod(root)
    base={'schema':'HENGCE_UNIFIED_SCAN_PUBLISHED_REPORT_V1','system':'HENGCE',
          'report_date':eod_date.isoformat() if eod_date else today.isoformat(), 'verified_eod_date':eod_date.isoformat() if eod_date else None,
          'ranked':[], 'exited':[], 'top5':[], 'qualified_count':0,
          'research_only':True,'formal_selection_authority':False,'trading_authority':False,
          'buy_signal':False,'sell_signal':False,'broker_execution':False,
          'authorized_lots':0,'capital_authority_twd':0,
          'output_policy':'ONE_MAIN_REPORT_ONE_RANKING_NO_FALLBACK'}
    def blocked(reason):
        return dict(base,status='RESEARCH_SCAN_BLOCKED',reason=reason,
                    model_updated=False, historical_rankings_not_promoted=True)
    if eod_date is None: return blocked('NO_VERIFIED_CANONICAL_EOD')
    if eod_date>today: return blocked('FUTURE_EOD_DATE')
    if (today-eod_date).days>4: return blocked('STALE_CANONICAL_EOD')
    c=read(root/'hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json')
    if not c or c.get('status')!='NO_ACTIVE_SELECTION_STRATEGY' or c.get('active_strategy_count')!=0 or c.get('broker_order_execution') is not False:
        return blocked('SCAN_ONCE_GOVERNANCE_UNVERIFIED')
    source=read(root/INPUT)
    if not source: return blocked('ORIGINAL_V22D_RECEIPT_MISSING_PRIVATE_CHECKPOINT')
    if source.get('schema')!=SCHEMA or source.get('status')!=EXPECTED_STATUS or source.get('system')!='HENGCE':
        return blocked('MODEL_RECEIPT_SCHEMA_UNVERIFIED')
    if source.get('model_classifier_sha256')!=MODEL_CLS or source.get('model_regressor_sha256')!=MODEL_REG:
        return blocked('MODEL_CHECKPOINT_HASH_MISMATCH')
    if source.get('model_id')!='v22d_daily_nowcast_liquidity_top5_v1':
        return blocked('MODEL_VERSION_MISMATCH')
    try:
        decision=dt.date.fromisoformat(source['decision_date'])
        known=dt.date.fromisoformat(source['source_tdcc_model_asof'])
        overlay=dt.date.fromisoformat(source['source_tdcc_research_overlay'])
    except (KeyError,TypeError,ValueError): return blocked('RECEIPT_DATE_INVALID')
    if decision!=eod_date or source.get('source_price_eod')!=eod_date.isoformat():
        return blocked('ORIGINAL_V22D_NOT_RECOMPUTED_FOR_LATEST_EOD')
    if known>decision-dt.timedelta(days=14):return blocked('TDCC_LOOKAHEAD')
    if overlay>decision: return blocked('TDCC_OVERLAY_FUTURE')
    if source.get('model_first_publication_pit_verified') is not False:
        return blocked('PIT_CERTIFICATION_CLAIM_UNVERIFIED')
    if any(source.get(k) is not False for k in ('formal_strategy_active','buy_signal','sell_signal','broker_order_execution')):
        return blocked('TRADING_AUTHORITY_VIOLATION')
    if eod.get('mother_sha256')!=source.get('source_canonical_mother_sha256'):
        return blocked('CANONICAL_MOTHER_HASH_MISMATCH')
    if source.get('original_eod_receipt')!=f'eod/{eod_date:%Y%m%d}/status.json':
        return blocked('WRONG_EOD_RECEIPT')
    valid,why=validate_rows(source)
    if not valid:return blocked(why)
    exiting=source.get('exited',[])
    if not isinstance(exiting,list) or len(exiting)>3000 or any(x.get('ticker') in {z['ticker'] for z in source['all_qualified']} for x in exiting if isinstance(x,dict)):
        return blocked('INVALID_EXIT_TRACKING')
    if not all(isinstance(x,dict) and isinstance(x.get('ticker'),str) and isinstance(x.get('reason'),str) for x in exiting):
        return blocked('INVALID_EXIT_ROWS')
    # Do not publish a stale HBA model or produce two independent ranked reports.
    result=dict(base,status='RESEARCH_SCAN_READY', reason=None,
                model_updated=True, decision_date=source['decision_date'],
                model_tdcc_date=source['source_tdcc_model_asof'],
                observed_tdcc_overlay_date=source['source_tdcc_research_overlay'],
                twse_only=True, tpex_covered=False,
                friday_shadow_only=source.get('friday_shadow_only') is True,
                model_score_is_stock_return_probability=False,
                rank_rule='20D_MEDIAN_TURNOVER_DESC',
                baseline_781_qualified=source.get('original_781_qualified'),
                ranked=source['all_qualified'],top5=source['top5'],
                qualified_count=len(source['all_qualified']),exited=exiting,
                previous_decision_date=source.get('previous_research_decision_date'),
                input_receipt_sha256=hashlib.sha256((root/INPUT).read_bytes()).hexdigest(),
                original_eod_sha256=eod['mother_sha256'])
    return result


def markdown(out):
    d=out.get('decision_date') or out['verified_eod_date'] or '未知'
    lines=['# 衡策 HENGCE｜唯一主報告', '',f'- 原血管最新完整盤後日：**{d}**',
           f'- 狀態：**{out["status"]}**（研究，非買賣訊號）','']
    if out['status']!='RESEARCH_SCAN_READY':
        lines += [f'- 阻擋原因：`{out["reason"]}`',
                  '- **本次未產生新排名**；既有歷史研究不得冒充目前進場榜單。',
                  '- 原本 EOD、TDCC、S5、Escape、RMS 與下單規則不變。','']
        return '\n'.join(lines)+'\n'
    lines += [f'- V2.2D 原始權重研究合格：**{out["qualified_count"]} 檔**。',
              '- 市場：TWSE 全上市可比母體；上櫃尚未納入。',
              f'- 模型集保截至 {out["model_tdcc_date"]}；研究層 10 張以下持有人集保截至 {out["observed_tdcc_overlay_date"]}。',
              '- 舊 781 檔僅是歷史比較，不另製榜單。','',
              '## 唯一排名','',
              '|名次|代碼|名稱|收盤價|V2.2D|10張以下人數週變動|其他持股占比|',
              '|---:|---|---|---:|---:|---:|---:|']
    for row in out['ranked']:
        lines.append(f'|{row["rank"]}|{row["ticker"]}|{row["name"]}|{row["close"]:.2f}|{row["score"]:.4f}|{fmtpct(row["retail_holder_week_delta_pct"])}|{row["other_shares_pct"]:.2f}%|')
    lines+=['','## 前次入選、本次退出（保留追蹤）','',
            '|代碼|名稱|目前V2.2D分數|退出原因|',
            '|---|---|---:|---|']
    for row in out['exited']:
        lines.append(f'|{row["ticker"]}|{row.get("name") or row["ticker"]}|{row.get("score",float("nan")):.4f}|{row["reason"]}|')
    if not out['exited']: lines.append('|—|本次無退出紀錄|—|—|')
    lines+=['','### 證據範圍',
            f'- 11/13 這份來源是 **{("週五研究影子重算" if out["friday_shadow_only"] else "原 V2.2D 研究重算")}**，未通過完整前瞻首次公告時間戳認證。',
            '- 無下單授權，模型分數不代表股價上漲機率。']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--out-json',type=Path,default=OUTPUT_JSON)
    p.add_argument('--out-md',type=Path,default=OUTPUT_MD)
    p.add_argument('--today',type=dt.date.fromisoformat)
    args=p.parse_args(argv)
    out=build(args.root,args.today)
    (args.root/args.out_json).parent.mkdir(parents=True,exist_ok=True)
    (args.root/args.out_json).write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (args.root/args.out_md).write_text(markdown(out),encoding='utf-8')
    print(json.dumps({'status':out['status'],'reason':out.get('reason'),
                      'decision_date':out.get('decision_date'),
                      'qualified':out.get('qualified_count',0),
                      'exit_count':len(out.get('exited',[]))},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())