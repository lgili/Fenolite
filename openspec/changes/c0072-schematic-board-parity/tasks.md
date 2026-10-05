## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `verification-loop`, `cli-contract` and `kicad-oracle` specs. Write under this task, with the date: whether c0060, c0062 and c0063 are archived (without c0060 the change waits; without c0062 the stage reports Fenolite's findings only and the comparison task 3.2 waits; without c0063 only `--netlist kicad` exists); whether c0070 is archived (own netlist over a sheet tree); and the demos of each tag that the corpus manifest lists with a board and a schematic. Proof: `openspec validate c0072-schematic-board-parity --strict --no-interactive` passes.

## 1. Probes and registers

- [ ] 1.1 Add the rows `H-K-PARITY-TYPES` and `H-K-PARITY-OWN` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `tests/kicad/check/test_parity_probes.py` (scenarios of "Parity types are probed"), record the outcomes and write the facts to `docs/formats/kicad/drc.md`. When an outcome is `different`, change Decision 2's table to the measured types before task 2.1, and say so under this task. Proof: `uv run pytest tests/kicad/check/test_parity_probes.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.

## 2. Comparison

- [ ] 2.1 Write `src/fenolite/checks/parity.py` and `tests/unit/checks/test_parity.py` (scenarios of "Parity comparison" and "Parity issue codes"), with authored sides and boards. Proof: `uv run pytest tests/unit/checks/test_parity.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 2.2 Write `src/fenolite/backends/kicad/parity_inputs.py`: components and pins from the sheets, nodes from the own netlist or from a netlist export; author `tests/data/kicad/parity/agree/`. Proof: `uv run pytest tests/unit/backends/kicad/test_parity_inputs.py`.

## 3. Command and stage

- [ ] 3.1 Write `src/fenolite/cli/cmd_parity.py` and `tests/unit/cli/test_parity_cmd.py` (scenarios of "Parity command"). Proof: `uv run pytest tests/unit/cli/test_parity_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_check_readonly.py`.
- [ ] 3.2 Add the stage `parity` with the comparison against KiCad's entries (scenarios of "Parity stage"). Proof: `uv run pytest tests/unit/checks/test_parity_stage.py tests/unit/checks tests/unit/cli/test_check_cmd.py`.

## 4. Oracle agreement

- [ ] 4.1 Write `tests/kicad/check/test_parity_agreement.py` (scenarios of "Own parity agrees with kicad-cli") and record `parity-own-agreement`. A mismatch is fixed in `checks/parity.py`, never in the test. Proof: `uv run pytest tests/kicad/check/test_parity_agreement.py -rA` on both majors with the corpus cached.

## 5. Documentation

- [ ] 5.1 Document the command, the stage, the codes and the summary counts in `docs/cli-contract.md`, and the comparison and its agreement with KiCad in `docs/verification.md` (or the page that describes `check`). Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0072-schematic-board-parity --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: both rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with the runs, or record what failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "New command `parity` and `check` stage `parity`: schematic against board and symbol pins against footprint pads, without KiCad for generated projects, cross-checked with KiCad's parity test when it runs". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
