"""Full run through the command line on data shaped like the live Oct 7 2026 responses."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from mfn import cli

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
BEFORE_EXPIRY = datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc)


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.p = lambda name: os.path.join(self.dir, name)
        self.f = lambda name: os.path.join(FIX, name)
        self.ledger = self.p("ledger.jsonl")
        # The fixture quotes expire 06:59Z; pin "now" before that.
        patcher = mock.patch("mfn.guard.datetime", wraps=datetime)
        self.addCleanup(patcher.stop)
        patcher.start().now.return_value = BEFORE_EXPIRY

    def test_full_run(self):
        code, out, _ = run("reconcile", "--veeqo", self.f("veeqo_orders.json"),
                           "--lm", self.f("lm_verdicts.json"),
                           "--amazon", self.f("datadoe_unshipped.json"), "--out", self.p("recon.json"))
        self.assertEqual(code, 0)
        self.assertIn("1617190851", out)
        self.assertNotIn("1617000001", out)  # the MCF order's allocation

        code, out, _ = run("plan", "--recon", self.p("recon.json"),
                           "--quotes", self.f("quotes.json"), "--out", self.p("plan.json"))
        plan = cli._load(self.p("plan.json"))
        self.assertEqual(plan["total"], 12.92)                       # 6.85 + 6.07
        self.assertIn("OnTrac Ground $5.25 -> USPS", out)             # switch reported
        self.assertIn("MCF order — Amazon ships it", out)
        self.assertIn("not yet requested", out)
        self.assertIn(f"Approve with code {plan['approval_code']}", out)

        code, _, err = run("check-buy", "--plan", self.p("plan.json"), "--code", "WRONG123",
                           "--ledger", self.ledger)
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err)

        code, out, _ = run("check-buy", "--plan", self.p("plan.json"),
                           "--code", plan["approval_code"], "--ledger", self.ledger,
                           "--out", self.p("payload.json"))
        self.assertEqual(code, 0)
        payload = cli._load(self.p("payload.json"))
        self.assertTrue(all(isinstance(i["expected_charge"], float) for i in payload["items"]))
        self.assertNotIn("ontrac", json.dumps(payload).lower())

        code, _, _ = run("record-buy", "--plan", self.p("plan.json"),
                         "--result", self.f("bulk_result.json"), "--ledger", self.ledger)
        self.assertEqual(code, 0)

        code, _, err = run("check-buy", "--plan", self.p("plan.json"),
                           "--code", plan["approval_code"], "--ledger", self.ledger)
        self.assertEqual(code, 2)
        self.assertIn("never buy twice", err)

        code, out, _ = run("print-plan", "--plan", self.p("plan.json"), "--ledger", self.ledger,
                           "--prefs", self.f("printing_preferences.json"))
        calls = json.loads(out)
        self.assertEqual([c["format"] for c in calls], ["shipping_labels", "packing_slip"])
        self.assertEqual(sorted(calls[0]["order_ids"]), [2177670160, 2177795799])

        common = ["print-check", "--plan", self.p("plan.json"), "--ledger", self.ledger,
                  "--prefs", self.f("printing_preferences.json"), "--jobs", self.f("print_jobs.json")]
        code, _, _ = run(*common, "--printed", "200001")
        self.assertEqual(code, 1)  # labels only: refuse to call the run done
        code, _, _ = run(*common, "--printed", "200001,200002", "--out", self.p("pc.json"))
        self.assertEqual(code, 0)

        code, out, _ = run("report", "--plan", self.p("plan.json"), "--ledger", self.ledger,
                           "--print-check", self.p("pc.json"), "--scan-form", "yes")
        self.assertIn("Labels bought: 2 of 2, $12.92", out)
        self.assertIn("labels AND packing slips", out)
        self.assertIn("MCF skipped: 112-9999999-0000001", out)


if __name__ == "__main__":
    unittest.main()
