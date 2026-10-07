"""Step 1: cross-check Veeqo, Listing Mirror and Amazon, and decide what may be quoted.

Inputs are the raw responses as the sources return them:
  veeqo_orders   veeqo_list_orders(channel_ids=159514, status="awaiting_fulfillment",
                 field_groups="fulfilmentState") -> its "results" list (or the whole response)
  lm             lm_get_order_fulfillment_channels(...) -> whole response (or its "results")
  amazon         DataDoe Order Line Items rows (fulfillment_channel=Merchant,
                 status Unshipped*), or None if the Amazon check could not run

Only Veeqo orders that pass every gate become "to_quote". Everything else is
"held" with a reason, and nothing held is ever bought by this run.
"""
from mfn import config

# Hold reasons. HELD_FOR_REVIEW can be released by Michael with --include;
# the others can never be bought by this run.
MCF = "mcf"                                  # Amazon MCF fills it — buying a label pays twice
LM_UNKNOWN = "lm_unknown"                    # Listing Mirror has no verdict
INTERNATIONAL = "international_customs"      # outside the 50 states (PR counts): customs gate
NOT_SHIPPABLE = "not_shippable"              # Veeqo says it cannot ship / not fully allocated
NOT_ON_AMAZON = "not_on_amazon_unshipped"    # cancelled on Amazon, or DataDoe hasn't caught up
ALREADY_LABELLED = "already_labelled"        # allocation already has a shipment
NO_ALLOCATION = "no_allocation"

HELD_FOR_REVIEW = {LM_UNKNOWN, NOT_ON_AMAZON, NOT_SHIPPABLE}

REASON_TEXT = {
    MCF: "MCF order — Amazon ships it, no label",
    LM_UNKNOWN: "Listing Mirror has no record in this store/window — not bought",
    INTERNATIONAL: "ships outside the 50 states — customs check needed",
    NOT_SHIPPABLE: "Veeqo says it can't ship yet (allocation/stock)",
    NOT_ON_AMAZON: "in Veeqo but not on Amazon's unshipped list (cancelled? or DataDoe lag)",
    ALREADY_LABELLED: "already has a label",
    NO_ALLOCATION: "no allocation to buy against",
}


def _results(payload):
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload.get("results", [])
    return payload


def _oz(package):
    weight = package.get("weight")
    if weight is None:
        return None
    unit = (package.get("weightUnit") or "oz").lower()
    factor = {"oz": 1.0, "lb": 16.0, "lbs": 16.0, "g": 0.035274, "kg": 35.274}.get(unit)
    return None if factor is None else weight * factor


def package_flags(package):
    flags = []
    oz = _oz(package)
    if oz is None or oz <= 0:
        flags.append("package has no weight")
    for dim in ("width", "height", "depth"):
        if not package.get(dim):
            flags.append("package is missing dimensions")
            break
    return flags


def reconcile(veeqo_orders, lm, amazon, include=()):
    """Return a JSON-able dict: to_quote, held, flags and counts."""
    veeqo_orders = _results(veeqo_orders) or []
    lm_rows = _results(lm) or []
    amazon_rows = _results(amazon)
    include = set(include)

    verdicts = {r["orderId"]: r for r in lm_rows}
    amazon_ids = None
    if amazon_rows is not None:
        amazon_ids = {r["amazon_order_id"] for r in amazon_rows}

    to_quote, held, flags = [], [], []
    veeqo_ids = set()

    for order in veeqo_orders:
        number = order["orderNumber"]
        veeqo_ids.add(number)
        if order.get("channelId") not in (None, config.AMAZON_CHANNEL_ID):
            continue  # wrong store slipped into the input; never ours to buy
        skus = [li.get("sku") for li in order.get("lineItems", [])]
        verdict = verdicts.get(number, {})
        base = {"order_id": order["id"], "order_number": number, "skus": skus}

        reasons = []
        if verdict.get("verdict") == "MCF" or verdict.get("isMcf"):
            reasons.append(MCF)
            mcf_status = verdict.get("mcfStatus")
            if mcf_status and "not yet" in str(mcf_status).lower():
                flags.append(f"{number}: MCF order not yet requested from Amazon by Listing Mirror")
        elif verdict.get("verdict") != "MFN":
            reasons.append(LM_UNKNOWN)
        if order.get("international"):
            reasons.append(INTERNATIONAL)
        if order.get("canBeShipped") is False or order.get("allocatedCompletely") is False:
            reasons.append(NOT_SHIPPABLE)
        if amazon_ids is not None and number not in amazon_ids:
            reasons.append(NOT_ON_AMAZON)
        if not order.get("allocations"):
            reasons.append(NO_ALLOCATION)

        released = number in include and reasons and set(reasons) <= HELD_FOR_REVIEW
        if reasons and not released:
            held.append({**base, "reasons": reasons})
            continue
        if released:
            flags.append(f"{number}: released by Michael despite: "
                         + ", ".join(REASON_TEXT[r] for r in reasons))

        for alloc in order["allocations"]:
            if alloc.get("shipmentId"):
                held.append({**base, "allocation_id": alloc["id"], "reasons": [ALREADY_LABELLED]})
                continue
            package = alloc.get("package") or {}
            for f in package_flags(package):
                flags.append(f"{number}: {f}")
            to_quote.append({
                **base,
                "allocation_id": alloc["id"],
                "package_oz": _oz(package),
                "delivery_method": (order.get("deliveryMethod") or {}).get("name"),
            })

    amazon_only = []
    if amazon_ids is not None:
        amazon_only = sorted(amazon_ids - veeqo_ids)
        for number in amazon_only:
            flags.append(f"{number}: on Amazon's unshipped list but not in Veeqo — not synced yet?")
    else:
        flags.append("Amazon cross-check did not run — orders missing from Veeqo would be invisible")

    mcf_count = sum(1 for h in held if MCF in h["reasons"])
    counts = {
        "veeqo_ready": len(veeqo_ids),
        "amazon_unshipped": None if amazon_ids is None else len(amazon_ids),
        "mcf": mcf_count,
        "to_quote": len(to_quote),
        "held": len(held),
    }
    if amazon_ids is not None:
        # Veeqo Ready To Ship should equal Amazon Unshipped (MCF orders still show in both
        # until tracking posts, so they cancel out); any gap is named above.
        counts["counts_match"] = not amazon_only and not any(
            NOT_ON_AMAZON in h["reasons"] for h in held)

    return {"to_quote": to_quote, "held": held, "flags": flags, "counts": counts,
            "amazon_only": amazon_only}
