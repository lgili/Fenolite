## Why

Milestone v0.4. This change is the part of c0120 (`agent-loop-scale`) that the maintainer split off on 2026-10-07 (decision 6 of that day: the DRC report limits become a change of their own and land early; the rest of c0120 is written later). It is c0120's Decision 11 with its measurements, and nothing else of c0120.

`fenolite check` gives a cut count as a complete one. Measured on 2026-10-05 with `kicad-cli` 10.0.6 and 9.0.9 on authored benches (design, Context):

- KiCad's DRC report stops at 499 entries of `clearance` and of `unconnected_items`, and at 199 entries of each of the eleven other types measured, per run and per type, on both majors.
- The report has no key that says a type was cut.
- On a generated 600-part board with 644 open connections, `check` reported `unconnected` 499 and 199 for two silkscreen types, and nothing said that the three counts were lower bounds.

On `origin/dev` at `9aba2dff` this is still so: `CLEARANCE_REPORT_LIMIT = 499` (`backends/kicad/canary.py:53`) serves only the canary's verdict `clearance-limit` (c0051), and `checks/drc.py` counts the report into `summary` and marks nothing. An agent that reads "499 unconnected" plans its routing against a wrong number; c0108 (open connections), c0119 (the yardstick's measures) and c0109 lean on the mark.

## What Changes

- **Protocol.** `backends.base` gains `DrcLimits(per_type, others)` and the optional protocol `LimitedOracle` (`report_limits()`), beside `Oracle`, which is unchanged.
- **KiCad.** `backends.kicad.drc.REPORT_LIMITS` holds the measured limits per major: 499 for `clearance` and `unconnected_items`, 199 for every other type. `KicadOracle` returns them, and `canary.CLEARANCE_REPORT_LIMIT` becomes that table's value.
- **Check.** The `drc.kicad` summary gains `limits`: one `{type, reported, limit}` per type whose count reached its limit, an empty list when every count is complete, `null` when the oracle states no limits. Each entry gives one `check.report-limit` warning. Status, evidence, canary verdict and exit code do not change.
- **Proof.** An authored bench of thirteen violation types at 700 copies, probed on 9.0.9 and 10.0.6 (`H-K-DRC-LIMITS`).

Size: 1.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `backend-protocol`: ADDED "DRC report limits of an oracle".
- `verification-loop`: ADDED "DRC report limits in check"; MODIFIED "Check output is deterministic".
- `kicad-oracle`: ADDED "DRC report limits are probed".

## Non-goals

- The count above a limit: c0108, whose `fenolite net` counts open connections from the copper; nowhere for the other types, because KiCad offers no second page of its report.
- A connectivity stage in `check`: nowhere, because it would give a second verdict beside KiCad's (design, Decision 5).
- Lifting the limit by running DRC again without the reported entries: nowhere, because it was not measured and costs one tool run per 199 entries.
- Limits of the ERC report and of the parity items of a DRC report: nowhere in this change, because no bench measured them; `limits` names violation types and unconnected items only.
- Staged plans, all-or-nothing writes, signals, progress and resumable routes: c0120.
- Anything for an Altium project: its checks are Fenolite's own and report every finding (design, Decision 6).

**Limits.** A type that no probe measured is taken to stop at 199, so a complete count of exactly 199 of such a type is marked "at least 199". 9.0.9 writes up to a few more than 499 `clearance` entries; any count from 499 on is marked.

## Evidence level required

- `H-K-DRC-LIMITS`: `KICAD-VERIFIED (9.0.x, 10.0.x)` before merge, by the authored bench; `REPORT_LIMITS` holds measured values only.
- The summary key, the issue and the protocol: mechanical, unit scenarios with a fake oracle.

## Impact

- New: `tests/kicad/check/_limitsbench.py`, `tests/kicad/check/test_drc_limits.py`, `tests/unit/checks/test_drc_stage_limits.py`, `tests/unit/backends/test_base_drc_limits.py`, `tests/unit/backends/kicad/test_oracle_limits.py`.
- Changed: `backends/base.py`, `backends/kicad/drc.py`, `oracle.py`, `canary.py`, `checks/drc.py`, `checks/codes.py`, `cli/data/explain.toml`, `tests/kicad/_probes.py`, the two probe files, docs.
- New names: hypothesis `H-K-DRC-LIMITS`; issue code `check.report-limit`; result key `summary.limits` of the stage `drc.kicad`; no CLI flag, no model field, no source id, no `FEN-` code.

## Prerequisites

- `0.3.0` is released from `dev`. Nothing else: c0051 (the canary and `H-K-DRC-LIMIT`), c0062 (the present text of "Check output is deterministic") and c0066 (`check --format concise`) are archived.
- No proposal of v0.4 must land first, and this one is meant to land in the first wave. Waiting for it: c0119 (reads the mark in its record), c0108 (names the mark where its count takes over), c0120 (no longer holds this part).
- c0096, c0097 and c0099: nothing here touches them. c0097 adds explanation lines to `copper.clearance` findings, another stage.
