# HENGCE — Codex Data Foundation V2 continuation

## Authorization and mission

User continuation authorization: `繼續` on 2026-10-23 after reviewing Data Foundation V1 at head `0c24f9795e36b52e28eafed186eee5591ec93353`.

Continue the research program from the exact V1 head. This is a **research-only data-readiness stage**, not a profitability/model-search stage.

Primary mission:

> Resolve the corporate-action entitlement, security-identity, delivery/payment, and direction-aware execution evidence gaps that currently keep adjusted-return research at `BLOCKED_DATA_READINESS`.

Do not retroactively rescue, rewrite, delete, or reclassify any of the 8,529 prior model evaluations. Do not promote any old apparent winner.

## Frozen parent

- Parent research head: `0c24f9795e36b52e28eafed186eee5591ec93353`
- Parent Data Foundation V1: `research/codex_full_reset_20261023/data_foundation_20261023/`
- Parent readiness: `BLOCKED_DATA_READINESS`
- Cumulative prior model evaluations: `8529`
- New model-evaluation budget for this stage: **0**
- Production authority: **none**

Do not silently rebase onto moving `main` or import later live observations into historical evidence.

## Authority boundary

- `research_only = true`
- `signal_authority = false`
- `ranking_authority = false`
- `capital_authority_twd = 0`
- `broker_order_execution = false`
- `production_promotion = false`
- `merge_authorized = false`
- no main push
- no production schedule change
- no Q017/E2/M1 production semantic change
- no live producer change

Use **free official sources only**. No paid datasets, account purchases, broker credentials, private data, access-control bypass, CAPTCHA bypass, or rate-limit evasion.

## Before any new network collection

Create and push a frozen machine-readable plan before collection begins. The plan must contain:

1. exact parent commit and tree;
2. exact source endpoints/document families intended;
3. finite request budget or deterministic batching rule;
4. retry, spacing, timeout, and failure-retention policy;
5. exact normalized schema;
6. stop conditions;
7. zero model-trial budget;
8. authority statement.

If official source discovery is needed, retain discovery probes separately from the preregistered collection and do not relabel them as historical first-seen evidence.

## Workstream A — classify all retained PIT electronics actions

Start from the already retained **1,151 exact-PIT electronics events** from V1. Do not recollect them unless byte-equivalence or source correction is specifically required.

For every event, produce a deterministic classification at minimum:

- cash dividend;
- stock dividend / free shares;
- rights / paid subscription;
- capital reduction — cash return;
- capital reduction — loss absorption / no cash;
- split / reverse split / share conversion;
- merger / delisting / relisting / ticker or security-identity transition;
- suspension/resumption associated with action;
- mixed action;
- unknown / insufficient schema.

Preserve source row identity, effective/ex date, ticker, PIT membership evidence, source hash, and parsing version.

Never infer missing numeric terms as zero.

## Workstream B — entitlement ledger

Build a normalized append-only entitlement ledger. For each event, include fields where official evidence exists:

- old security identity;
- new security identity, if any;
- effective/ex date;
- last trading date before action, if applicable;
- resumption/listing date, if applicable;
- cash entitlement per old share;
- free/new shares per old share;
- paid-subscription shares per old share;
- subscription price;
- subscription/payment deadline;
- cash payment date;
- new-share delivery/listing/saleable date;
- fractional-share treatment;
- tax/withholding only if the historical research contract requires it and official evidence supports it;
- source document/endpoint;
- source publication/printed date;
- original first-seen timestamp only when actually proven;
- revision/supersession lineage only when actually proven;
- confidence/status: `PROVEN`, `PARTIAL`, `UNKNOWN`, `CONFLICT`.

Do not convert an ex-right reference-price ratio into an entitlement factor unless the underlying terms prove it.

Do not assume cash or shares are immediately reinvestable or saleable on the ex date.

## Workstream C — security identity continuity

Build an explicit identity-transition table for every retained event that changes share count, ticker, listing identity, or tradable instrument continuity.

Requirements:

- distinguish economic continuity from exchange-symbol continuity;
- preserve old/new security IDs and dates;
- prove 2327-style conversions from official evidence rather than price ratios;
- do not map delisted/relisted names using current security masters as historical substitutes;
- no survivorship/current-universe fallback.

If a transition cannot be proven, mark it `UNKNOWN` and keep dependent PnL blocked.

## Workstream D — historical impact map

Create a deterministic map from corporate-action/suspension events to every historical research trade/outcome window used in the 8,529 retained evaluations.

The map must answer:

- which event intersects an entry date;
- which event intersects a holding period;
- which event intersects an exit date;
- whether the affected trial currently uses raw price movement, censoring, or missing-data handling;
- what exact entitlement/identity field is required to make that observation research-valid.

This impact map is diagnostic only. It must **not** rewrite old trial returns or statuses.

Use it to prioritize official-detail retrieval when full-market detail coverage is expensive or unavailable, while still reporting global coverage honestly.

