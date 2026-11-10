"""Replay-verified research ranking. Authorized lots are always zero.

--simulate adds a separate, explicitly hypothetical whole-lot budget scenario.
CSV PASS text is a scenario input, never evidence of formal RMS/S5/Escape approval.
"""
import argparse
import csv
import json
import math
from pathlib import Path

from provenance import (AUTHORITY, DEFAULT_DAILY, DEFAULT_CHIPS, DEFAULT_CONTRACT,
                        verify_record)

from strategy import BUY_COST, TOP_N, MAX_POSITIONS, POSITION_CAP, CASH_RESERVE


def require_number(v, name, positive=False):
    if isinstance(v,bool):
        raise ValueError(f'Invalid {name}: boolean')
    try:
        n=float(v)
    except (ValueError,TypeError):
        raise ValueError(f'Invalid {name}: {v!r}')
    if not math.isfinite(n) or (positive and n<=0):
        raise ValueError(f'Invalid {name}: {v!r}')
    return n


def read_csv_by_ticker(path):
    if not path:
        return {}
    with open(path,encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if not rows or 'ticker' not in rows[0]:
        raise ValueError(f'CSV needs ticker column: {path}')
    result={}
    for row in rows:
        ticker=(row.get('ticker') or '').strip()
        if not ticker or ticker in result:
            raise ValueError(f'Empty/duplicate ticker: {ticker!r}')
        row['ticker']=ticker
        result[ticker]=row
    return result


def ok_gate(row):
    """Untrusted scenario input only. Never use as an authorization check."""
    return bool(row) and all(str(row.get(k,'')).strip().upper()=='PASS'
                            for k in ['rms','s5','escape','account_eligible','tradable'])


def account_state(acct):
    nav=require_number(acct['nav'],'nav',True)
    cash=require_number(acct['cash'],'cash')
    if not 0<=cash<=nav:
        raise ValueError('cash out of range')
    held=acct.get('held_tickers',[])
    if not isinstance(held,list) or any(not isinstance(t,str) or not t.strip() for t in held):
        raise ValueError('held_tickers must be a list of nonempty strings')
    positions={t.strip() for t in held}
    if len(positions)!=len(held) or len(positions)>MAX_POSITIONS:
        raise ValueError('duplicate holdings or more than five positions')
    values=acct.get('position_market_values',{})
    if not isinstance(values,dict) or set(values)!=positions:
        return nav,cash,positions,'持倉市值未完整對應，停止資金模擬'
    values={t:require_number(v,f'position {t}',True) for t,v in values.items()}
    if abs(cash+sum(values.values())-nav)>.01:
        return nav,cash,positions,'現金加持倉市值與NAV不符，停止資金模擬'
    if any(v>POSITION_CAP*nav for v in values.values()):
        return nav,cash,positions,'既有持倉超過18%集中度，停止新增模擬'
    return nav,cash,positions,''


def run(frozen, prices, acct, risk, lag=14, now=None, *, daily=DEFAULT_DAILY,
        weekly=DEFAULT_CHIPS, contract=DEFAULT_CONTRACT, simulate=False):
    if lag!=14:
        raise ValueError('Main model only uses lag 14; never merge lag 21')
    # No positive quantity path exists before or after this verification.
    lanes=verify_record(frozen,daily,weekly,contract)
    rows=lanes['14']['candidates'][:TOP_N]
    decision=frozen['decision']
    nav,cash,positions,account_issue=account_state(acct)
    price_rows,risk_rows=read_csv_by_ticker(prices),read_csv_by_ticker(risk)
    rem_cash,occupied=cash,len(positions)
    output=[]
    for rank,c in enumerate(rows,1):
        ticker=str(c['ticker'])
        p,gates=price_rows.get(ticker,{}),risk_rows.get(ticker,{})
        lots=0
        reference_price=p.get('reference_price','')
        scenario='未啟用假設資金模擬'
        if simulate:
            if not p:
                scenario='缺少價格'
            else:
                price=require_number(reference_price,'reference_price',True)
                if account_issue:
                    scenario=account_issue
                elif ticker in positions:
                    scenario='已持有，不追買'
                elif p.get('as_of')!=decision or gates.get('as_of')!=decision or acct.get('as_of')!=decision:
                    scenario='價格/情境風控/帳戶日期未對應決策日'
                elif not ok_gate(gates):
                    scenario='情境輸入並非全PASS（不是正式風控認證）'
                elif occupied>=MAX_POSITIONS:
                    scenario='已達最多5檔'
                else:
                    unit=price*1000*(1+BUY_COST)
                    lots=math.floor(min(POSITION_CAP*nav,max(0,rem_cash-CASH_RESERVE*nav))/unit)
                    if lots:
                        rem_cash-=lots*unit
                        occupied+=1
                        scenario='假設資金試算，無交易授權'
                    else:
                        scenario='整張成本或現金限制'
        output.append(dict(decision=decision,research_only=True,authority=AUTHORITY,
                           rank=rank,ticker=ticker,reference_price=reference_price,
                           r20_pct=round(100*c['r20'],3),r5_pct=round(100*c['r5'],3),
                           retail_people_2week_pct=round(100*c['retail_delta'],3),
                           median_20d_turnover=round(c['liquidity']),reference_control=next((p['control'] for p in lanes['14']['research_pairs'] if p['ticker']==ticker),''),
                           lots_for_manual_review=0,authorized_lots=0,gate_all_pass=False,
                           authorization_status='OFFICIAL_EVIDENCE_UNAVAILABLE',
                           input_gate_all_pass=ok_gate(gates),simulation_lots=lots,
                           simulation_enabled=simulate,simulation_status=scenario,
                           status='缺正式來源及RMS/S5/Escape證據鏈；授權張數固定為0'))
    return output


FIELDS=['decision','research_only','authority','rank','ticker','reference_price','r20_pct','r5_pct',
        'retail_people_2week_pct','median_20d_turnover','reference_control',
        'lots_for_manual_review','authorized_lots','gate_all_pass','authorization_status',
        'input_gate_all_pass','simulation_lots','simulation_enabled','simulation_status','status']


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ['freeze','prices','account','risk','output']:
        cli.add_argument('--'+name,required=True,type=Path)
    cli.add_argument('--daily',type=Path,default=DEFAULT_DAILY)
    cli.add_argument('--weekly',type=Path,default=DEFAULT_CHIPS)
    cli.add_argument('--contract',type=Path,default=DEFAULT_CONTRACT)
    cli.add_argument('--lag',type=int,default=14)
    cli.add_argument('--simulate',action='store_true',help='僅額外輸出simulation_lots，授權張數仍為0')
    args=cli.parse_args()
    try:
        frozen=json.loads(args.freeze.read_text(encoding='utf-8'))
        account=json.loads(args.account.read_text(encoding='utf-8'))
        out=run(frozen,args.prices,account,args.risk,args.lag,daily=args.daily,
                weekly=args.weekly,contract=args.contract,simulate=args.simulate)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS)
            w.writeheader();w.writerows(out)
    except (ValueError,KeyError,OSError,TypeError) as exc:
        cli.exit(2,f'排名拒絕：{exc}\n')
    print(f'Research candidates: {len(out)}; authorized lots: 0; simulation only: {sum(r["simulation_lots"] for r in out)}')


if __name__=='__main__': main()
