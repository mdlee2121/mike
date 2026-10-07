"""Step 2a: pick one rate per allocation.

Veeqo returns rates promise-met first, then cheapest, so the first rate is the pick —
unless its carrier is banned, in which case the next allowed rate replaces it and the
switch is reported.
"""
from mfn import config


class NoRate(Exception):
    pass


def is_banned(rate):
    fields = (rate.get("serviceCarrier"), rate.get("subCarrierId"), rate.get("serviceTitle"),
              rate.get("carrier"))
    text = " ".join(str(f) for f in fields if f).lower()
    return any(b in text for b in config.BANNED_CARRIERS)


def charge(rate):
    """totalNetCharge arrives as a string ("6.07"); the buy needs a number."""
    return round(float(rate["totalNetCharge"]), 2)


def choose(quote, package_oz=None):
    """Return (rate, notes) where notes is a list of {"kind", "text"} for the report.

    Raises NoRate when nothing buyable remains.
    """
    available = quote.get("available") or []
    if not available:
        raise NoRate("no rates available")

    notes = []
    allowed = [r for r in available if not is_banned(r)]
    if not allowed:
        raise NoRate("only banned carriers offered")
    pick = allowed[0]

    if is_banned(available[0]):
        old, new = available[0], pick
        diff = charge(new) - charge(old)
        text = (f"switched {old.get('serviceTitle')} ${charge(old):.2f} -> "
                f"{new.get('serviceTitle')} ${charge(new):.2f}")
        notes.append({"kind": "switch", "text": text})
        if diff > config.SWITCH_ALERT_DOLLARS and diff > charge(old) * config.SWITCH_ALERT_PERCENT:
            notes.append({"kind": "flag", "text": f"carrier switch costs ${diff:.2f} more"})

    if pick.get("carrier") != config.CARRIER:
        raise NoRate(f"chosen rate is on carrier {pick.get('carrier')}, not {config.CARRIER}")
    if pick.get("requiresValueAddedServiceChoice"):
        raise NoRate("chosen rate needs a value-added-service choice")
    if pick.get("meetsDeliveryPromise") is False:
        notes.append({"kind": "flag", "text": "best rate misses Amazon's delivery promise"})

    title = (pick.get("serviceTitle") or "").lower()
    if (package_oz is not None and package_oz <= config.LIGHT_PACKAGE_OZ
            and any(w in title for w in config.EXPEDITED_WORDS)):
        notes.append({"kind": "flag",
                      "text": f"expedited service ({pick.get('serviceTitle')}) on a "
                              f"{package_oz:.1f} oz package"})
    return pick, notes
