"""Steps 2c/2d: the buy guard and the label ledger.

check_buy() is the only way to get a buy payload. It refuses when:
  - the approval code doesn't match the plan's contents (plan edited after approval)
  - any allocation is already in the ledger (bought, failed-maybe-charged, or unverified)
  - the quotes have expired (re-quote, re-plan, re-approve)
  - a charge isn't a number, or the batch mixes carriers

record_buy() writes every attempted allocation to the ledger, including failures:
Veeqo may have charged a failed item, so it must never be retried automatically.
"""
import json
import os
from datetime import datetime, timezone

from mfn import config
from mfn.plan import _ts as parse_ts, approval_code


class BuyRefused(Exception):
    pass


def load_ledger(path):
    entries = {}
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    entries[int(e["allocation_id"])] = e
    return entries


def check_buy(plan, code, ledger, now=None):
    now = now or datetime.now(timezone.utc)
    items = plan.get("items") or []
    if not items:
        raise BuyRefused("plan has nothing to buy")
    if not code or code.strip().upper() != plan.get("approval_code"):
        raise BuyRefused("approval code does not match this plan")
    if approval_code(plan["carrier"], items) != plan["approval_code"]:
        raise BuyRefused("plan contents changed after the approval code was made")
    if plan["carrier"] != config.CARRIER:
        raise BuyRefused(f"carrier {plan['carrier']} is not {config.CARRIER}")

    seen = set()
    for item in items:
        alloc = int(item["allocation_id"])
        if alloc in seen:
            raise BuyRefused(f"allocation {alloc} appears twice")
        seen.add(alloc)
        if alloc in ledger:
            e = ledger[alloc]
            raise BuyRefused(f"allocation {alloc} already in ledger ({e.get('status')}, "
                             f"{e.get('at')}) — never buy twice")
        charge = item.get("expected_charge")
        if isinstance(charge, bool) or not isinstance(charge, (int, float)):
            raise BuyRefused(f"allocation {alloc}: expected_charge must be a number")

    expires = plan.get("quotes_expire_at")
    if expires and parse_ts(expires) <= now:
        raise BuyRefused(f"quotes expired at {expires} — re-quote and re-approve")

    return {"carrier": plan["carrier"], "items": items}


def classify_result(result):
    """Map a veeqo_get_bulk_shipment_result response to {allocation_id: status}.

    status is one of: bought, failed, verify (state unclear — check the order by hand).
    """
    if not result.get("settled"):
        raise ValueError("bulk result is not settled yet — keep polling")
    confirmed = {int(a) for a in result.get("labelConfirmedDespiteState") or []}
    blocked = {int(a) for a in result.get("blockedByExistingShipment") or []}
    unknown = {int(a) for a in result.get("labelProvenanceUnknown") or []}

    out = {}
    for item in result.get("items") or []:
        alloc = int(item["allocationId"])
        if alloc in blocked or alloc in unknown:
            out[alloc] = {"status": "verify", "shipment_id": item.get("shipmentId")}
        elif item.get("shipmentId") or alloc in confirmed:
            out[alloc] = {"status": "bought", "shipment_id": item.get("shipmentId")}
        elif item.get("errors"):
            out[alloc] = {"status": "failed", "errors": item["errors"]}
        else:
            out[alloc] = {"status": "verify"}
    return out


def record_buy(plan, result, ledger_path, now=None):
    """Append one ledger line per planned allocation. Returns the classification."""
    now = now or datetime.now(timezone.utc)
    statuses = classify_result(result)
    by_alloc = {l["allocation_id"]: l for l in plan["lines"]}
    os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
    with open(ledger_path, "a") as f:
        for item in plan["items"]:
            alloc = int(item["allocation_id"])
            # Anything the result doesn't mention was submitted, so it may exist: verify.
            s = statuses.get(alloc, {"status": "verify"})
            statuses[alloc] = s
            f.write(json.dumps({
                "allocation_id": alloc,
                "order_number": by_alloc.get(alloc, {}).get("order_number"),
                "status": s["status"],
                "shipment_id": s.get("shipment_id"),
                "charge": item["expected_charge"],
                "bulk_shipment_id": result.get("bulkShipmentId"),
                "approval_code": plan["approval_code"],
                "at": now.isoformat(timespec="seconds"),
            }) + "\n")
    return statuses
