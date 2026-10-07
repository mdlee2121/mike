import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from mfn import guard, rates
from mfn.plan import build_plan
from mfn.reconcile import reconcile
from tests.factory import datadoe_rows, lm_response, quote, rate, veeqo_list, veeqo_order

A, B = "113-0000001-0000001", "114-0000002-0000002"
BEFORE_EXPIRY = datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc)
AFTER_EXPIRY = datetime(2026, 10, 7, 7, 0, tzinfo=timezone.utc)
ONTRAC = rate("OnTrac Ground", "5.10", carrier="ontrac", sub="ONTRAC")


def make_plan(quotes_by_order, weight=16):
    orders = [veeqo_order(n, alloc_id=i + 1, weight=weight) for i, n in enumerate(quotes_by_order)]
    recon = reconcile(veeqo_list(*orders), lm_response(**{n: "MFN" for n in quotes_by_order}),
                      datadoe_rows(*quotes_by_order))
    quotes = {str(i + 1): q for i, q in enumerate(quotes_by_order.values())}
    return build_plan(recon, quotes, "2026-10-07T05:50:00+00:00")


class RateChoiceTest(unittest.TestCase):
    def test_first_rate_is_the_pick(self):
        pick, notes = rates.choose(quote(rate(), rate("UPS Ground", "9.34", "ups", "UPS")))
        self.assertEqual(pick["serviceTitle"], "USPS Ground Advantage (less than 1lb)")
        self.assertEqual(notes, [])

    def test_ontrac_is_switched_and_reported(self):
        pick, notes = rates.choose(quote(ONTRAC, rate()))
        self.assertEqual(pick["subCarrierId"], "USPS")
        self.assertEqual(notes[0]["kind"], "switch")
        self.assertIn("OnTrac Ground $5.10 -> USPS", notes[0]["text"])

    def test_expensive_switch_is_flagged(self):
        _, notes = rates.choose(quote(ONTRAC, rate("UPS Ground", "12.00", "ups", "UPS")))
        self.assertIn("flag", [n["kind"] for n in notes])

    def test_only_ontrac_means_no_rate(self):
        with self.assertRaises(rates.NoRate):
            rates.choose(quote(ONTRAC))

    def test_expedited_on_light_package_is_flagged(self):
        _, notes = rates.choose(quote(rate("FedEx 2Day®", "14.00", "fedex", "FEDEX")),
                                package_oz=16)
        self.assertTrue(any("expedited" in n["text"] for n in notes))

    def test_missed_promise_is_flagged(self):
        _, notes = rates.choose(quote(rate(promise=False)))
        self.assertTrue(any("delivery promise" in n["text"] for n in notes))

    def test_value_added_choice_is_refused(self):
        with self.assertRaises(rates.NoRate):
            rates.choose(quote(rate(vas=True)))


