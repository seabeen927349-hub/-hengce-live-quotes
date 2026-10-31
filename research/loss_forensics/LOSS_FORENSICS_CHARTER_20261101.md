# HENGCE LOSS FORENSICS — Research Charter
Date: 2026-11-01
Branch: `research/loss-forensics-20261101`
Status: ACTIVE_RESEARCH
Trading authority: NONE

## Objective
Answer a different question from Selection Core:

> How does capital actually lose money in Taiwan equities, and what observable sequence distinguishes a temporary adverse move from genuine thesis/control failure?

The target is explanation / forensic attribution, not a production model.

## Evidence scope — OPEN
All legitimately obtainable evidence may be used, including:
- raw and corporate-action-adjusted price/volume;
- intraday/realtime quotes and transaction statistics when available;
- TDCC shareholder distribution across holder tiers, Big400/Big1000, holder counts and shares;
- margin financing / short balances;
- institutional trading, including foreign/trust/dealer and aggregate flows;
- broker branch / main-broker / single-broker histories and concentration/Gini where available;
- major announcements, MOPS disclosures, corporate actions, insider transfer filings;
- revenue, income statement, balance sheet, cash flow, profitability, working-capital and capital-expenditure data;
- supply-chain / sector / market regime context;
- news and public event chronology;
- Fugle content APIs and other official/public sources;
- forward returns and failed cases.

No information family is excluded merely because it was previously unsuitable for a pristine Selection challenger.

## What is deliberately NOT required
- no requirement to produce a model;
- no requirement for a single formula or threshold;
- no requirement to preserve untouched OOS data inside this forensic lane;
- no ban on looking at failed cases or forward outcomes;
- no ban on combining price, ownership, leverage, broker, fundamental and event evidence;
- no requirement that one observable identity equals one true controller.

## Non-negotiable evidence discipline
These are not modeling restrictions and remain mandatory:
1. Do not fabricate unavailable data.
2. Tag observation time separately from event/snapshot date; never represent later-known evidence as contemporaneously known.
3. Correct or explicitly censor corporate-action mechanical effects before interpreting price stress or holder-tier migration.
4. Distinguish fact, inference and causal claim.
5. Missing retrieval is `DATA_UNAVAILABLE/RETRIEVAL_BLOCKED`, not evidence of absence.
6. A retrospective explanation is not automatically a prospective trading rule.

## Primary forensic object
Do not begin from labels such as foreign/trust/dealer. Reconstruct the inventory lifecycle:

`inventory capture -> control/retention -> price financing -> outward transfer/repair -> stress -> abandonment or recovery -> realized loss`

Key questions:
- Who/which observable holder layer is absorbing inventory?
- Is leverage being removed or becoming the marginal buyer?
- When price rises, does strong ownership remain, rotate within strong layers, or leak outward?
- After the first apparent distribution, is ownership repaired?
- When price turns adverse, does the prior ownership regime defend, rotate, or abandon?
- Was the loss caused by wrong thesis, wrong timing, weak financing, liquidity, forced selling, corporate event, or buying another cohort's exit?

## Initial working hypothesis
The leading mechanism to investigate is not simply `smart money was wrong`.

A recurring loss path already visible in existing HENGCE evidence is:

`strong-hand accumulation -> attractive/accelerating price -> strong-hand leakage -> leverage/weaker buyers take inventory -> ownership repair fails -> price support disappears -> late holder realizes loss`.

This remains a hypothesis until tested across broader cases and alternative explanations.

## Immediate data agenda
1. Reconstruct full 2026 ownership/price/leverage/institutional timelines for known contrasting cases: 6415, 6213, 2408, 8021, 6782.
2. Add corporate-action-continuous price series to prevent fake stress signals.
3. Pull Fugle-accessible datasets where retrieval works: 15y price, adjusted price, 3-4y institutions, 6m margin, 1y TDCC, main broker, 240d single broker, 240d broker Gini, disclosures, insider transfer and financial statements.
4. Build loss episodes from realized peak-to-trough / entry-to-exit outcomes, then classify the observable inventory path without optimizing a score.
5. Search explicitly for counterexamples: ownership withdrawal followed by recovery, leverage expansion followed by continued gains, and strong-holder retention followed by losses.

## Separation from Selection Core
Existing Selection Core governance and preregistrations remain unchanged on their branch. This forensic lane may inspect forward outcomes and post-event evidence because its purpose is explanation rather than pristine alpha validation.
