"""CLI: demo | report | check.

SYNTHETIC DATA ONLY. Exit codes for check:
  0 = every case SERVEs (clean scenario set)
  1 = at least one REFUSE (the seeded set exits 1 BY DESIGN - it
      contains planted refusals)
  2 = usage / IO / data-quality error
Other commands: 0 = success, 2 = error.
"""
from __future__ import annotations
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generator import clean_partitions, load_partitions, seeded_partitions  # noqa: E402
from report import build_report  # noqa: E402
from validation import validate_partitions  # noqa: E402
EXIT_OK, EXIT_FAIL, EXIT_ERROR = 0, 1, 2

def canonical(x): return json.dumps(x, sort_keys=True)

def _parts_or_error(args):
    if getattr(args, "clean", False):
        return clean_partitions(), EXIT_OK
    if not getattr(args, "input", None):
        return seeded_partitions(), EXIT_OK
    try:
        parts = load_partitions(args.input)
    except FileNotFoundError:
        print(f"error: file not found: {args.input}", file=sys.stderr); return None, EXIT_ERROR
    except (ValueError, OSError, TypeError) as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr); return None, EXIT_ERROR
    issues = validate_partitions(parts)
    if issues:
        for i in issues[:20]: print(f"data-quality: {i}", file=sys.stderr)
        return None, EXIT_ERROR
    return parts, EXIT_OK

def cmd_report(args):
    parts, code = _parts_or_error(args)
    if parts is None: return code
    print(canonical(build_report(parts))); return EXIT_OK

def cmd_check(args):
    parts, code = _parts_or_error(args)
    if parts is None: return code
    rep = build_report(parts)
    for c in rep["cases"]:
        print(f"{c['case']}: {c['partition_id']} -> {c['decision']} {c['reasons']}")
    bc = rep["backfill_case"]
    print(f"{bc['case']}: {bc['partition_id']} -> {bc['decision']} {bc['reasons']} (two-step story, reported separately)")
    print(f"served={rep['served']} refused={rep['refused']} total={rep['total_cases']}")
    if rep["refused"]:
        print("check FAIL: refusals present (by design on the seeded set)")
        return EXIT_FAIL
    print("check PASS"); return EXIT_OK

def cmd_demo(args):
    import demo as demo_mod
    try: demo_mod.main()
    except AssertionError as exc:
        print(f"demo FAILED: {exc}", file=sys.stderr); return EXIT_FAIL
    return EXIT_OK

def build_parser():
    p = argparse.ArgumentParser(prog="metric-freshness-sla-kit",
        description="Metric-serving gate: refuse on freshness + definition version only.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, helptext in (("report", cmd_report, "per-case verdict report (JSON)"),
                               ("check", cmd_check, "gate: exit 0 clean / 1 refusals / 2 error")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("--input", default=None, help="partitions JSON file; default: seeded set")
        s.add_argument("--clean", action="store_true", help="use the clean scenario set")
        s.set_defaults(func=fn)
    sub.add_parser("demo", help="run the end-to-end demo").set_defaults(func=cmd_demo)
    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
