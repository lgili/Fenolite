## Context

- `fenolite.backends.matrix.rows()` collects one `MatrixRow` per backend and kind from each package's
  `claims` module; `tools/gen_evidence_matrix.py` writes `docs/evidence/matrix.md`; `capabilities` returns
  `result.matrix` (`cli-contract`, "Evidence matrix in capabilities"), which already requires an
  `UNVERIFIED` operation to be listed in the row's `experimental`.
- KiCad format versions per major: `docs/formats/kicad/versions.md`, "Constants". The oracle runs pin
  `kicad-cli` 9.0.9 and 10.0.6 (CI jobs `kicad-9`, `kicad-10`).
- Altium: kit run records under `docs/evidence/altium-kit/` name the Altium Designer version; register rows
  labelled `ALTIUM-VERIFIED(kit; …)` name the run (`verify.kit.record`).
- c0200 (`inferred-hypotheses`, archived on 2026-10-27) refuses, by a source test, an
  `Evidence(Level.INFERRED)` without hypotheses in the package, and registered `H-G-CATALOG`,
  `H-G-VIEW-SCENE` and others; a reply's evidence is combined at run time and is not checked.
- Measured on 2026-10-28, the example of each visible command (`evidence.level`, number of hypotheses):
  `view` `INFERRED` 0, `analyze` `UNVERIFIED` 6, `route` `UNVERIFIED` 0; `capabilities`, `doctor`, `edit`,
  `explain`, `fetch`, `guide`, `init`, `manifest`, `mcp`, `publish`, `restore` and `skill` `UNVERIFIED` 0;
  `catalog` and `kit` `INFERRED` with one hypothesis since c0200; every other command `INFERRED` or above
  with at least one hypothesis.

## Goals / Non-Goals

**Goals:** the version axis; a published matrix; the two rules on every reply; the five gaps closed.

**Non-Goals:** new tests of formats; raised levels.

## Decisions

1. **A cell holds versions.** `MatrixRow` operations stay labels; a new field `versions:
   Mapping[str, tuple[VersionEvidence, ...]]` keyed by operation, each `VersionEvidence(version, tool,
   level, source)` with `source` a test path or a kit run id. The `claims` modules declare them; KiCad's
   come from the pinned oracle jobs, Altium's from the register rows with a kit label. The matrix label of
   an operation stays the lowest of its versions (lowest wins).
2. **The generator checks sources.** A version whose `source` names no existing test file or recorded kit
   run fails `tools/gen_evidence_matrix.py --check`.
3. **Published form.** `docs/evidence/conformance.json` (`fenolite.conformance.v1`: rows with backend, kind,
   operation, version, tool, level, source) and `docs/evidence/conformance.md` (one table per backend);
   `release.yml` attaches the JSON to the release and a test reads the workflow textually, as
   `tests/unit/test_ci_workflow.py` does.
