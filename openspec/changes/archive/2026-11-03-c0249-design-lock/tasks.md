## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`design-dsl`, `cli-contract`, `layout-lens`), and record under this task, with the date and the base commit:
  - whether c0248 is archived. If it is, regenerate the MODIFIED block of "Design structure and names" from the living text, which then holds `device=`;
  - which open change holds a delta of "Design structure and names" or "Reproducible builds" (c0251 is likely to touch the first). If one was archived, regenerate the MODIFIED block from the living text;
  - that `FEN-7004` is still free in `src/fenolite/cli/errors.py` and in the open changes (c0216 `contract-v1` included);
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0249-design-lock --strict`; `make check-fast`.
  - 2026-10-29, base 3cabfe5a (`circuits-as-code`): c0248 is not archived nor merged in `circuits-as-code`, so `device=` and the device's `ref_prefix` are left to the merge with c0248 (this branch keeps `lib_id` required and takes the prefix from `prefix=` or the catalog symbol). c0251 holds a delta of "Design structure and names"; nothing touching it or "Reproducible builds" is archived. `FEN-7004` is free in `src/fenolite/cli/errors.py` and in the open changes (c0266 cites it as c0249's; c0216 does not use it). The maintainer's answers to the four open questions are pending; the recommended answers are implemented (lowest free number, explicit refs recorded, `<stem>.lock`, no `check --frozen`). `openspec` is not installed in this environment, so `openspec validate` was not run; `make check-fast` passes. Left open for the maintainer's answers.
  - 2026-11-01, closure base `7c2f1df2`: c0248 and c0251 are implemented and still open, so no archived delta needs regeneration; device-based prefixes and the complete lock-section order are present. `FEN-7004` is now c0249's implemented frozen-lock code, not an available new code. The user accepted all four recommended decisions (`design.md`). Fresh strict validation passes. Task 0.1 stays open because its exact Proof also requires root's serialized full gate; no unavailable maintainer answer is being inferred.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0248 and c0251 remain active, with device-based parts/prefixes and blocks implemented.
  No new archival requires regenerating this delta: c0249 and c0251 both hold "Design structure
  and names"; only c0249 holds "Reproducible builds". The living copies still precede those
  active changes. `FEN-7004` is c0249's implemented frozen-lock refusal, not a free code;
  c0216 does not claim it for another meaning. `dsl.lock.SECTIONS` now orders refs, picks,
  pins, blocks, library. The accepted four recommendations remain lowest-free allocation,
  explicit refs recorded, `<stem>.lock`, and frozen checking on build only.

  Available proof: `openspec validate c0249-design-lock --strict` passes without warnings
  (OpenSpec 1.16.0).
  The literal `make check-fast` is not run by this worker and has no applicable passing
  serialized receipt yet. Task 0.1 remains unchecked for that actual proof; independent
  CI, native/manual and release criteria are unchanged.

  Entry proof completed 2026-11-02 on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`: root
  ran the serialized `make check-fast` from 09:45:03 to 10:17:02 UTC, exit 0
  (19564 passed, 55 skipped; JUnit records zero failures/errors). Fresh OpenSpec
  1.16.0 strict validation of this change also passes without warnings. The
  `a85f7846` entry review was checked against this source: dependencies remain
  active, no new archival requires rebasing a delta, and the named APIs, accepted
  decisions and current dispatcher/record contracts still apply.
  This dated proof supersedes the earlier missing-fast-gate blocker only.
  Independent CI, native/manual, corpus, external-library and release criteria
  remain unchanged. The source-bound receipt, log and JUnit hashes are recorded
  in [the integration validation record](../c0319-integration-repairs/validation.md).

## 1. Part keys and prefixes

- [x] 1.1 Make `ref` optional on `Part`, `Design.part` and `Module.part`. Add `name=` and `prefix=`, the key rule, and the prefix sources (scenarios "Key from the prefix", "A second unnamed part", "Name and explicit ref", "Prefix from the catalog symbol", "No prefix known", "Path from a name"). Proof: `uv run pytest tests/unit/dsl/test_part_keys.py tests/unit/dsl/test_ids.py -q`.
  - 2026-10-29: done, proof passed (24 tests). `device=` waits for c0248: the scenarios with a device use `prefix=` or a catalog symbol, and `Design.part`/`Module.part` are a minimal `Container.part` taking the arguments of `Part` (c0248 widens it). The DSL now imports `fenolite.catalog` for the symbol prefix (allowed in `tests/unit/dsl/test_fields.py`).
  - 2026-10-29: merged with c0248 on `circuits-as-code`: `Container.part` (and `b.part` of c0251) takes
    `device=`, and the device's `ref_prefix` is the prefix of a part without a ref when `prefix=` is not
    given. Proof: `uv run pytest tests/unit/dsl/test_device_hooks.py tests/unit/dsl/test_part_keys.py -q`.

## 2. Assignment and the lock

- [x] 2.1 Add `dsl/lock.py`: `Lock`, `read_lock`, `lock_text`, `LockSection`, and the reserved `picks` and `pins` sections (scenarios "Canonical bytes", "Two paths with one ref", "Picks before c0254"). Proof: `uv run pytest tests/unit/dsl/test_lock.py -k "read or text or reserved" -q`.
  - 2026-10-29: done, proof passed.
