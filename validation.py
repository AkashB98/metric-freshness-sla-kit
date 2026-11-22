"""Data-quality gate for partition records. Reports, never raises."""
from __future__ import annotations
from models import parse_ts

REQUIRED = ("metric", "partition_id", "load_ts", "data_as_of",
            "actual_rows", "expected_rows", "definition_version",
            "value", "content_hash")

def validate_partitions(parts):
    issues = []
    seen = set()
    for i, p in enumerate(parts):
        d = p.to_dict() if hasattr(p, "to_dict") else dict(p)
        for f in REQUIRED:
            if f not in d or d[f] is None or d[f] == "":
                issues.append(f"row {i}: missing field {f}")
        for f in ("actual_rows", "expected_rows"):
            v = d.get(f)
            if isinstance(v, bool) or not isinstance(v, int):
                issues.append(f"row {i}: {f} must be int, got {type(v).__name__}")
            elif v < 0:
                issues.append(f"row {i}: {f} must be >= 0")
        if isinstance(d.get("actual_rows"), int) and isinstance(d.get("expected_rows"), int) \
                and d.get("expected_rows", 1) > 0 and d["actual_rows"] > d["expected_rows"] * 2:
            issues.append(f"row {i}: actual_rows implausibly exceeds expected_rows")
        for f in ("load_ts", "data_as_of"):
            try: parse_ts(str(d.get(f, "")))
            except (ValueError, TypeError): issues.append(f"row {i}: bad timestamp {f}")
        key = (d.get("metric"), d.get("partition_id"), d.get("content_hash"))
        if key in seen: issues.append(f"row {i}: duplicate partition record {key}")
        seen.add(key)
    return issues
