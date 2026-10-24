# HENGCE V43 frozen diagnostics index — 2026-10-24

This record continues research on the already-frozen V43 frontier without changing the model. It is validation-only: **0 new model evaluations, 0 parameter searches, 0 production changes**.

## Source integrity
- Frozen V43 Actions artifact SHA-256: `b900fde5eee6d97ca24cce1e0d77b1977dc9103642d55c228b73ba6be2bb87e3`
- Frozen V43 events SHA-256: `ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e`
- Frozen basket count: `30`
- Diagnostic bundle SHA-256: `49e99107d32f0b02bae4300006b54354ed6395cf8539add392194f98b0b4cd6f`
- The bundle contains the rerunnable diagnostic script plus JSON and Markdown outputs.

## Stronger historical fragility diagnostics at 1.2% cost
- Baseline compounded return: `+342.65%`
- Formal max drawdown: `-17.67%`
- Win rate: `20/30 = 66.7%`
- Remove best basket: `+193.12%`
- Remove top 2 baskets: `+132.83%`
- Remove top 3 baskets: `+96.38%`
- Remove top 5 baskets: `+54.21%`
- Every one of the 30 leave-one-out histories remains positive.
- Maximum consecutive non-positive baskets: `2`.

## Regime attribution
- STRONG: 15 baskets, 73.3% win rate, `+228.22%` compounded, mean basket `+8.95%`.
- WEAK: 15 baskets, 60.0% win rate, `+34.86%` compounded, mean basket `+2.24%`.

This is the principal historical caution: V43 alpha is materially stronger in STRONG breadth than WEAK breadth. This is a prospective validation target, not a tuning instruction.

## Sequence and name concentration
- Worst rolling 3-basket compounded return: `-10.55%`; 23/28 windows positive.
- Worst rolling 5-basket compounded return: `-10.23%`; 23/26 windows positive.
- Worst rolling 6-basket compounded return: `-6.54%`; 20/25 windows positive.
- Every rolling 10-basket window is positive; worst is `+1.42%`.
- 90 basket slots use 71 distinct tickers.
- Top 5 tickers by cumulative basket weight are 19.66% of total weight mass; top 10 are 32.03%.
- Most frequent ticker is `2454`, appearing in 4/30 baskets.

## Frozen-weight stability
Across the 30 accepted baskets, factor weights stay in narrow ranges:
- resid_rev: 0.1800–0.2300
- mom20: 0.2439–0.2773
- skip5_60: 0.2700–0.3030
- liquidity: 0.0450–0.0799
- lowvol: 0.1800–0.2196

## PIT / no-lookahead audit of V43 learning
The formal V43 result contains 30 weight-log entries and **zero fallback entries**. Same-regime prior anchor counts are 3–25 (mean about 11.57). V43's frozen source selects regime anchors only when `anchor.exit_date < signal_date`, so the ICIR update uses only fully realized prior labels.

Therefore the annual `GLOBAL[y]` fallback is not part of any of the 30 formal V43 historical baskets. This removes one potential intra-event lookahead concern for the accepted V43 result.

This does **not** erase model-selection bias: V43 and its upstream fixed stack were selected using exposed 2024–2026 research history. V43 remains historical research evidence, not pristine prospective evidence.

## Prospective observer gap
The current V43 prospective-shadow wrapper is frozen correctly, but its imported V13 data/evaluation period ends at `2026-10-22`. As written, extending the data file alone cannot produce a post-lock basket. Future prospective validation therefore requires research-only observer plumbing that reproduces the already-frozen V43 rules without rerunning historical challenger selection. Do not solve this by extending old screening periods or retuning parameters.

## Research conclusion
V43 survives materially stronger concentration, leave-one-out, sequence and name-concentration diagnostics. The two unresolved questions are now sharply defined:
1. whether the STRONG-vs-WEAK performance gap persists prospectively; and
2. whether frozen V43 can accumulate genuine post-lock baskets through a clean observer that does not reopen model selection.

No V45 is authorized by this work.

Authority remains research-only: capital authority 0; broker execution false; production promotion false; main/Q017/E2/M1 unchanged; PR #30 unmerged.
