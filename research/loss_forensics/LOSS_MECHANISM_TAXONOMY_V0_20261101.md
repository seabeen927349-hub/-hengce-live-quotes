# HENGCE LOSS FORENSICS — Loss Mechanism Taxonomy V0
Date: 2026-11-01
Status: RETROSPECTIVE_FORENSIC_WORKING_MAP
Trading authority: NONE

## Core question
What observable sequence explains why a holder loses money, without assuming that every large holder or institution is always correct?

## Initial answer
The strongest current explanation is not simply `smart money was wrong` and not simply `large holders sold`.

The recurrent damaging sequence is:

1. **Strong inventory forms** — ownership concentrates in Big400/Big1000 or another credible strong layer while weak leverage is reduced or absorbed.
2. **Price becomes attractive/strong** — the stock reprices or rallies.
3. **Financing quality changes** — the original strong layer stops adding or starts leaking inventory while margin/other weaker buyers become increasingly important.
4. **Outward transfer occurs** — ownership migrates from stronger hands to weaker or more leveraged hands.
5. **Repair test fails** — the original or replacement strong layer does not promptly rebuild ownership.
6. **Price support disappears under stress** — once marginal buying weakens, the stock no longer has the ownership structure that supported the earlier repricing.
7. **Late holder realizes loss** — the buyer who interpreted price strength as continuing information quality is left holding inventory transferred from the earlier strong cohort.

## Why first outflow alone is insufficient
Counterexamples exist.

### 2408 repair
- 2026-05-22: Big400 and Big1000 fall sharply; institutions also sell.
- 2026-05-29: Big400/Big1000 rebuild strongly and foreign/institutional support returns while margin falls.
- Interpretation: first outflow was not durable abandonment.

### 8021 repair
- 2026-06-18: Big400/Big1000 outflow.
- 2026-06-26: strong ownership returns, institutions are positive, leverage remains lower.
- Interpretation: ownership repaired; first outflow alone would create false SELL attribution.

Therefore the key forensic split is:

`OUTFLOW -> REPAIR` versus `OUTFLOW -> FAILED REPAIR`.

## Clean failure examples
### 6415 — euphoria handoff
- 2026-06-12: price weak; Big1000 +~5.48m shares; margin -8.89%. Strong ownership reconcentrates during fear.
- 2026-06-15 to 06-18: price surges while foreign-identity accounts sell ~4.22m shares and margin rises sharply.
- 2026-06-18 ownership snapshot: price +29.16% week/week; Big400 -~3.36m; Big1000 -~4.77m; margin +31.29%; institutions net sell.
- Subsequent ownership does not immediately repair the earlier strong inventory state; large decline follows.

Interpretation: the loss is not caused by buying after obviously bad price action. The loss path is buying into attractive price action while strong inventory is being transferred outward and weak/leverage-funded demand becomes the marginal buyer.

### 6213 — control withdrawal
- 2026-06-26: strong new-control concentration; margin falls; Big400/Big1000 and foreign/institutional ownership rise sharply.
- 2026-07-03 onward: price remains elevated while margin grows, foreign/institutional sponsors sell, Big1000 stops adding and begins leaking.
- 2026-07-17 / 07-24: ownership withdrawal becomes much more visible as price collapses.

Interpretation: the behavioral change precedes the largest visible ownership collapse. Waiting for the final dump is too late for forensic understanding.

## Distinguish wrong thesis from transferred risk
A large holder can lose money. But we should not infer that from price alone.

Possible loss mechanisms include:
- thesis invalidation;
- forced deleveraging / VaR / redemption;
- sector or benchmark rotation;
- liquidity need;
- failed sponsor replacement;
- corporate event / fundamental deterioration;
- deliberate inventory transfer into stronger price;
- mechanical corporate-action distortion.

The forensic task is to classify which mechanism best fits the evidence, not to assume omniscient smart money.

## First operational conclusion
The most dangerous observable configuration is currently:

`previous strong ownership + attractive/accelerating price + original strong layer stops absorbing + leverage/weak-hand participation rises + no rapid ownership repair`.

This should be investigated as a **loss mechanism**, not converted directly into a trading rule.

## Required counterexample search
To avoid story-fitting, actively search for:
1. large-holder withdrawal + margin rise + continued durable gains;
2. large-holder retention + subsequent major losses;
3. apparent failed repair that later reverses;
4. strong ownership exit caused mainly by corporate actions or non-information liquidity events;
5. cases where fundamentals/events clearly explain the move better than ownership transfer.
