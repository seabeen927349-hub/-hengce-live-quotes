#!/usr/bin/env python3
"""HENGCE IF-07 Stage A V0.2 transport-hardening wrapper.

This file deliberately does NOT change any accounting logic, periods, thresholds,
correction handling, sample gates, or output semantics from
`if07_stage_a_accounting_upper_bound_builder.py`.

It only replaces the V0.1 bulk download acceptance test. V0.1 accepted a body
when HTTP=200 and the first two bytes were PK. Run 41175553232 proved that this
can accept a truncated/corrupt response whose ZIP central directory is invalid.

V0.2 accepts a quarterly bulk package only if:
- HTTP 200;
- ZIP magic is present;
- Python can parse the complete ZIP central directory;
- the archive contains >100 distinct consolidated iXBRL members matching the
  requested year/quarter naming contract;
- three deterministic matched members can be read from the archive.

NO prices. NO forward returns. NO null outcomes.
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from typing import Any

import requests

import if07_stage_a_accounting_upper_bound_builder as base


def hardened_download_bulk(
    s: requests.Session, year: int, q: int
) -> tuple[bytes, dict[str, Any]]:
    fn = f'tifrs-{year}Q{q}.zip'
    params = {
        'step': '9',
        'functionName': 'show_file2',
        'fileName': fn,
        'filePath': f'/ifrs/{year}/',
    }
    pattern = re.compile(
        rf'^tifrs-fr1-m1-ci-cr-\d{{4}}-{year}Q{q}\.html$', re.I
    )
    last: dict[str, Any] | None = None
    backoff = [5, 10, 20, 30]

    for attempt in range(1, 5):
        try:
            r = s.get(
                base.BULK_URL,
                params=params,
                headers={'Referer': 'https://mopsov.twse.com.tw/mops/web/t203sb02'},
                timeout=300,
            )
            b = r.content
            receipt: dict[str, Any] = {
                'year': year,
                'quarter': q,
                'attempt': attempt,
                'http_status': r.status_code,
                'bytes': len(b),
                'sha256': base.sha256(b),
                'content_type': r.headers.get('content-type'),
                'content_length_header': r.headers.get('content-length'),
                'zip_magic': b[:2] == b'PK',
                'transport_validation_version': 'CENTRAL_DIRECTORY_PLUS_MEMBER_READ_V0_2',
                'central_directory_valid': False,
                'matched_consolidated_member_count': 0,
                'sample_member_reads_pass': False,
            }

            if r.status_code != 200 or b[:2] != b'PK':
                receipt['reject_reason'] = 'HTTP_OR_ZIP_MAGIC_FAIL'
                last = receipt
            else:
                try:
                    with zipfile.ZipFile(io.BytesIO(b)) as z:
                        names = z.namelist()  # forces central-directory parse
                        receipt['central_directory_valid'] = True
                        matched = sorted(
                            n for n in names if pattern.match(n.rsplit('/', 1)[-1])
                        )
                        receipt['zip_member_count'] = len(names)
                        receipt['matched_consolidated_member_count'] = len(matched)
                        if len(matched) <= 100:
                            receipt['reject_reason'] = 'TOO_FEW_TARGET_QUARTER_CONSOLIDATED_MEMBERS'
                            last = receipt
                        else:
                            # Deterministic integrity spot reads. The main builder subsequently
                            # reads every in-scope member, so targeted-member corruption will
                            # still fail closed later rather than being silently skipped.
                            sample_idx = [0, len(matched) // 2, len(matched) - 1]
                            samples = [matched[i] for i in sample_idx]
                            sample_receipts = []
                            for name in samples:
                                payload = z.read(name)
                                sample_receipts.append({
                                    'name': name,
                                    'bytes': len(payload),
                                    'ixbrl_marker': (
                                        b'ix:nonFraction' in payload
                                        or b'ix:nonfraction' in payload.lower()
                                    ),
                                })
                            receipt['sample_member_reads'] = sample_receipts
                            receipt['sample_member_reads_pass'] = all(
                                x['bytes'] > 1000 and x['ixbrl_marker']
                                for x in sample_receipts
                            )
                            if receipt['sample_member_reads_pass']:
                                receipt['accepted'] = True
                                return b, receipt
                            receipt['reject_reason'] = 'SAMPLE_MEMBER_READ_OR_IXBRL_MARKER_FAIL'
                            last = receipt
                except (zipfile.BadZipFile, EOFError, OSError) as exc:
                    receipt['reject_reason'] = 'ZIP_STRUCTURE_FAIL'
                    receipt['zip_error_type'] = type(exc).__name__
                    receipt['zip_error'] = str(exc)
                    last = receipt
        except Exception as exc:
            last = {
                'year': year,
                'quarter': q,
                'attempt': attempt,
                'reject_reason': 'REQUEST_OR_VALIDATION_EXCEPTION',
                'error_type': type(exc).__name__,
                'error': str(exc),
                'transport_validation_version': 'CENTRAL_DIRECTORY_PLUS_MEMBER_READ_V0_2',
            }

        if attempt < 4:
            time.sleep(backoff[attempt - 1])

    raise RuntimeError(f'BULK_DOWNLOAD_FAILED_AFTER_HARD_VALIDATION:{year}Q{q}:{last}')


def main() -> None:
    base.download_bulk = hardened_download_bulk
    base.main()


if __name__ == '__main__':
    main()
