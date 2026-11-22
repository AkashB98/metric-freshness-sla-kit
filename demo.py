"""End-to-end demo: seeded scenarios -> verdicts -> naive contrast
-> backfill invalidation -> CLI exit codes. Exits 0. Asserts throughout.
SYNTHETIC DATA ONLY; fixed injected clock, no wall clock, no network.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cache import AnswerCache
from checker import check_partition, naive_timestamp_check
from cli import main as cli_main
from generator import METRICS, NOW, backfill_pair, seeded_partitions
from report import build_report

def main():
    print("== 1. seeded scenarios through the full checker ==")
    rep = build_report()
    for c in rep["cases"]:
        print(f"   {c['case']}: {c['partition_id']} -> {c['decision']} {c['reasons']}")
    bc = rep["backfill_case"]
    print(f"   {bc['case']}: {bc['partition_id']} -> {bc['decision']} {bc['reasons']}")
    by_case = {}
    for c in rep["cases"]:
        by_case.setdefault(c["case"], []).append(c)
    assert all(c["decision"] == "SERVE" for c in by_case["clean_control"])
    assert by_case["late_partition"][0]["decision"] == "REFUSE"
    assert by_case["partial_load"][0]["decision"] == "REFUSE"
    assert by_case["stale_definition"][0]["decision"] == "REFUSE"
    assert bc["decision"] == "REFUSE" and bc["initial_decision"] == "SERVE"

    print("\n== 2. headline: naive timestamp-only checker false-passes the partial load ==")
    contrast = rep["naive_vs_full_on_partial_load"]
    print(f"   naive={contrast['naive_decision']} full={contrast['full_decision']} "
          f"false_pass={contrast['naive_false_pass']}")
    assert contrast["naive_false_pass"] is True

    print("\n== 3. backfill rewrite invalidates the cached answer ==")
    original, rewritten = backfill_pair()
    cache = AnswerCache()
    v = check_partition(METRICS[original.metric], original, "2026-01-14T12:00:00Z")
    assert v.decision == "SERVE"
    cache.store(original, v)
    assert cache.reservice_check(original).decision == "SERVE"
    recheck = cache.reservice_check(rewritten)
    print(f"   re-serve after backfill -> {recheck.decision} {recheck.reasons}")
    assert recheck.decision == "REFUSE" and "BACKFILL_INVALIDATED" in recheck.reasons

    print("\n== 4. CLI check exit codes (1 seeded by design / 0 clean / 2 bad input) ==")
    seeded_code = cli_main(["check"])
    clean_code = cli_main(["check", "--clean"])
    bad_code = cli_main(["check", "--input", "/tmp/no-such-freshness-xyz.json"])
    print(f"   seeded={seeded_code} clean={clean_code} bad={bad_code}")
    assert (seeded_code, clean_code, bad_code) == (1, 0, 2)
    print("\nDemo OK: freshness + version gate, naive contrast, backfill invalidation verified.")

if __name__ == "__main__":
    main()
