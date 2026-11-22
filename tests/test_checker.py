import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from checker import check_partition, naive_timestamp_check
from generator import METRICS, NOW, seeded_partitions

def by_id(pid): return next(p for p in seeded_partitions() if p.partition_id == pid)

class TestPlantedCases(unittest.TestCase):
    def test_clean_controls_serve(self):
        for pid in ("rev-2026-01-15", "au-2026-01-15"):
            p = by_id(pid)
            v = check_partition(METRICS[p.metric], p, NOW)
            self.assertEqual(v.decision, "SERVE", pid); self.assertEqual(v.reasons, [])
            self.assertIsNotNone(v.value)
    def test_late_partition_refused_stale(self):
        p = by_id("rev-2026-01-12"); v = check_partition(METRICS[p.metric], p, NOW)
        self.assertEqual(v.decision, "REFUSE"); self.assertIn("STALE", v.reasons); self.assertIsNone(v.value)
    def test_partial_load_refused_incomplete(self):
        p = by_id("rev-2026-01-15-partial"); v = check_partition(METRICS[p.metric], p, NOW)
        self.assertEqual(v.decision, "REFUSE"); self.assertIn("INCOMPLETE", v.reasons)
        self.assertNotIn("STALE", v.reasons)
    def test_stale_definition_refused_superseded(self):
        p = by_id("rev-2026-01-15-v1"); v = check_partition(METRICS[p.metric], p, NOW)
        self.assertEqual(v.decision, "REFUSE"); self.assertEqual(v.reasons, ["SUPERSEDED"])
    def test_naive_false_passes_partial_load(self):
        p = by_id("rev-2026-01-15-partial")
        naive = naive_timestamp_check(METRICS[p.metric], p, NOW)
        full = check_partition(METRICS[p.metric], p, NOW)
        self.assertEqual(naive.decision, "SERVE"); self.assertEqual(full.decision, "REFUSE")
    def test_naive_catches_genuinely_late_load(self):
        p = by_id("rev-2026-01-12")
        self.assertEqual(naive_timestamp_check(METRICS[p.metric], p, NOW).decision, "REFUSE")
    def test_naive_also_serves_clean(self):
        p = by_id("rev-2026-01-15")
        self.assertEqual(naive_timestamp_check(METRICS[p.metric], p, NOW).decision, "SERVE")
    def test_completeness_at_threshold_serves(self):
        from models import Partition
        p = Partition("daily_revenue", "edge", "2026-01-15T11:00:00Z", "2026-01-15T06:00:00Z", 950, 1000, "v2", 1.0, "h")
        self.assertEqual(check_partition(METRICS["daily_revenue"], p, NOW).decision, "SERVE")
    def test_completeness_just_below_threshold_refuses(self):
        from models import Partition
        p = Partition("daily_revenue", "edge2", "2026-01-15T11:00:00Z", "2026-01-15T06:00:00Z", 949, 1000, "v2", 1.0, "h")
        self.assertEqual(check_partition(METRICS["daily_revenue"], p, NOW).decision, "REFUSE")
    def test_freshness_exactly_at_sla_serves(self):
        from models import Partition
        p = Partition("daily_revenue", "edge3", "2026-01-15T11:00:00Z", "2026-01-14T10:00:00Z", 1000, 1000, "v2", 1.0, "h")
        self.assertEqual(check_partition(METRICS["daily_revenue"], p, NOW).decision, "SERVE")
    def test_multiple_reasons_accumulate(self):
        from models import Partition
        p = Partition("daily_revenue", "bad", "2026-01-13T01:00:00Z", "2026-01-13T00:00:00Z", 10, 1000, "v1", 1.0, "h")
        v = check_partition(METRICS["daily_revenue"], p, NOW)
        self.assertEqual(set(v.reasons), {"STALE", "INCOMPLETE", "SUPERSEDED"})

if __name__ == "__main__": unittest.main()
