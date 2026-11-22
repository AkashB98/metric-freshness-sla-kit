"""The freshness + version gate, plus the naive checker it beats.

The full checker refuses on exactly three grounds - and only these:
  STALE        data-as-of is older than the metric freshness SLA
  INCOMPLETE   actual rows fall below the completeness contract
  SUPERSEDED   partition was computed under a non-certified definition

It deliberately does NOT check provenance, source tables, query text,
or certification status of the metric itself - that ground belongs to
the sibling semantic-metrics-agent-kit.
"""
from __future__ import annotations
from datetime import timedelta
from models import MetricDef, Partition, Verdict, parse_ts

def check_partition(metric: MetricDef, part: Partition, now) -> Verdict:
    now_dt = parse_ts(now)
    reasons, details = [], []
    age_h = (now_dt - parse_ts(part.data_as_of)).total_seconds() / 3600.0
    if age_h > metric.freshness_sla_hours:
        reasons.append("STALE")
        details.append(f"data age {age_h:.1f}h exceeds SLA {metric.freshness_sla_hours}h")
    if part.completeness < metric.completeness_threshold:
        reasons.append("INCOMPLETE")
        details.append(f"completeness {part.completeness:.3f} below threshold {metric.completeness_threshold} ({part.actual_rows}/{part.expected_rows} rows)")
    if part.definition_version != metric.certified_version:
        reasons.append("SUPERSEDED")
        details.append(f"definition {part.definition_version} superseded by certified {metric.certified_version}")
    if reasons:
        return Verdict(metric.name, part.partition_id, "REFUSE", reasons, "; ".join(details), None)
    return Verdict(metric.name, part.partition_id, "SERVE", [], f"fresh ({age_h:.1f}h), complete ({part.actual_rows}/{part.expected_rows}), definition {part.definition_version}", part.value)

def naive_timestamp_check(metric: MetricDef, part: Partition, now) -> Verdict:
    """Timestamp-only checker: looks ONLY at load_ts freshness.

    This is the checker most pipelines actually run - and the eval
    harness proves it false-passes a partial load, because a load can
    finish on time while carrying a fraction of its rows.
    """
    now_dt = parse_ts(now)
    load_age_h = (now_dt - parse_ts(part.load_ts)).total_seconds() / 3600.0
    if load_age_h > metric.freshness_sla_hours:
        return Verdict(metric.name, part.partition_id, "REFUSE", ["STALE_LOAD"], f"load age {load_age_h:.1f}h exceeds SLA {metric.freshness_sla_hours}h", None)
    return Verdict(metric.name, part.partition_id, "SERVE", [], f"load looks fresh ({load_age_h:.1f}h)", part.value)
