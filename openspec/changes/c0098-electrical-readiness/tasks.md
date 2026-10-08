## 0. Entry

- [x] 0.1 Record the maintainer's decision of 2026-10-08 in `docs/roadmap.md` (row 35 of "Open decisions": "decided by the maintainer on 2026-10-08: in v0.4"; the section of v0.4 no longer says that c0098 is on hold), add the row c0098 to the table of `openspec/README.md`, and register `H-G-READY-RULES` (`INFERRED`, result `pending`) in `docs/hypotheses.md`. Proof: `openspec validate c0098-electrical-readiness --strict`; `uv run pytest tests/unit/test_hypotheses_register.py -q`; `grep -n "decided by the maintainer on 2026-10-08: in v0.4" docs/roadmap.md` prints row 35.
  - 2026-10-08, on `origin/v04` at `04ef42a`: `openspec validate c0098-electrical-readiness --strict`: valid; `uv run pytest tests/unit/test_hypotheses_register.py -q`: 36 passed; the `grep` prints line 711, row 35. The section of v0.4 lists c0098 under board authoring with its branch, and the milestone table and "Milestone names" name it.

## 1. Shared definitions

- [ ] 1.1 Add `model.circuit.power_interface_nets` and use it in `checks/erc_lite.py` and `backends/kicad/schgen.py`; move the footprint rule of `validate_stage` into `checks.validate.unresolved_footprints`. Proof: `uv run pytest tests/unit/checks tests/unit/backends/kicad -q -k "validate or erc_lite or flag or power"`; `uv run pyright src`.

## 2. Rules

- [ ] 2.1 Write `src/fenolite/checks/readiness.py` (`READY_CHECKS`, `READY_ISSUE_CODES`, `EVIDENCE`, the stages of the three rules, `open_stage`, `skipped_check`) and `tests/unit/checks/test_readiness.py` (scenarios of the rules of the `verification-loop` delta); name the table in `cli.explain.TABLES` and add the five entries to `cli/data/explain.toml`. Proof: `uv run pytest tests/unit/checks/test_readiness.py tests/unit/cli/test_explain_cmd.py tests/unit/test_import_graph.py -q`.

## 3. Command

- [ ] 3.1 Add the fixture `tests/data/kicad/ready/` (the starter of `fenolite init`, built for target 10 and routed with `--router direct`: board, schematic, project) with its rows in `tests/data/MANIFEST.toml`, and `EXAMPLE_READY` in `cli/_examples.py`. Proof: `uv run pytest tests/unit/test_provenance.py tests/residue -q`.
- [ ] 3.2 Write `src/fenolite/cli/cmd_ready.py` and `tests/unit/cli/test_ready_cmd.py` (scenarios of the `cli-contract` delta, with the fake `kicad-cli`). Proof: `uv run pytest tests/unit/cli/test_ready_cmd.py tests/unit/cli/test_hermetic_examples.py tests/consistency -q`.

## 4. Documentation and guide

- [ ] 4.1 Describe `ready` in `docs/cli-contract.md`; name it in the prose of "The loop" of `src/fenolite/agent/skill/SKILL.md` (the block stays ten lines) and add a tested line and a section to `references/checks.md`, with `ready` in `HOME["checks"]` of `tests/unit/agent/test_pages.py`; regenerate `references/commands.md`. Proof: `uv run python tools/gen_agent_guide.py --check`; `uv run python tools/gen_schemas.py --check`; `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/agent tests/unit/test_agent_skill.py -q`.

## 5. Closing

- [ ] 5.1 Run the residue scan. Proof: `uv run python tools/residue/scan.py`; `uv run pytest tests/residue -q`.
- [ ] 5.2 Update the evidence labels: `H-G-READY-RULES` with the run of task 2.1 as its first record (stays `INFERRED`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 5.3 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`. Proof: `make check-fast` exits 0.
