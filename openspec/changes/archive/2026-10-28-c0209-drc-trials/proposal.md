## Why

Tasks 12.2 and 12.3 of c0175 (package 11, release checks). A writing command that lays copper trusts its
own checks; KiCad's DRC is the oracle, but nothing lets a caller try an edit against it and keep only what
it accepts. And a project the user does not build from a script has no way to accept a finding: `check`
reads the exclusions KiCad's DRC dialog stores, and Fenolite never wrote one, because the key needs a
marker position the report does not give.

## What Changes

- `fenolite check BOARD --exclude CODE:ITEM_A:ITEM_B --reason TEXT` stores one KiCad DRC exclusion in the
  board's `.kicad_pro` under the mutation protocol, in both item orders, with the reason as its comment.
  The marker position is found by probe keys on a copy, and a last `kicad-cli` run confirms the key before
  the write is planned. New codes `check.exclusion-unmatched`, `-ambiguous`, `-unlocated` (errors) and
  `-present` (info). `check` becomes a mutating command that plans no write without `--exclude`.
- The DRC stage judges two keys of one exclusion in both orders as one accepted exception and lists it in
  `summary.accepted` of `drc.kicad`; such an exclusion of a type KiCad does not repeat is live when applied.
- `fenolite.api.trial(board, edit, *, kicad_cli=None, refill=True, gate=False)` applies an edit to a copy,
  refills the zones on KiCad 10, runs DRC on the edited and the unedited copy, and maps each new finding to
  the edit's items; with `gate=True` it drops those items until no new finding names one. `KicadCli.drc`
  takes `refill_zones`.
- `docs/formats/kicad/drc.md` "Written exclusions" (facts measured on `kicad-cli` 10.0.7);
  `H-K-DRC-EXCLUSION` and `H-K-DRC-TRIAL`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `kicad-oracle`: ADDED "Trial edits judged by DRC", "Trial gate", "Trial refill and tool", "DRC exclusions
  written", "Exclusion lookup refusals", "Written exclusions judged" and "Written exclusion facts" (from
  c0175's "Trial edits gated by DRC" and "DRC exclusions written").

## Non-goals

- A `--gate drc` option of a writing command (`route`, `place`, `build`): it stays in c0175 as
  "DRC gate on writing commands" (task 12.2). The gate is delivered as the library call it would run.
- Removing an exclusion, or excluding by a waiver file: `design.waive()` stays the way for a built project.
- Exclusions of ERC findings.
- Locating a marker that sits at no anchor of its items (the finding is refused with
  `check.exclusion-unlocated`, and KiCad's dialog remains the way).

## Evidence level required

`KICAD-VERIFIED` on 10.0.x with the local `kicad-cli` 10.0.7; the `kicad-9` job settles 9.0.x for the
exclusion facts and three of the four trial tests (the refill test is 10 only).

## Impact

- New: `src/fenolite/backends/kicad/exclusions.py`, `src/fenolite/cli/_exclude.py`,
  `src/fenolite/api/trials.py`.
- Changed: `src/fenolite/cli/cmd_check.py` (mutating, `--exclude`, `--reason`), `src/fenolite/checks/drc.py`,
  `src/fenolite/checks/codes.py`, `src/fenolite/backends/kicad/cli.py` (`refill_zones`),
  `src/fenolite/api/__init__.py` (one import), `src/fenolite/cli/explain.py`, `explain.toml`.
- Tests: `tests/kicad/check/test_exclusions_write.py`, `tests/kicad/check/test_trial.py`,
  `tests/unit/backends/kicad/test_exclusions_write.py`, `tests/unit/checks/test_drc_accepted.py`,
  `tests/unit/cli/test_check_exclude.py`, `tests/unit/api/test_trial_api.py`; `tests/_cliexamples.py`
  (`check` plans nothing in its example), `tests/unit/checks/test_drc_stage.py` and
  `tests/unit/agent/test_pages.py` (`check` is no longer a read-only row).
- Docs: `docs/cli-contract.md` ("Writing a DRC exclusion", "Trial edits"), `docs/formats/kicad/drc.md`,
  `project.md`, `docs/hypotheses.md`, the guide's `checks` page, `LEGAL-ANNEX.md`, `CHANGELOG.md`.
