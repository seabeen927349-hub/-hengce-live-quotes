"""Compare small-holder signals against same-date price-matched controls."""
import argparse

import numpy as np
import pandas as pd

from validation import keys


def read_daily(path):
    columns = ["Date","Ticker","Close","Volume","Turnover"]
    d = pd.read_csv(path, usecols=columns, dtype={"Ticker":str}, low_memory=False)
    d["Date"] = pd.to_datetime(d.Date)
    for c in ["Close","Volume","Turnover"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    keys(d)
    for c in ['Volume', 'Turnover']:
        if (~np.isfinite(d[c]) | d[c].lt(0)).any():
            raise ValueError(f'{c} must be finite and nonnegative')
    # Missing official close can coexist with odd-lot volume; never fill it.
    invalid_close = ~np.isfinite(d.Close) | d.Close.le(0)
    if (d.Close.le(0) | np.isinf(d.Close)).any():
        raise ValueError('Close must be positive when present')
    d.loc[invalid_close, 'Close'] = np.nan
    return d.sort_values(['Date', 'Ticker'])


def screen(daily, chip, lag, decision=None, *, require_control=True):
    daily = daily.sort_values(['Date', 'Ticker'])
    chip = chip.sort_values(['Date', 'Ticker'])
    def wide(key):
        return daily.pivot(index="Date", columns="Ticker", values=key)

    volume = wide("Volume")
    close = wide("Close").where(volume.gt(0))
    liquidity = wide("Turnover").rolling(20).median()
    r5 = close / close.shift(5) - 1
    r20 = close / close.shift(20) - 1
    risk = np.log(close.where(close.gt(0))).diff().rolling(20).std()
    weeks = close.index.to_series().groupby(close.index.to_period("W-FRI")).last()
    if decision is not None:
        weeks = weeks[weeks.eq(decision)]
    all_rows = []
    for date in weeks:
        if date.year < 2019 or date.weekday() != 4:
            continue
        when = date - pd.Timedelta(days=lag)
        known = chip[chip.Date.le(when)]
        if known.empty or (when - known.Date.iloc[-1]).days > 7:
            continue
        group = known[known.Date.eq(known.Date.iloc[-1])].set_index("Ticker")
        metrics = pd.DataFrame({"r5":r5.loc[date],"r20":r20.loc[date],
                                "risk":risk.loc[date],"liquidity":liquidity.loc[date]})
        metrics = metrics.join(group[["delta","Date"]], how="inner").dropna()
        metrics = metrics[metrics.liquidity.ge(10_000_000) & metrics.risk.gt(0)]
        j = close.index.get_loc(date)
        if decision is None and j+1 >= len(close):
            continue
        setups = {
            "rise_retail_down": (metrics.r20.ge(.05) & metrics.r5.ge(0), metrics.delta.le(-.01)),
        }
        for name,(price_ok,chip_ok) in setups.items():
            if not require_control:
                for t,m in metrics[price_ok & chip_ok].sort_index().sort_values('liquidity',ascending=False,kind='stable').iterrows():
                    all_rows.append(dict(decision=date,trade=close.index[j+1] if j+1<len(close) else pd.NaT,
                                         lag=lag,ticker=t,control=None,liquidity=m.liquidity,
                                         chip_date=m.Date,r5=m.r5,r20=m.r20,retail_delta=m.delta,
                                         control_r5=None,control_r20=None,control_delta=None))
                continue
            controls = metrics[price_ok & metrics.delta.abs().lt(.01)].copy()
            for t, m in metrics[price_ok & chip_ok].sort_index().sort_values("liquidity",ascending=False,kind="stable").iterrows():
                dr5 = (controls.r5-m.r5).abs()
                dr20 = (controls.r20-m.r20).abs()
                dv = abs(np.log(controls.risk/m.risk))
                dl = abs(np.log(controls.liquidity/m.liquidity))
                valid = dr5.le(.05) & dr20.le(.08) & dv.le(np.log(2)) & dl.le(np.log(4))
                distance = (dr5/.05 + dr20/.08 + dv + dl)[valid]
                if distance.empty:
                    continue
                c = distance.idxmin()
                controls_before = controls.loc[c]
                controls = controls.drop(c)
                all_rows.append(dict(decision=date, trade=close.index[j+1] if j+1<len(close) else pd.NaT,
                                     lag=lag, ticker=t, control=c, liquidity=m.liquidity,
                                     chip_date=m.Date, r5=m.r5, r20=m.r20, retail_delta=m.delta,
                                     control_r5=controls_before.r5, control_r20=controls_before.r20,
                                     control_delta=controls_before.delta))
    columns = ['decision','trade','lag','ticker','control','liquidity','chip_date',
               'r5','r20','retail_delta','control_r5','control_r20','control_delta']
    return pd.DataFrame(all_rows, columns=columns)


def eligible_stocks(daily, chip, lag, decision=None):
    """All base-qualified stocks. Control matching is research-only."""
    return screen(daily,chip,lag,decision,require_control=False)


def read_chips(path):
    chip = pd.read_csv(path, usecols=["SnapshotDate","Ticker","HolderLe10Lots","RetailPeopleValid"],
                       dtype={"Ticker":str,"SnapshotDate":str})
    chip["Date"] = pd.to_datetime(chip.SnapshotDate,format="%Y%m%d")
    keys(chip)
    chip = chip.sort_values(['Date','Ticker'])
    valid = chip.RetailPeopleValid.astype(str).str.strip().str.lower()
    if not valid.isin(['true','false','1','0']).all():
        raise ValueError('RetailPeopleValid must be true/false or 1/0')
    chip['RetailPeopleValid'] = valid.isin(['true','1'])
    chip['HolderLe10Lots'] = pd.to_numeric(chip.HolderLe10Lots, errors='coerce')
    counts = chip.HolderLe10Lots
    if (chip.RetailPeopleValid & (~np.isfinite(counts) | counts.lt(0) | counts.mod(1).ne(0))).any():
        raise ValueError('Valid holder counts must be finite nonnegative integers')
    count = chip.HolderLe10Lots.where(chip.RetailPeopleValid.eq(True))
    previous = count.groupby(chip.Ticker).shift(2)
    gap = chip.groupby("Ticker").Date.diff().dt.days
    prior_gap = gap.groupby(chip.Ticker).shift()
    chip["delta"] = (count/previous-1).where(previous.gt(0) & gap.between(5,10) & prior_gap.between(5,10))
    return chip


def main():
    p = argparse.ArgumentParser()
    p.add_argument("daily")
    p.add_argument("weekly")
    p.add_argument("output")
    args = p.parse_args()
    from provenance import load_inputs, AUTHORITY
    try:
        d,chip,_ = load_inputs(args.daily,args.weekly)
        # This CLI also uses the pinned reference. screen() is a calculation primitive.
        rows = pd.concat([eligible_stocks(d, chip, lag) for lag in [14,21]], ignore_index=True)
        rows['research_only'] = True
        rows['authority'] = AUTHORITY
        with open(args.output,'x',encoding='utf-8-sig',newline='') as target:
            rows.to_csv(target,index=False)
    except (ValueError,KeyError,OSError) as exc:
        p.exit(2,f'研究篩選拒絕：{exc}\n')


if __name__=="__main__":
    main()
