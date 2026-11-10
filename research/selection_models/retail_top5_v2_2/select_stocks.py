"""全基礎合格股 Top 5；研究配對獨立輸出，無交易授權。"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from provenance import (DEFAULT_CONTRACT,DEFAULT_DAILY,DEFAULT_CHIPS,CONTRACT_SHA256,
                        AUTHORITY,load_inputs,code_hashes,compute_lanes)
from strategy import PARAMETERS,TOP_N,BUY_COST

ROOT=Path(__file__).resolve().parent


def select(daily_path,chip_path,decision,output,contract_path=DEFAULT_CONTRACT,mode='research'):
    if mode!='research':
        raise ValueError('OFFICIAL_EVIDENCE_UNAVAILABLE: 未接官方母體、公告及風控證據鏈')
    daily,chips,contract=load_inputs(daily_path,chip_path,contract_path)
    lanes=compute_lanes(daily,chips,decision,contract)
    lane=lanes['14']
    columns=['decision','trade','lag','ticker','control','liquidity','chip_date','r5','r20',
             'retail_delta','control_r5','control_r20','control_delta']
    all_rows=pd.DataFrame(lane['candidates'],columns=columns)
    today=daily[daily.Date.eq(pd.Timestamp(decision))].set_index('Ticker')
    pairs=pd.DataFrame(lane['research_pairs'],columns=columns)
    matched=dict(zip(pairs.ticker,pairs.control))
    all_rows.insert(0,'rank',range(1,len(all_rows)+1))
    all_rows['selected_top5']=all_rows['rank'].le(TOP_N)
    all_rows['control']=all_rows.ticker.map(matched)
    all_rows['reference_close']=all_rows.ticker.map(today.Close)
    all_rows['one_lot_estimated_cost']=(all_rows.reference_close*1000*(1+BUY_COST)).round(2)
    for frame in (all_rows,pairs):
        frame['research_only']=True
        frame['authority']=AUTHORITY
        frame['authorized_lots']=0
    rows=all_rows.head(TOP_N).copy()
    manifest=dict(version='hengce_selection_v2_2',mode='research_selection',authority=AUTHORITY,
                  verification_scope='BUNDLED_REFERENCE_ONLY',official_source_verified=False,
                  contract_sha256=CONTRACT_SHA256,generated_at=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
                  decision=str(pd.Timestamp(decision).date()),chip_date=lane['chip_date'],
                  data_latest=str(daily.Date.max().date()),
                  input_sha256={'daily':contract['daily_sha256'],'chips':contract['chip_sha256']},
                  code_sha256=code_hashes(),price_rows=len(today),
                  qualified_count=len(all_rows),selected_count=len(rows),
                  matched_research_count=len(pairs),parameters=PARAMETERS,
                  candidates=json.loads(rows.to_json(orient='records',date_format='iso')),
                  all_qualified=json.loads(all_rows.to_json(orient='records',date_format='iso')),
                  research_pairs=json.loads(pairs.to_json(orient='records',date_format='iso')))
    # Validate everything before creating any output.
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    rows.to_csv(output/'candidates.csv',index=False,encoding='utf-8-sig')
    all_rows.to_csv(output/'all_qualified.csv',index=False,encoding='utf-8-sig')
    pairs.to_csv(output/'research_pairs.csv',index=False,encoding='utf-8-sig')
    (output/'selection.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text=[f'# 衡策全合格股 Top 5：{manifest["decision"]}', '',
          f'決策日輸入 {len(today)} 檔；基礎條件合格 {len(all_rows)} 檔；Top 5 入選 {len(rows)} 檔。',
          f'研究成功配對 {len(pairs)} 檔，另列research_pairs.csv，不作為入選門檻。',
          f'集保快照 {lane["chip_date"]}，主模型保守延遲14日。', '',
          '|名次|代號|入選Top5|20日漲幅|5日漲幅|兩週小額戶變化|20日成交額中位數|收盤參考價|估計一張成本|',
          '|---|---|---|---|---|---|---|---|---|']
    for r in all_rows.itertuples():
        text.append(f'|{r.rank}|{r.ticker}|{"是" if r.selected_top5 else "否"}|{r.r20:.2%}|{r.r5:.2%}|{r.retail_delta:.2%}|{r.liquidity:,.0f}|{r.reference_close:g}|{r.one_lot_estimated_cost:,.2f}|')
    if rows.empty:
        text.append('\n本次無合格股票，不放寬門檻。')
    text+=['', '排序：20日成交額中位數降冪、代號升冪。沒有因配對失敗排除股票；21日敏感度不混入主名單。',
           '五檔假設資金規則：單檔最多NAV18%，最多5個持倉，保留10%現金；每張1000股，買進成本估0.25%。',
           '買不起一張、已持有或未通過情境條件則零張，不遞補第6、7名、不重新分配餘額。',
           '已核對隨包固定基準的清單與SHA，不等於官方母體、公告時間或公司行動驗證。',
           'RESEARCH_ONLY / NO_TRADING_AUTHORITY。未接正式風控，授權張數固定為0；本表不是今日買進指示。']
    (output/'report.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return manifest


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--daily',type=Path,default=DEFAULT_DAILY)
    cli.add_argument('--weekly',type=Path,default=DEFAULT_CHIPS)
    cli.add_argument('--decision',required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--contract',type=Path,default=DEFAULT_CONTRACT)
    cli.add_argument('--mode',choices=['research','official'],default='research')
    args=cli.parse_args()
    try:
        result=select(args.daily,args.weekly,args.decision,args.output,args.contract,args.mode)
    except (ValueError,KeyError,OSError) as exc:
        cli.exit(2,f'選股失敗：{exc}\n')
    print(f'全合格 {result["qualified_count"]} 檔；Top5 {result["selected_count"]} 檔；研究配對 {result["matched_research_count"]} 檔；報告：{args.output/"report.md"}')


if __name__=='__main__': main()
