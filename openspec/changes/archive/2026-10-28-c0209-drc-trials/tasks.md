## 1. DRC exclusions written

- [x] 1.1 Measure where KiCad keys an exclusion that the report does not locate, and pin it (requirement "Written exclusion facts"). Proof: `uv run pytest tests/kicad/check/test_exclusions_write.py -k order -rA` on `kicad-cli`.
  - 2026-10-28: proof passed on local `kicad-cli` 10.0.7 (2 tests): the missing connection between two tracks is keyed at the end of the first track, in either uuid order; a clearance only in the report's order at the first item's position, also with the uuid order flipped.
- [x] 1.2 Add `backends/kicad/exclusions.py` (keys, anchors, probe run, project text) and `check --exclude CODE:ITEM_A[:ITEM_B] --reason TEXT` with the four `check.exclusion-*` codes (requirements "DRC exclusions written" and "Exclusion lookup refusals"). Proof: `uv run pytest tests/kicad/check/test_exclusions_write.py -rA` on `kicad-cli` and `uv run pytest tests/unit/backends/kicad/test_exclusions_write.py tests/unit/cli/test_check_exclude.py -q`.
  - 2026-10-28: proofs passed: 6 tests on local `kicad-cli` 10.0.7 (unconnected track pair by uuid, unconnected pad pair by `R1-1:R2-1`, clearance pair, one-item `via_dangling`, `present` on a second run, `unmatched` exit 5, dry run writes nothing); 12 unit tests.
- [x] 1.3 Judge mirrored keys as one exception and list them in `summary.accepted` (requirement "Written exclusions judged"). Proof: `uv run pytest tests/unit/checks/test_drc_accepted.py tests/unit/checks/test_drc_stage.py -q`.
  - 2026-10-28: proof passed (4 and 22 tests); `SUMMARY_KEYS` of `test_drc_stage.py` gains `accepted`.

## 2. Trial edits

- [x] 2.1 Add `fenolite.api.trial` in `api/trials.py`, `refill_zones` of `KicadCli.drc`, and the gate (requirements "Trial edits judged by DRC", "Trial gate" and "Trial refill and tool"). Proof: `uv run pytest tests/kicad/check/test_trial.py -rA` on `kicad-cli` and `uv run pytest tests/unit/api/test_trial_api.py -q`.
  - 2026-10-28: proofs passed: 4 tests on local `kicad-cli` 10.0.7 (new `clearance` names only the offending track; the gate drops it in one round and the board keeps the first track; a clean edit; refill removes the touching finding a stored fill gives); 3 unit tests.

## 3. Documents and teaching

- [x] 3.1 Record "Written exclusions" in `docs/formats/kicad/drc.md` and the writer in `project.md`, register `H-K-DRC-EXCLUSION` and `H-K-DRC-TRIAL`, add the five codes to `explain.toml`, document `check --exclude` and `fenolite.api.trial` in `docs/cli-contract.md`, teach `--exclude` on the guide's `checks` page and regenerate the guide, add the `LEGAL-ANNEX.md` row and the CHANGELOG entry. Proof: `uv run pytest tests/unit/agent tests/unit/cli/test_explain_cmd.py tests/unit/test_inferred_hypotheses.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_format_facts.py tests/unit/test_import_graph.py tests/consistency -q`.
  - 2026-10-28: proof passed (641 passed, 28 skipped). `check` is now mutating, so `test_pages.py`, `test_describe.py` and `test_capabilities_brief.py` take `inspect` as their read-only command, `tests/_cliexamples.py` lists `check` among the commands whose example plans nothing, `tests/unit/checks/test_codes.py` learns the four codes, and `docs/evidence/matrix.md` is regenerated for the new module (`tools/gen_evidence_matrix.py`); `tests/unit/cli tests/unit/checks tests/unit/api` and `tests/unit/test_*.py` pass.

## 4. Validation

- [x] 4.1 `make check-fast` on the integrated head, and the required CI jobs green on it (the `kicad-9` job runs `tests/kicad/check/test_exclusions_write.py` and `test_trial.py` on 9.0.x; on success the 9.0.x half of `H-K-DRC-EXCLUSION` and `H-K-DRC-TRIAL` and of the "Written exclusions" rows is recorded). Proof: `make check-fast` and the required jobs green on the head that holds this change. Done 2026-10-28: `make check-fast` passed on the integrated head (14366 passed, 41 skipped), and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, viewer, wheel, dco) passed on `dev-c0204-c0209` at 01068dd (run 40703612332).