class PlanTest(unittest.TestCase):
    def test_charges_are_numbers_and_total_adds_up(self):
        plan = make_plan({A: quote(rate(charge="6.07")), B: quote(rate(charge="7.44"))})
        self.assertEqual([i["expected_charge"] for i in plan["items"]], [6.07, 7.44])
        self.assertEqual(plan["total"], 13.51)
        self.assertRegex(plan["approval_code"], r"^[0-9A-F]{8}$")

    def test_approval_code_changes_with_contents(self):
        p1 = make_plan({A: quote(rate(charge="6.07"))})
        p2 = make_plan({A: quote(rate(charge="6.08"))})
        self.assertNotEqual(p1["approval_code"], p2["approval_code"])

    def test_order_without_quote_is_left_out_and_flagged(self):
        plan = make_plan({A: quote(rate()), B: quote()})
        self.assertEqual(len(plan["items"]), 1)
        self.assertTrue(any(B in f and "no rates" in f for f in plan["flags"]))

    def test_earliest_expiry_wins(self):
        plan = make_plan({A: quote(rate(), expires="2026-10-07T08:00:00Z"),
                          B: quote(rate(), expires="2026-10-07T07:59:59+01:00")})
        self.assertEqual(plan["quotes_expire_at"], "2026-10-07T07:59:59+01:00")


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan({A: quote(rate()), B: quote(rate(charge="7.44"))})
        self.code = self.plan["approval_code"]
        self.ledger_path = os.path.join(tempfile.mkdtemp(), "state", "ledger.jsonl")

    def check(self, plan=None, code=None, now=BEFORE_EXPIRY):
        return guard.check_buy(plan or self.plan, code or self.code,
                               guard.load_ledger(self.ledger_path), now)

    def test_approved_plan_produces_payload(self):
        payload = self.check()
        self.assertEqual(payload["carrier"], "amazon_shipping_v2")
        self.assertEqual(len(payload["items"]), 2)

    def test_wrong_code_is_refused(self):
        with self.assertRaisesRegex(guard.BuyRefused, "does not match"):
            self.check(code="DEADBEEF")

    def test_code_is_case_insensitive(self):
        self.check(code=self.code.lower())

    def test_plan_edited_after_approval_is_refused(self):
        tampered = json.loads(json.dumps(self.plan))
        tampered["items"][0]["expected_charge"] = 1.00
        with self.assertRaisesRegex(guard.BuyRefused, "changed"):
            self.check(plan=tampered)

    def test_expired_quotes_are_refused(self):
        with self.assertRaisesRegex(guard.BuyRefused, "expired"):
            self.check(now=AFTER_EXPIRY)

    def test_string_charge_is_refused(self):
        bad = json.loads(json.dumps(self.plan))
        bad["items"][0]["expected_charge"] = "6.07"
        from mfn.plan import approval_code
        bad["approval_code"] = approval_code(bad["carrier"], bad["items"])
        with self.assertRaisesRegex(guard.BuyRefused, "must be a number"):
            self.check(plan=bad, code=bad["approval_code"])

    def test_second_buy_of_same_plan_is_refused(self):
        self.check()
        guard.record_buy(self.plan, settled_result(self.plan), self.ledger_path, BEFORE_EXPIRY)
        with self.assertRaisesRegex(guard.BuyRefused, "never buy twice"):
            self.check()

    def test_failed_item_blocks_rebuy(self):
        # A failed item may still have been charged — no automatic retry, ever.
        result = settled_result(self.plan, fail={1})
        statuses = guard.record_buy(self.plan, result, self.ledger_path, BEFORE_EXPIRY)
        self.assertEqual(statuses[1]["status"], "failed")
        self.assertEqual(statuses[2]["status"], "bought")
        replan = make_plan({A: quote(rate())})
        with self.assertRaisesRegex(guard.BuyRefused, "already in ledger"):
            guard.check_buy(replan, replan["approval_code"],
                            guard.load_ledger(self.ledger_path), BEFORE_EXPIRY)

    def test_unsettled_result_is_not_recorded(self):
        with self.assertRaises(ValueError):
            guard.record_buy(self.plan, {"settled": False, "items": []}, self.ledger_path)
        self.assertFalse(os.path.exists(self.ledger_path))

    def test_result_states_are_classified(self):
        result = {"settled": True, "bulkShipmentId": 9, "items": [
            {"allocationId": 1, "state": "started", "shipmentId": None},
            {"allocationId": 2, "state": "created", "shipmentId": 77},
        ], "labelConfirmedDespiteState": [1], "blockedByExistingShipment": [2]}
        statuses = guard.classify_result(result)
        self.assertEqual(statuses[1]["status"], "bought")
        self.assertEqual(statuses[2]["status"], "verify")

    def test_allocation_missing_from_result_is_recorded_as_verify(self):
        result = {"settled": True, "bulkShipmentId": 9,
                  "items": [{"allocationId": 1, "shipmentId": 5}]}
        statuses = guard.record_buy(self.plan, result, self.ledger_path, BEFORE_EXPIRY)
        self.assertEqual(statuses[2]["status"], "verify")
        self.assertEqual(len(guard.load_ledger(self.ledger_path)), 2)


def settled_result(plan, fail=()):
    items = []
    for i in plan["items"]:
        a = i["allocation_id"]
        if a in fail:
            items.append({"allocationId": a, "state": "failed", "errors": ["rate moved"]})
        else:
            items.append({"allocationId": a, "state": "completed", "shipmentId": 9000 + a})
    return {"settled": True, "complete": True, "bulkShipmentId": 42, "items": items}


if __name__ == "__main__":
    unittest.main()
