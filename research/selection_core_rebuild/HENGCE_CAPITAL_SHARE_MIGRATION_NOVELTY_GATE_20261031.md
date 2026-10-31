# HENGCE Selection Core Rebuild — Capital-Share Migration Novelty Gate

Date: 2026-10-31
Status: `NOVELTY_GATE_FAIL`
Forward-return test executed: `NO`
Preregistered challenger: `NO`
Trading / production authority: `NONE`

## Candidate examined

Draft idea: rank TWSE-listed electronics by the stock's share of total eligible-electronics trading value, and/or by persistent increases in that share, as a proxy for capital migration into the stock.

This document records a pre-forward-return novelty decision only. No candidate return was inspected to make this decision.

## Frozen legacy comparison

Immutable historical source snapshot:
- repository: `seabeen927349-hub/-hengce-live-quotes`
- commit: `b5e53bc459d216958893c6b0fd28eb6f5ab8c70f`

V6 factor space recovered from `ranking_v41_expanding_regime_ic.py` and `ranking_v13_weak_regime_profiles.py`:
- `resid_rev`: 0.20
- `mom20`: 0.25
- `skip5_60`: 0.30
- `liquidity`: 0.05
- `lowvol`: 0.20

The V13 feature builder defines `liquidity = cross-sectional rank(turn20)`, where `turn20` is the stock's 20-session mean trading value among eligible stocks.

## Mathematical equivalence

For stock i on date t, define:

`share(i,t) = turnover(i,t) / sum_j turnover(j,t)`.

On a fixed date t, the denominator is identical for every stock, therefore:

`rank_i(share(i,t)) = rank_i(turnover(i,t))`.

So a cross-sectional capital-share level factor is exactly redundant with a turnover-level rank. It is not a new information family.

For fixed lookback L:

`share(i,t) / share(i,t-L)`
`= [turnover(i,t) / turnover(i,t-L)] / [market_turnover(t) / market_turnover(t-L)]`.

At a fixed evaluation date, the market-wide denominator is common across stocks. Therefore cross-sectional ranking of share growth is equivalent to ranking individual turnover growth over the same lookback. Daily share-rank persistence is likewise turnover-rank persistence because the two ranks are identical on every date.

## Existing graveyard evidence

Research Ledger R-017 (`Liquidity-adjusted Price Impact Collapse v0.1`) already tested a turnover-shock construction (`turnover / ADV20`) together with price state. Its raw pattern looked strong, but after controlling for same-day return rank, 20-day return rank, turnover-shock rank and liquidity rank, monotonicity disappeared in discovery and validation. R-017 was frozen as `KILL AS INCREMENTAL ENGINE / CONTEXT ONLY`.

The Research Ledger information-family registry also classifies Volume/Liquidity — volume, turnover, ADV and liquidity percentile — as one existing, correlated information family, with the permanent rule that the hard-gate thesis is killed and this family is primarily context/capacity unless a genuinely orthogonal mechanism appears.

## Decision

`CROSS_STOCK_CAPITAL_SHARE_MIGRATION_DRAFT = NOVELTY_GATE_FAIL`

Reason:
1. share level is mathematically identical to turnover level for cross-sectional ranking;
2. share growth is a market-normalized turnover-growth transform, not an independent source;
3. persistence remains a transform of the same Volume/Liquidity family;
4. R-017 already demonstrates the central failure mode: apparent turnover/impact alpha can vanish after controlling momentum and liquidity;
5. renaming a Volume/Liquidity transform as "smart-money migration" would be narrative substitution for new information.

## Governance consequence

- Do not preregister this draft as a new challenger.
- Do not run forward returns for the purpose of rescuing it.
- Do not tune lookbacks, persistence counts, percentile thresholds, or market normalizations to create novelty after this verdict.
- V6 remains a frozen historical comparison only; this verdict does not revive V6 or V43.
- Next research lane must come from a genuinely different information family, with data availability and point-in-time integrity audited before any forward-return test.
