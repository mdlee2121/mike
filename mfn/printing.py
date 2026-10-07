"""Step 3: print every document in Michael's saved preference, and prove it happened.

Buying through the API prints nothing. The known failure (Oct 6 2026) was printing
labels but not packing slips. print_check() only passes when every bought order has
every template in a print job that is ready AND was sent to a printer.
"""
from mfn import config


def required_templates(prefs):
    """Templates from veeqo_get_printing_preferences, label templates first."""
    templates = prefs.get("templates") or []
    if not templates:
        raise ValueError("printing preference returned no templates")
    return sorted(templates, key=lambda t: t["format"] not in config.LABEL_TEMPLATE_FORMATS)


def printer_for(template, prefs):
    if template["format"] in config.LABEL_TEMPLATE_FORMATS:
        return config.LABEL_PRINTER
    # Non-label documents follow the saved document size, not the UI's DirectPrint routing.
    return config.LABEL_PRINTER if prefs.get("documentSize") == "4x6" else config.LETTER_PRINTER


def print_plan(prefs, order_ids):
    """The veeqo_generate_order_document calls to make — one per template.

    Label and non-label templates must never share a call: mixing them fails the batch.
    """
    if not order_ids:
        return []
    return [{
        "order_ids": list(order_ids),
        "templates": [{"templateRef": t["name"]}],
        "format": t["format"],
        "printer": printer_for(t, prefs),
    } for t in required_templates(prefs)]


def _job_orders(job):
    return {s.strip() for s in (job.get("identifier") or "").split(",") if s.strip()}


def print_check(prefs, order_numbers, jobs, printed_job_ids):
    """jobs: veeqo_list_print_jobs results; printed_job_ids: jobs confirmed sent to a printer."""
    jobs = jobs.get("results", []) if isinstance(jobs, dict) else jobs
    printed = {str(j) for j in printed_job_ids}
    wanted = set(order_numbers)

    missing, to_print, failed = [], [], []
    for template in required_templates(prefs):
        covered_ready, covered_printed = set(), set()
        for job in jobs:
            formats = {t.get("format") for t in job.get("templates") or []}
            if template["format"] not in formats:
                continue
            orders = _job_orders(job) & wanted
            if not orders:
                continue
            if job.get("status") == "failed" or job.get("failures"):
                failed.append({"job_id": job["jobId"], "format": template["format"],
                               "failures": job.get("failures")})
                continue
            if job.get("status") != "document_ready":
                continue
            covered_ready |= orders
            if str(job["jobId"]) in printed:
                covered_printed |= orders
            elif not orders <= covered_printed:
                to_print.append({"job_id": job["jobId"], "format": template["format"],
                                 "printer": printer_for(template, prefs),
                                 "urls": job.get("documentUrls") or []})
        for number in sorted(wanted - covered_printed):
            missing.append({"order_number": number, "format": template["format"],
                            "state": "ready, not printed" if number in covered_ready
                            else "no ready document"})

    return {"complete": not missing and not failed, "missing": missing,
            "to_print": to_print, "failed": failed}
