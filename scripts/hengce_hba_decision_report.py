#!/usr/bin/env python3
"""Existing HBA research-only decision report: two real-share groups, prices, and falsifiers.

Consumes ONLY the existing original HBA + integrated sidecar and the verified original
EOD 3-leg price vessel. No provider calls, alternative data pipe, order, portfolio,
capital, formal strategy selection, or live quote fabrication.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

VERSION = 'HENGCE_HBA_RESEARCH_DECISION_V1_20261110'
VALID_STAGES = ('行情確認（待人工評估）','準備監控','疑似症狀','撤退警戒')
ROLE = 'DESCRIPTIVE_HUMAN_REVIEW_ONLY_NO_SELECTION_OR_TRADING'
ORDER = {
    '風險優先覆核':0,
    '優先人工追蹤':1,
    '等待價格確認':2,
    '一般研究觀察':3,
    '兩方資料缺失':4,
}

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None

def digest_file(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None

def fnum(v):
    if isinstance(v,bool):return None
    try:
        n=float(v)
        return n if n==n and abs(n)<float('inf') else None
    except (ValueError,TypeError,OverflowError):return None

def original_eod_closes(root, day):
    """Original verified EOD prices only. Never derive 'live' data from yesterday."""
    if not isinstance(day,str):
        return {}
    path=root/'eod'/day.replace('-','')
    status=read_json(path/'status.json') or {}
    if not (status.get('formal_complete_day') is True and
            status.get('downstream_ready') is True and
            all(status.get(k+'_date')==day for k in ('price','institutional','margin'))):
        return {}
    files=sorted(path.glob('price_*.csv'))
    if not files:return {}
    prices={}
    try:
        for file in files:
            with file.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f)
                if not {'Date','Ticker','Name','Close'}.issubset(reader.fieldnames or ()):
                    return {}
                for row in reader:
                    ticker=str(row.get('Ticker') or '')
                    # Keep every original EOD row accounted for; silently
                    # dropping malformed or duplicate rows would mask defects.
                    if row.get('Date')!=day or len(ticker)!=4 or not ticker.isdigit() or ticker in prices:
                        return {}
                    close_text=str(row.get('Close') or '').strip().replace(',','')
                    close=fnum(close_text)
                    if close is None or close<=0:
                        # '--' OHLC means that the original official row has no
                        # regular-session close (e.g. 1538/2314 on 2026-11-10).
                        # Record missing as null; never use the previous close,
                        # quote, zero, or a fabricated EOD price.
                        if (close_text!='--'
                            or not {'Open','High','Low'}.issubset(reader.fieldnames or ())
                            or any(str(row.get(k) or '').strip()!='--'
                                   for k in ('Open','High','Low'))):
                            return {}
                        close=None
                    prices[ticker]={'name':row.get('Name') or ticker,'close':close}
    except (OSError,UnicodeError,csv.Error):
        return {}
    count=status.get('price_rows')
    if isinstance(count,int) and len(prices)!=count:
        return {}  # Original row count must still match, including no-close rows.
    if not any(x['close'] is not None for x in prices.values()):
        return {}  # The whole market cannot be interpreted without any real close.
    return prices

def build(root, original, integrated, raw_hba_hash=None, raw_integrated_hash=None):
    out={'schema':VERSION,'authority':{
            'active_selection_strategy_count':0,'formal_selection':False,
            'ranking':False,'signal':False,'trading':False,
            'broker_execution':False,'capital_twd':0},
         'research_role':ROLE,'status':'BLOCKED',
         'target_tw_date':original.get('target_tw_date') if isinstance(original,dict) else None,
         'observed_eod_date':original.get('latest_verified_eod') if isinstance(original,dict) else None,
         'input_sha256':{'original_hba':raw_hba_hash,'integrated_hba':raw_integrated_hash},
         'not_live_quotes':True,'price_reference':'LATEST_VERIFIED_ORIGINAL_EOD_ONLY',
         'not_buy_or_sell_advice':True,
         'full_market_observations':[],
         'human_review_examples':[],
         'research_summary':{},
         'missing_data':[],
         'evidence_scope':'REFERENCE_WEEK_AND_EOD_DESCRIPTIVE_ONLY',
         'invalidations_are_review_checks_not_tested_stop_prices':True,
         'historical_alpha_validated':False,
         'historical_A_B_full_cycle_today_verified':False,
         'decision_notes':[
           '觀察方向不是買進或賣出訊號；不能以昨日收盤價冒充今日盤中價格',
           '集保1至3級距的人數與實際股數需分別看，持股級距不是交易人身份',
           '一週價格與持股配對無法證實操作者意圖、買賣獲利、完整多年循環',
           '歷史MOM20及S5/三法人閘門曾在2024–2025失效；未證明這組描述性分類有超額報酬',
           '缺正式SOX/VIX、S5、Escape時保留未知，不可自行填中性']}
    if raw_hba_hash is None or raw_integrated_hash is None:
        out['missing_data'].append('原始報告SHA256缺失')
        return out
    if not isinstance(original,dict) or not isinstance(integrated,dict):
        out['missing_data'].append('原HBA或整合報告不存在／不可解析');return out
    d=out['observed_eod_date']
    target=out['target_tw_date']
    if not isinstance(d,str) or not isinstance(target,str) or d>target or \
       original.get('data_gate')=='BLOCKED' or integrated.get('readiness')!='RESEARCH_READY' or \
       integrated.get('observed_eod_date')!=d or integrated.get('target_tw_date')!=target:
        out['missing_data'].append('EOD/整合報告日期不一致、未通過資料閘門或尚未完成');return out
    try:
        age=(date.fromisoformat(target)-date.fromisoformat(d)).days
        if age<0 or age>5:
            out['missing_data'].append('正式EOD超過5日或日期在未來')
            return out
    except ValueError:
        out['missing_data'].append('交易日期無法解析')
        return out
    contract=read_json(root/'hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json') or {}
    if contract.get('status')!='NO_ACTIVE_SELECTION_STRATEGY' or \
       contract.get('active_strategy_count')!=0 or contract.get('broker_order_execution') is not False:
        out['missing_data'].append('正式選股停用契約未核實；不得輸出研究建議');return out
    if integrated.get('authority',{}).get('new_selection') is not False or \
       integrated.get('authority',{}).get('trade') is not False:
        out['missing_data'].append('整合報告權限異常');return out
    tg=integrated.get('two_group_research') or {}
    registry=integrated.get('two_group_market_registry') or []
    if tg.get('status')!='VERIFIED_TWO_GROUP_RESEARCH' or \
       (tg.get('price_pair') or {}).get('status')!='VERIFIED_REFERENCE_WEEK_PRICES' or \
       tg.get('historical_13week_continuity_verified') is not False or \
       tg.get('multiweek_a_to_b_cycle_validated') is not False or \
       not isinstance(registry,list) or len(registry)!=tg.get('market_registry_total') or not registry:
        out['missing_data'].append('兩方實股／對齊價格未核驗或完整多年階段聲稱不合格');return out
    snaps=(tg.get('previous_tdcc_date'),tg.get('last_tdcc_date'))
    pair=tg.get('price_pair') or {}
    if (pair.get('first_eod_date'),pair.get('last_eod_date'))!=snaps:
        out['missing_data'].append('集保與價格的週日期不一致');return out
    prices=original_eod_closes(root,d)
    if not prices:
        out['missing_data'].append('正式EOD價格來源缺失、不完整或未核驗');return out
    # All 1,082 matched names receive a research description, regardless of
    # their membership in the old HBA 307-alert short-window list.
    old=original.get('all_candidates')
    if not isinstance(old,list) or len(old)!=original.get('total_candidates_before_limit'):
        out['missing_data'].append('原HBA完整警報名單缺失，不能只用前15檔替代');return out
    hba={str(x.get('ticker')):x for x in old if isinstance(x,dict)}
    if len(hba)!=len(old):
        out['missing_data'].append('原HBA有重複或非法股票代碼');return out
    if any(x.get('stage') not in VALID_STAGES for x in hba.values()):
        out['missing_data'].append('HBA分層未知，不得自訂強弱等級');return out
    seen=set()
    examples=[]
    group=Counter()
    for x in registry:
        if not isinstance(x,dict):continue
        ticker=str(x.get('ticker'))
        if ticker in seen or ticker not in prices:
            out['missing_data'].append('兩方逐股資料重複或EOD股票缺漏');return {**out,'full_market_observations':[]}
        seen.add(ticker)
        small=fnum(x.get('small_shares_delta'))
        other=fnum(x.get('other_shares_delta'))
        p=fnum(x.get('same_week_price_return_pct'))
        pp=fnum(x.get('small_share_delta_pp'))
        if small is None or other is None or pp is None:
            out['missing_data'].append('兩方實股數值遺漏');return {**out,'full_market_observations':[]}
        # Relative share percentages can be complementary even if absolute totals
        # vary slightly. Never misstate the absolute flows as zero-sum when not so.
        info=hba.get(ticker) or {}
        stage=info.get('stage')
        today=fnum(info.get('day_return_pct'))
        five=fnum(info.get('five_day_return_pct'))
        margin=fnum(info.get('margin_change5_pct'))
        pattern=x.get('same_week_price_ownership_pattern')
        descriptive={
          'UP_OTHER_SHARE_GAIN':'上漲時其他持有人占比增加',
          'UP_SMALL_SHARE_GAIN':'上漲時散戶占比增加',
          'DOWN_SMALL_SHARE_GAIN':'下跌時散戶占比增加',
          'DOWN_OTHER_SHARE_GAIN':'下跌時其他持有人占比增加',
          'FLAT_OR_UNCLASSIFIED':'價籌方向未明確分類',
          'PRICE_PAIR_MISSING':'同週價格不足'}
        if pattern not in descriptive:
            out['missing_data'].append('未知的同週價籌分類');return {**out,'full_market_observations':[]}
        # These are editorial HUMAN-REVIEW categories, not fitted alphas,
        # probabilities, formal selection ranks or enter/exit thresholds.
        if prices[ticker]['close'] is None:
            group_name='兩方資料缺失'  # Preserve observation, suppress price conclusions.
        elif stage=='撤退警戒':
            group_name='風險優先覆核'
        elif stage=='行情確認（待人工評估）':
            if (margin is not None and margin>=20) or (five is not None and five>=20):
                group_name='風險優先覆核'
            elif pattern=='DOWN_OTHER_SHARE_GAIN' and today is not None and today>0:
                group_name='優先人工追蹤'
            else:
                group_name='等待價格確認'
        elif stage=='準備監控':
            group_name='一般研究觀察'
        else:
            group_name='一般研究觀察' if pattern!='PRICE_PAIR_MISSING' else '兩方資料缺失'
        rationale=[descriptive[pattern]]
        if p is not None:rationale.append('同週股價%+.2f%%'%p)
        rationale.append('散戶實股%+d股、其他實股%+d股'%(int(small),int(other)))
        if info:
            rationale.append('原HBA：'+stage)
        if today is not None:rationale.append('最新EOD單日%+.2f%%'%today)
        risk=[]
        if prices[ticker]['close'] is None:
            risk.append('最新正式EOD無有效收盤價，暫停本股價格推論')
        if stage=='撤退警戒':risk.append('原HBA撤退警戒，僅為研究風險旗標')
        if margin is not None and margin>=12:risk.append('近5日融資增加%.1f%%，須覆核追價及槓桿'%margin)
        if five is not None and five>=20:risk.append('近5日股價已大漲%.1f%%，須避免把已發生行情當成未來保證'%five)
        if pattern=='UP_SMALL_SHARE_GAIN':risk.append('上漲伴隨散戶增持，但不得機械視為利空或排除買進')
        if pattern=='DOWN_SMALL_SHARE_GAIN':risk.append('下跌伴隨散戶承接，需看後續價格是否恢復')
        if pattern=='DOWN_OTHER_SHARE_GAIN':risk.append('下跌時其他持有人增持，不等於已證明止跌')
        if pattern=='PRICE_PAIR_MISSING':risk.append('同週配對價格缺失')
        if not info:risk.append('原HBA未納入短期警報，不代表沒有未觀測風險')
        if not risk:risk.append('單週持股不能證明資金長期階段或下一週漲跌')
        if small and fnum(x.get('small_holders_delta')) is not None and \
           small*fnum(x.get('small_holders_delta'))<0:
            risk.append('散戶人數與股數方向相反，不得用人數代替實股')
        # Contradiction checks are evidence instructions, never stop orders.
        price_review=(
            '下次正式EOD：以%s收盤%.2f元作強弱觀察基準；突破或跌破都需重新評估，非停損指令'%(d,prices[ticker]['close'])
            if prices[ticker]['close'] is not None else
            '下次正式EOD：%s缺少有效收盤價，先確認首次可驗證新價格，禁止使用零值或昨收代替'%d
        )
        falsifiers=[
          price_review,
          '下次已公布TDCC：核對散戶與其他實股是否維持原方向；若反向需重估',
          '股本發生顯著變化／來源時滯不合格：撤銷價籌可比判斷']
        # Save concise evidence for every ticker: no duplicated prose causing
        # original GitHub report to exceed the normal 1MB contents API limit.
        row={'ticker':ticker,'name':prices[ticker]['name'],
             'review_group':group_name,'hba_stage':stage,
             'last_verified_eod':d,'latest_eod_close':prices[ticker]['close'],
             'same_week_tdcc_price_pct':p,'same_week_pattern':pattern,
             'small_shares_delta':int(small),'other_shares_delta':int(other),
             'small_holders_delta':int(fnum(x.get('small_holders_delta')) or 0),
             'small_share_delta_pp':round(pp,6),
             'eod_day_return_pct':today,'eod_5day_return_pct':five,
             'margin_5day_change_pct':margin}
        out['full_market_observations'].append(row)
        # Narrative evidence is rendered only for the finite audit/display
        # examples; complete compact data still survives for every ticker.
        if stage in ('行情確認（待人工評估）','撤退警戒'):
            narrative=dict(row, why='；'.join(rationale),
                           risks='；'.join(risk),
                           change_of_view='；'.join(falsifiers),
                           authority='RESEARCH_ONLY')
            examples.append(narrative)
        group[group_name]+=1
    if len(out['full_market_observations'])!=tg.get('comparable_stock_count'):
        out['missing_data'].append('全市場與集保可比數量不一致')
        out['full_market_observations']=[]
        return out
    # Display is editorial only: all registered stocks are retained, no scoring,
    # fitted weighting, probability, recommended order, or "top" buy list.
    # Always surface ALL of the original four high-attention alerts before the
    # risk-watch examples, so an 87-name exit-watch queue cannot drown them out.
    attention=sorted((x for x in examples if x['hba_stage']=='行情確認（待人工評估）'),
                     key=lambda x:(ORDER.get(x['review_group'],9),x['ticker']))
    risk_watch=sorted((x for x in examples if x['hba_stage']=='撤退警戒'),
                      key=lambda x:x['ticker'])
    out['human_review_examples']=(attention[:6]+risk_watch[:6])[:12]
    out['research_summary']={
       'market_covered':len(out['full_market_observations']),
       'hba_all_candidate_count':len(hba),
       'human_review_examples_count':len(out['human_review_examples']),
       'groups':dict(group),
       'two_group_categories':tg.get('categories'),
       'reference_tdcc_weeks':list(snaps),
       'first_observed_taipei':tg.get('first_observed_taipei'),
       'price_pair':pair.get('status'),
       'macro':(integrated.get('market_environment') or {}).get('overseas',{}).get('status','UNKNOWN'),
       's5':(integrated.get('market_environment') or {}).get('s5',{}).get('status','UNKNOWN'),
       'escape':(integrated.get('market_environment') or {}).get('escape',{}).get('status','UNKNOWN')}
    out['status']='RESEARCH_ADVISORY_READY'
    return out

def markdown(obj):
    date_str=obj.get('target_tw_date') or '日期不明'
    day=obj.get('observed_eod_date') or '未知'
    lines=['# 衡策｜固定決策研究報告｜'+date_str,
       '', '**正式選股器：0套；沒有買賣訊號、下單或投資組合指令。**',
       '',f'資料依據：正式EOD {day}；集保最近兩週必須有原始憑證；最新收盤價不是盤中即時價。',
       '',f"研究報告狀態：**{obj.get('status')}**。此報告只提供人工研究優先度，沒有交易績效驗證。"]
    if obj['status']!='RESEARCH_ADVISORY_READY':
        lines += ['','資料未通過：'+('；'.join(obj['missing_data']) or '未知原因'),
                  '缺證據不填入「中性」、不建立候選名單。']
        return '\n'.join(lines)+'\n'
    z=obj['research_summary']
    lines.extend(['', '## 全市場研究覆蓋',
      f"- 兩方實股可比 {z['market_covered']:,} 檔；原HBA完整監測 {z['hba_all_candidate_count']:,} 檔",
      f"- 集保對照：{z['reference_tdcc_weeks'][0]} → {z['reference_tdcc_weeks'][1]}，最早可用收件時間 {z['first_observed_taipei']}",
      f"- SOX/VIX：{z['macro']}；S5：{z['s5']}；Escape：{z['escape']}（資料缺失不得冒充正式市場環境）",
      '- 週分類不是整段資金循環；不能以散戶增持作自動禁買，也不能用其他增持作自動買進。',
      '', '## 研究覆核分組（不是選股排名）'])
    for g,n in z['groups'].items():
        lines.append(f'- {g}：{n:,} 檔')
    lines.extend(['','## 優先人工覆核案例（僅由既有HBA明顯警報選出，非全市場最佳投資排名）'])
    for row in obj['human_review_examples']:
        close_display=(f"{row['latest_eod_close']:.2f}元"
                       if row['latest_eod_close'] is not None else '缺有效收盤價')
        lines.extend(['',f"### {row['ticker']} {row['name']}｜{row['review_group']}",
          f"- 最新**正式EOD**收盤：{close_display}（{row['last_verified_eod']}），不是盤中報價",
          '- 理由：'+row['why'],
          '- 風險及反證：'+row['risks'],
          '- 何時重估：'+row['change_of_view']])
    lines.extend(['','## 研究限度與下次掃描',
       '- 每次只使用已發布且校驗通過的 EOD／TDCC；任何股價觀察價位都不是已驗證的停損。',
       '- 僅能從同週價格與兩方持股觀察分布；未通過多年A/B事件級、成交可得性與前瞻獲利驗證。',
       '- 完整逐股研究項目與正反證存於同流程 decision_latest.json，可依股票查詢。',
       '- 本份研究建議不修改原HBA分層、S5、Escape、RMS、MOM20或已退役策略。'])
    return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path('.'))
    ap.add_argument('--original',default='research/hba_surveillance/latest.json')
    ap.add_argument('--integrated',default='research/hba_surveillance/integrated_latest.json')
    ap.add_argument('--out',default='research/hba_surveillance/decision_latest.json')
    x=ap.parse_args()
    original_path=x.root/x.original
    integrated_path=x.root/x.integrated
    obj=build(x.root,read_json(original_path),read_json(integrated_path),
              digest_file(original_path),digest_file(integrated_path))
    out=x.root/x.out
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,
                              separators=(',',':'))+'\n',encoding='utf-8')
    out.with_suffix('.md').write_text(markdown(obj),encoding='utf-8')
    print(json.dumps({'status':obj['status'],'date':obj['observed_eod_date'],
      'market_covered':obj['research_summary'].get('market_covered',0),
      'examples':len(obj['human_review_examples']),
      'bytes':out.stat().st_size},ensure_ascii=False))
    return 0 if obj['status']=='RESEARCH_ADVISORY_READY' else 2

if __name__=='__main__':
    raise SystemExit(main())
