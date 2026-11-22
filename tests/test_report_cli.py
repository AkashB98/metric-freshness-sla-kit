import io, os, sys, unittest
from contextlib import redirect_stdout, redirect_stderr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli import main as cli_main
from generator import clean_partitions, partitions_to_json, seeded_partitions
from report import build_report

def run_cli(argv):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return cli_main(argv)

class TestReport(unittest.TestCase):
    def test_seeded_report_counts(self):
        rep = build_report()
        self.assertEqual(rep["total_cases"], 5); self.assertEqual(rep["served"], 2); self.assertEqual(rep["refused"], 3)
        self.assertEqual(rep["backfill_case"]["decision"], "REFUSE")
        self.assertEqual(rep["backfill_case"]["initial_decision"], "SERVE")
    def test_report_deterministic(self):
        self.assertEqual(build_report(), build_report())
    def test_generator_deterministic(self):
        self.assertEqual(partitions_to_json(seeded_partitions()), partitions_to_json(seeded_partitions()))
    def test_clean_set_all_serve(self):
        rep = build_report(clean_partitions())
        self.assertTrue(all(c["decision"] == "SERVE" for c in rep["cases"]))
        self.assertEqual(rep["refused"], 0)
    def test_naive_contrast_flag(self):
        self.assertTrue(build_report()["naive_vs_full_on_partial_load"]["naive_false_pass"])

class TestCli(unittest.TestCase):
    def test_check_seeded_exits_1_by_design(self): self.assertEqual(run_cli(["check"]), 1)
    def test_check_clean_exits_0(self): self.assertEqual(run_cli(["check", "--clean"]), 0)
    def test_check_missing_file_exits_2(self):
        self.assertEqual(run_cli(["check", "--input", "/tmp/no-such-freshness-xyz.json"]), 2)
    def test_report_exits_0(self): self.assertEqual(run_cli(["report"]), 0)

if __name__ == "__main__": unittest.main()
