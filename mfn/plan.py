"""Step 2b: build the buy plan and its approval code.

The approval code is a fingerprint of exactly what will be bought. Michael approves a
code, and check-buy refuses any batch whose fingerprint differs — so the buy can never
contain something he didn't see.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from mfn import config, rates


def _ts(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def approval_code(carrier, items):
    canonical = json.dumps({"carrier": carrier, "items": items}, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:8].upper()


def build_plan(recon, quotes, created_at):
    """recon: output of reconcile(); quotes: {allocation_id: veeqo_get_allocation_rates response}."""
    quotes = {int(k): v for k, v in quotes.items()}
    lines, items, flags, switches, unbuyable = [], [], list(recon["flags"]), [], []
    expiries = []

    for entry in recon["to_quote"]:
        alloc = int(entry["allocation_id"])
        quote = quotes.get(alloc)
        if quote is None:
            unbuyable.append({**entry, "reason": "no quote fetched"})
            continue
        try:
            rate, notes = rates.choose(quote, entry.get("package_oz"))
        except rates.NoRate as e:
            unbuyable.append({**entry, "reason": str(e)})
            continue
        for n in notes:
            text = f"{entry['order_number']}: {n['text']}"
            (switches if n["kind"] == "switch" else flags).append(text)
        if quote.get("quotesExpireAt"):
            expiries.append(quote["quotesExpireAt"])

        item = {
            "allocation_id": alloc,
            "service_type": rate["serviceType"],
            "remote_shipment_id": rate["remoteShipmentId"],
            "expected_charge": rates.charge(rate),
        }
        for src, dst in (("serviceCarrier", "service_carrier"), ("subCarrierId", "sub_carrier_id")):
            if rate.get(src):
                item[dst] = rate[src]
        items.append(item)
        lines.append({
            "order_number": entry["order_number"],
            "order_id": entry["order_id"],
            "allocation_id": alloc,
            "skus": entry["skus"],
            "service": rate.get("serviceTitle"),
            "carrier": rate.get("subCarrierId") or rate.get("serviceCarrier"),
            "charge": rates.charge(rate),
        })

    items.sort(key=lambda i: i["allocation_id"])
    lines.sort(key=lambda l: l["allocation_id"])
    for u in unbuyable:
        flags.append(f"{u['order_number']}: not in plan — {u['reason']}")

    total = round(sum(i["expected_charge"] for i in items), 2)
    return {
        "created_at": created_at,
        "carrier": config.CARRIER,
        "items": items,
        "lines": lines,
        "total": total,
        "service_split": dict(Counter(l["service"] for l in lines)),
        "quotes_expire_at": min(expiries, key=_ts) if expiries else None,
        "held": recon["held"],
        "unbuyable": unbuyable,
        "switches": switches,
        "flags": flags,
        "counts": recon["counts"],
        "approval_code": approval_code(config.CARRIER, items) if items else None,
    }
