"""Create an exclusive research rehearsal record; official sealing is unavailable."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from strategy import PARAMETERS

from provenance import (AUTHORITY, CONTRACT_SHA256, DEFAULT_CONTRACT, load_inputs,
                        compute_lanes, code_hashes)


def make_record(daily_path, chip_path, decision, contract_path=DEFAULT_CONTRACT):
    daily,chips,contract=load_inputs(daily_path,chip_path,contract_path)
    lanes=compute_lanes(daily,chips,decision,contract)
    return dict(version='retail_forward_v2_2',kind='rehearsal',authority=AUTHORITY,
                verification_scope='BUNDLED_REFERENCE_ONLY',strategy=PARAMETERS,
                decision=str(pd.Timestamp(decision).date()),
                generated_at=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
                price_rows=int(daily.Date.eq(pd.Timestamp(decision)).sum()),
                price_sha256=contract['daily_sha256'],chip_sha256=contract['chip_sha256'],
                contract_sha256=CONTRACT_SHA256,code_sha256=code_hashes(),
                integrity='RECOMPUTABLE_NOT_SIGNED',official_publication_verified=False,
                intended_fill=None,lanes=lanes)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('daily',type=Path)
    cli.add_argument('weekly',type=Path)
    cli.add_argument('decision')
    cli.add_argument('output',type=Path)
    cli.add_argument('--rehearsal',action='store_true')
    cli.add_argument('--contract',type=Path,default=DEFAULT_CONTRACT)
    args=cli.parse_args()
    if not args.rehearsal:
        cli.error('OFFICIAL_EVIDENCE_UNAVAILABLE: 本包沒有正式存證／授權鏈，僅支援 --rehearsal')
    try:
        record=make_record(args.daily,args.weekly,args.decision,args.contract)
        with args.output.open('x',encoding='utf-8') as target:
            json.dump(record,target,ensure_ascii=False,indent=2)
            target.write('\n')
    except (ValueError,KeyError,OSError) as exc:
        cli.exit(2,f'封存失敗：{exc}\n')
    print({lag:len(lane['candidates']) for lag,lane in record['lanes'].items()})


if __name__=='__main__': main()
