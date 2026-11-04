# HENGCE FinMind single-name bridge — 2026-11-04 (research only)

## Purpose
One query interface for any currently governed TWSE listed ordinary stock (e.g. 3042, 2330, 2408) **inside the already existing FinMind full-market snapshot vessel**.

## Actual implementation
- `scripts/hengce_finmind_single_name_bridge.py`: `lookup(snapshot_map, ticker, now, allowed_tickers)` returns an **in-memory ephemeral** quote or a concrete fail-closed reason; it makes zero provider calls and writes no files.
- `scripts/hengce_escape_finmind_twse_common_shadow.py`: uses the *same* `taiwan_stock_tick_snapshot` snapshot already fetched once, and exposes an **optional synchronous in-process `private_quote_consumer` hook** to trusted private execution. The default/public workflow has no private consumer.
- The public status exposes only small aggregate coverage/health counters, with **no paid prices, individual quote payloads, trading signals or raw FinMind records**.
- `.github/workflows/hengce-escape-twse-full-market-finmind-shadow.yml` compiles and runs synthetic, network-free tests before the existing monitor pipeline.
- `tests/engineering/test_hengce_finmind_single_name_bridge.py`: multiple names in one snapshot, invalid codes, outside-universe, missing, stale >480 seconds, prior-day, bad prices, timezone.

## Governance / non-promotion
- This is *not* a new collector, second mother, new universe or direct provider fetch.
- Does not modify original EOD 3 legs, Market State freeze, Frozen V1, Selection Core, Q017, or authority/promotion.
- Existing `HENGCE_DATA_VESSEL_PRIORITY_LOCK_v1_20261103` and `HENGCE_MARKET_DATA_PROVIDER_SCOPE_LOCK_v1_20261104` still apply.
- Existing Market State FinMind v0.5 contract disallows public per-security vendor persistence; this work does not relax it.
- Paid quote values are only held in process memory, *not* written to the public GitHub repo or CI artifacts.
- A stock's availability in the snapshot does not imply it is entitled for distribution or use for trading/model authority.
- No live price may be asserted unless validated for today's date and within **480 seconds** of source timestamp.

## What is NOT yet done
- No private/authorized network or connector interface currently permits ChatGPT to read the runner's in-memory quote. ChatGPT cannot truthfully show live 3042 yet.
- No live-data test with the private consumer has passed. Synthetic adapter and CI checks are separate from a real paid-source verification.
- Do not promote to main or advertise an operational real-time quote service without (a) CI PASS, (b) actual FinMind runner snapshot PASS, (c) confirmed licensed secure private recipient, and (d) a real end-to-end request with fresh quote age <= 480 sec.
- The existing public `legacy_live/quotes/3042.json` is still Fugle prior-day data; **do not overwrite it with paid FinMind rows**.

## Next operational step
Configure a license-compliant, access-controlled private recipient in the existing HENGCE execution architecture and call `private_quote_consumer` synchronously during that execution. Verify source fields, 480s TTL, no public persistence, E2E data flow, then approve a separately governed rollout. No external ad-hoc download is authorized.
