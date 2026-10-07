import unittest

from mfn import reconcile as r
from tests.factory import datadoe_rows, lm_response, veeqo_list, veeqo_order

A, B, C = "113-0000001-0000001", "114-0000002-0000002", "112-0000003-0000003"


def held_reasons(recon, number):
    return [h["reasons"] for h in recon["held"] if h["order_number"] == number]


class ReconcileTest(unittest.TestCase):
    def test_clean_run_quotes_everything(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A), veeqo_order(B)),
                            lm_response(**{A: "MFN", B: "MFN"}), datadoe_rows(A, B))
        self.assertEqual([q["order_number"] for q in recon["to_quote"]], [A, B])
        self.assertEqual(recon["held"], [])
        self.assertTrue(recon["counts"]["counts_match"])

    def test_mcf_order_still_in_veeqo_is_never_quoted(self):
        # MCF orders sit in Veeqo until tracking posts; buying one pays twice.
        recon = r.reconcile(veeqo_list(veeqo_order(A), veeqo_order(B)),
                            lm_response(**{A: "MFN", B: "MCF"}), datadoe_rows(A, B))
        self.assertEqual([q["order_number"] for q in recon["to_quote"]], [A])
        self.assertEqual(held_reasons(recon, B), [[r.MCF]])
        self.assertEqual(recon["counts"]["mcf"], 1)

    def test_mcf_cannot_be_released_with_include(self):
        recon = r.reconcile(veeqo_list(veeqo_order(B)), lm_response(**{B: "MCF"}),
                            datadoe_rows(B), include=[B])
        self.assertEqual(recon["to_quote"], [])

    def test_lm_unknown_and_missing_verdicts_are_held(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A), veeqo_order(B)),
                            lm_response(**{A: "unknown"}), datadoe_rows(A, B))
        self.assertEqual(recon["to_quote"], [])
        self.assertEqual(held_reasons(recon, A), [[r.LM_UNKNOWN]])
        self.assertEqual(held_reasons(recon, B), [[r.LM_UNKNOWN]])

    def test_unknown_can_be_released_by_michael(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A)), lm_response(**{A: "unknown"}),
                            datadoe_rows(A), include=[A])
        self.assertEqual(len(recon["to_quote"]), 1)
        self.assertTrue(any("released by Michael" in f for f in recon["flags"]))

    def test_puerto_rico_goes_to_customs_gate(self):
        # Oct 6 2026: the API quoted and dry-ran an order the UI blocked on customs.
        recon = r.reconcile(veeqo_list(veeqo_order(A, international=True)),
                            lm_response(**{A: "MFN"}), datadoe_rows(A))
        self.assertEqual(recon["to_quote"], [])
        self.assertEqual(held_reasons(recon, A), [[r.INTERNATIONAL]])

    def test_international_cannot_be_released(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A, international=True)),
                            lm_response(**{A: "MFN"}), datadoe_rows(A), include=[A])
        self.assertEqual(recon["to_quote"], [])

    def test_order_missing_from_veeqo_is_flagged(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A)), lm_response(**{A: "MFN"}),
                            datadoe_rows(A, C))
        self.assertEqual(recon["amazon_only"], [C])
        self.assertFalse(recon["counts"]["counts_match"])
        self.assertTrue(any(C in f and "not in Veeqo" in f for f in recon["flags"]))

    def test_order_not_on_amazon_unshipped_is_held(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A), veeqo_order(B)),
                            lm_response(**{A: "MFN", B: "MFN"}), datadoe_rows(A))
        self.assertEqual(held_reasons(recon, B), [[r.NOT_ON_AMAZON]])

    def test_no_amazon_data_is_flagged_not_silently_ignored(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A)), lm_response(**{A: "MFN"}), None)
        self.assertEqual(len(recon["to_quote"]), 1)
        self.assertTrue(any("cross-check did not run" in f for f in recon["flags"]))

    def test_already_labelled_allocation_is_skipped(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A, shipment_id=555)),
                            lm_response(**{A: "MFN"}), datadoe_rows(A))
        self.assertEqual(recon["to_quote"], [])
        self.assertEqual(held_reasons(recon, A), [[r.ALREADY_LABELLED]])

    def test_unshippable_order_is_held(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A, can_ship=False)),
                            lm_response(**{A: "MFN"}), datadoe_rows(A))
        self.assertEqual(held_reasons(recon, A), [[r.NOT_SHIPPABLE]])

    def test_other_channel_is_ignored(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A, channel_id=185260)),
                            lm_response(**{A: "MFN"}), datadoe_rows())
        self.assertEqual(recon["to_quote"], [])

    def test_missing_weight_is_flagged(self):
        recon = r.reconcile(veeqo_list(veeqo_order(A, weight=0)), lm_response(**{A: "MFN"}),
                            datadoe_rows(A))
        self.assertTrue(any("no weight" in f for f in recon["flags"]))

    def test_datadoe_line_items_are_deduplicated(self):
        rows = datadoe_rows(A, A, A)  # one row per line item
        recon = r.reconcile(veeqo_list(veeqo_order(A)), lm_response(**{A: "MFN"}), rows)
        self.assertEqual(recon["counts"]["amazon_unshipped"], 1)


if __name__ == "__main__":
    unittest.main()