- [x] 2.2 Add `assign_refs` with natural path order, lowest free numbers, explicit, taken, prefix-changed and released entries, and the aliases of `dsl.moves` (scenarios "First assignment", "Locked refs are kept", "Explicit ref takes a locked number", "Order independent of the script"). Register `H-G-LOCK-REFS` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/dsl/test_lock.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-29: done, proof passed; `H-G-LOCK-REFS` updated in place from its proposed row.
- [x] 2.3 Add `to_model(..., refs=)` and the default assignment against an empty lock (scenario "Ids do not follow refs"). Check that the blink's model is unchanged. Proof: `uv run pytest tests/unit/dsl/test_ids.py tests/unit/dsl/test_lock_model.py -q`.
  - 2026-10-29: done, proof passed with `tests/unit/lens/test_build_bytes_pinned.py` (the blink and the pinned designs are byte-identical).

## 3. Build

- [x] 3.1 Read and plan the lock in `cmd_build` (KiCad and Altium targets), with `--lock FILE`, `result.lock`, the lock codes in `BUILD_ISSUE_CODES` and `explain.toml`, and the amended script-folder rule (scenarios "First build writes the lock", "Rebuild leaves the lock alone", "Explicit refs get no lock", "A hand edit renumbers", "First build is quiet", "Changes listed", "Lock elsewhere"). Proof: `uv run pytest tests/unit/cli/test_build_lock.py tests/unit/lens/test_build_issues.py -q`.
  - 2026-10-29: done, proof passed (`src/fenolite/cli/_lock.py`; `--lock`, `result.lock`, lock codes in `BUILD_ISSUE_CODES` and `explain.toml`; the existing lock is a declared input of the plan).
- [x] 3.2 Carry lock entries by alias and release orphans (scenarios "Module renamed with moved()", "Renamed without moved()"). Proof: `uv run pytest tests/unit/cli/test_build_lock.py -k moved -q`.
  - 2026-10-29: done, proof passed.
- [x] 3.3 Add `--frozen` and `FEN-7004` with `lock.changed` (scenarios "Frozen build with a new part", "Frozen build unchanged", "Missing lock under --frozen", "Code explained"). Proof: `uv run pytest tests/unit/cli/test_build_frozen.py tests/unit/cli/test_explain_cmd.py -q`; `uv run pytest tests/consistency -q`.
  - 2026-10-29: done, proof passed (`tests/consistency` 571 passed).
- [x] 3.4 Determinism and layout: the lock is byte-identical across seeds and processes, and a renumbered part keeps its layout (scenarios "Lock reproducible", "Script folder unchanged", "Lock edit renumbers without moving"). Proof: `uv run pytest tests/unit/lens/test_build_determinism.py tests/unit/lens/test_build_lock_layout.py -q`.
  - 2026-10-29: done, proof passed.

## 4. Example and oracle

- [x] 4.1 Author `examples/lock/` (two modules with unnamed device parts, one named part, one explicit ref) and commit its `design.lock`. Add the KiCad ERC test, which must report no duplicate or unannotated reference. Proof: `uv run pytest tests/unit/test_examples.py -k lock -q`; `uv run pytest tests/kicad/build/test_lock_build.py -rA` (in CI).
  - 2026-10-29: done: `examples/lock/` with its committed `design.lock`; unit proof passed, and `tests/kicad/build/test_lock_build.py` passed locally on `docker:kicad/kicad:10.0.6` (ERC clean, no duplicate or unannotated reference); CI runs it too.

## 5. Closing

- [x] 5.1 Docs: a "Reference designators and the design lock" section of `docs/dsl.md` (keys, prefixes, assignment, natural order, hand edits, `moved()`), the lock in `docs/lens.md`, `--frozen`, `--lock` and `FEN-7004` in `docs/cli-contract.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page or contract_page" -q`.
  - 2026-10-29: done, proof passed (69 tests).
- [x] 5.2 Agent guide: add tested lines to `design-script.md` (a part without a ref, `name=`) and to `files.md` (the lock and `build --frozen`), and add `FEN-7004` to `recovery.md`. Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
  - 2026-10-29: done, proof passed; generated pages regenerated.
- [x] 5.3 Residue and evidence: the example is authored for Fenolite, the hypothesis is registered, and the evidence matrix is regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-29: done: `make residue` 0 hits, `gen_evidence_matrix.py --check` exit 0.
- [x] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
  - 2026-10-29: entry under `## [Unreleased]` › `### Added` on `circuits-as-code`, after `dev` (0.7.0.dev0) was merged into it.
  - 2026-10-29: open: `dev` is at the unpublished 0.6.0, whose guard needs `[Unreleased]` empty; waits for 0.7.0.dev0.
- [x] 5.5 Run `make check-fast`, publish the batch (with c0248) to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
  - 2026-10-29: open: `make check-fast` passes locally (15360 passed, 46 skipped). Under the maintainer's rule of 2026-10-29 the branch is not pushed; CI runs with the batch. c0248 is not in it yet.


## Scoped implementation closure — 2026-11-03

The maintainer clarified that problematic geometry was already outside this
closure CI batch before the run. Close only this specification’s implementation
on tested source 985f59a1d01a612b2eac0219243199896c24075a and reviewed
archival documentation. Run 41708879698 remains FAILURE: the27known c0332
geometry failures are DEFERRED_NOT_PASSED, not passed tests. KiCad9 and all
five unit jobs succeeded. The relevant KiCad10 module results are inferred
from complete unfiltered collection and the exhaustive -ra non-pass report;
no nominal PASSED line or green KiCad10 job is claimed.

`scoped-ci-985f59a1.json` binds the exact tests, explicit KiCad9 positive
lines, complete log hashes, reused fast proof and existing scoped records.
The isolated runtime/tests/tools/configuration remain byte-identical to985;
this does not validate later CAC runtime, close c0355 or replace subsequent
integration CI. Existing authored/native/default-map proofs and limitations
remain intact. No suite, native CAD test or CI rerun was started for archive.
