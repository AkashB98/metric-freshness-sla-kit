"""Golden evals for metric-freshness-sla-kit.

SYNTHETIC DATA ONLY. Deterministic: the report contains only names,
booleans and pinned values from the seeded fixtures - no timestamps
of the run, no temp paths - so eval_report.json is byte-identical
across runs. Per-case verdicts are reported individually; there is
no weighted score.

E1 determinism, E2 clean controls, E3 late partition, E4 partial load
(the headline, with the naive false-pass), E5 stale definition,
E6 backfill invalidation, E7 CLI exit codes, E8 boundary semantics,
E9 validation, E10 fixture parity.
"""
from __future__ import annotations
import hashlib, io, json, os, sys
from contextlib import redirect_stderr, redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cache import AnswerCache
from checker import check_partition, naive_timestamp_check
from cli import main as cli_main
from generator import METRICS, NOW, backfill_pair, load_partitions, partitions_to_json, seeded_partitions
from models import Partition
from report import build_report
from validation import validate_partitions

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = []

def check(name, passed, detail=""):
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return passed

def _cli(argv):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return cli_main(argv)

def by_id(pid): return next(p for p in seeded_partitions() if p.partition_id == pid)

def main():
    print("== golden evals: metric-freshness-sla-kit ==")
    rep = build_report()
    cases = {}
    for c in rep["cases"]: cases.setdefault(c["case"], []).append(c)

    md5 = hashlib.md5(partitions_to_json(seeded_partitions()).encode()).hexdigest()
    check("E1 generator determinism (seeded partitions md5 pinned)",
          partitions_to_json(seeded_partitions()) == partitions_to_json(seeded_partitions())
          and md5 == "cdd198003ddc08a90e330f08ea54b25a", f"md5={md5}")
    check("E2 clean controls SERVE (2/2, values carried)",
          len(cases["clean_control"]) == 2
          and all(c["decision"] == "SERVE" for c in cases["clean_control"])
          and rep["served"] == 2)
    late = by_id("rev-2026-01-12")
    v = check_partition(METRICS[late.metric], late, NOW)
    check("E3 late partition REFUSED stale (60h age vs 26h SLA)",
          v.decision == "REFUSE" and v.reasons == ["STALE"] and cases["late_partition"][0]["decision"] == "REFUSE")
    partial = by_id("rev-2026-01-15-partial")
    full = check_partition(METRICS[partial.metric], partial, NOW)
    naive = naive_timestamp_check(METRICS[partial.metric], partial, NOW)
    check("E4 partial load REFUSED incomplete (120/1000 rows)",
          full.decision == "REFUSE" and full.reasons == ["INCOMPLETE"])
    check("E5 naive timestamp-only checker FALSE-PASSES the partial load (headline)",
          naive.decision == "SERVE" and rep["naive_vs_full_on_partial_load"]["naive_false_pass"] is True,
          f"naive={naive.decision} full={full.decision}")
    v1 = by_id("rev-2026-01-15-v1")
    vv = check_partition(METRICS[v1.metric], v1, NOW)
    check("E6 stale definition REFUSED superseded (v1 after v2 certified, data fresh+complete)",
          vv.decision == "REFUSE" and vv.reasons == ["SUPERSEDED"])
    original, rewritten = backfill_pair()
    cache = AnswerCache()
    first = check_partition(METRICS["daily_revenue"], original, "2026-01-14T12:00:00Z")
    cache.store(original, first)
    before = cache.reservice_check(original)
    after = cache.reservice_check(rewritten)
    check("E7 backfill rewrite invalidates cached answer",
          first.decision == "SERVE" and before.decision == "SERVE"
          and after.decision == "REFUSE" and after.reasons == ["BACKFILL_INVALIDATED"]
          and rep["backfill_case"]["decision"] == "REFUSE")
    codes = (_cli(["check"]), _cli(["check", "--clean"]), _cli(["check", "--input", "/tmp/no-such-freshness-xyz.json"]))
    check("E8 CLI check exit codes 1 seeded-by-design / 0 clean / 2 bad input", codes == (1, 0, 2), f"codes={codes}")
    edge_ok = Partition("daily_revenue", "e1", "2026-01-15T11:00:00Z", "2026-01-14T10:00:00Z", 950, 1000, "v2", 1.0, "h")
    edge_bad = Partition("daily_revenue", "e2", "2026-01-15T11:00:00Z", "2026-01-15T06:00:00Z", 949, 1000, "v2", 1.0, "h")
    check("E9 boundary semantics (age == SLA serves; completeness == threshold serves, one row below refuses)",
          check_partition(METRICS["daily_revenue"], edge_ok, NOW).decision == "SERVE"
          and check_partition(METRICS["daily_revenue"], edge_bad, NOW).decision == "REFUSE")
    bad = Partition("daily_revenue", "b1", "not-a-time", "2026-01-15T06:00:00Z", True, 1000, "v2", 1.0, "h")
    check("E10 validation (seeded clean; bool-rows + bad timestamp flagged)",
          validate_partitions(seeded_partitions()) == [] and len(validate_partitions([bad])) >= 2)
    fixture = load_partitions(os.path.join(ROOT, "fixtures", "scenarios.json"))
    check("E11 fixture parity (fixtures/scenarios.json == seeded partitions)",
          partitions_to_json(fixture) == partitions_to_json(seeded_partitions()))
    check("E12 report shape (per-case verdicts, no weighted score)",
          rep["total_cases"] == 5 and rep["refused"] == 3 and "score" not in rep)

    passed = sum(1 for r in RESULTS if r["passed"]); total = len(RESULTS)
    doc = {"passed": passed, "total": total, "all_passed": passed == total, "evals": RESULTS}
    with open(os.path.join(HERE, "eval_report.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, sort_keys=True) + "\n")
    print(f"\n{passed}/{total} evals passed -> evals/eval_report.json")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