## Workstream E — direction-aware one-price / limit execution evidence

V1 proved 26 unique 2025-04-07 one-price cases equal the official lower limit. V2 must separate **market-state diagnosis** from **order execution proof**.

For every affected observation, retain at minimum:

- buy vs sell direction;
- intended decision timestamp;
- intended order type and price assumption from the historical research contract;
- official opening/reference price and price limits;
- official daily traded volume;
- any free official opening-auction matched volume / allocation / quote evidence that actually exists;
- whether a specified order fill is `PROVEN`, `DISPROVEN`, or `UNKNOWN`.

Hard rule:

- `one price at lower limit` is **not** universal no-fill evidence for a buy;
- daily volume is **not** proof that the simulated order received allocation;
- no queue priority, depth, timestamp, or capacity may be invented.

If a complete free official historical auction archive cannot be established, preserve `UNKNOWN` and design future model research around an explicitly preregistered conservative execution contract.

Do not retroactively alter the old symmetric censor in this stage.

## Workstream F — adjusted-return state machine

Implement a research-only adjusted-return/entitlement state machine **only if** the required fields are proven.

It must distinguish at least:

1. ordinary price return;
2. cash receivable not yet paid;
3. stock entitlement not yet delivered/saleable;
4. subscription right requiring cash and a deadline;
5. suspension/no tradable price;
6. old security converted into new security;
7. unresolved action -> block observation.

No guessed prices, zero-fills, immediate reinvestment, or same-day sale of undelivered shares.

The state machine must fail closed on missing or conflicting entitlement/identity evidence.

## Readiness gates

Do **not** start a new model study unless a new `READINESS_V2.json` proves the selected study specification can be evaluated without fabricating corporate-action or execution outcomes.

At minimum report separately:

- global 1,151-event term coverage;
- global delivery/payment-date coverage;
- security-identity continuity coverage;
- historical-trial impact coverage;
- entry/exit observations still blocked by action terms;
- observations still blocked by execution uncertainty;
- historical first-seen/revision coverage;
- whether any future study can legally use adjusted PnL under a narrower explicitly frozen scope.

Possible statuses:

- `BLOCKED_DATA_READINESS`
- `PARTIAL_SCOPE_READY`
- `READY_FOR_PREREGISTERED_RESEARCH`

`PARTIAL_SCOPE_READY` must name the exact admissible dates/securities/action types and cannot silently drop adverse or inconvenient cases after seeing model outcomes.

## Testing and audit requirements

Add fully synthetic/offline tests for at least:

- mixed cash + stock entitlement;
- stock dividend with delayed delivery;
- paid subscription requiring cash;
- cash capital reduction;
- no-cash capital reduction;
- split / conversion old-to-new identity;
- suspension spanning an intended exit;
- unknown payment/delivery date blocks reinvestment;
- current security-master substitution rejected;
- event-detail mismatch rejected;
- duplicate/conflicting official terms fail closed;
- direction-aware lower-limit buy vs sell semantics;
- daily volume does not become proof of order allocation;
- old 8,529 experiment ledger bytes/statuses remain unchanged;
- zero new model evaluations;
- zero production authority.

Run all inherited relevant offline audits/regressions and report exact pass/fail counts. CI must not recollect live official data or launch model trials.

## Required V2 deliverables

Create a new versioned directory, for example:

`research/codex_full_reset_20261023/data_foundation_v2_20261023/`

Include at minimum:

1. `PLAN_V2.json`
2. `EVENT_CLASSIFICATION.jsonl`
3. `ENTITLEMENT_LEDGER.jsonl`
4. `IDENTITY_TRANSITIONS.jsonl`
5. `HISTORICAL_IMPACT_MAP.jsonl`
6. `EXECUTION_EVIDENCE.jsonl`
7. `COVERAGE_V2.json`
8. `READINESS_V2.json`
9. `REPORT.md`
10. raw/receipt/hash manifests for any new official-source collection
11. offline tests and a one-command audit entrypoint

## Stop conditions

Stop and report instead of inventing evidence if:

- official detail coverage is unavailable without paid/private access;
- payment or share-delivery timing cannot be proven;
- historical identity continuity cannot be proven;
- source schemas conflict and cannot be reconciled from official evidence;
- order allocation/fill cannot be established;
- the only way to declare readiness is to assume immediate entitlement availability, guessed adjustment factors, or guessed fills;
- prior experiment history would need to be rewritten;
- trial accounting or evidence hashes become incomplete.

## Completion standard

A successful V2 does **not** need to declare the data fully ready. A scientifically valid result may remain `BLOCKED_DATA_READINESS` if official evidence is incomplete.

The valuable outcome is a narrower, auditable statement of exactly which historical observations are valid, which are blocked, why they are blocked, and what future preregistered model study can be run without hindsight or fabricated execution.

**PRODUCTION MODEL CHANGES: NONE.**
