# Corrected Pass 4 target precedence correction

Date: 2026-11-01
Status: GOVERNANCE CORRECTION, NOT RETUNING

The frozen authority file `PASS4_INCREMENTAL_TARGET_CORRECTION_20261101.md` defines the corrected Pass 4 target as next-TDCC durability / recognition latency relative to CONTROL available at t.

An assistant-created execution lock later referenced the Pass-3 BASE probability, whose deterministic Pass-3 execution label was two-snapshot durability. That cannot override the earlier frozen Pass-4 correction because it would change the target back away from CONTROL's next-snapshot durability problem.

Therefore corrected Pass 4 uses:
- target: `T1_CONTROL_DURABLE = 1` iff Big400Pct(t+1) >= Big400Pct(t-1) for a positive strong inflow/reload candidate at t;
- t-time baseline: a current100 replication of the frozen CONTROL feature set and HGB model class, trained/calibrated in strict time order on the same eligible strong-inflow candidate population;
- early models: the same t-time CONTROL features plus only post-t daily/cross-stock evidence available at fixed h=1,2,3 trading-day checkpoints before t+1 ownership;
- no t+1 ownership input and no future destination ownership reconcentration.

This correction is forced by the frozen Pass-4 authority and does not change candidate gates, HGB parameters, calibration protocol, or numeric promotion criteria.

Replication boundary: historical original-V1 per-event `ControlProb` values are not present in the handoff/current100 artifacts. The Pass-4 baseline is therefore a current100 strict-time replication of CONTROL, not a claim of bit-identical historical V1 probabilities.
