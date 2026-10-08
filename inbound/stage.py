"""Step 8: decide what goes into which Send to Amazon workflow.

Input is the units in hand from one invoice, each with the SKU chosen in step 7 and
its FNSKU as DataDoe reports it. Output is one or two workflows, ready to write as
upload files, plus every line held back and why.
"""
from collections import OrderedDict

from inbound import config


class StageRefused(Exception):
    pass


def barcode_problem(sku, asin, fnsku):
    """Why this SKU can't be staged yet, or None if its barcode is usable."""
    fnsku = (fnsku or "").strip().upper()
    asin = (asin or "").strip().upper()
    if not fnsku:
        return (f"{sku}: no FBA barcode yet. A new SKU can take 20 minutes to several hours; "
                "recheck later. An old SKU with none was never converted to FBA.")
    if asin and fnsku == asin:
        return (f"{sku}: FNSKU equals the ASIN (manufacturer barcode), Amazon will reject it. "
                "Create an a-suffix SKU on the same ASIN and stage that instead.")
    if not fnsku.startswith("X00"):
        return f"{sku}: unexpected FNSKU {fnsku}; check it in Seller Central before staging."
    return None


def _quantity(line):
    qty = line.get("qty")
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise StageRefused(f"{line.get('sku')}: quantity must be a whole number above 0, got {qty!r}")
    return qty


def build_stage(doc):
    """doc: {"vendor", "invoice", "lines": [{"sku", "asin", "fnsku", "qty"}]}"""
    vendor = (doc.get("vendor") or "").strip()
    invoice = (doc.get("invoice") or "").strip()
    if not vendor or not invoice:
        raise StageRefused("vendor and invoice are both required; they name the workflow")
    if not doc.get("lines"):
        raise StageRefused("no lines to stage")

    merged, held, flags = OrderedDict(), [], []
    for line in doc["lines"]:
        sku = (line.get("sku") or "").strip()
        if not sku:
            raise StageRefused(f"line without a SKU: {line}")
        qty = _quantity(line)
        problem = barcode_problem(sku, line.get("asin"), line.get("fnsku"))
        if problem:
            held.append({"sku": sku, "asin": line.get("asin"), "qty": qty, "reason": problem})
            continue
        if sku in merged:
            merged[sku]["qty"] += qty
            flags.append(f"{sku}: appears on more than one invoice line; quantities added together")
        else:
            merged[sku] = {"sku": sku, "asin": line.get("asin"), "qty": qty}

    rows = list(merged.values())
    big = [r for r in rows if r["qty"] >= config.MIN_UNITS_OPTIMIZED]
    small = [r for r in rows if r["qty"] < config.MIN_UNITS_OPTIMIZED]
    name = f"{vendor} {invoice}"

    workflows = []
    if big:
        workflows.append(_workflow(name, big))
        if small:
            workflows.append(_workflow(name + config.PART2_SUFFIX, small))
    elif small:
        workflows.append(_workflow(name, small))
        flags.append(f"every SKU is under {config.MIN_UNITS_OPTIMIZED} units, so there is one "
                     "workflow and it will miss Amazon-optimized placement")

    return {"vendor": vendor, "invoice": invoice, "workflows": workflows,
            "held": held, "flags": flags}


def _workflow(name, rows):
    units = sum(r["qty"] for r in rows)
    return {"name": name, "skus": rows, "sku_count": len(rows), "units": units,
            "expected_counter": f"SKUs ready to send: {len(rows)} ({units} units)"}