4. **No-claim commands.** `fenolite.cli.api.NO_CLAIM` lists the commands whose replies state nothing about a
   design or a file (decided on 2026-10-27): `capabilities`, `catalog`, `doctor`, `explain`, `guide`, `skill`, `init`,
   `fetch`, `manifest` and `restore` (it restores Fenolite's own `.bak` copies). A no-claim command answers `UNVERIFIED` with no
   hypothesis; its `capabilities` entry says `claims: false`.
5. **The rules.** In `cli.output`, before an envelope is written: `INFERRED` (or any level but `UNVERIFIED`
   and `UNKNOWN`) with no hypothesis, or `UNVERIFIED` from a command outside `NO_CLAIM` whose reply names no
   experimental feature, is a contract fault. With `FENOLITE_CONTRACT_CHECK=1` (set by the test suites) it
   raises `FEN-1001`; otherwise the reply is written as it is and one `cli.evidence-unsound` (warning) joins
   its issues, so a user never loses a reply to the check. `UNKNOWN` is allowed only in the reply of a
   backend's detection of a file that no backend knows (open question 3, decided).
6. **The gaps.** `catalog` and `kit` name a hypothesis since c0200 (`H-G-CATALOG`, `H-A-KIT-STABLE`);
   `catalog` stays in `NO_CLAIM` as decided, which only allows it `UNVERIFIED`. `view` still answers
   `INFERRED` with none: it draws a reading and takes the evidence of the reading it draws (the backend's
   read label) with `H-G-VIEW-SCENE`, which c0200 registered; `analyze`
   takes `INFERRED` with the hypotheses it already lists; `route` plans copper that `check` judges later:
   it answers `INFERRED` with the Specctra rows it relies on (`H-G-DSN-*`; open question 2, decided). `manifest` lists files with digests and claims nothing of a design: no-claim.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/matrix.py`, `backends/*/claims.py` | `VersionEvidence`, `MatrixRow.versions` |
| `tools/gen_evidence_matrix.py` | `conformance.md`, `conformance.json`, the source check |
| `src/fenolite/cli/api.py` | `NO_CLAIM` |
| `src/fenolite/cli/output.py` | the two rules, `cli.evidence-unsound` |
| `.github/workflows/release.yml` | attach `conformance.json` |

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| a listed version has a source | mechanical (generator check) |
| every example reply follows the rules | mechanical (consistency suite with `FENOLITE_CONTRACT_CHECK=1`) |
| the release attaches the matrix | mechanical (workflow test); the first release shows it |

## Risks / Trade-offs

- A reply's level depends on its inputs (an Altium board gives a lower level than a KiCad one); the
  examples cover one input each, so the unit tests of each command's evidence stay the finer check.

## Open questions

The maintainer accepted every recommended answer below on 2026-10-27 (roadmap, "Open decisions", row 49).

1. The list of no-claim commands. Recommended: as Decision 4. Decided by the maintainer on 2026-10-27: as recommended.
2. `route`: no-claim, experimental, or `INFERRED`? Recommended: `INFERRED` with the Specctra rows it relies
   on (`H-G-DSN-*`), since a route plans copper and `check` judges it. Decided by the maintainer on 2026-10-27: as recommended.
3. Is `UNKNOWN` allowed in a reply at 1.0? Recommended: only for a backend's `detect` of an unknown file. Decided by the maintainer on 2026-10-27: as recommended.
4. The commands added after these answers (`edit` and `mcp` of c0195 and c0196, `publish`, `refs` and
   `snapshot` of c0201): which are no-claim? Recommended: `edit` (it writes a text verbatim; the build that
   reads it claims), `mcp` (it serves the other commands, whose replies carry their own evidence) and
   `publish` (it copies files guarded by receipts); `refs` and `snapshot` already name a hypothesis. Open:
   raised on 2026-10-28, when the five changes were rebased on the work of c0195 to c0203.

## Current-source selective iteration A (review approved)

Port only typed version scopes, current backend claims, source validation, generated conformance
artifacts and release attachment first. Existing labels/hypotheses/experimental declarations stay
unchanged. KiCad pins come from current CI (9.0.9 and 10.0.6); Altium references must match validated
non-synthetic published kit records and supporting current register rows. Test source existence is
traceability, not execution proof. Specctra has no recorded version-specific native oracle and retains
empty scopes. No inferred tool versions or evidence upgrades.

Negative controls cover missing tests, missing/synthetic/mismatched kit records, unsupported
operations and scopes above their existing cell/register. Existing source guards remain in force.
Iteration B (reply checks and evidence tails) is separate: actual output census first; edit/mcp/publish
remain the explicit open question and are not silently added to NO_CLAIM. Model writer activation is
not part of this change; CLI remains v0.

## Current-source underlying evidence iteration C (review approved)

Keep view's H-G-VIEW-SCENE when combining the actual displayed scene level, using lowest-wins;
never replace UNKNOWN/UNVERIFIED with INFERRED. Native kit verification/recording derives its
hypothesis IDs solely from actually passing verdict entries; failed/synthetic verdicts keep their
existing inferred kit-stability label and cannot gain a native label. Analysis already lowers
incomplete/unsupported reports and that lowering remains intact.

Route refinement approved separately: do not attach DSN hypotheses to DirectRouter, which creates
tracks without DSN. A narrowly authored H-G-ROUTE-PLAN may describe only deterministic same-input
plan materialization/provenance, backed by stale-input/fault/unsupported controls, with no electrical
or DRC claim. Actual external DSN evidence applies only to the external DSN path. Historical blanket
outcome promotion is not a current authority. The route part follows focused view/kit proof.

### Route materialization boundary

The new H-G-ROUTE-PLAN records only the deterministic guarded plan/replay mechanism; supported
same-input copper bytes are materialized as reviewed and stale inputs/targets refuse. A complete,
error-free route can expose that INFERRED mechanical scope, carrying only hypotheses actually supplied
by its router plus the plan hypothesis. UNKNOWN remains UNKNOWN. Incomplete/unattempted/open/error
outcomes retain their existing lower evidence, and a DRC gate keeps its independently measured
verdict. No DSN constants are imported into cmd_route. Default DirectRouter evidence has no native
hypotheses, so its successful reply names the plan hypothesis only. Actual external DSN hypotheses
are retained only from the external outcome, never assigned to an unrelated algorithm. This is not
a connectivity/clearance assertion and the guide continues to require check after routing.
