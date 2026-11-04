"""Independent invariants for fixed N2 Top1 audit outputs."""
from pathlib import Path
import pandas as pd, json, pytest
ROOT=Path(__file__).parent
D=pd.read_csv(ROOT/'N2_TOP1_ALL84_DIVIDEND_EXECUTION_DIAGNOSTICS.csv',dtype={'ticker':str})
E=pd.read_csv(ROOT/'HOLDING_4_CASH_DIVIDEND_ENTITLEMENTS.csv',dtype={'ticker':str})
F=pd.read_csv(ROOT/'SIGNAL_9_EXDIVIDEND_LOOKBACK_DIAGNOSTICS.csv',dtype={'ticker':str})
S=json.loads((ROOT/'audit_summary.json').read_text())

def test_invariant_84_no_reselection():
 assert len(D)==84 and D.signal.nunique()==84
 assert (D.shares%1000==0).all()
 assert not D.duplicated('signal').any()

def test_price_pnl_parity_both_costs():
 assert D.price_only_pnl40.sum()==pytest.approx(19_883_039)
 assert D.price_only_pnl80.sum()==pytest.approx(18_237_928)

def test_dividend_4_ex_only():
 assert len(E)==4 and set(E.event_type)=={'息'}
 assert E.holding_rights_stock_multiplier_certified.eq(False).all() if 'holding_rights_stock_multiplier_certified' in E.columns else E.rights_stock_multiplier_certified.eq(False).all()
 assert E.gross_cash_entitlement_proxy.sum()==pytest.approx(453563.814)

def test_lookback_9_preserved():
 assert len(F)==9
 assert (F.signal_reselected==False).all()
 assert (F.ex_cash_diagnostic_5d_return_pct>=F.raw_5d_return_pct).all()

def test_dividend_gross_accrual_not_fake_live():
 assert D.gross_dividend_accrual_pnl40.sum()==pytest.approx(20_336_602.814)
 assert D.gross_dividend_accrual_pnl80.sum()==pytest.approx(18_691_491.814)
 assert S['recommendation'].startswith('TRADING_NO_GO')

def test_2024_bad_not_all_losing():
 X=D[D.signal.str.startswith('2024')]
 assert len(X)==9 and (X.price_only_pnl40>0).sum()==2 and (X.price_only_pnl40<0).sum()==7
 assert X.price_only_pnl40.sum()==pytest.approx(-2_643_856.4)
 assert X.holding_cash_events.sum()==0

def test_84_open_fills_all_blocked():
 assert (D.open_fill_status=='EXECUTION_DATA_BLOCKED_NO_0900_AUCTION_TRADE_DEPTH').all()
 assert S['open_auction']['data_blocked']==84

def test_all_4_cash_entitlement_matches_formula():
 for r in E.itertuples():
  assert r.gross_cash_entitlement_proxy==pytest.approx(r.cash_per_share_proxy_when_cash_only*r.shares)
