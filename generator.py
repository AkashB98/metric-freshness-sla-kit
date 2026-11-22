"""Deterministic seeded scenarios: the four planted cases + controls.

Fixed clock: NOW is a constant of the fixture, never the wall clock.
All data is synthetic; the fictional source is a daily metrics load
for two metrics (daily_revenue, active_users).
"""
from __future__ import annotations
import hashlib, json
from models import MetricDef, Partition

NOW = "2026-01-15T12:00:00Z"
DEFAULT_SEED = 42

METRICS = {
    "daily_revenue": MetricDef("daily_revenue", 26.0, 1000, "v2", 0.95),
    "active_users": MetricDef("active_users", 26.0, 5000, "v2", 0.95),
}

def _hash(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]

def _part(metric, pid, load_ts, as_of, actual, expected, version, value):
    return Partition(metric, pid, load_ts, as_of, actual, expected, version,
                     value, _hash(metric, pid, actual, value, version))

def seeded_partitions():
    """The planted scenario set, in stable order."""
    return [
        # clean control: fresh, complete, current version -> SERVE
        _part("daily_revenue", "rev-2026-01-15", "2026-01-15T11:00:00Z",
              "2026-01-15T06:00:00Z", 1000, 1000, "v2", 125000.0),
        # clean control, second metric -> SERVE
        _part("active_users", "au-2026-01-15", "2026-01-15T11:30:00Z",
              "2026-01-15T08:00:00Z", 4980, 5000, "v2", 48210.0),
        # 1. LATE PARTITION: data-as-of 60h old vs 26h SLA -> REFUSE STALE
        _part("daily_revenue", "rev-2026-01-12", "2026-01-13T01:00:00Z",
              "2026-01-13T00:00:00Z", 1000, 1000, "v2", 118000.0),
        # 2. PARTIAL LOAD (key demo): load_ts fresh, data fresh, but
        #    120/1000 rows -> REFUSE INCOMPLETE; naive checker SERVEs.
        _part("daily_revenue", "rev-2026-01-15-partial", "2026-01-15T11:00:00Z",
              "2026-01-15T10:00:00Z", 120, 1000, "v2", 15100.0),
        # 4. STALE DEFINITION: fresh + complete, computed under v1
        #    after v2 certified -> REFUSE SUPERSEDED
        _part("daily_revenue", "rev-2026-01-15-v1", "2026-01-15T11:00:00Z",
              "2026-01-15T06:00:00Z", 1000, 1000, "v1", 124000.0),
    ]

def clean_partitions():
    """A scenario set with no planted defects - every case SERVEs."""
    return [p for p in seeded_partitions() if p.partition_id in
            ("rev-2026-01-15", "au-2026-01-15")]

def backfill_pair():
    """Case 3: an original partition and its backfill rewrite.

    Same partition_id, same timestamps, corrected value and row set -
    hence a different content hash. The rewrite lands AFTER the
    original answer was served and cached.
    """
    original = _part("daily_revenue", "rev-2026-01-14", "2026-01-14T11:00:00Z",
                     "2026-01-14T06:00:00Z", 1000, 1000, "v2", 119000.0)
    rewritten = _part("daily_revenue", "rev-2026-01-14", "2026-01-15T09:00:00Z",
                      "2026-01-14T06:00:00Z", 1000, 1000, "v2", 121500.0)
    return original, rewritten

CASE_LABELS = {
    "rev-2026-01-15": "clean_control",
    "au-2026-01-15": "clean_control",
    "rev-2026-01-12": "late_partition",
    "rev-2026-01-15-partial": "partial_load",
    "rev-2026-01-15-v1": "stale_definition",
    "rev-2026-01-14": "backfill_rewrite",
}

def partitions_to_json(parts):
    return json.dumps([p.to_dict() for p in parts], sort_keys=True)

def load_partitions(path):
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("expected a JSON array of partitions")
    return [Partition(**row) for row in raw]
