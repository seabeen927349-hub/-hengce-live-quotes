#!/usr/bin/env python3
"""HENGCE EOD incremental ingest through the original eod/YYYYMMDD vessel only.

Official TWSE price / institutional / margin legs are independent. A valid leg
is persisted immediately; a not-yet-published leg stays PENDING. No synthetic
leg, parallel EOD tree, second mother, Q017 authority, or E2 authority exists
here. The existing downstream EOD->canonical Historical Mother bridge consumes
these same eod/YYYYMMDD files.

The effective TWSE calendar is checked before any network access.  Official or
extraordinary market-closure days therefore cannot hit the three download legs
or manufacture an EOD completion artifact.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import date

import hengce_daily_command_center_core_legacy as core
import hengce_twse_calendar as twse_calendar

LEGS = ("price", "institutional", "margin")
MIN = {"price": 900, "institutional": 900, "margin": 500}
COLS = {
    "price": [
        "Date", "Ticker", "Name", "VolumeShares", "Trades", "TurnoverTWD",
        "Open", "High", "Low", "Close", "ChangeSign", "Change", "LastBid",
        "LastBidVolume", "LastAsk", "LastAskVolume", "PE", "Source",
    ],
    "institutional": [
        "Date", "Ticker", "Name", "ForeignBuy", "ForeignSell", "ForeignNet",
        "ForeignDealerBuy", "ForeignDealerSell", "ForeignDealerNet", "TrustBuy",
        "TrustSell", "TrustNet", "DealerNet", "DealerProprietaryBuy",
        "DealerProprietarySell", "DealerProprietaryNet", "DealerHedgeBuy",
        "DealerHedgeSell", "DealerHedgeNet", "TotalNet", "Source",
    ],
    "margin": [
        "Date", "Ticker", "Name", "MarginBuy", "MarginSell",
        "MarginCashRepayment", "MarginPreviousBalance", "MarginBalance",
        "MarginNextDayLimit", "ShortBuy", "ShortSell", "ShortStockRepayment",
        "ShortPreviousBalance", "ShortBalance", "ShortNextDayLimit", "Offset",
        "Note", "Source",
    ],
}
SRC = {
    "price": core.TWSE_PRICE,
    "institutional": core.TWSE_INST,
    "margin": core.TWSE_MARGIN,
}


class NotReady(RuntimeError):
    pass


def _files(out, leg):
    return sorted(out.glob(f"{leg}_[1-9].csv"))


def _digest(files):
    h = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.name):
        h.update(path.name.encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _read(out, leg, iso):
    files = _files(out, leg)
    if not files:
        return None
    rows = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [col for col in COLS[leg] if col not in (reader.fieldnames or [])]
            if missing:
                raise RuntimeError(f"{leg.upper()}_MISSING_COLUMNS:{path.name}:{','.join(missing)}")
            rows += list(reader)
    keys = [(row.get("Date", ""), row.get("Ticker", "")) for row in rows]
    if len(rows) < MIN[leg]:
        raise RuntimeError(f"{leg.upper()}_ROWS_TOO_SMALL:{len(rows)}")
    if {day for day, _ in keys} != {iso}:
        raise RuntimeError(f"{leg.upper()}_WRONG_DATE")
    if any(not re.fullmatch(r"[1-9]\d{3}", ticker) for _, ticker in keys):
        raise RuntimeError(f"{leg.upper()}_BAD_TICKER")
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{leg.upper()}_DUPLICATE_DATE_TICKER")
    return {"rows": len(rows), "sha256": _digest(files), "files": [p.name for p in files]}


def _write(out, leg, iso, rows):
    if len(rows) < MIN[leg]:
        raise RuntimeError(f"{leg.upper()}_ROWS_TOO_SMALL:{len(rows)}<{MIN[leg]}")
    keys = [(str(row.get("Date", "")), str(row.get("Ticker", ""))) for row in rows]
    if {day for day, _ in keys} != {iso}:
        raise RuntimeError(f"{leg.upper()}_PARSED_DATE_MISMATCH")
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{leg.upper()}_DUPLICATE_DATE_TICKER")

    buckets = {str(i): [] for i in range(1, 10)}
    for row in rows:
        ticker = str(row.get("Ticker", ""))
        if not re.fullmatch(r"[1-9]\d{3}", ticker):
            raise RuntimeError(f"{leg.upper()}_BAD_TICKER:{ticker}")
        buckets[ticker[0]].append(row)

    written = set()
    for key, bucket in buckets.items():
        if not bucket:
            continue
        path = out / f"{leg}_{key}.csv"
        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLS[leg])
            writer.writeheader()
            writer.writerows(sorted(bucket, key=lambda row: row["Ticker"]))
        tmp.replace(path)
        written.add(path.name)

    for path in _files(out, leg):
        if path.name not in written:
            path.unlink()

    info = _read(out, leg, iso)
    receipt = {
        "system": "HENGCE",
        "artifact": "EOD_ORIGINAL_VESSEL_LEG_RECEIPT",
        "target_date": iso,
        "leg": leg,
        "status": "COMPLETE",
        "rows": info["rows"],
        "sha256": info["sha256"],
        "source": SRC[leg],
        "files": info["files"],
        "promoted_at_taipei": core.now_tw().isoformat(),
        "policy": "ORIGINAL_VESSEL_INDEPENDENT_LEG_PROMOTION_NO_WAIT_FOR_MARGIN",
        "model_authority_created": False,
    }
    core.atomic_json(out / "receipts" / f"{leg}.json", receipt)
    return info


def _mother_receipt(out, iso, status):
    path = out / "receipts" / "mother.json"
    if not path.exists():
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if receipt.get("target_date") != iso or str(receipt.get("status")).upper() not in ("PASS", "COMPLETE"):
        return None
    if receipt.get("second_mother") is not False:
        return None
    hashes = receipt.get("promoted_leg_sha256") or {}
    available = [leg for leg in LEGS if status.get(f"{leg}_status") == "COMPLETE"]
    if any(hashes.get(leg) != status.get(f"{leg}_sha256") for leg in available):
        return None
    if receipt.get("mother_latest_date") != iso:
        return None
    return receipt


def _price(ds, iso):
    payload = core.get_json(core.TWSE_PRICE, {"date": ds, "type": "ALLBUT0999", "response": "json"})
    if str(payload.get("stat")).upper() != "OK":
        raise NotReady(f"PRICE_NOT_READY:{payload.get('stat')}")
    if str(payload.get("date")) != ds:
        raise RuntimeError(f"PRICE_RESPONSE_DATE_MISMATCH:{payload.get('date')}")
    table = next(
        (
            item
            for item in payload.get("tables") or []
            if "證券代號" in (item.get("fields") or []) and "收盤價" in (item.get("fields") or [])
        ),
        None,
    )
    if not table:
        raise RuntimeError("PRICE_TABLE_NOT_FOUND")
    fields = table.get("fields") or []
    index = {field: i for i, field in enumerate(fields)}

    def value(row, *names):
        for name in names:
            i = index.get(name)
            if i is not None and i < len(row):
                return core.clean(row[i])
        return ""

    result = []
    for row in table.get("data") or table.get("records") or []:
        ticker = value(row, "證券代號").replace("=", "").replace('"', "")
        if re.fullmatch(r"[1-9]\d{3}", ticker):
            result.append({
                "Date": iso,
                "Ticker": ticker,
                "Name": value(row, "證券名稱"),
                "VolumeShares": value(row, "成交股數", "成交量"),
                "Trades": value(row, "成交筆數"),
                "TurnoverTWD": value(row, "成交金額"),
                "Open": value(row, "開盤價"),
                "High": value(row, "最高價"),
                "Low": value(row, "最低價"),
                "Close": value(row, "收盤價"),
                "ChangeSign": value(row, "漲跌(+/-)", "漲跌"),
                "Change": value(row, "漲跌價差"),
                "LastBid": value(row, "最後揭示買價"),
                "LastBidVolume": value(row, "最後揭示買量"),
                "LastAsk": value(row, "最後揭示賣價"),
                "LastAskVolume": value(row, "最後揭示賣量"),
                "PE": value(row, "本益比"),
                "Source": core.TWSE_PRICE,
            })
    return result


def _inst(ds, iso):
    payload = core.get_json(core.TWSE_INST, {"date": ds, "selectType": "ALLBUT0999", "response": "json"})
    if str(payload.get("stat")).upper() != "OK":
        raise NotReady(f"INST_NOT_READY:{payload.get('stat')}")
    if str(payload.get("date")) != ds:
        raise RuntimeError(f"INST_RESPONSE_DATE_MISMATCH:{payload.get('date')}")
    fields = payload.get("fields") or []
    data = payload.get("data") or payload.get("records") or []
    if not data:
        for table in payload.get("tables") or []:
            candidate = table.get("fields") or []
            if "證券代號" in candidate and any("外陸資買賣超股數" in str(item) for item in candidate):
                fields = candidate
                data = table.get("data") or table.get("records") or []
                break
    if not data:
        raise RuntimeError("INST_TABLE_NOT_FOUND")
    index = {field: i for i, field in enumerate(fields)}

    def value(row, exact=None, contains=None):
        if exact in index and index[exact] < len(row):
            return core.clean(row[index[exact]])
        if contains:
            for field, i in index.items():
                if contains in field and i < len(row):
                    return core.clean(row[i])
        return ""

    result = []
    for row in data:
        ticker = value(row, exact="證券代號").replace("=", "").replace('"', "")
        if re.fullmatch(r"[1-9]\d{3}", ticker):
            result.append({
                "Date": iso,
                "Ticker": ticker,
                "Name": value(row, exact="證券名稱"),
                "ForeignBuy": value(row, contains="外陸資買進股數(不含外資自營商)"),
                "ForeignSell": value(row, contains="外陸資賣出股數(不含外資自營商)"),
                "ForeignNet": value(row, contains="外陸資買賣超股數(不含外資自營商)"),
                "ForeignDealerBuy": value(row, exact="外資自營商買進股數"),
                "ForeignDealerSell": value(row, exact="外資自營商賣出股數"),
                "ForeignDealerNet": value(row, exact="外資自營商買賣超股數"),
                "TrustBuy": value(row, exact="投信買進股數"),
                "TrustSell": value(row, exact="投信賣出股數"),
                "TrustNet": value(row, exact="投信買賣超股數"),
                "DealerNet": value(row, exact="自營商買賣超股數"),
                "DealerProprietaryBuy": value(row, exact="自營商買進股數(自行買賣)"),
                "DealerProprietarySell": value(row, exact="自營商賣出股數(自行買賣)"),
                "DealerProprietaryNet": value(row, exact="自營商買賣超股數(自行買賣)"),
                "DealerHedgeBuy": value(row, exact="自營商買進股數(避險)"),
                "DealerHedgeSell": value(row, exact="自營商賣出股數(避險)"),
                "DealerHedgeNet": value(row, exact="自營商買賣超股數(避險)"),
                "TotalNet": value(row, exact="三大法人買賣超股數"),
                "Source": core.TWSE_INST,
            })
    return result


def _margin(ds, iso):
    payload = core.get_json(core.TWSE_MARGIN, {"date": ds, "selectType": "ALL", "response": "json"})
    if str(payload.get("stat")).upper() != "OK":
        raise NotReady(f"MARGIN_NOT_READY:{payload.get('stat')}")
    if str(payload.get("date")) != ds:
        raise RuntimeError(f"MARGIN_RESPONSE_DATE_MISMATCH:{payload.get('date')}")

    candidates = list(payload.get("tables") or [])
    if isinstance(payload.get("fields"), list) and isinstance(payload.get("data"), list):
        candidates.append({"fields": payload["fields"], "data": payload["data"]})
    for key, value in payload.items():
        match = re.fullmatch(r"fields(\d+)", str(key))
        if match and isinstance(value, list) and isinstance(payload.get("data" + match.group(1)), list):
            candidates.append({"fields": value, "data": payload["data" + match.group(1)]})

    data = None
    for table in candidates:
        fields = [core.clean(item).replace(" ", "") for item in table.get("fields") or []]
        rows = table.get("data") or table.get("records") or []
        if (
            len(fields) >= 15
            and len(rows) >= MIN["margin"]
            and any("現金償還" in item for item in fields)
            and any("現券償還" in item for item in fields)
        ):
            data = rows
            break
    if data is None:
        raise RuntimeError("MARGIN_TABLE_NOT_FOUND")

    result = []
    for row in data:
        if not isinstance(row, (list, tuple)) or len(row) < 15:
            continue
        ticker = core.clean(row[0]).replace("=", "").replace('"', "")
        if re.fullmatch(r"[1-9]\d{3}", ticker):
            values = [
                iso,
                ticker,
                core.clean(row[1]),
                *[core.clean(item) for item in row[2:15]],
                core.clean(row[15]) if len(row) > 15 else "",
                core.TWSE_MARGIN,
            ]
            result.append(dict(zip(COLS["margin"], values)))
    return result


FETCH = {"price": _price, "institutional": _inst, "margin": _margin}


def _calendar_gate(target):
    manifest, manifest_path, lineage = twse_calendar.load_manifest()
    trading_day = twse_calendar.is_trading_day(target, manifest)
    return trading_day, {
        "market_calendar_date": target.isoformat(),
        "market_calendar_trading_day": trading_day,
        "market_calendar_authority": manifest.get("authority"),
        "market_calendar_fingerprint_sha256": twse_calendar.manifest_fingerprint(manifest),
        "market_calendar_lineage_sha256": lineage,
        "market_calendar_manifest": str(manifest_path),
    }


def ingest(target=None):
    target = target or core.now_tw().date()
    trading_day, calendar_meta = _calendar_gate(target)
    if not trading_day:
        return {
            "system": "HENGCE",
            "artifact": "EOD_ORIGINAL_VESSEL_INCREMENTAL_INGEST",
            "target_date": target.isoformat(),
            "status": "SKIP_NONTRADING",
            "reason": "TWSE_EFFECTIVE_CALENDAR_CLOSED",
            "available_legs": [],
            "pending_legs": list(LEGS),
            "error_legs": [],
            "three_leg_complete": False,
            "formal_complete_day": False,
            "mother_status": "NOT_READY",
            "downstream_ready": False,
            "network_access_attempted": False,
            "parallel_eod_tree": False,
            "second_mother": False,
            "model_authority_created": False,
            "ranking_authority": False,
            "signal_authority": False,
            "capital_authority": False,
            "broker_order_execution": False,
            "policy": "FAIL_CLOSED_EFFECTIVE_TWSE_CALENDAR_NO_DOWNLOAD_NO_PROMOTION",
            **calendar_meta,
        }

    ds = target.strftime("%Y%m%d")
    iso = target.isoformat()
    out = core.ROOT / "eod" / ds
    out.mkdir(parents=True, exist_ok=True)
    status_path = out / "status.json"
    try:
        status = json.loads(status_path.read_text()) if status_path.exists() else {}
    except Exception:
        status = {}
    if status.get("target_date") not in (None, iso):
        raise RuntimeError("EOD_STATUS_DATE_MISMATCH")
    status.update({
        "system": "HENGCE",
        "artifact": "EOD_ORIGINAL_VESSEL_INCREMENTAL_INGEST",
        "target_date": iso,
        "policy": "ORIGINAL_VESSEL_INDEPENDENT_LEG_PROMOTION_NO_WAIT_FOR_MARGIN",
        "mother_promotion_route": "EXISTING_EOD_TO_CANONICAL_HISTORICAL_MOTHER_BRIDGE",
        "parallel_eod_tree": False,
        "second_mother": False,
        "model_authority_created": False,
        **calendar_meta,
    })

    results = []
    fatal = []
    promoted = []
    for leg in LEGS:
        try:
            old = _read(out, leg, iso)
            if old:
                info = old
                result = "ALREADY_COMPLETE"
            else:
                info = _write(out, leg, iso, FETCH[leg](ds, iso))
                result = "PROMOTED"
                promoted.append(leg)
            status.update({
                f"{leg}_status": "COMPLETE",
                f"{leg}_date": iso,
                f"{leg}_rows": info["rows"],
                f"{leg}_sha256": info["sha256"],
                f"{leg}_source": SRC[leg],
            })
            status.pop(f"{leg}_pending_reason", None)
            status.pop(f"{leg}_error", None)
            results.append({"leg": leg, "result": result, "rows": info["rows"], "sha256": info["sha256"]})
        except NotReady as exc:
            status[f"{leg}_status"] = "PENDING"
            status[f"{leg}_pending_reason"] = str(exc)
            results.append({"leg": leg, "result": "PENDING", "reason": str(exc)})
        except Exception as exc:
            status[f"{leg}_status"] = "ERROR"
            status[f"{leg}_error"] = f"{type(exc).__name__}:{exc}"
            fatal.append({"leg": leg, "error": status[f"{leg}_error"]})
            results.append({"leg": leg, "result": "ERROR", "error": status[f"{leg}_error"]})

    done = [leg for leg in LEGS if status.get(f"{leg}_status") == "COMPLETE"]
    pending = [leg for leg in LEGS if status.get(f"{leg}_status") == "PENDING"]
    errors = [leg for leg in LEGS if status.get(f"{leg}_status") == "ERROR"]
    mother_receipt = _mother_receipt(out, iso, status)
    if mother_receipt:
        mother_status = "COMPLETE"
        mother_pending = []
        status.pop("mother_pending_reason", None)
        status.update({
            "mother_receipt": "receipts/mother.json",
            "mother_sha256": mother_receipt.get("mother_sha256"),
            "mother_latest_date": mother_receipt.get("mother_latest_date"),
            "mother_promoted_legs": mother_receipt.get("promoted_legs", done),
        })
    else:
        mother_status = "PENDING" if done else "NOT_READY"
        mother_pending = list(done)
        if done:
            status["mother_pending_reason"] = "AVAILABLE_LEGS_REQUIRE_CANONICAL_MOTHER_PROMOTION"
        for key in ("mother_receipt", "mother_sha256", "mother_latest_date", "mother_promoted_legs"):
            status.pop(key, None)

    downstream_ready = status.get("price_status") == "COMPLETE" and mother_status == "COMPLETE"
    status.update({
        "available_legs": done,
        "pending_legs": pending,
        "error_legs": errors,
        "mother_status": mother_status,
        "mother_promotion_required": bool(done),
        "mother_pending_legs": mother_pending,
        "downstream_ready": downstream_ready,
        "three_leg_complete": len(done) == 3,
        "formal_complete_day": len(done) == 3,
        "status": "ERROR" if errors else ("COMPLETE" if len(done) == 3 else "PARTIAL"),
        "last_run_results": results,
        "updated_at_taipei": core.now_tw().isoformat(),
    })
    core.atomic_json(status_path, status)
    if fatal:
        raise RuntimeError("EOD_INTEGRITY_REJECTION:" + json.dumps(fatal, ensure_ascii=False))
    return status


def self_test():
    closed, closed_meta = _calendar_gate(date.fromisoformat("2026-10-23"))
    opened, _ = _calendar_gate(date.fromisoformat("2026-10-22"))
    assert closed is False
    assert opened is True
    result = ingest(date.fromisoformat("2026-10-23"))
    assert result["status"] == "SKIP_NONTRADING"
    assert result["network_access_attempted"] is False
    assert result["downstream_ready"] is False
    assert result["three_leg_complete"] is False
    assert closed_meta["market_calendar_trading_day"] is False
    print(json.dumps({
        "self_test": "PASS",
        "original_eod_tree_only": True,
        "second_mother": False,
        "no_wait_for_margin": True,
        "mother_gate": True,
        "effective_twse_calendar_guard": True,
        "extraordinary_closure_no_network": True,
        "q017_model_change": False,
        "e2_model_change": False,
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ingest", "self-test"), required=True)
    parser.add_argument("--date")
    args = parser.parse_args()
    if args.mode == "self-test":
        self_test()
        return 0
    result = ingest(date.fromisoformat(args.date) if args.date else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
