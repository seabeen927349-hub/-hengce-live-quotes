# HENGCE Daily H-Score Report Contract v1.0

Status: SHADOW / DISPLAY ONLY

## Daily Top3 block

|Rank|Ticker|Name|H-Score|Grade|Teacher|NEW|
|---:|---|---|---:|---|---|---|
|1|...|...|...|...|...|...|
|2|...|...|...|...|...|...|
|3|...|...|...|...|...|...|

Mandatory footer:

> H-Score is relative signal strength, not probability of profit. It does not change Top1, entry, exit, capital allocation, or switching.

## Position block

- CurrentPosition: <ticker/name or CASH>
- Dn: <D1..D11 or N/A>
- CapitalAvailable: <amount>
- CurrentPositionHScore: <score or N/A>
- TodayTop1HScore: <score or N/A>
- ScoreGapVsPosition: <today top1 - current position>
- Action: OBSERVE_ONLY

A large H-Score gap is information only. No switching is allowed unless a separate causal switching study is validated and explicitly promoted.

## Official H-Score components

- Market context: 25 points
- Q017 selection strength: 55 points
- Leader separation: 20 points

Each component must be converted from a point-in-time percentile using only observations strictly earlier than the scored date.

## Teacher context

Display-only tag based on prior-known foreign investor, investment trust and margin data. Preferred observed pattern from 2026 research:

- 外資賣／投信接／融資退

Teacher context is not included in the official 0-100 H-Score until it passes a separate promotion gate.

## Grades

- S: 90-100
- A: 80-89.9
- B: 70-79.9
- C: 60-69.9
- WEAK: below 60

## Governance guards

1. H-Score never creates candidates.
2. H-Score never changes the existing Top1 ranking.
3. H-Score never causes an automatic buy, sell, add, reduce or switch.
4. H-Score never uses future returns or future distribution data.
5. H-Score must show N/A when point-in-time calibration history is insufficient.
6. Teacher context remains display-only until causal and forward validation justify promotion.
