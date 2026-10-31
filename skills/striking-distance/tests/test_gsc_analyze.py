#!/usr/bin/env python3
"""Unit tests for gsc_analyze.py — run against the bundled sample export."""

import importlib.util
import json
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "scripts" / "gsc_analyze.py"
SAMPLE = SKILL_DIR / "scripts" / "sample_gsc.csv"

spec = importlib.util.spec_from_file_location("gsc_analyze", SCRIPT)
gsc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gsc)


class TestParsing(unittest.TestCase):
    def test_ctr_percent_string(self):
        self.assertAlmostEqual(gsc.parse_ctr("12.5%"), 0.125)

    def test_ctr_plain_ratio(self):
        self.assertAlmostEqual(gsc.parse_ctr("0.125"), 0.125)

    def test_ctr_plain_percent_number(self):
        self.assertAlmostEqual(gsc.parse_ctr("12.5"), 0.125)

    def test_missing_query_column_raises(self):
        import csv
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", delete=False) as tmp:
            tmp.write("Clicks,Impressions\n1,2\n")
            name = tmp.name
        try:
            with self.assertRaises(ValueError):
                gsc.load_rows(name)
        finally:
            os.unlink(name)

    def test_sample_loads(self):
        rows = gsc.load_rows(str(SAMPLE))
        self.assertEqual(len(rows), 22)
        self.assertTrue(all(r["query"] for r in rows))


class TestAnalyses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = gsc.analyze(str(SAMPLE))

    def test_meta_counts(self):
        self.assertEqual(self.result["meta"]["rows"], 22)
        self.assertEqual(self.result["meta"]["queries"], 20)

    def test_striking_distance_top_query(self):
        top = self.result["striking_distance"][0]
        self.assertEqual(top["query"], "buy running shoes")
        self.assertEqual(top["impressions"], 5200)

    def test_striking_distance_bounds(self):
        for q in self.result["striking_distance"]:
            self.assertGreater(q["position"], 7.0)
            self.assertLessEqual(q["position"], 20.0)

    def test_striking_distance_sorted_by_impressions(self):
        imps = [q["impressions"] for q in self.result["striking_distance"]]
        self.assertEqual(imps, sorted(imps, reverse=True))

    def test_page_one_query_not_striking(self):
        queries = [q["query"] for q in self.result["striking_distance"]]
        self.assertNotIn("digikala discount code", queries)

    def test_ctr_opportunity_flags_low_ctr(self):
        flagged = {q["query"]: q for q in self.result["ctr_opportunities"]}
        self.assertIn("buy running shoes", flagged)
        self.assertIn("dubai visa apply", flagged)
        self.assertGreater(
            flagged["buy running shoes"]["est_extra_clicks"], 0)

    def test_ctr_benchmark_is_self_computed(self):
        flagged = {q["query"]: q for q in self.result["ctr_opportunities"]}
        # median of [2.5, 7.0, 8.0] at rounded position 9
        # (marathon training plan rounds to 10, so it is not a peer)
        self.assertEqual(flagged["buy running shoes"]["peer_median_ctr"], 7.0)

    def test_ctr_healthy_query_not_flagged(self):
        flagged = [q["query"] for q in self.result["ctr_opportunities"]]
        self.assertNotIn("tehran hotel booking", flagged)

    def test_cannibalization_finds_two_page_query(self):
        can = {q["query"]: q for q in self.result["cannibalization"]}
        self.assertIn("gorgan restaurants", can)
        pages = can["gorgan restaurants"]["pages"]
        self.assertEqual(len(pages), 2)
        self.assertEqual(
            {p["url"] for p in pages}, {"/restaurants", "/food"})

    def test_cannibalization_second_query(self):
        can = {q["query"]: q for q in self.result["cannibalization"]}
        self.assertIn("wireless earbuds under 50", can)

    def test_single_page_query_not_cannibalized(self):
        can = [q["query"] for q in self.result["cannibalization"]]
        self.assertNotIn("buy running shoes", can)

    def test_json_serializable(self):
        text = json.dumps(self.result, ensure_ascii=False)
        back = json.loads(text)
        self.assertIn("striking_distance", back)
        self.assertIn("ctr_opportunities", back)
        self.assertIn("cannibalization", back)


if __name__ == "__main__":
    unittest.main()
