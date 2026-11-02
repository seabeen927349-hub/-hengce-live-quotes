# HENGCE Market State × Selection — Numeric Parser Correction Audit

Date: 2026-11-02

## Defect

The first empirical execution parsed the official 2018–2026 electronics archives with mixed dtype inference. In the 2026 archive, numeric fields changed formatting and include comma separators, e.g. `3,750.00`. The first notebook execution subsequently repaired `turnover_ntd` formatting but did not uniformly repair all 2026 OHLC fields. High-priced 2026 observations could therefore be treated as missing.

This defect affected outcome eligibility and the first result commit.

## Detection

A separately written reproducibility script loaded every yearly archive as strings and applied one uniform numeric sanitation function to all numeric fields:

`strip comma separators -> numeric conversion -> invalid remains missing`

That replay produced a different primary sample and inferential result, triggering an immediate stop before a final user conclusion.

## Repair boundary

The correction changes **only numeric parsing**. It does not change:
- literature gate;
- preregistration;
- frozen S5 state classifier;
- state labels;
- date-correct universe;
- U100 liquidity rule;
- MOM20 selection rule;
- Top-5 count;
- next-session-open entry;
- 20-session horizon;
- outcome quality gate;
- DELTA definition;
- HAC lag 20;
- bootstrap block length 20;
- 10,000 bootstrap resamples;
- temporal split;
- conclusion thresholds.

Therefore this is an implementation/data-parser correction, not outcome-driven retuning.

## Independent replay

After repair, a second independent notebook implementation was written from the preregistration and archive schema rather than reusing the first result object. It exactly reproduced:
- primary n = 1,986;
- DIFFUSE_NORMAL n = 1,641;
- SYNCHRONIZED_STRESS n = 345;
- DELTA = −0.02475458730908983;
- HAC p = 0.0380353870221183;
- HAC 95% CI = [−0.04814137975275434, −0.0013677948654252613];
- 10,000-resample moving-block-bootstrap 95% CI = [−0.04700400675170316, −0.0006962675800019758];
- early DELTA = −0.028205898846635675;
- late DELTA = −0.018211759546438628.

## Supersedence

The corrected result files supersede the earlier `INCONCLUSIVE` execution result. Git history is intentionally preserved; the prior result is not deleted or hidden.

Corrected formal conclusion:
`ECONOMICALLY_MATERIAL_CANDIDATE / RESEARCH_ONLY_NO_TRADING_OR_PRODUCTION_AUTHORITY`.
