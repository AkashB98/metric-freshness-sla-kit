# metric-freshness-sla-kit

**A metric-serving gate that refuses to answer when the data underneath is not trustworthy — on freshness and definition-version grounds only. Its headline proof: a load that finishes on time carrying 12% of its rows looks fresh to the timestamp check most pipelines run, and this gate refuses it.**

Every analytics team has served a confident number off a broken load. The load "ran" — the scheduler is green, the freshness timestamp is recent — but the partition holds a fraction of its rows, or the data is two days old, or the number was computed under last quarter's definition. This kit builds the thin layer that sits between a metric and its consumer and says *no*, with a machine-readable reason, in exactly those cases.

> **Synthetic data only.** Every partition is a fabricated record for two fictional metrics (`daily_revenue`, `active_users`). No real company, warehouse, or customer data is used anywhere in this project.

Stdlib-only Python — deliberately. A refusal gate is an audit artifact: anyone should be able to read every line of the checks, re-run it offline, and get byte-identical outputs. Zero network, zero API keys, zero external dependencies. All time comparisons use an **injected clock** (a fixed `now` supplied by the caller), never the wall clock, so tests and evals are hermetic.

## Scope — what this gate does and deliberately does not do

This gate refuses on **exactly three grounds**:

| Reason code | Ground |
|---|---|
| `STALE` | The partition's data-as-of timestamp is older than the metric's freshness SLA |
| `INCOMPLETE` | Actual rows fall below the metric's expected-completeness contract |
| `SUPERSEDED` | The partition was computed under a definition version that is no longer the certified one |

Plus one cache rule: `BACKFILL_INVALIDATED` — a cached answer whose partition was rewritten by a backfill must not be re-served.

It does **not** do provenance display (source tables, query text), and it does **not** refuse uncertified metrics or wrong-grain asks. That ground is already covered by the sibling project **[semantic-metrics-agent-kit](../semantic-metrics-agent-kit/)**, which carries definition/version/provenance on every answer and refuses uncertified, deprecated, superseded-version, and grain-mismatched requests. This kit is the complementary half: that one governs *what the number means*, this one governs *whether the data under it is fresh and complete enough to serve at all*.

## Quickstart

```bash
python3 demo.py                  # end-to-end demo; exits 0
python3 cli.py report            # per-case verdicts (JSON) on the seeded scenarios
python3 cli.py check; echo $?    # 1 on the seeded set BY DESIGN (planted refusals present)
python3 cli.py check --clean; echo $?   # 0 on the clean scenario set
python3 cli.py check --input partitions.json; echo $?  # 2 on bad input
python3 evals/run_evals.py       # golden evals -> evals/eval_report.json
python3 -m unittest discover -s tests
```

**Exit codes for `check`:** `0` = every case serves (clean set), `1` = at least one refusal (the seeded set exits 1 by design — it contains planted refusals), `2` = usage / IO / data-quality error. The backfill case is a two-step story (serve → rewrite → re-serve refused); it is printed by `check` and reported as its own `backfill_case` block, separate from the per-partition verdict counts.

## The seeded scenarios at a glance (fixed clock: `now = 2026-01-15T12:00:00Z`)

Each metric declares a freshness SLA (26 h), an expected row count per load (1,000 for `daily_revenue`, 5,000 for `active_users`), a completeness threshold (95% of expected rows), and a certified definition version (`v2`).

| Case | What is planted | Full checker | Naive timestamp-only checker |
|---|---|---|---|
| Clean control ×2 | Fresh (4–6 h), complete, definition v2 | ✅ **SERVE** | SERVE |
| **Late partition** | Data-as-of is 60 h old vs a 26 h SLA; rows complete | ❌ **REFUSE** `STALE` | REFUSE (load is old too) |
| **Partial load** *(the key demo)* | Load finished 1 h ago, data-as-of is fresh — but **120 of 1,000 rows** arrived | ❌ **REFUSE** `INCOMPLETE` | ⚠️ **SERVE — false pass** |
| **Stale definition** | Fresh and complete, but computed under definition **v1** after v2 was certified | ❌ **REFUSE** `SUPERSEDED` | SERVE (it never looks at versions) |
| **Backfill rewrite** | Answer served and cached; a backfill then rewrites the same partition (corrected value, new content hash) | ❌ Re-serving the cached value **REFUSED** `BACKFILL_INVALIDATED` | — (no cache concept) |

