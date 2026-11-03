# HENGCE Broker H20 — Final Frozen Validation (2026-11-03)

## Verdict

**INCREMENTAL_VALUE_ESTABLISHED_RECONSTRUCTION_ONLY**

This is a frozen historical reconstruction result only. It does **not** grant a trading rule, signed position rule, top-k rule, threshold, named-broker interpretation, production authority, or capital authority.

## Frozen-test result

- Input dates: **1,274**
- Included primary dates: **1,274**; excluded: **0**
- Frozen U100 geometry: **127,400 stock-dates = 1,274 × 100**
- Minimum joint complete-case date size: **97**, above frozen minimum 95
- Mean daily Broker coefficient: **0.084763728938**
- HAC lag-20 SE: **0.016185992360**
- HAC t: **5.236857**
- HAC two-sided p: **1.90932568342e-07**
- HAC 95% CI: **[0.053009575596, 0.116517882280]**
- Moving-block bootstrap (block=20, draws=10,000, seed=20261103) 95% CI: **[0.054851157463, 0.118261768259]**
- Early mean (<=2022-12-31): **0.113544618560**
- Late mean (>=2023-01-01): **0.072758352288**
- HAC CI excludes zero: **PASS**
- Bootstrap CI excludes zero: **PASS**
- Early/late sign stability: **PASS**
- Frozen survival gate: **PASS**

## Year diagnostics (descriptive only)

- 2021: n=129, mean b_broker=0.103687991664
- 2022: n=246, mean b_broker=0.118713337541
- 2023: n=239, mean b_broker=0.085579761827
- 2024: n=242, mean b_broker=0.101749029744
- 2025: n=243, mean b_broker=0.030616541870
- 2026: n=175, mean b_broker=0.073674918619

The 2025 annual mean is materially weaker than earlier years. This is a genuine attenuation signal and should remain visible in future monitoring; it was not used to alter the frozen verdict.

## State diagnostics (secondary; cannot rescue primary)

- DIFFUSE_NORMAL: n=1014, mean=0.093232769204, median=0.088267811941, fraction>0=0.697239
- SYNCHRONIZED_STRESS: n=260, mean=0.051734471899, median=0.042867966630, fraction>0=0.607692

## Data / lineage closure

The full source audit covered all 1,274 event dates. The original handoff's `u100_membership_segments_1274.csv` was found to disagree with the sealed upstream U100 membership on 11 dates / 12 replacement stock-dates. The mismatch was treated as a plumbing defect, not tuned after outcome: the exact sealed-upstream membership was read from `date_ord` + `ticker` only, the 12 missing HHI values were re-derived from the same whole-day FinMind source objects, and the repeated retrieval physical/logical hashes matched 11/11.

After correction:
- exact source HHI keyset = sealed upstream U100: **true**
- exact HHI rows: **127,400**
- minimum HHI coverage/date: **100/100**
- final judge panel SHA256: `bcbb9b2f32ef43672f050c915be622217742955e07c64a997d9ee253b8365fa3`
- exact judge Git blob: `1f8a34f115741fef21ee04c3eb475cf3fb2712c0`
- exact judge SHA256: `e33bfea256e98760b07f2de72ed978ac8099134b1de2ed4993bcd6f4232e68b4`
- result JSON SHA256: `c1c338862e25dd0508c302d057f475d7f4404b50417e4e2d95647b3324517b96`
- daily beta CSV SHA256: `b19972175e225483833b0e52bf1142f8a5f0374dc33760c18c57cfc3de824739`

## Interpretation boundary

The supported statement is narrow: **within the frozen historical reconstruction, higher `BROKER_GROSS_HHI_1D` rank contains statistically stable incremental cross-sectional information for H20 return rank after the preregistered controls.** This does not establish causality, broker identity, “smart money,” live-time data availability, or a profitable implementable strategy. Historical Broker source authority remains `EVENT_DAY_FACT_RECONSTRUCTION`, not strict vendor-as-known-then PIT.

No post-outcome retuning or rescue is authorized.
