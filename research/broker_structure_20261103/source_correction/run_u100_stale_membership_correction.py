#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DATASET='TaiwanStockTradingDailyReportSecIdAgg'
SOURCE_PLAN='SponsorPro'
SOURCE_CLASS='EVENT_DAY_FACT_RECONSTRUCTION'
EXPECTED_COLS=['date','stock_id','securities_trader_id','buy_volume','sell_volume','buy_price','sell_price']
PREREG_COMMIT='303b2e60501ecc93af6d3b67215f74d17795fa53'
SEALED_UPSTREAM_SHA256='035ab93ca1d3412e979c11afd4e2699b09e24cff9da7a5c6f43c003b0e5df219'


def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()


def norm_ticker(x)->str:
    s=str(x).strip()
    if re.fullmatch(r'\d+(?:\.0+)?',s):
        s=s.split('.')[0]
        if len(s)<=4: return s.zfill(4)
    return s


def canon(v):
    if v is None: return None
    if isinstance(v,np.generic): return canon(v.item())
    if isinstance(v,float):
        if math.isnan(v): return {'__nonfinite__':'NaN'}
        if math.isinf(v): return {'__nonfinite__':'+Inf' if v>0 else '-Inf'}
        return v
    if isinstance(v,(date,datetime)): return v.isoformat()
    if isinstance(v,bytes): return {'__bytes_hex__':v.hex()}
    return v


