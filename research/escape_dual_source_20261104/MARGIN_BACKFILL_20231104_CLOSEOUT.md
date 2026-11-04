# HENGCE Escape — margin source-repair correction and 919-session replay (2026-11-04)

**Status:** `RESEARCH_SIDECAR_REBUILT; FORMAL_ESCAPE_BLOCKED; NO_TRADING_AUTHORITY`. No change to `main`, canonical historical mother, frozen metric specification or active selection engines.

## Correction to earlier DATA_BLOCK

The existing joined `/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv` really has null institutional and margin columns for 2018–2025, but it was **incorrect to conclude that all original historical financing data were unavailable**. Separately retained `TWSE_2023_2025_mother.csv` (735,618 price/institutional rows) and `TWSE_2023_2025_margin.csv` (717,643 TWSE official margin rows) were located in the Library and read in full.

Full `Date,Ticker` reconciliation:
- 716,342 margin rows match a 2023–2025 mother price key.
- 14,287 nonnull pre-existing joined balances match the official raw source **exactly**; no conflicts.
- **702,055 missing joined margin balances restored** in an *independent, versioned research-only sidecar*. No missing-as-zero, no invented price rows.
- 1,301 margin-only records had no mother price key; do **not** force them into price rows.
- 19,276 historical mother price rows had no matching TWSE margin report row; do **not** interpret these absences as zero.
- The original 2026 joined mother has 209,196 matching nonnull margin balances, all equal to its 2026 TWSE raw margin source; no new 2026 balance rows were invented.

The existing mother's original SHA256 remains `6f7494b46af07a11f68429981b3ec666ad0a520ed9b51ae0150f4c34435639e7`.

## Independent vendor probes

Direct public FinMind `TaiwanStockMarginPurchaseShortSale` query for 2330 for 2024-01-02 through 2024-01-05 returned values **12844, 13785, 13655, 13891** (lots), exactly **4/4** the TWSE raw margin source. A corresponding query for 2330 for 2018-01-02 through 2018-01-05 returned **9703, 9434, 9066, 8554**; this proves **sample availability**, *not* a full-market 2018–2022 backfill. A 2026-10-26 to 2026-10-27 6908 query returned `data: []`; do not reinterpret absence as zero or conclusive ineligibility. Fugle content specs confirmed near-six-month per-symbol margin coverage; this does not itself establish full-market pre-2023 data coverage.

## Executed 2023–2026 historical replay

Merged `2023–2025` repaired full-market source with existing 2026 mother **through 2026-10-27**: 946,213 raw rows before excluding nonordinary securities, 942,320 research ordinary rows; 919 dated E cohorts from separate archived TWSE electronics files (2023:239, 2024:242, 2025:243, 2026:195 days). No historical membership reconstructed from present-day labels. Archived E prices match joined mother; 2026-10-08, 2026-10-21 and 2026-10-22 have **494** preexisting volume/turnover revision differences, preserved as unresolved.

Two predeclared sensitivity interpretations:
1. `STRICT_ALL_E_REPORTING`: historical E margin observations cover min 96.696%, mean 98.286%, max 99.527% of daily E members, but never 100%. Leverage metric is unverified (all 919 days), and only 16/17 frozen-name metrics have usable histories.
2. `TWSE_REPORTED_MARGIN_BALANCES_ONLY_RESEARCH`: aggregate only **non-null reported MI_MARGN balances for E PIT securities**, preserving unreported rows as NULL. This produces 17/17 numeric candidate features on **889** dates; **849** dates have 40 past observations for all 17. First eligible research-only date 2023-04-28. No implication that every E security had independently verified margin eligibility. This is not formal Escape admission.

No independent 2018–2022 full-market institutional/margin source was bulk-restored in this session. The confirmed ability to query individual 2018 FinMind data is not a substitute. Unresolved: PIT U registry and margin eligibility, source version reconciliation, 2018–2022 whole-market gap, external OOS/false-alarm validation. Full formal Escape state remains `UNVERIFIED`.

## Independent integrity / deliverables

Local SHA-verified **19/19** non-destructive integrity regressions PASS. Existing 16 computed feature columns are **bitwise-equal** between the strict and reported-margin research variants; only margin leverage and downstream completeness fields differ.

Deliverables held in the conversation files and (if persisted) the HENGCE Library Research Outputs:
- `HENGCE_Escape_2023_2025_Margin_702055_Patch.zip`, 4,204,743 bytes, SHA256 `12121d2684874cb96ec456edce980aa696af6c2a1bf2ae834157ea33588b8b4d`
- `HENGCE_Escape_2023_2026_919Day_Repaired_Research.zip`, 53,911,422 bytes, SHA256 `67d833114dda72aa89f0890bac65d84d37686bfd06f66c18da728af7e721e052`

Do not merge or promote to formal trading engine solely from candidate feature numerical completeness.