**The headline is the partial load.** The naive checker shipped in this repo's eval harness (`checker.naive_timestamp_check`) looks only at when the load finished — which is what most freshness monitoring actually does. On the partial-load partition it returns SERVE for a number computed from 12% of the expected data. The full checker refuses, because freshness has two halves — *when did it load* and *how much arrived* — and a timestamp only ever proves the first.

## How it works

**The contract, per metric.** A freshness SLA in hours, judged against the partition's **data-as-of** timestamp (the newest data inside the load), not the load timestamp — a load can finish recently while carrying old data, and the late-partition case is exactly that shape in reverse. An expected-completeness contract: `actual_rows / expected_rows` must meet the threshold (0.95). A certified definition version: any partition computed under another version is refused even when its data is fresh and complete, because a correct-looking number under a superseded definition is a wrong number with good posture.

**Partitions are simulated loads.** Each carries a load timestamp, a data-as-of timestamp, actual and expected row counts, the definition version used, the value it would serve, and a content hash fingerprinting its contents. The three timestamps/counts are deliberately independent fields — collapsing them is how the failure modes above become invisible.

**The cache and the backfill rule.** When an answer is served, the cache stores it with the partition's fingerprint (partition id + content hash + definition version). A backfill that rewrites history produces the same partition id with a different hash; the fingerprint mismatch makes re-serving the old value a refusal, not a silent stale answer. Recompute is the only way back to SERVE.

**Boundary semantics** (pinned by tests and evals): data age exactly equal to the SLA serves; completeness exactly at the threshold serves; one row below it refuses. Multiple defects accumulate — a partition that is stale, incomplete, and superseded reports all three reason codes.

## Architecture

| Module | Job |
|---|---|
| `models.py` | `MetricDef` (SLA, expected rows, completeness threshold, certified version), `Partition` (one simulated load), `Verdict`; ISO-8601 parsing |
| `checker.py` | The full gate (`check_partition`: STALE / INCOMPLETE / SUPERSEDED) and `naive_timestamp_check`, the load-timestamp-only checker the evals prove wrong |
| `cache.py` | `AnswerCache`: fingerprint-keyed served answers; backfill rewrite → `BACKFILL_INVALIDATED` on re-serve |
| `generator.py` | Deterministic seeded fixtures: the two metrics, the five seeded partitions, the clean subset, the backfill pair; fixed clock `NOW` |
| `report.py` | Report assembly: per-case verdicts (no weighted score), the separate `backfill_case` block, and the naive-vs-full contrast on the partial load |
| `validation.py` | Data-quality gate for partition records: required fields, the int/bool trap on row counts, timestamp parsing, duplicates — reports, never raises |
| `cli.py` | `report` / `check` (exit 0 clean / 1 refusals / 2 error) / `demo` |
| `demo.py` | End-to-end narrative with asserts: seeded verdicts, the naive false-pass, backfill invalidation, CLI exit codes 1/0/2 |
| `fixtures/` | `scenarios.json` — the seeded partitions as data, pinned equal to the generator by eval E11 |

## Evals

`python3 evals/run_evals.py` → **12/12 golden evals**, report committed at `evals/eval_report.json` (md5 `b7808036f7780d9ad07afd68fd2488c3`, byte-identical across 2 verified runs). Verdicts are reported per case; there is no weighted score.