def logical_sha(table)->str:
    t=table.select(EXPECTED_COLS).sort_by([(c,'ascending') for c in EXPECTED_COLS])
    h=hashlib.sha256(); h.update(('HENGCE_LOGICAL_ROW_HASH_V2_NONFINITE_CANONICAL\n'+'\x1f'.join(EXPECTED_COLS)+'\n').encode())
    for batch in t.to_batches(max_chunksize=65536):
        cols=[batch.column(i).to_pylist() for i in range(batch.num_columns)]
        for vals in zip(*cols):
            h.update(json.dumps([canon(v) for v in vals],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()); h.update(b'\n')
    return h.hexdigest()


def compute_one(pdf:pd.DataFrame,ticker:str)->float:
    p=pdf.copy(); p['stock_norm']=p.stock_id.map(norm_ticker)
    s=p[p.stock_norm==ticker].copy()
    if s.empty: raise RuntimeError(f'{ticker}:MISSING_SOURCE_DATA')
    if s.duplicated(['date','stock_id','securities_trader_id']).any(): raise RuntimeError(f'{ticker}:DUPLICATE_KEY')
    if s.securities_trader_id.isna().any() or (s.securities_trader_id.astype(str).str.strip()=='').any(): raise RuntimeError(f'{ticker}:INVALID_IDENTITY')
    buy=pd.to_numeric(s.buy_volume,errors='coerce').to_numpy(float); sell=pd.to_numeric(s.sell_volume,errors='coerce').to_numpy(float)
    if (not np.isfinite(buy).all()) or (not np.isfinite(sell).all()) or np.any(buy<0) or np.any(sell<0): raise RuntimeError(f'{ticker}:INVALID_VOLUME')
    gross=buy+sell; gross=gross[gross>0]
    total=float(gross.sum())
    if not np.isfinite(total) or total<=0: raise RuntimeError(f'{ticker}:ZERO_TOTAL_GROSS_VOLUME')
    v=float(np.sum((gross/total)**2))
    if not np.isfinite(v) or not (0<v<=1+1e-12): raise RuntimeError(f'{ticker}:HHI_RANGE_INVALID')
    return v


async def main_async()->dict:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from finmind_mcp.client import FinMindClient

    root=Path(__file__).resolve().parent
    target=pd.read_csv(root/'u100_stale_membership_correction_20261103.csv',dtype={'required_frozen_ticker':str,'stale_membership_ticker':str})
    if len(target)!=12 or target.date.nunique()!=11: raise RuntimeError('CORRECTION_TARGET_GEOMETRY_INVALID')
    target['required_frozen_ticker']=target.required_frozen_ticker.str.zfill(4); target['stale_membership_ticker']=target.stale_membership_ticker.str.zfill(4)
    if target.duplicated(['date','required_frozen_ticker']).any(): raise RuntimeError('CORRECTION_TARGET_DUPLICATE')
    if not os.environ.get('FINMIND_TOKEN'): raise RuntimeError('FINMIND_TOKEN_MISSING')

    client=FinMindClient(); out_rows=[]; lineage=[]
    with tempfile.TemporaryDirectory(prefix='hengce-h20-u100-correction-') as td0:
        td=Path(td0)
        for d,g in target.groupby('date',sort=True):
            raw=td/f'{d}.parquet'; last=None
            ret_utc=datetime.now(timezone.utc).isoformat(); ret_tw=datetime.now(ZoneInfo('Asia/Taipei')).isoformat()
            for attempt in range(5):
                try:
                    signed=await client.storage_object_url(DATASET,str(d)); await client.download(signed,raw); last=None; break
                except Exception as e:
                    last=f'{type(e).__name__}:{e}'; await asyncio.sleep(min(20.0,1.5*(2**attempt)))
            if last is not None or not raw.is_file(): raise RuntimeError(f'{d}:TRANSPORT:{last}')
            try:
                psha=sha256_file(raw); pbytes=raw.stat().st_size
                pf=pq.ParquetFile(raw); cols=pf.schema_arrow.names
                miss=sorted(set(EXPECTED_COLS)-set(cols))
                if miss: raise RuntimeError(f'{d}:MISSING_REQUIRED_SCHEMA:{miss}')
                table=pf.read(columns=EXPECTED_COLS)
                obs={str(x) for x in pc.unique(table['date']).to_pylist() if x is not None}
                if obs!={str(d)}: raise RuntimeError(f'{d}:SOURCE_DATE_MISMATCH:{sorted(obs)}')
                pdf=table.to_pandas(); lsha=logical_sha(table)
                stocks={norm_ticker(x) for x in pdf.stock_id.dropna()}
                for r in g.itertuples(index=False):
                    t=str(r.required_frozen_ticker).zfill(4)
                    v=compute_one(pdf,t)
                    out_rows.append({'date':str(d),'ticker':t,'BROKER_GROSS_HHI_1D':v,'replaces_stale_membership_ticker':str(r.stale_membership_ticker).zfill(4),'date_index':int(r.date_index)})
                lineage.append({
                    'dataset':DATASET,'event_date':str(d),'source_plan':SOURCE_PLAN,'source_revision_class':SOURCE_CLASS,
                    'retrieval_timestamp_utc':ret_utc,'retrieval_timestamp_taipei':ret_tw,
                    'query_or_download_mode':'FinMindClient.storage_object_url whole-day parquet',
                    'row_count':int(table.num_rows),'unique_stock_id_count':len(stocks),
                    'unique_securities_trader_id_count':int(pdf.securities_trader_id.dropna().astype(str).nunique()),
                    'physical_object_sha256':psha,'physical_object_bytes':pbytes,'logical_content_sha256':lsha,
                    'logical_digest_spec':'HENGCE_LOGICAL_ROW_HASH_V2_NONFINITE_CANONICAL_SORT_ALL_REQUIRED_FIELDS_JSON_LINES',
                    'schema_field_list':cols,'required_correction_tickers':sorted(str(x).zfill(4) for x in g.required_frozen_ticker),
                    'required_correction_ticker_count':len(g),
                })
            finally:
                raw.unlink(missing_ok=True)

    od=pd.DataFrame(out_rows).sort_values(['date','ticker']).reset_index(drop=True)
    if len(od)!=12 or od.date.nunique()!=11 or od.duplicated(['date','ticker']).any(): raise RuntimeError('CORRECTION_OUTPUT_GEOMETRY_INVALID')
    csvp=root/'broker_hhi_u100_correction_12rows.csv'; jsonlp=root/'broker_hhi_u100_correction_lineage_11dates.jsonl'; recp=root/'broker_hhi_u100_correction_receipt.json'
    od.to_csv(csvp,index=False,float_format='%.17g')
    with jsonlp.open('w',encoding='utf-8') as f:
        for x in lineage: f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
    receipt={
        'schema_version':1,'system':'HENGCE','artifact':'BROKER_H20_U100_STALE_MEMBERSHIP_BOUNDED_CORRECTION',
        'authority':'PLUMBING_CORRECTION_ONLY_NO_RETUNING_NO_TRADING_AUTHORITY','status':'PASS_BOUNDED_CORRECTION',
        'prereg_commit':PREREG_COMMIT,'sealed_upstream_sha256':SEALED_UPSTREAM_SHA256,
        'source_revision_class':SOURCE_CLASS,'correction_dates':11,'correction_rows':12,
        'hhi_csv_sha256':sha256_file(csvp),'lineage_jsonl_sha256':sha256_file(jsonlp),
        'raw_broker_rows_persisted':False,'forward_returns_loaded':False,
        'scope':'Only 12 frozen U100 stock-dates missing because handoff membership CSV disagreed with sealed upstream membership on 11 dates.'
    }
    recp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    return receipt


def main()->int:
    try:
        r=asyncio.run(main_async()); print(json.dumps(r,ensure_ascii=False,sort_keys=True)); return 0
    except Exception as e:
        print(json.dumps({'status':'DATA_OR_LINEAGE_INVALID_STOP','error':f'{type(e).__name__}:{e}'},ensure_ascii=False)); return 2

if __name__=='__main__': raise SystemExit(main())
