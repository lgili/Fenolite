## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs `verification-loop`, `enclosure-model` and `enclosure-fit` (c0307 and c0308 archived, or their folders); record under this task, with the date and base commit: the final names of the fit record's fields; the current `STAGE_ORDER` and `DOCUMENT_STAGES` (a stage added since 2026-10-30 moves the insertion point); that the `enclosure.*` codes of `design.md` collide with no code of `checks/codes.py` or an open change; that S-0959 and S-0960 are still this line's rows; the maintainer's answers to the open questions. Proof: `openspec validate c0309-enclosure-fit-check --strict --no-interactive`; `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.

## 1. Stage and codes

- [ ] 1.1 `checks/enclosure.py`: `EnclosureJudge`, `enclosure_stage`, skip reasons, `check.enclosure-unreadable`; the stage in `STAGE_ORDER` and `DOCUMENT_STAGES` (scenarios "No record", "A fake judge"). Proof: `uv run pytest tests/unit/checks/test_enclosure_stage.py -k "record or fake" -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 1.2 The sixteen codes in `checks/codes.py`, `explain.toml` and `docs/cli-contract.md` (scenario "Codes are keys and explained"). Proof: `uv run pytest tests/unit/checks -k codes -q`; `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 1.3 `cmd_check`: `--enclosure FILE`, the injected judge, `FEN-3009` for a broken named record. Proof: `uv run pytest tests/unit/cli/test_check_enclosure.py -q`.

## 2. The judge

- [ ] 2.1 Author `tests/data/enclosure/fit/`: one good board and one seeded bad board per rule, built from `examples/enclosure/fit_box.py` variants, authored for Fenolite. Proof: `uv run pytest tests/unit/enclosure/test_judge.py -k fixtures -q`.
- [ ] 2.2 2D rules: outline outside and inside with margins, holes on bosses and their size, envelopes, zones present, thickness (scenarios "Seeded fixtures" for these codes, "Smaller outline reported"). Proof: `uv run pytest tests/unit/enclosure/test_judge.py -k "outline or hole or envelope or zone or thickness" -q`.
- [ ] 2.3 Heights by source and the face, aperture and web rules (scenario "Three sources"; "Seeded fixtures" for the rest). Proof: `uv run pytest tests/unit/enclosure/test_judge.py -k "heights or face or aperture or web" -q`.
- [ ] 2.4 Evidence, summary and `enclosure.model-unverified`; the stage end to end (scenario "A bad fit fails"). Proof: `uv run pytest tests/unit/checks/test_enclosure_stage.py -q`.

## 3. Model tops

- [ ] 3.1 Record the STEP facts used (statement form, unit entity, the entity names of points, circles, spheres and tori, the control-point bounding box of a B-spline) in `docs/formats/step/entities.md` with S-0954, S-0959, S-0960 and their labels. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
- [ ] 3.2 `enclosure/bounds.py`: unit check, assembly refusal, the bound box, the model transform (scenario "Inch file refused", on models authored for Fenolite). Proof: `uv run pytest tests/unit/enclosure/test_bounds.py -q`.
- [ ] 3.3 Locate models in `cmd_check` and pass `bounds`; measure `H-K-ENCL-MODEL-TOP` (scenario "Never below KiCad's mesh"). Proof: `uv run pytest tests/kicad/enclosure/test_model_top.py -q` in the job `kicad-10`.

## 4. Build guard

- [ ] 4.1 The judge in the build's placement guard, warnings only, family `enclosure` (scenario "A too tall part warns"). Proof: `uv run pytest tests/unit/cli/test_build_fit.py -k guard -q`.

## 5. Docs and guide

- [ ] 5.1 `docs/enclosures.md` ("Fit check": the rules, the height sources, the first-board warning, the parameters) and `docs/cli-contract.md` (`check --enclosure`, the stage). Proof: `uv run pytest tests/unit/docs tests/consistency -q`.
- [ ] 5.2 Agent guide: a tested line on `checks.md` for the stage and for `check --enclosure`; regenerate. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 6. Closing

- [ ] 6.1 Residue and fast checks. Proof: `make residue`; `make check-fast`.
- [ ] 6.2 Evidence labels of `H-G-ENCL-FIT-CHECK` and `H-K-ENCL-MODEL-TOP`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 6.3 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 6.4 CI green on the exact commit (unit and KiCad jobs). Proof: the required jobs of `gh run list --branch <branch> --limit 1` succeed.