- **E1** generator determinism — seeded partitions pinned by md5
- **E2** clean controls serve (2/2, values carried through)
- **E3** late partition refused `STALE` (60 h age vs 26 h SLA)
- **E4** partial load refused `INCOMPLETE` (120/1,000 rows)
- **E5** the headline: the naive timestamp-only checker **false-passes** the partial load (naive SERVE, full REFUSE)
- **E6** stale definition refused `SUPERSEDED` (v1 after v2 certified, data fresh and complete)
- **E7** backfill rewrite invalidates the cached answer (serve → rewrite → re-serve refused)
- **E8** CLI `check` exit codes: 1 seeded-by-design / 0 clean / 2 bad input
- **E9** boundary semantics (age == SLA serves; completeness == threshold serves, one row below refuses)
- **E10** validation (seeded set clean; bool row counts and bad timestamps flagged)
- **E11** fixture parity (`fixtures/scenarios.json` equals the generator output)
- **E12** report shape (5 seeded cases, 2 served / 3 refused, no `score` field anywhere)

Unit tests: `python3 -m unittest discover -s tests` → **31 hermetic tests**, including each planted case, the timestamp-only false-pass contrast, boundary conditions on both the SLA and the completeness threshold, multi-reason accumulation, the full backfill lifecycle (including that a REFUSE verdict cannot be cached), CLI exit codes, validation defects, determinism, and a no-network enforcement test (sockets stubbed).

## Development loop — what the checks actually caught

1. **The scope was cross-checked before a line was written, and it shrank.** The first sketch of this kit also displayed provenance and refused uncertified metrics — until the cross-check pointed out that the shipped semantic-metrics-agent-kit already owns exactly that ground. The build was narrowed to freshness + versioning only, and the boundary between the two kits is stated in this README rather than blurred.
2. **The backfill case broke the `check` contract on the first demo run.** The report originally appended the backfill refusal into the same verdict list as the per-partition cases — which meant the *clean* scenario set also exited 1, contradicting the documented exit codes. The fix is structural, not a special case: the backfill story is a two-step sequence (an answer must exist before it can be invalidated), so it is reported as its own block and never counted in the per-partition served/refused totals. Demo and evals now pin all three exit codes.
3. **The naive checker had to be honest to be damning.** An early draft of the partial-load fixture also made its data-as-of timestamp old, which let the naive checker refuse it for the wrong reason and proved nothing. The planted partition's load *and* data timestamps are both fresh — the only thing wrong with it is the row count — so the false pass isolates exactly the blind spot the kit exists to close.

## Scope and honest limits

- **Simulated loads, not a warehouse connector.** Partitions are records with the fields a real load would report; wiring this gate to a real orchestrator's metadata (Airflow, dbt artifacts, a warehouse `INFORMATION_SCHEMA`) is the natural next step and is named as such, not claimed here.
- **Row-count completeness is a proxy.** A load can hit its row count and still be wrong (duplicated rows, a shifted column). The contract here catches volume failures — the most common silent one — and the validation module catches a few structural defects; content-level checks belong to a data-quality suite upstream.
- **The cache is in-memory and single-process.** It demonstrates the invalidation rule; a production serving layer would persist fingerprints alongside cached answers in its store of choice.
- **Thresholds are per-metric constants.** Real SLAs and completeness thresholds vary by metric criticality and day-of-week seasonality; here they are explicit fields on the metric definition, visible rather than buried, which is the part worth keeping.

## Why this project — POC framing

This is a proof of concept for a pattern its author has needed in production analytics work: the moment a metric is served to a decision-maker, *someone* has to be able to say why the number is trustworthy — or refuse to show it. The refusal is the feature. A dashboard that goes blank with `INCOMPLETE: 120/1000 rows` is more useful than one that confidently renders a number built on 12% of the data, and a serving layer that invalidates its own cache when history is rewritten is the difference between a backfill being a fix and being a second, quieter incident. Built stdlib-only, with planted failures and a deliberately naive baseline checker, so every claim in this README is re-runnable in seconds.

## License

MIT — see LICENSE. Copyright (c) 2026 Akash Bhargava.
