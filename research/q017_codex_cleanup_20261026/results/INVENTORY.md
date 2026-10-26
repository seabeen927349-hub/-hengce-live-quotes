# Q017 inventory

Baseline: `780e8a225de637c32b42da0d28f5aa1428e49e20`. Scanned 166 code/workflow files; full definitions, local imports, source hashes and artifact literals are in `SOURCE_INVENTORY.json`.

Read `Q017_AUTHORITY_ROUTE_MAP.json` for every inventoried workflow and the capture → observation → validation → compute/rank → decision → display/output path. `DUPLICATE_AND_DEAD_CODE_MAP.json` records duplicate candidates and every deliberate non-refactor.

## Formal schema-5 path

Morning macro cache and prewarm snapshot → independent primary/backup supervisors → original v5 observation collector using v4/legacy transport helpers → immutable dated observation → frozen v5 decision builder → immutable dated decision → deterministic v5 guard → current-session formal output boundary → compatibility display/router. Recovery can promote an already preserved valid backup; it cannot fetch replacement quotes.

The 09:01 lane still uses the existing TWSE MIS contract and retry window. No model/cache/transport/capture/recovery mathematics changed. Positive-beta eligible quote rows require 100% completeness. A row without an opening price is causal unopened-market state, not permission to backfill.

## Distinct daily candidate bridge

The daily canonical producer uses top1, daily electronics residuals, no DXY and H20; schema-5 uses top3, immutable opening evidence, the frozen DXY gate and H10 research horizon. These are not interchangeable. Legacy geometry is not a candidate source. A daily bridge without exact schema-5 observation/decision bindings cannot produce formal action; it remains available internally for research.

## Coupling and legacy state

v5 → v4 → legacy decision helpers → public command-center data helpers → retained legacy core. This is live dependency reuse, so old filenames are not dead-code evidence. Former v3/v4 guard aliases and old radar outputs cannot satisfy the schema-5 output gate. The legacy public radar kill switch stays enabled. E2/NOVA/V43/W1/Q1/M1 and other retained experiment files remain audit/research only.

Router health reads were an observability dependency rejected by the existing producer audit; the formal router now emits an observability-only placeholder. Health output does not select or authorize stocks.

## Ownership and replay risks

Root `latest.json` and `live/active.json` are quote transport. Radar `latest.json`, `observation_latest.json` and `decision_latest.json` are projections/pointers. Current dated observation/decision files and their bound hashes control authority. Stale pointers cannot select a prior session or override a current valid decision. Publication receipts must bind the complete transaction and its freshness.

Monitor payloads previously could retain ticker order while changing scores or market state; the guard now checks all immutable decision fields. The frozen builder is shared by deterministic replay and production; profiling observes its full candidate list rather than implementing a second ranking formula.

## Files by role

