"""Core data model: metric definitions, simulated partitions, verdicts.

SYNTHETIC DATA ONLY. All timestamps are ISO-8601 UTC strings; all
comparisons go through an injected clock value (``now``) supplied by
the caller - nothing in this package reads the wall clock.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

def parse_ts(s):
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass(frozen=True)
class MetricDef:
    name: str
    freshness_sla_hours: float
    expected_rows_per_load: int
    certified_version: str
    completeness_threshold: float = 0.95
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class Partition:
    """One simulated data load for a metric."""
    metric: str
    partition_id: str
    load_ts: str          # when the load finished
    data_as_of: str       # newest data timestamp inside the load
    actual_rows: int
    expected_rows: int
    definition_version: str
    value: float          # the metric value this partition would serve
    content_hash: str     # fingerprint of the partition contents
    def to_dict(self): return asdict(self)
    @property
    def completeness(self):
        if self.expected_rows <= 0: return 0.0
        return self.actual_rows / self.expected_rows

@dataclass
class Verdict:
    metric: str
    partition_id: str
    decision: str  # "SERVE" or "REFUSE"
    reasons: list = field(default_factory=list)  # machine codes
    detail: str = ""
    value: float | None = None  # set only on SERVE
    def to_dict(self): return asdict(self)
