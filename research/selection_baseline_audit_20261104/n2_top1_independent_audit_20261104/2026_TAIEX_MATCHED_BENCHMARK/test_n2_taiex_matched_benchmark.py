from pathlib import Path
import pandas as pd
import pytest
from n2_taiex_matched_benchmark import INDEX, run

LEDGER = Path('/mnt/data/n2_top1_fixed5m_20261104/all84_trades_fixed5m.csv')

@pytest.fixture(scope='session')
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp('taiex')
    return run(LEDGER, out)

def test_exact_window_count(result):
    assert result['frozen_events'] == 7

def test_dates_unique():
    assert len({(a,b) for a,b,*_ in INDEX}) == 7

def test_all_original_ledger_preserved():
    d=pd.read_csv(LEDGER)
    assert len(d)==84 and len(d[d.signal.str.startswith('2026')])==7

def test_known_n2_replay(result):
    assert result['n2_price_pnl_40bp'] == 3396871.60

def test_market_comparison_addition(result):
    assert abs(result['n2_price_pnl_40bp'] - result['taiex_hypothetical_price_pnl_40bp'] - result['n2_excess_vs_taiex_40bp']) < 0.02

def test_market_excess_sign(result):
    assert result['n2_excess_vs_taiex_40bp'] > 0

def test_beat_loss_count(result):
    assert result['n2_beats_taiex_windows'] == 3
    assert result['n2_loses_taiex_windows'] == 4

def test_leave_best_result(result):
    assert result['top_n2_trade_ticker'] == '3026'
    assert result['without_top_excess_40bp'] < 0

def test_80bp_cost_stress(result):
    assert result['n2_price_pnl_80bp'] < result['n2_price_pnl_40bp']
    assert result['taiex_hypothetical_price_pnl_80bp'] < result['taiex_hypothetical_price_pnl_40bp']

def test_no_intraday_fill_claim(result):
    assert 'execution-data blocked' in '\n'.join(result['qualifications'])
