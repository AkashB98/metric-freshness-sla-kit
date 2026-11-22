"""Report assembly: per-case verdicts, no weighted score."""
from __future__ import annotations
from cache import AnswerCache
from checker import check_partition, naive_timestamp_check
from generator import CASE_LABELS, METRICS, NOW, backfill_pair, seeded_partitions

def evaluate_partitions(parts, now=NOW, metrics=None):
    metrics = metrics or METRICS
    out = []
    for p in parts:
        m = metrics.get(p.metric)
        if m is None:
            out.append({"case": "unknown_metric", "partition_id": p.partition_id,
                        "metric": p.metric, "decision": "REFUSE",
                        "reasons": ["UNKNOWN_METRIC"], "detail": "no metric definition"})
            continue
        v = check_partition(m, p, now)
        out.append({"case": CASE_LABELS.get(p.partition_id, "ad_hoc"),
                    "partition_id": p.partition_id, "metric": p.metric,
                    "decision": v.decision, "reasons": v.reasons, "detail": v.detail})
    return out

def build_report(parts=None, now=NOW):
    parts = list(parts) if parts is not None else seeded_partitions()
    cases = evaluate_partitions(parts, now)
    # Backfill case is a two-step story, reported separately.
    original, rewritten = backfill_pair()
    cache = AnswerCache()
    m = METRICS[original.metric]
    first = check_partition(m, original, "2026-01-14T12:00:00Z")
    if first.decision == "SERVE":
        cache.store(original, first)
    recheck = cache.reservice_check(rewritten)
    backfill_case = {"case": "backfill_rewrite", "partition_id": rewritten.partition_id,
                     "metric": rewritten.metric, "decision": recheck.decision,
                     "reasons": recheck.reasons, "detail": recheck.detail,
                     "initial_decision": first.decision}
    # The headline contrast: naive timestamp-only vs full checker.
    partial = next(p for p in seeded_partitions()
                   if p.partition_id == "rev-2026-01-15-partial")
    naive = naive_timestamp_check(METRICS[partial.metric], partial, now)
    full = check_partition(METRICS[partial.metric], partial, now)
    served = sum(1 for c in cases if c["decision"] == "SERVE")
    return {"now": now, "cases": cases, "backfill_case": backfill_case,
            "served": served,
            "refused": len(cases) - served, "total_cases": len(cases),
            "naive_vs_full_on_partial_load": {
                "partition_id": partial.partition_id,
                "naive_decision": naive.decision, "full_decision": full.decision,
                "naive_false_pass": naive.decision == "SERVE" and full.decision == "REFUSE"}}
