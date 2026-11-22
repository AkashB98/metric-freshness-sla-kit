import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import seeded_partitions
from models import Partition
from validation import validate_partitions

class TestValidation(unittest.TestCase):
    def test_seeded_validates_clean(self):
        self.assertEqual(validate_partitions(seeded_partitions()), [])
    def test_bool_rows_rejected(self):
        p = Partition("daily_revenue", "x", "2026-01-15T11:00:00Z", "2026-01-15T06:00:00Z", True, 1000, "v2", 1.0, "h")
        self.assertTrue(any("must be int" in i for i in validate_partitions([p])))
    def test_negative_rows_rejected(self):
        p = Partition("daily_revenue", "x", "2026-01-15T11:00:00Z", "2026-01-15T06:00:00Z", -5, 1000, "v2", 1.0, "h")
        self.assertTrue(validate_partitions([p]))
    def test_bad_timestamp_rejected(self):
        p = Partition("daily_revenue", "x", "not-a-time", "2026-01-15T06:00:00Z", 100, 1000, "v2", 1.0, "h")
        self.assertTrue(any("bad timestamp" in i for i in validate_partitions([p])))

if __name__ == "__main__": unittest.main()
