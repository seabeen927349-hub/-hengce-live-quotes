"""Shared input checks; invalid/missing observations never become buy signals."""
import numpy as np
import pandas as pd


def keys(frame, date='Date'):
    if frame.empty:
        raise ValueError('資料為空')
    if frame[date].isna().any() or frame['Ticker'].isna().any():
        raise ValueError('日期或股票代號缺漏')
    frame['Ticker'] = frame.Ticker.str.strip()
    if frame.Ticker.eq('').any() or frame.duplicated([date, 'Ticker']).any():
        raise ValueError('股票代號空白或日期/股票代號重複')
    if not frame[date].eq(frame[date].dt.normalize()).all():
        raise ValueError('資料日期不可包含盤中時間')


def decision_data(daily, chips, decision, lag=14, contract=None):
    from provenance import load_contract, validate_coverage
    if contract is None:
        contract = load_contract()
    validate_coverage(daily, chips, contract)
    day = pd.Timestamp(decision)
    if day.tzinfo is not None or day != day.normalize() or day.weekday() != 4:
        raise ValueError('決策日必須為週五日期（YYYY-MM-DD）')
    daily = daily[daily.Date.le(day)].copy()
    daily = daily[daily.Date.isin(sorted(daily.Date.unique())[-25:])]
    if daily.empty or daily.Date.max() != day or daily.Date.nunique() < 21:
        raise ValueError('缺少決策日收盤或至少21個交易日資料')
    counts = daily.groupby('Date').size()
    if counts.iloc[-1] < .95 * counts.iloc[:-1].tail(5).median():
        raise ValueError('決策日股票覆蓋率低於近期95%')
    cutoff = day - pd.Timedelta(days=lag)
    known = chips[chips.Date.le(cutoff)].copy()
    last = known.Date.max()
    if pd.isna(last) or (cutoff-last).days > 7:
        raise ValueError(f'缺少{lag}日延遲下的有效集保快照')
    return daily, known, last
