# HENGCE governed FinMind private single-name quote delivery (research, 2026-11-04)

## Verified scope
- The existing, scheduled `.github/workflows/hengce-escape-twse-full-market-finmind-shadow.yml` already reads one paid FinMind `taiwan_stock_tick_snapshot` snapshot into GitHub Actions memory. **Do not create a second quote fetcher.**
- `hengce_finmind_single_name_bridge.lookup(snapshot_map, ticker, now, allowed_codes)` extracts any stock whose membership was verified against official current TWSE, TPEx or Emerging issuer rosters.
- Reject missing, wrong ticker, stale >480 s, prior-market-date, bad timestamp, nonexistent price. Market State remains governed by its *separate* frozen TWSE-only v0.5 contract.
- The public workflow and GitHub repo contain only aggregate market statistics and redacted private delivery status; never vendor individual quote prices or keys.

## This PR's secure delivery components
1. `scripts/hengce_finmind_private_delivery.py`: **opt-in**, owner-approved signed HTTPS POST. Disabled unless endpoint, 24+ char bearer, 32+ char HMAC key, and exact approval are present. Rejects insecure URLs, redirects, and non-202 receipts. No network request if not configured.
2. `scripts/hengce_escape_finmind_twse_common_shadow.py`: integrates that delivery from the **same single** FinMind snapshot, in process. Provider data never goes into an artifact or publicly readable quote JSON.
3. `scripts/hengce_finmind_private_receiver.py`: executable **reference** private receiver, binds 127.0.0.1:8787 behind owner-controlled HTTPS reverse proxy. In-memory only, HMAC verification, 480 s source freshness checks, nonce replay defense, separate read key, no access logs.
4. `.github/workflows/hengce-escape-twse-full-market-finmind-shadow.yml`: protected default-disabled secrets settings in existing runner; secrets are **not** made available to pull-request jobs.
5. Offline synthetic tests: lookup, cross-board official issuer roster, sender, receiver, and 3042/3420 end-to-end delivery.

## Explicit setup still required; no automatic rollout
1. Owner must obtain independent confirmation the FinMind paid terms allow the intended **private personal-use** delivery. Merely having a FinMind account does not prove redistribution rights.
2. Owner must provision a secure private receiver and TLS termination, and ensure it is authenticated, reachable only by authorized clients, and appropriately hardened. **No receiver is deployed by this PR.** Never expose port 8787 directly to the Internet.
3. Set GitHub Actions encrypted repo secrets `HENGCE_PRIVATE_QUOTE_ENDPOINT`, `HENGCE_PRIVATE_QUOTE_BEARER`, `HENGCE_PRIVATE_QUOTE_HMAC_KEY`; store `HENGCE_PRIVATE_QUOTE_READ_KEY` on the receiver only. Configure GitHub Actions repository variable `HENGCE_PRIVATE_QUOTE_LICENSED_PRIVATE_USE_APPROVED=I_CONFIRM_AUTHORIZED_PRIVATE_USE` only after owner approval. **Do not paste any key or quote payload into a chat, issue, PR, artifact or public repo.**
4. Perform an authorized end-to-end real-time market-session test and validate the receiver's `GET /hengce/v1/quotes/3042` and `GET /hengce/v1/quotes/3420` from an authenticated **private** client. Never accept a quote older than 480 s or from a prior session.
5. To read from **ChatGPT**, the owner also needs a connected, approved private app/plugin supporting authenticated queries to the receiver; the current GitHub connector only sees public project files, not runner memory or the private endpoint. **This PR cannot grant a ChatGPT network capability by itself.**
6. Governance / deployment gates: designated approved private recipient, successful CI with no newly caused failures, verified source field semantics, and a successful live end-to-end test. Do not merge this draft PR until those gates are met.

## Authority and containment
- No new quote-collection path, new mother, altered EOD three legs, altered Selection Core, altered frozen Market State, or trading/capital authority.
- Do not reactivate Q017; unrelated prior engineering tests that fail against absent main-branch files are not bypassed.
- Public `legacy_live/quotes/3042.json` remains the existing Fugle historical snapshot, not private FinMind live data.
- A private receiver is a temporary *transport destination*, not a canonical market-data corpus or substitute for the EOD mother. Values auto-expire and the receiver does not write disk.
- No automatic broker order placement, live trading signal or market prediction is created.

## Current honest status
**Code/test phase only.** Until a private receiver is provisioned, licensed private delivery is confirmed, secrets are installed, and a ChatGPT-connected authenticated read interface is active, the command `衡策晶技` **cannot** truthfully present the private FinMind real-time price.
