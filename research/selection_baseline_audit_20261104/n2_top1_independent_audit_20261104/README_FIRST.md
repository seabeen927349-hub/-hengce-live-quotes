# Independent N2 Top1 audit package | 2026-11-04

- First read `N2_TOP1_INDEPENDENT_VALIDATION_20261104.md` and `audit_summary.json`.
- `N2_TOP1_ALL84_DIVIDEND_EXECUTION_DIAGNOSTICS.csv` preserves all **84 unchanged signal/entry/exit/ticker tuples**; price-only vs conditional gross-dividend receivable results, liquidity caveat and historical feature diagnostics are separate fields.
- `HOLDING_4_CASH_DIVIDEND_ENTITLEMENTS.csv`: 4 holdings with cash-only ex-dates. `SIGNAL_9_EXDIVIDEND_LOOKBACK_DIAGNOSTICS.csv`: 9 historical 5d selection-side ex-dividend events; never re-rank original Top1.
- `SHADOW_HYPOTHESES_PRE_REG_20261104.md` is prospective *observation* protocol, **not a validated revision**.
- Re-run against the **separate untouched FULL HANDOFF ZIP** after extracting it: `python n2_ca_execution_audit.py --input-dir /PATH/EXTRACTED_HANDOFF --output-dir /PATH/OUTPUT`. Requirements: pandas. The original `run.py` / `test_run.py` from package 05 were also re-run with all source files in `/mnt/data` and passed 93/93 tests; logs included. The additional independent 8 checks run from this directory with pytest, directly from the extracted audit folder.
- Audit input SHA: complete uploaded ZIP `301c56aaca3ad3251b4b3ffd0e23e34fea1d8aa30b126305aef031ae1d5bd961` . No canonical files are included/altered in this output package. The parent research branch and frozen baseline remain untouched. Trading NO-GO.
