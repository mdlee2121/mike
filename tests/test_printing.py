import unittest

from mfn import printing
from tests.factory import PREFS, print_job

A, B = "113-0000001-0000001", "114-0000002-0000002"


class PrintPlanTest(unittest.TestCase):
    def test_one_call_per_template_never_mixed(self):
        calls = printing.print_plan(PREFS, [11, 22])
        self.assertEqual([c["format"] for c in calls], ["shipping_labels", "packing_slip"])
        for c in calls:
            self.assertEqual(len(c["templates"]), 1)
            self.assertEqual(c["order_ids"], [11, 22])

    def test_4x6_slips_go_to_the_zebra(self):
        # Oct 6 2026: the UI's "Preview in browser" routing was wrongly treated as a veto.
        calls = printing.print_plan(PREFS, [11])
        self.assertEqual({c["printer"] for c in calls}, {"4X6 Zebra"})

    def test_letter_slips_go_to_the_canon(self):
        prefs = {**PREFS, "documentSize": "letter"}
        calls = printing.print_plan(prefs, [11])
        self.assertEqual(calls[1]["printer"], "Canon Printer")

    def test_no_templates_is_an_error(self):
        with self.assertRaises(ValueError):
            printing.print_plan({"templates": []}, [11])


class PrintCheckTest(unittest.TestCase):
    def jobs(self):
        return [print_job(2, [A, B], "packing_slip", "[Veeqo]packing_slip"),
                print_job(1, [A, B], "shipping_labels")]

    def test_labels_without_slips_fails(self):
        # The exact Oct 6 2026 failure.
        result = printing.print_check(PREFS, [A, B], self.jobs(), printed_job_ids=["1"])
        self.assertFalse(result["complete"])
        self.assertEqual({m["format"] for m in result["missing"]}, {"packing_slip"})
        self.assertEqual(result["to_print"][0]["job_id"], "2")

    def test_everything_printed_passes(self):
        result = printing.print_check(PREFS, [A, B], self.jobs(), printed_job_ids=["1", "2"])
        self.assertTrue(result["complete"])

    def test_job_missing_an_order_fails(self):
        jobs = [print_job(2, [A], "packing_slip"), print_job(1, [A, B], "shipping_labels")]
        result = printing.print_check(PREFS, [A, B], jobs, ["1", "2"])
        self.assertEqual(result["missing"], [{"order_number": B, "format": "packing_slip",
                                              "state": "no ready document"}])

    def test_still_rendering_is_not_printed(self):
        jobs = [print_job(2, [A], "packing_slip", status="document_generating"),
                print_job(1, [A], "shipping_labels")]
        result = printing.print_check(PREFS, [A], jobs, ["1", "2"])
        self.assertFalse(result["complete"])

    def test_failed_job_is_reported(self):
        jobs = [print_job(2, [A], "packing_slip", status="failed"),
                print_job(1, [A], "shipping_labels")]
        result = printing.print_check(PREFS, [A], jobs, ["1"])
        self.assertEqual(result["failed"][0]["job_id"], "2")

    def test_accepts_raw_list_print_jobs_response(self):
        result = printing.print_check(PREFS, [A, B], {"results": self.jobs()}, ["1", "2"])
        self.assertTrue(result["complete"])


if __name__ == "__main__":
    unittest.main()