| Path | Role |
|---|---|
| `.github/workflows/fugle-live-quotes.yml` | WORKFLOW |
| `.github/workflows/hengce-daily-command-center.yml` | WORKFLOW |
| `.github/workflows/hengce-data-vessel-health.yml` | WORKFLOW |
| `.github/workflows/hengce-detached-launcher-test.yml` | WORKFLOW |
| `.github/workflows/hengce-dual-engine-display-refresh.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-morning-backup.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-no-fill-ci.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-pit-diagnose.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-live.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-macro.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-membership-v2.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-membership.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-round2-masks.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-round2-retry.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-profit-max-round2.yml` | WORKFLOW |
| `.github/workflows/hengce-e2-round2-macro-flags.yml` | WORKFLOW |
| `.github/workflows/hengce-electronics-live-coverage-ci.yml` | WORKFLOW |
| `.github/workflows/hengce-engineering-replay.yml` | WORKFLOW |
| `.github/workflows/hengce-eod-complete-ingest-20261015.yml` | WORKFLOW |
| `.github/workflows/hengce-eod-complete-ingest-20261019.yml` | WORKFLOW |
| `.github/workflows/hengce-eod-download-20261020.yml` | WORKFLOW |
| `.github/workflows/hengce-eod-partial-ingest-20261014.yml` | WORKFLOW |
| `.github/workflows/hengce-export-full-package.yml` | WORKFLOW |
| `.github/workflows/hengce-full-market-shadow-smoke.yml` | WORKFLOW |
| `.github/workflows/hengce-full-market-shadow.yml` | WORKFLOW |
| `.github/workflows/hengce-governance-freeze.yml` | WORKFLOW |
| `.github/workflows/hengce-intraday-action-board-test.yml` | WORKFLOW |
| `.github/workflows/hengce-intraday-handoff-runner-test.yml` | WORKFLOW |
| `.github/workflows/hengce-intraday-hard-bind-bundle.yml` | WORKFLOW |
| `.github/workflows/hengce-lane-coherence-repair.yml` | WORKFLOW |
| `.github/workflows/hengce-live-overlay-artifact.yml` | WORKFLOW |
| `.github/workflows/hengce-live-overlay-export.yml` | WORKFLOW |
| `.github/workflows/hengce-live-universe-authoritative-handoff.yml` | WORKFLOW |
| `.github/workflows/hengce-margin-compact-rescue-20261014.yml` | WORKFLOW |
| `.github/workflows/hengce-margin-rescue-20261014.yml` | WORKFLOW |
| `.github/workflows/hengce-phase1-foundation.yml` | WORKFLOW |
| `.github/workflows/hengce-q012-microstructure.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-authority-guard.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-backup-observer.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-coverage-semantics-repair.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-dxy-source-smoke.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-hypothetical-open-reconstruction.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-infrastructure-selfverify.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-macro-cache.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-primary-observer.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-prospective-characterization.yml` | WORKFLOW |
| `.github/workflows/hengce-q017-recovery.yml` | WORKFLOW |
| `.github/workflows/hengce-recovery-fault-tests.yml` | WORKFLOW |
| `.github/workflows/hengce-system-health.yml` | WORKFLOW |
| `.github/workflows/hengce-tdcc-51w-pit-rebuild.yml` | WORKFLOW |
| `.github/workflows/hengce-tdcc-blank-historical-probe.yml` | WORKFLOW |
| `.github/workflows/hengce-unified-q017-integration.yml` | WORKFLOW |
| `.github/workflows/hengce-v43-daily-screen.yml` | WORKFLOW |
| `.github/workflows/hengce-writer-race-tests.yml` | WORKFLOW |
| `.github/workflows/q017-2026-sox-electronics-research.yml` | WORKFLOW |
| `patch/INSTALL_HENGCE_INTRADAY_HARD_BIND.sh` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/e2_profit_max/acquire_macro_q017_sources.py` | Q017_RUNTIME_OR_BOUNDARY |
| `research/e2_profit_max/acquire_pit_electronics_membership.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/e2_profit_max/acquire_pit_electronics_membership_v2.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/e2_profit_max/round2/build_candidate_macro_masks.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/e2_profit_max/round2/run_round2_finite.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase1_audit/inventory.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase1_audit/ledger.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase1_audit/scope_guard.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase1_audit/test_foundation.py` | OFFLINE_TEST_OR_AUDIT |
| `research/phase2_governance/checkpoint.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase2_governance/freeze.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase2_governance/governance.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase2_governance/ledger_store.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/phase2_governance/test_governance.py` | OFFLINE_TEST_OR_AUDIT |
| `research/phase2_governance/test_p2a_authorization.py` | OFFLINE_TEST_OR_AUDIT |
| `research/phase2_q017/guard.py` | Q017_RUNTIME_OR_BOUNDARY |
| `research/phase2_q017/run_characterization.py` | Q017_RUNTIME_OR_BOUNDARY |
| `research/q012/HENGCE_MICROSTRUCTURE_FEATURES_v0_1.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/q012/HENGCE_MICROSTRUCTURE_FEATURES_v0_2.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `research/q012/test_microstructure_features.py` | OFFLINE_TEST_OR_AUDIT |
| `research/q017_sox_tw_electronics/acquire_official_pit.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/CHECK_HENGCE_RUN.sh` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/RUN_HENGCE.sh` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/RUN_HENGCE_COMPLETE.sh` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/RUN_INTRADAY_ACTION_BOARD.sh` | FORMAL_OUTPUT_SURFACE |
| `scripts/RUN_IN_WORK_DETACHED.sh` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/apply_20261019_lane_coherence_repair.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/apply_20261019_q017_coverage_semantics_repair.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/check_live_q017_authority_overlay.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_daily_command_center.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_daily_command_center_core_legacy.py` | LEGACY_DATA_LIBRARY_RETAINED |
| `scripts/hengce_dual_engine_display.py` | FORMAL_OUTPUT_SURFACE |
| `scripts/hengce_e2_live.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_electronics_live_coverage.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_eod_guarded_ingest.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_eod_incremental_ingest.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_full_market_shadow.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_health_collect_runs.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_intraday_action_board.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_live_quote_transport.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_live_trial_guard.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_live_universe_guard.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_live_universe_handoff.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_market_session_guard.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_publish.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_q017_10d_review.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_10d_review_extension.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_authority_guard.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_authority_guard_v4.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_authority_guard_v5.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_backup_observer_v5.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_canonical_producer.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_decision_lock.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_decision_lock_v4.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_formal_output.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_hypothetical_open_reconstruction.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_macro_cache_v1.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_observation_lock_v5.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_observer_supervisor_v1.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_observer_supervisor_v2.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_only_runner.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_premarket_snapshot_v1.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_q017_recovery_compute_v5.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_recovery_transaction.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_scan_once_router.py` | FORMAL_OUTPUT_SURFACE |
| `scripts/hengce_system_health.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_three_line_resonance.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_total_scoreboard.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_twse_calendar.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_unified_action_board.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_unified_candidate_adapter.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_unified_contracts.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_unified_q017_admission.py` | Q017_RUNTIME_OR_BOUNDARY |
| `scripts/hengce_unified_runner.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_unified_scan_display.py` | FORMAL_OUTPUT_SURFACE |
| `scripts/hengce_v43_daily_screen.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_v43_history_sync.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/hengce_v43_publish.py` | OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE |
| `scripts/test_hengce_dual_engine_display_hard_lock.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_e2_morning_release.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_e2_no_fill.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_eod_original_vessel_incremental.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_q017_adversarial_v4.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_q017_canonical_producer.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_q017_decision_lock.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_q017_observer_resilience_v1.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_q017_resilience_v5.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_reporting_v23.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_twse_calendar.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_unified_boundaries.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_unified_q017.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_unified_q017_admission.py` | OFFLINE_TEST_OR_AUDIT |
| `scripts/test_hengce_unified_runtime.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/health_dependency_audit.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/q017_cleanup_audit.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/q017_cleanup_inventory.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/recovery_topology.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/replay_equivalence.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/replay_equivalence_single_hengce.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_health_dependency_audit.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_q017_cleanup.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_q017_operational_boundary.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_recovery_base_characterization.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_recovery_faults.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_recovery_workflows.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_replay_workflow.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_system_health.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_writer_races.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/test_writer_workflows.py` | OFFLINE_TEST_OR_AUDIT |
| `tests/engineering/writer_topology.py` | OFFLINE_TEST_OR_AUDIT |
