## Context

**Scope.** Milestone v0.4. The complex-board review of 2026-10-05 asked for "report limits of KiCad's DRC marked per type". c0120 held it as its Decision 11; the maintainer split it off on 2026-10-07 so that it lands early, because c0108, c0116 and c0119 cite c0120 as a given while c0120 is large and unwritten. This change takes Decision 11, measurements 8 to 10 and the hypothesis `H-K-DRC-LIMITS` from c0120; c0120 keeps the rest and no longer names any of it.

**What exists** (`origin/dev` at `9aba2dff`, read on 2026-10-07):

- `backends/base.py` defines `Oracle` (`name`, `version()`, `drc(project) -> DrcOutcome`) and, beside it, the `@runtime_checkable` protocols of the ERC, netlist and round-trip oracles. `DrcReport` keeps the tool's own type strings.
- `KicadOracle.drc` runs a plain and a canary `pcb drc` on 9 and 10 (`CANARY_TWO_RUN`); the summary is counted on the plain run's report, from which every canary violation is removed.
- `CLEARANCE_REPORT_LIMIT = 499` (`backends/kicad/canary.py:53`, c0051) decides only the canary verdict `inconclusive` with reason `clearance-limit` (`H-K-DRC-LIMIT`, `KICAD-VERIFIED`).
- `checks/drc.py::_summary` (line 30) gives `violations`, `by_type`, `by_severity`, `unconnected` and the rest of "DRC stage and the rules canary"; nothing marks a count as cut.
- `tests/kicad/check/_limitbench.py` and `test_drc_limit.py` (c0051) are an authored bench of close track pairs for the `clearance` limit. c0120's design named a new file `_limitbench.py`; that name is taken, so this change's bench is `_limitsbench.py`.
- `check` of an Altium project runs `checks.documents.run_document_checks`, which has no `drc.kicad` stage and asks no tool for a report (c0088, open on `dev`, adds `copper.clearance` and `parity` to that pipeline as Fenolite's own checks).
- `fenolite.checks.codes.ISSUE_CODES` is a closed table: "a later change adds its codes to the table through its own ADDED requirement". `tests/unit/cli/test_explain_cmd.py` fails for a code without a table in `cli/data/explain.toml`.

**Measured on 2026-10-05** (from c0120's design, where they were measurements 8 to 10; `kicad-cli` 10.0.6 on macOS and 9.0.9 in the pinned image; taken on the review branch at `27ef3ad7` and not repeated on `dev`: they are facts of `kicad-cli`, and task 1.2 takes each again as a recorded probe before `REPORT_LIMITS` is written):

1. *Check at 600 parts.* `fenolite check` on a filled, generated 600-part board: 897 issues; the `drc.kicad` summary gives `unconnected` 499 and `by_type` `silk_over_copper` 199 and `silk_overlap` 199, canary `fired`, and nothing says a count was cut. The board holds 644 open connections by c0108's count. (The run took 30.3 s with six `kicad-cli` processes at `27ef3ad7`; `check` has since gained `erc.kicad` and `parity`, so the time is not quoted as a fact of `dev`.)
2. *Report limits on 10.0.6.* Authored benches: a 400 mm square board of format 20241229 with a `{}` project and a rules file, 700 copies of one violation per bench, run with `kicad-cli pcb drc --format json --severity-all`. `clearance` 499; `unconnected_items` 499; `track_dangling`, `via_dangling`, `copper_edge_clearance`, `track_width` (rule 0.2 mm on 0.1 mm tracks), `hole_to_hole` (rule 1 mm), `hole_clearance` (rule 1 mm), `annular_width` (rule 0.15 mm), `silk_overlap`, `courtyards_overlap`, `lib_footprint_issues` and `shorting_items` (two pads of two nets in one footprint) 199 each. With 150 copies, `track_dangling`, `silk_overlap` and `unconnected_items` give 150. `--all-track-errors` leaves `track_dangling` at 199. The line "Found N violations" counts the entries written. The report has no key that marks a type as cut: its keys are `$schema`, `coordinate_units`, `date`, `ignored_checks`, `included_severities`, `kicad_version`, `schematic_parity`, `source`, `unconnected_items` and `violations`.
3. *Report limits on 9.0.9.* One board holding nine benches of 700 copies, run in the pinned image and locally on 10.0.6: 9.0.9 gives `clearance` 500, `unconnected_items` 499 and 199 for each of `copper_edge_clearance`, `courtyards_overlap`, `hole_to_hole`, `lib_footprint_issues`, `silk_overlap`, `track_dangling`, `track_width` and `via_dangling`; 10.0.6 gives 499, 499 and 199. With c0051's record (9.0.9 reports 499 to 508 `clearance` violations), the limits are per type, independent of each other, and equal on both majors, except that 9.0.9 can pass 499 `clearance` by a few.

**Constraints.** Stdlib only. `checks` imports `core`, `model`, `geometry` and `backends.base` only. The bench is authored; no value comes from a board of any organisation: 700, 150 and 400 mm are round values chosen for the bench.

## Goals / Non-Goals

**Goals**
- An agent that reads `check` knows which counts KiCad cut, per type.
- The limit is one number per type and major, measured, in one table that the canary also reads.
- No verdict moves: the mark adds knowledge and changes no status, evidence or exit code.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **A protocol beside `Oracle`, not a field of it.** `DrcLimits(per_type, others)` and the `@runtime_checkable` protocol `LimitedOracle` (`report_limits() -> DrcLimits`) go into `backends/base.py`, as the netlist and round-trip oracles stand beside `Oracle`. "Oracle protocol" is not modified.
   - Why: every fake oracle of the test suite and any future oracle keeps working unchanged, and "this oracle states no limits" stays expressible.
   - Rejected: a `limits` field on `DrcOutcome`: it would modify "Oracle protocol" and every construction of the outcome, for a value that does not depend on the run.
   - Rejected: the table in `checks`: `checks` may not import a backend, and the numbers are KiCad's.

2. **One table, measured values only.** `backends/kicad/drc.py` holds `REPORT_LIMITS: Mapping[int, DrcLimits]` with `DrcLimits({"clearance": 499, "unconnected_items": 499}, others=199)` for 9 and for 10, each number pinned to a probe (Decision 7). `canary.CLEARANCE_REPORT_LIMIT` becomes `REPORT_LIMITS[10].limit("clearance")`, so the canary's reason `clearance-limit` and the mark cannot drift apart.
   - `others=199` is measured for eleven types and assumed for the rest. A type whose own probe later shows another limit gets its key in `per_type` with that probe.
   - Rejected: a table of thirteen explicit types and no default: a type outside it would never be marked, which is the defect this change repairs.

3. **`summary.limits` has three states.** `null`: no report, or the oracle is not a `LimitedOracle` (nothing is known). `[]`: every count is under its limit (every count is complete). A list of `{type, reported, limit}`, sorted by type: these counts are lower bounds. The counts are those the summary already gives (`by_type`, `unconnected`), after the canary's violations are removed and, on the two-run majors, from the plain run.
   - Why `null` and not an absent key: a reader of JSON can then tell "complete" from "unknown" without knowing which oracle ran.
   - Why "at least" for a count equal to its limit: 9.0.9 writes up to 508 `clearance` entries, and a type no probe measured is taken to stop at 199; a complete count of exactly its limit is then marked, which says "at least" and is still true.
   - Rejected: marking inside `by_type` (a string such as `"199+"`): every consumer that adds the counts would break.

4. **One warning per marked type, under a code of `check`.** `check.report-limit` (warning), `where` the issue code of the type (`kicad.drc.unconnected-items`), so a reader that groups issues by `where` finds the mark beside the findings it limits.
   - The code is `check.report-limit`, not `kicad.drc.report-limit`: a KiCad violation type maps to `kicad.drc.<type>` through `type_code`, so a tool type named `report_limit` would collide; and c0114 (v0.4) lets `kicad.drc.*` findings be waived and gives them severities, which a statement about the report must not be subject to.
   - Status, evidence, canary verdict and exit code do not change: a warning never makes a stage `errors` ("Check stages and statuses"), and a count under its limit is complete (measurement 2), so "no error" still means none.
   - The new code needs its row in `checks.codes.ISSUE_CODES` (added by this change's requirement, as "Check issue codes" asks) and its table in `cli/data/explain.toml` (task 2.2).

5. **No connectivity stage, and no second DRC run.** Above the limit of `unconnected_items`, the count of open connections is c0108's (`fenolite net`, from the copper); the documentation of `check.report-limit` names it once c0108 is on `dev`, and until then says only that the count is a lower bound.
   - Rejected: a connectivity stage in `check`: a second verdict beside KiCad's, held at c0108's parity with it.
   - Rejected: running DRC again with the reported entries excluded: not measured, and one more tool run per 199 entries.

6. **The second backend.** `dev` writes and checks Altium documents (c0084 to c0088). `check` of an Altium project runs the document pipeline, which has no `drc.kicad` stage; its `copper.clearance` and `parity` stages (c0088) are Fenolite's own code and report every finding they have. So no Altium module satisfies `LimitedOracle`, no document stage gains `limits`, and "Document check pipeline" is not modified. If an Altium tool is ever run as an oracle, it implements `report_limits()` with its own measured table, or implements nothing and gets `null`. No rule kind, selector or model field is added, so the Altium rule table (c0084) and the lowering are not concerned.

7. **The bench and the probes.** `tests/kicad/check/_limitsbench.py` writes, by code, a 400 mm × 400 mm board with a `{}` project and a rules file, holding N copies of one construct per type on a grid: thirteen types at 700 copies, three of them again at 150, `track_dangling` once more with `--all-track-errors`, and the report's top-level keys. Each count is a probe `drc-limit-*` recorded per version; the test compares the probes with `REPORT_LIMITS`.
   - c0051's `_limitbench.py` and `test_drc_limit.py` stay as they are: they prove the canary's verdict at the `clearance` limit over five runs, another claim.
   - A count that differs between two runs of one bench takes its type out of `per_type` and into the register row; the fallback `others` then applies, which marks from 199 on and stays true.
   - Rejected: reading the limits out of KiCad's source: the rule is facts from public sources with an oracle's proof, and a constant in a source file says nothing about the JSON report of a given version.

8. **Determinism.** "Check output is deterministic" is modified: on a board whose report the tool does not repeat, the entries of `summary.limits` and the `check.report-limit` warnings for `clearance`, `hole_clearance` and `unconnected_items` may differ with the counts they come from. For every other type, and on every board the tool repeats, they are equal between two runs.

9. **Other changes that hold the same requirements** (checked 2026-10-07 on `origin/dev` at `9aba2dff`, and against the review of the 26 proposals of v0.4).
   - "Check output is deterministic" (`verification-loop`): the living text is c0062's (archived). No open change on `dev` holds a delta of it (c0088, c0090 and c0126 hold other `verification-loop` deltas). c0120 named it too, for this very sentence; after the split c0120 does not modify it. The delta here is the living text of `9aba2dff` with one clause and one scenario added.
   - `backend-protocol`: six open changes on `dev` add to or modify the capability (c0088, c0090, c0092, c0126, c0128, c0130); none holds a requirement named "DRC report limits of an oracle", and none modifies "Oracle protocol" or "Neutral DRC report".
   - `kicad-oracle`: the names are free. "Check canary injection" (living) names `CLEARANCE_REPORT_LIMIT`; it is not modified, because the constant keeps its name and its value.
   - "DRC stage and the rules canary" lists what `summary` must hold and is not modified: the list is not closed, and the new key is stated by this change's own requirement, as "Check issue codes" asks for codes. c0114 (v0.4) modifies another requirement of the capability.
   - c0119 reads `summary.limits` in its record when the reply holds it. c0108 may name `check.report-limit` in its documentation. c0120 keeps no part of this change; its proposal says so.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/base.py` | `DrcLimits(per_type, others)` with `limit(type)`; `LimitedOracle` (`report_limits() -> DrcLimits`) |
| `src/fenolite/backends/kicad/drc.py` | `REPORT_LIMITS: Mapping[int, DrcLimits]` |
| `src/fenolite/backends/kicad/oracle.py`, `canary.py` | `KicadOracle.report_limits()`; `CLEARANCE_REPORT_LIMIT` from the table |
| `src/fenolite/checks/drc.py`, `checks/codes.py` | `summary.limits`; `check.report-limit` (warning) |
| `src/fenolite/cli/data/explain.toml` | the table of `check.report-limit` |
| `tests/unit/backends/test_base_drc_limits.py`, `tests/unit/backends/kicad/test_oracle_limits.py`, `tests/unit/checks/test_drc_stage_limits.py` (new); `tests/unit/checks/fakes.py` | hermetic: the types, the oracle's table, the stage with fake oracles with and without limits |
| `tests/kicad/check/_limitsbench.py`, `tests/kicad/check/test_drc_limits.py` (new); `tests/kicad/_probes.py`; `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | the bench, the `drc-limit-*` probes |
| `docs/cli-contract.md`, `docs/formats/kicad/drc.md`, `docs/evidence/kicad-check.md`, `docs/hypotheses.md`, `AGENTS.md` | the key, the code, the limits with their labels; one line in the CLI section of `AGENTS.md` that a marked count is a lower bound |

Public names: `fenolite.backends.base.DrcLimits`, `LimitedOracle`; the result key `summary.limits` of the stage `drc.kicad`; the issue code `check.report-limit`. No CLI flag, no model field, no schema of the model.

## Sources registered by this change

None. The facts rest on S-0020 and S-0029 (the two `kicad-cli` oracles); task 1.1 widens their "used for" cells.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-DRC-LIMITS | `kicad-cli pcb drc --format json --severity-all` writes at most 499 entries of `clearance` (9.0.9: 499 to 508) and of `unconnected_items`, and at most 199 entries of every other type, per run and per type, on 9.0.9 and 10.0.6; a type under its limit is written in full; `--all-track-errors` does not lift the limit of `track_dangling`; no key of the report says that a type was cut (S-0020, S-0029) | `tests/kicad/check/test_drc_limits.py` | probes `drc-limit-<type>` for the 13 types of measurement 2 at 700 copies, `drc-limit-below` at 150 copies, `drc-limit-all-track-errors` and `drc-limit-keys`, `equal` on both majors: each count equal to `REPORT_LIMITS[major]`, `clearance` on 9.0.9 at least 499 and below 700 |

It starts `INFERRED`, with measurements 2 and 3 as its first record. Ids used without changing their level: `H-K-DRC-LIMIT` (c0051; the singular id is the canary's claim about `clearance` alone and stays), `H-K-DRC-REPEAT`, `H-K-DRC-JSON`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| `REPORT_LIMITS` for 9 and 10 | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-DRC-LIMITS`, the `drc-limit-*` probes |
| `check` marks the bench | KICAD-VERIFIED (9.0.x, 10.0.x) | scenario "Check marks the bench" |
| `DrcLimits`, `LimitedOracle`, `summary.limits`, the warning, no verdict moved | mechanical | the unit tests of "Files and public API" |

## Risks / Trade-offs

- **A later KiCad changes a limit.** Each number is a probe pinned per version; the test fails before the table drifts, and a new major has no row until it is measured.
- **A count of exactly the limit is marked although it is complete.** The mark says "at least"; it is true, and the cost is one warning.
- **More warnings on large boards.** At most one per type; a reader that counts warnings sees up to a dozen more on a board at KiCad's limits, and none on a board below them.
- **Two bench files with near names.** `_limitbench.py` (c0051, clearance and the canary) and `_limitsbench.py` (this change, thirteen types). Each docstring names the other.

## Migration Plan

- Additive: one summary key, one issue code, two public names in `backends.base`. A `check` reply of a board under every limit gains `"limits": []` in the `drc.kicad` summary and nothing else; a caller that ignores unknown keys is unaffected.
- A `check` of a board at KiCad's limits gains warnings; its exit code and status stay.
- No model key is added, so model documents of every release are read and written as before.
- Rollback: remove the key, the code and the protocol; `CLEARANCE_REPORT_LIMIT` returns to its literal.

## Budget (1.25 days)

| part | days |
|---|---|
| entry check, register, the bench and its probes on both majors, the fact rows | 0.75 |
| protocol, table, `summary.limits`, the code, its explanation, the determinism text | 0.25 |
| documentation and closing | 0.25 |

Never cut: the probes on both majors; without them the table holds unmeasured numbers.

## Open Questions

- **Should a marked `unconnected_items` lower the stage's evidence?** Default: no; KiCad's verdict on the reported entries is unchanged, and the mark says what is missing.
- **Should `inspect` or `net` repeat the mark?** Default: no; c0108 decides what its count says beside it.
