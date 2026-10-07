"""Command line: python -m mfn <step> ...

Every step reads and writes JSON files, so the same commands work whether the data
came from Cowork connectors today or from direct API calls in the cloud later.
Exit codes: 0 ok, 1 incomplete/attention needed, 2 refused.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

from mfn import guard, printing, report
from mfn.plan import build_plan
from mfn.reconcile import reconcile


def _load(path):
    with open(path) as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _run_statuses(plan, ledger_path):
    """This run's ledger entries, keyed by allocation id."""
    ledger = guard.load_ledger(ledger_path)
    mine = {int(i["allocation_id"]) for i in plan["items"]}
    return {a: e for a, e in ledger.items()
            if a in mine and e.get("approval_code") == plan["approval_code"]}


def cmd_reconcile(a):
    amazon = None if a.no_amazon else _load(a.amazon)
    recon = reconcile(_load(a.veeqo), _load(a.lm), amazon, include=a.include or ())
    _save(a.out, recon)
    print(json.dumps(recon["counts"]))
    print("quote these allocations:", " ".join(str(q["allocation_id"]) for q in recon["to_quote"]))
    return 0


def cmd_plan(a):
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    plan = build_plan(_load(a.recon), _load(a.quotes), created)
    _save(a.out, plan)
    print(report.approval_message(plan))
    return 0


def cmd_check_buy(a):
    plan = _load(a.plan)
    try:
        payload = guard.check_buy(plan, a.code, guard.load_ledger(a.ledger))
    except guard.BuyRefused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    if a.out:
        _save(a.out, payload)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_record_buy(a):
    statuses = guard.record_buy(_load(a.plan), _load(a.result), a.ledger)
    print(json.dumps({str(k): v for k, v in statuses.items()}, indent=2))
    return 0 if all(s["status"] == "bought" for s in statuses.values()) else 1


def _bought(plan, ledger_path):
    statuses = _run_statuses(plan, ledger_path)
    lines = {l["allocation_id"]: l for l in plan["lines"]}
    return [lines[a] for a, e in statuses.items() if e["status"] == "bought" and a in lines]


def cmd_print_plan(a):
    plan = _load(a.plan)
    bought = _bought(plan, a.ledger)
    order_ids = list(dict.fromkeys(l["order_id"] for l in bought))
    calls = printing.print_plan(_load(a.prefs), order_ids)
    print(json.dumps(calls, indent=2))
    return 0


def cmd_print_check(a):
    plan = _load(a.plan)
    numbers = sorted({l["order_number"] for l in _bought(plan, a.ledger)})
    printed = [p for p in (a.printed or "").split(",") if p]
    result = printing.print_check(_load(a.prefs), numbers, _load(a.jobs), printed)
    if a.out:
        _save(a.out, result)
    print(json.dumps(result, indent=2))
    return 0 if result["complete"] else 1


def cmd_report(a):
    plan = _load(a.plan)
    statuses = _run_statuses(plan, a.ledger)
    pc = _load(a.print_check) if a.print_check else None
    scan = None if a.scan_form is None else a.scan_form == "yes"
    print(report.final_report(plan, statuses, pc, scan))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mfn", description="Instrumentpro MFN label run")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("reconcile", help="cross-check Veeqo, Listing Mirror and Amazon")
    s.add_argument("--veeqo", required=True)
    s.add_argument("--lm", required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--amazon")
    g.add_argument("--no-amazon", action="store_true")
    s.add_argument("--include", nargs="*", help="order numbers Michael released from review")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_reconcile)

    s = sub.add_parser("plan", help="pick rates and make the approval code")
    s.add_argument("--recon", required=True)
    s.add_argument("--quotes", required=True, help="{allocation_id: rates response}")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_plan)

    s = sub.add_parser("check-buy", help="verify approval and emit the exact buy payload")
    s.add_argument("--plan", required=True)
    s.add_argument("--code", required=True)
    s.add_argument("--ledger", required=True)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_check_buy)

    s = sub.add_parser("record-buy", help="write the settled bulk result to the ledger")
    s.add_argument("--plan", required=True)
    s.add_argument("--result", required=True)
    s.add_argument("--ledger", required=True)
    s.set_defaults(fn=cmd_record_buy)

    s = sub.add_parser("print-plan", help="list the document calls to make")
    s.add_argument("--plan", required=True)
    s.add_argument("--ledger", required=True)
    s.add_argument("--prefs", required=True)
    s.set_defaults(fn=cmd_print_plan)

    s = sub.add_parser("print-check", help="prove labels AND slips were printed")
    s.add_argument("--plan", required=True)
    s.add_argument("--ledger", required=True)
    s.add_argument("--prefs", required=True)
    s.add_argument("--jobs", required=True)
    s.add_argument("--printed", help="comma-separated job ids sent to a printer")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_print_check)

    s = sub.add_parser("report", help="end-of-run summary")
    s.add_argument("--plan", required=True)
    s.add_argument("--ledger", required=True)
    s.add_argument("--print-check")
    s.add_argument("--scan-form", choices=("yes", "no"))
    s.set_defaults(fn=cmd_report)

    a = p.parse_args(argv)
    return a.fn(a)
