## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs `cli-contract` and `manufacturing-exports`, and record under this task, with the date and base commit: whether c0307 to c0310 changed since 2026-10-30; whether `FEN-3009` and `FEN-3010` are still free on every branch; whether S-0950 to S-0958 are still this line's rows; the maintainer's answers to the open questions of `design.md`. Proof: `openspec validate c0306-enclosure-fit-step --strict --no-interactive`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

## 1. Footprint and command

- [ ] 1.1 Write the enclosure footprint generator (`cli/_enclosure_place.py`): library link, attributes, the model line with the Z offset, the `F.Fab` reference, the `.kicad_mod` and the `fp-lib-table` row (scenario "The written footprint", first part). Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py -k footprint -q`.
- [ ] 1.2 Add `fenolite enclosure place` to `cli/cmd_enclosure.py`: arguments, lengths with units, the pose in nm and µdeg, `result.place`, Altium refusal (scenarios "Altium input refused", "The reply of a plan"). Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py -k "reply or altium" -q`.
- [ ] 1.3 The STEP header sniff and `FEN-3010` in `cli/errors.py`, `explain.toml`, `docs/cli-contract.md`; record the header fact in `docs/formats/step/header.md` with S-0954 and its label (scenarios "Not a STEP file", "Error code registered"). Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py tests/unit/cli/test_explain_cmd.py -k "header or explain" -q`.
- [ ] 1.4 The copy into `enclosure/`, `--in-place`, `enclosure.step-local`, and no absolute path in any reply value (scenario "In place"). Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py -k "copy or in_place" -q`.
- [ ] 1.5 Replace and refuse by reference: `enclosure.replaced`, `enclosure.ref-taken` (scenario "Reference taken"). Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py -k ref -q`.
- [ ] 1.6 Rebuild keeps the footprint as board-only (scenario "The written footprint", rebuild part). Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py -k rebuild -q`.
- [ ] 1.7 `--drc` on copies before and after, with the two library types set aside. Proof: `uv run pytest tests/unit/cli/test_enclosure_place.py -k drc -q`.

## 2. KiCad probes

- [ ] 2.1 The fixture box: an authored board exported with `pcb export step --board-only` at test time; record the thickest board KiCad accepts if 30 mm is refused. Proof: `uv run pytest tests/kicad/enclosure/test_combined_step.py -k fixture -q` in the KiCad jobs.
- [ ] 2.2 Measure `H-K-ENCL-STEP` on 9.0.x and 10.0.x (scenario "The box reaches the STEP") and the `filter` value through `--component-filter`; write the result row. Proof: `uv run pytest tests/kicad/enclosure/test_combined_step.py -q` in CI jobs `kicad-9` and `kicad-10`.
- [ ] 2.3 Measure `H-K-ENCL-RENDER` (PNG with and without the footprint differ) and `H-K-ENCL-DRC` (no new violation type). Proof: `uv run pytest tests/kicad/enclosure/test_render_drc.py -q` in the KiCad jobs.

## 3. Docs, guide and Altium

- [ ] 3.1 Write `docs/enclosures.md` (stage 0: what the command does, the pose, the STEP's terms, the render from the bottom, the 9.0 note if measured) and the "Altium" checklist (scenario "Checklist present"). Proof: `uv run pytest tests/unit/docs/test_enclosures_doc.py -q`.
- [ ] 3.2 Add the section `enclosure` to `docs/cli-contract.md` with the three issue codes and their `explain.toml` tables. Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 3.3 Agent guide: one tested line for `enclosure place` on `fabrication.md`, a `recovery.md` row for `FEN-3010`; regenerate. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 3.4 Ask the maintainer for the Altium checklist report and record `H-A-ENCL-IMPORT`. Proof: the hypothesis row names the report; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 4. Closing

- [ ] 4.1 Residue scan and fast checks. Proof: `make residue`; `make check-fast`.
- [ ] 4.2 Update evidence labels in `docs/hypotheses.md` and `docs/formats/step/header.md`; append the c0306 use to S-0037's row. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.
- [ ] 4.3 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 4.4 CI green on the exact commit (unit and both KiCad jobs). Proof: `gh run list --branch <branch> --limit 1` shows success for the required jobs.
