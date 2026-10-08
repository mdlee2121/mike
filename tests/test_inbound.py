import json
import os
import tempfile
import unittest
import zipfile

from inbound import config, stafile
from inbound.cli import main
from inbound.stage import StageRefused, barcode_problem, build_stage


def line(sku, qty, fnsku="X00TESTFN1", asin="B000000001"):
    return {"sku": sku, "asin": asin, "fnsku": fnsku, "qty": qty}


def doc(*lines, vendor="Radial", invoice="INV38499"):
    return {"vendor": vendor, "invoice": invoice, "lines": list(lines)}


class BarcodeTest(unittest.TestCase):
    def test_amazon_barcode_is_fine(self):
        self.assertIsNone(barcode_problem("A", "B00009J580", "X005CP3PVP"))

    def test_fnsku_equal_to_asin_is_commingled(self):
        self.assertIn("a-suffix", barcode_problem("A", "B00009J580", "b00009j580"))

    def test_blank_fnsku_is_held(self):
        self.assertIn("no FBA barcode", barcode_problem("A", "B00009J580", ""))


class SplitTest(unittest.TestCase):
    def test_under_five_goes_to_part_2(self):
        s = build_stage(doc(line("RADR8001100A", 40), line("RADPROD8", 2), line("RADJ48", 5)))
        names = [w["name"] for w in s["workflows"]]
        self.assertEqual(names, ["Radial INV38499", "Radial INV38499 Part 2"])
        self.assertEqual([r["sku"] for r in s["workflows"][0]["skus"]], ["RADR8001100A", "RADJ48"])
        self.assertEqual(s["workflows"][1]["expected_counter"], "SKUs ready to send: 1 (2 units)")

    def test_no_part_2_when_everything_is_five_or_more(self):
        s = build_stage(doc(line("A", 5), line("B", 12)))
        self.assertEqual(len(s["workflows"]), 1)
        self.assertEqual(s["workflows"][0]["units"], 17)

    def test_all_small_is_one_workflow_and_flagged(self):
        s = build_stage(doc(line("A", 1), line("B", 4)))
        self.assertEqual([w["name"] for w in s["workflows"]], ["Radial INV38499"])
        self.assertTrue(any("optimized" in f for f in s["flags"]))

    def test_duplicate_sku_lines_are_added_before_splitting(self):
        s = build_stage(doc(line("A", 3), line("A", 3)))
        self.assertEqual(s["workflows"][0]["skus"][0]["qty"], 6)
        self.assertEqual(s["workflows"][0]["name"], "Radial INV38499")

    def test_bad_barcodes_are_held_not_staged(self):
        s = build_stage(doc(line("A", 10), line("B", 10, fnsku="B000000001"), line("C", 10, fnsku="")))
        self.assertEqual([r["sku"] for r in s["workflows"][0]["skus"]], ["A"])
        self.assertEqual([h["sku"] for h in s["held"]], ["B", "C"])

    def test_refuses_bad_quantity_and_missing_names(self):
        for bad in (0, -1, 2.5, "3", True, None):
            with self.assertRaises(StageRefused):
                build_stage(doc(line("A", bad)))
        with self.assertRaises(StageRefused):
            build_stage(doc(line("A", 5), invoice=""))


class FileTest(unittest.TestCase):
    def test_sheet_rows_follow_the_template(self):
        wf = build_stage(doc(line("A&B", 7)))["workflows"][0]
        rows = stafile.sheet_rows(wf)
        self.assertEqual(rows[0], ["Default prep owner", config.PREP_OWNER])
        self.assertEqual(rows[3], list(config.STA_HEADER))
        self.assertEqual(rows[4], ["A&B", 7, config.PREP_OWNER, config.LABELING_OWNER])

    def test_cli_writes_one_file_per_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.json")
            with open(src, "w") as f:
                json.dump(doc(line("A&B", 7), line("C", 2), line("D", 3, fnsku="")), f)
            out = os.path.join(d, "out")
            self.assertEqual(main(["sta-file", "--input", src, "--out-dir", out]), 1)
            files = sorted(os.listdir(out))
            self.assertEqual(files, ["Radial_INV38499.xlsx", "Radial_INV38499_Part_2.xlsx", "stage.json"])
            with zipfile.ZipFile(os.path.join(out, "Radial_INV38499.xlsx")) as z:
                self.assertIsNone(z.testzip())
                sheet = z.read("xl/worksheets/sheet1.xml").decode()
            self.assertIn("A&amp;B", sheet)
            self.assertIn('<c r="B5"><v>7</v></c>', sheet)


if __name__ == "__main__":
    unittest.main()
