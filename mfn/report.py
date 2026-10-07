"""Plain-text messages for Michael: the approval request and the end-of-run report."""
from mfn.reconcile import REASON_TEXT


def _held_lines(held):
    out = []
    for h in held:
        why = "; ".join(REASON_TEXT.get(r, r) for r in h["reasons"])
        out.append(f"  - {h['order_number']} ({', '.join(filter(None, h['skus']))}): {why}")
    return out


def approval_message(plan):
    lines = []
    if not plan["items"]:
        lines.append("MFN run: nothing to buy.")
    else:
        lines.append(f"MFN run: {len(plan['items'])} label(s), ${plan['total']:.2f} total.")
        for l in plan["lines"]:
            lines.append(f"  - {l['order_number']} {', '.join(filter(None, l['skus']))}: "
                         f"{l['service']} ${l['charge']:.2f}")
        split = ", ".join(f"{n} x {s}" for s, n in sorted(plan["service_split"].items()))
        lines.append(f"Services: {split}")
    c = plan["counts"]
    if c.get("amazon_unshipped") is not None:
        lines.append(f"Counts: Veeqo {c['veeqo_ready']} ready, Amazon {c['amazon_unshipped']} "
                     f"unshipped, {c['mcf']} MCF — {'match' if c.get('counts_match') else 'MISMATCH'}")
    if plan["held"]:
        lines.append("Not buying:")
        lines += _held_lines(plan["held"])
    if plan["switches"]:
        lines.append("Carrier switches (OnTrac rule):")
        lines += [f"  - {s}" for s in plan["switches"]]
    if plan["flags"]:
        lines.append("Flags:")
        lines += [f"  - {f}" for f in plan["flags"]]
    if plan["items"]:
        lines.append(f"Quotes expire {plan['quotes_expire_at']}.")
        lines.append(f"Approve with code {plan['approval_code']}.")
    return "\n".join(lines)


def final_report(plan, statuses, print_result=None, scan_form_printed=None):
    by_status = {}
    for alloc, s in statuses.items():
        by_status.setdefault(s["status"], []).append(int(alloc))
    lines_by_alloc = {l["allocation_id"]: l for l in plan["lines"]}
    bought = [lines_by_alloc[a] for a in by_status.get("bought", []) if a in lines_by_alloc]
    spent = sum(l["charge"] for l in bought)

    out = [f"Labels bought: {len(bought)} of {len(plan['items'])}, ${spent:.2f}."]
    carriers = {}
    for l in bought:
        carriers[l["carrier"]] = carriers.get(l["carrier"], 0) + 1
    if carriers:
        out.append("Carriers: " + ", ".join(f"{k} {v}" for k, v in sorted(carriers.items())))
    for status, label in (("failed", "FAILED (may still be charged — do not retry blindly)"),
                          ("verify", "CHECK BY HAND (label may exist)")):
        for a in by_status.get(status, []):
            num = lines_by_alloc.get(a, {}).get("order_number", a)
            out.append(f"  {label}: {num}")
    mcf = [h for h in plan["held"] if "mcf" in h["reasons"]]
    if mcf:
        out.append("MCF skipped: " + ", ".join(h["order_number"] for h in mcf))
    if plan["switches"]:
        out.append("OnTrac switches: " + "; ".join(plan["switches"]))
    if print_result is not None:
        if print_result["complete"]:
            out.append("Printed: labels AND packing slips for every order.")
        else:
            out.append("PRINTING INCOMPLETE:")
            out += [f"  - {m['order_number']} {m['format']}: {m['state']}"
                    for m in print_result["missing"]]
            out += [f"  - job {f['job_id']} {f['format']} failed" for f in print_result["failed"]]
    if scan_form_printed is not None:
        out.append("USPS scan form printed." if scan_form_printed else "USPS scan form NOT printed.")
    out.append("Scan form covers USPS only — UPS/FedEx packages go to those carriers.")
    if plan["flags"]:
        out.append("Flags:")
        out += [f"  - {f}" for f in plan["flags"]]
    return "\n".join(out)
