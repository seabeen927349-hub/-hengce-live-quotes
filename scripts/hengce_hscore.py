#!/usr/bin/env python3
"""HENGCE H-Score report-layer utility.

H-Score compares relative signal strength. It has NO selection, entry, exit,
capital-allocation, or switching authority.

Percentiles passed here must be produced point-in-time from observations strictly
before the scored date. This module intentionally does not inspect future returns.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class HScoreInput:
    market_percentile: float
    selection_percentile: float
    leader_separation_percentile: float
    foreign_net: Optional[float] = None
    trust_net: Optional[float] = None
    margin_balance_change: Optional[float] = None


@dataclass(frozen=True)
class HScoreResult:
    hscore: float
    grade: str
    market_points: float
    selection_points: float
    leader_points: float
    teacher: str
    teacher_shadow_points: Optional[float]
    authority: str = "DISPLAY_ONLY"
    label: str = "H-Score is relative signal strength, not probability of profit."

    def to_dict(self):
        return asdict(self)


def _clamp01(x: float) -> float:
    if x is None:
        raise ValueError("percentile cannot be None")
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise ValueError(f"percentile outside [0,1]: {x}")
    return x


def grade(score: float) -> str:
    if score >= 90.0:
        return "S"
    if score >= 80.0:
        return "A"
    if score >= 70.0:
        return "B"
    if score >= 60.0:
        return "C"
    return "WEAK"


def teacher_context(foreign_net, trust_net, margin_balance_change):
    """Return human-readable teacher context and a DISPLAY-ONLY shadow score.

    The only teacher pattern retained from 2026 causal research is:
    foreign sells + trust buys + margin declines. It remains too weak to alter
    trading decisions, so shadow points never enter the official H-Score.
    """
    if foreign_net is None or trust_net is None or margin_balance_change is None:
        return "N/A", None

    f = float(foreign_net)
    t = float(trust_net)
    m = float(margin_balance_change)

    if f < 0 and t > 0 and m < 0:
        return "外資賣／投信接／融資退", 20.0
    if f > 0 and t > 0 and m < 0:
        return "雙法人買／融資退", 15.0
    if f > 0 and t <= 0 and m < 0:
        return "外資買／投信未接／融資退", 10.0
    if f < 0 and t > 0 and m >= 0:
        return "外資賣／投信接／融資未退", 8.0
    if f > 0 and t > 0 and m >= 0:
        return "雙法人買／融資增", 6.0
    return "老師不同步", 0.0


def compute_hscore(x: HScoreInput) -> HScoreResult:
    mp = _clamp01(x.market_percentile)
    sp = _clamp01(x.selection_percentile)
    lp = _clamp01(x.leader_separation_percentile)

    market_points = 25.0 * mp
    selection_points = 55.0 * sp
    leader_points = 20.0 * lp
    score = round(market_points + selection_points + leader_points, 1)

    teacher, shadow = teacher_context(
        x.foreign_net, x.trust_net, x.margin_balance_change
    )

    return HScoreResult(
        hscore=score,
        grade=grade(score),
        market_points=round(market_points, 1),
        selection_points=round(selection_points, 1),
        leader_points=round(leader_points, 1),
        teacher=teacher,
        teacher_shadow_points=shadow,
    )


def top3_markdown_row(rank, ticker, name, result: HScoreResult, is_new: bool):
    return (
        f"|{rank}|{ticker}|{name}|{result.hscore:.1f}|{result.grade}|"
        f"{result.teacher}|{'NEW' if is_new else ''}|"
    )


def position_comparison(current_position_hscore, today_top1_hscore):
    """Reporting only. Never returns a switch instruction."""
    if current_position_hscore is None or today_top1_hscore is None:
        return {
            "score_gap_vs_position": None,
            "action": "OBSERVE_ONLY",
            "reason": "HSCORE_NOT_COMPLETE",
        }
    gap = round(float(today_top1_hscore) - float(current_position_hscore), 1)
    return {
        "score_gap_vs_position": gap,
        "action": "OBSERVE_ONLY",
        "reason": "HSCORE_HAS_NO_SWITCH_AUTHORITY",
    }


if __name__ == "__main__":
    # deterministic smoke example only; not a market prediction
    demo = compute_hscore(HScoreInput(0.80, 0.90, 0.75, -1, 1, -1))
    print(demo.to_dict())
