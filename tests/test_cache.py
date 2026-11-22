import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cache import AnswerCache
from checker import check_partition
from generator import METRICS, backfill_pair

class TestBackfill(unittest.TestCase):
    def setUp(self):
        self.original, self.rewritten = backfill_pair()
        self.cache = AnswerCache()
        v = check_partition(METRICS["daily_revenue"], self.original, "2026-01-14T12:00:00Z")
        assert v.decision == "SERVE"
        self.cache.store(self.original, v)
    def test_cached_answer_serves_before_backfill(self):
        self.assertEqual(self.cache.reservice_check(self.original).decision, "SERVE")
    def test_backfill_rewrite_invalidates(self):
        v = self.cache.reservice_check(self.rewritten)
        self.assertEqual(v.decision, "REFUSE"); self.assertIn("BACKFILL_INVALIDATED", v.reasons)
        self.assertIsNone(v.value)
    def test_hashes_differ(self):
        self.assertNotEqual(self.original.content_hash, self.rewritten.content_hash)
        self.assertEqual(self.original.partition_id, self.rewritten.partition_id)
    def test_uncached_partition_refused(self):
        v = AnswerCache().reservice_check(self.original)
        self.assertEqual(v.decision, "REFUSE"); self.assertIn("NOT_CACHED", v.reasons)
    def test_refuse_verdict_cannot_be_cached(self):
        from models import Verdict
        with self.assertRaises(ValueError):
            AnswerCache().store(self.original, Verdict("daily_revenue", "x", "REFUSE", ["STALE"], "", None))
    def test_invalidate(self):
        self.cache.invalidate("daily_revenue", self.original.partition_id)
        self.assertEqual(self.cache.reservice_check(self.original).reasons, ["NOT_CACHED"])

if __name__ == "__main__": unittest.main()
