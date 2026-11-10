"""Versioned research assumptions; not performance-optimized or trading approval."""
TOP_N = 5
MAX_POSITIONS = 5
CASH_RESERVE = .10
POSITION_CAP = .18
BUY_COST = .0025
PARAMETERS = dict(strategy_id='all_qualified_top5_v1',lag=14,r20_min=.05,r5_min=0,
                  retail_delta_max=-.01,turnover_min=10000000,top_n=TOP_N,
                  ranking='liquidity_desc_ticker_asc',control_required=False,
                  max_positions=MAX_POSITIONS,position_cap=POSITION_CAP,
                  cash_reserve=CASH_RESERVE,buy_cost=BUY_COST,lot_size=1000,
                  unaffordable='zero_lots_no_replacement',unused_budget='no_redistribution')
