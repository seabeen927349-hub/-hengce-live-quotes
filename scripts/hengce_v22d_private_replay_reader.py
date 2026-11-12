#!/usr/bin/env python3
"""Read signed-source V2.2D PRIVATE retrospective receipts; never promote to live."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.hengce_v22d_private_original_inference import (
    PRICE_HASH, TDCC_HASH, MODEL_HASH, REG_HASH
)

TZ = ZoneInfo("Asia/Taipei")


def read_private_replay(path=None, now=None):
    now = now or dt.datetime.now(TZ)
    now = (now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
    info = {"status": "PRIVATE_ORIGINAL_MODEL_REPLAY_NOT_ATTACHED",
            "source_path": None, "source_date": None, "top5": [],
            "research_only": True, "retrospective_only": True,
            "current_selection": False, "formal_selection_authority": False,
            "buy_signal": False, "sell_signal": False,
            "broker_execution": False, "authorized_lots": 0,
            "capital_authority_twd": 0}
    if path is None:
        return info
    info["source_path"] = str(path)
    try:
        p = json.loads(Path(path).read_text(encoding="utf-8"))
        date = dt.date.fromisoformat(p["decision_date"])
        issued = dt.datetime.fromisoformat(p["generated_at_taipei"]).astimezone(TZ)
        src = p["source_sha256"]
        top = p["top5"]
        signature = p.get("receipt_sha256")
        content = {k:v for k,v in p.items() if k != "receipt_sha256"}
        signed_hash = hashlib.sha256(json.dumps(
            content, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        safe = (
            type(signature) is str and signature == signed_hash
            and isinstance(src, dict)
            p.get("schema") == "HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1"
            and p.get("system") == "HENGCE"
            and p.get("model_id") == "v22d_daily_nowcast_liquidity_top5_v1"
            and p.get("status") == "RESEARCH_REPLAY_NOT_PIT_CERTIFIED"
            and p.get("fixed_cohort_count") == 781
            and p.get("historical_tdcc_first_observed_pit_certified") is False
            and p.get("prediction_is_real_daily_retail_count") is False
            and p.get("score_is_calibrated_probability") is False
            and p.get("current_selection") is False
            and p.get("retrospective_only") is True
            and all(p.get(k) is False for k in (
                "trading_authority", "formal_selection_authority",
                "buy_signal", "sell_signal", "broker_execution"))
            and p.get("authorized_lots") == 0
            and p.get("capital_authority_twd") == 0
            and src.get("original_prices") == PRICE_HASH
            and src.get("original_tdcc") == TDCC_HASH
            and src.get("classifier") == MODEL_HASH
            and src.get("regressor") == REG_HASH
            and len(src.get("original_2026_canonical", "")) == 64
            and date.weekday() <= 3 and date <= now.date()
            and issued.date() >= date and issued <= now
            and type(p.get("feature_coverage")) is int
            and 0 < p["feature_coverage"] <= 781
            and type(p.get("qualified_count")) is int
            and 0 <= p["qualified_count"] <= p["feature_coverage"]
            and type(top) is list
            and len(top) <= min(p["qualified_count"], 5)
        )
        if not safe:
            info["status"] = "PRIVATE_REPLAY_RECEIPT_REJECTED"
            return info
        seen = set()
        prior_turnover = float("inf")
        for i, row in enumerate(top, 1):
            ticker = row.get("ticker")
            turnover = row.get("median_20d_turnover_twd")
            score = row.get("daily_decline_score")
            r20 = row.get("return_20d")
            r5 = row.get("return_5d")
            if (type(ticker) is not str or len(ticker) != 4 or
                not ticker.isdigit() or ticker in seen or
                row.get("rank") != i or
                type(turnover) not in (int,float) or not math.isfinite(turnover) or
                type(score) not in (int,float) or not math.isfinite(score) or
                type(r20) not in (int,float) or not math.isfinite(r20) or
                type(r5) not in (int,float) or not math.isfinite(r5) or
                score < .50 or score > 1 or r20 < .05 or r5 < 0 or
                turnover < 10_000_000 or turnover > prior_turnover):
                info["status"] = "PRIVATE_REPLAY_RECEIPT_REJECTED"
                return info
            seen.add(ticker)
            prior_turnover = turnover
        info.update(status="PRIVATE_V22D_ORIGINAL_REPLAY_VERIFIED_RESEARCH_ONLY",
                    source_date=p["decision_date"], top5=top,
                    model_coverage=p["feature_coverage"],
                    qualified_count=p["qualified_count"],
                    last_assumed_tdcc_snapshot=p.get("last_assumed_tdcc_snapshot"),
                    source_sha_claims_match_pins=True,
                    model_pit_certified=False,
                    daily_top5_is_current_trading_signal=False)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        info["status"] = "PRIVATE_REPLAY_RECEIPT_UNREADABLE"
    return info
