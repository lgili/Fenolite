## 0. Entry check

- [ ] 0.1 c0060 and c0061 are archived: `KicadCli.export_netlist`, `read_schematic`, `generate_schematic`, `netnames` and `schlayout.pin_point` exist, and the living "Assignment compare stage" holds c0061's rule for pads on no net. If the living text differs from the base of this change's delta, re-base the delta first and note it under this task. Proof: `openspec list` shows both archived; `openspec validate c0063-netlist-compare --strict --no-interactive` passes.

## 1. Registers and fact rows

- [ ] 1.1 Register the hypotheses and widen the sources. This is the first commit of the implementation.
  - Add the rows `H-K-NETLIST-SHAPE` and `H-K-NETLIST-OWN` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context", per major.
  - Widen the "used for" cell of S-0020 with the observed shape of the export per major, and of S-0022 and S-0037 with `sch export netlist` and its formats.
  - Re-check every name consumed from c0060, c0061 and archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-NETLIST-' docs/hypotheses.md` prints `2`.
- [ ] 1.2 Add to `docs/formats/kicad/schematic.md` the fact rows of the export: its root children per major, the parts the reader uses and those it ignores with the reason, `#` references, pin types and the flag suffix. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Write `tests/kicad/schematic/test_netlist_facts.py` with the three probes of "Schematic netlist through the package runner", reading the export with c0060's test helper until group 3 exists; add the probes to `PROBES` and regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task each outcome that differs from design "Context" and the fallback applied. Proof: `uv run pytest tests/kicad/schematic/test_netlist_facts.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 3. Reader and own netlist

- [ ] 3.1 Write `src/fenolite/backends/kicad/netlist.py` and the two authored exports under `tests/data/kicad/netlist/` (declared in `tests/data/MANIFEST.toml`), and `tests/unit/backends/kicad/test_netlist.py` (scenarios of "Netlist export reading"). Proof: `uv run pytest tests/unit/backends/kicad/test_netlist.py tests/unit/test_repo_layout.py tests/residue`; `uv run pyright src`.
- [ ] 3.2 Add `sch.opaque_heads`, write `src/fenolite/backends/kicad/sch_netlist.py` with `grammar_issues` and `own_netlist`, and `tests/unit/backends/kicad/test_sch_netlist.py` (scenarios of "Own netlist of a generated sheet" and "Netlist grammar check"), with one test per reason of the table. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py tests/unit/backends/kicad/test_sch_read.py`; `uv run pyright src`.

## 4. Build guard

- [ ] 4.1 Add the guard to `build_design` and `build.schematic-netlist-differs` to the build codes; write `tests/unit/lens/test_build_netlist_guard.py` (scenarios of "Schematic netlist guard in a build"). Proof: `uv run pytest tests/unit/lens tests/unit/cli/test_build_schematic_cmd.py tests/consistency`.

## 5. Check

- [ ] 5.1 Add `SchematicNetlistOracle` to `src/fenolite/backends/base.py` and `KicadOracle.schematic_netlist`; teach `tests/_fakecli.py` to write a given netlist for `sch export netlist`; extend `tests/unit/backends/kicad/test_oracle.py` and `tests/unit/backends/test_base_types.py` (scenarios of "Schematic netlist oracle" and of the oracle method). Proof: `uv run pytest tests/unit/backends`; `uv run pyright src`.
- [ ] 5.2 Add the `schematic` source and its pairs to `checks/assignment_compare.py`, name model elements by pad number, and add a `SchematicNetlistOracle` fake to `tests/unit/checks/fakes.py`; extend `tests/unit/checks/test_assignment_compare.py` (the five new scenarios of "Assignment compare stage"). Proof: `uv run pytest tests/unit/checks tests/unit/test_import_graph.py`.
- [ ] 5.3 Extend `tests/kicad/check/test_netlist_oracle.py`: the built blink and the units design give 0 differences in every pair on both majors, and the hidden-power sheet of c0061's probes gives a (`model`, `schematic`) difference when its symbol is embedded with the pins hidden. Proof: `uv run pytest tests/kicad/check/test_netlist_oracle.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 6. Command

- [ ] 6.1 Write `src/fenolite/cli/cmd_netlist.py`, add `EXAMPLE_SCHEMATIC` to `src/fenolite/cli/_examples.py`, and write `tests/unit/cli/test_netlist_cmd.py` (scenarios of "Netlist command"); add `netlist` to `tests/unit/cli/test_check_readonly.py`. Add the section "netlist" to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_netlist_cmd.py tests/unit/cli/test_check_readonly.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 7. Acceptance

- [ ] 7.1 Write `tests/_gendesigns.py` and `tests/unit/test_gendesigns.py`. Proof: `uv run pytest tests/unit/test_gendesigns.py tests/residue`.
- [ ] 7.2 Write `tests/kicad/schematic/test_own_netlist.py` (requirement "Own netlists equal kicad-cli's"), add its probes and regenerate the probe files. Each difference is fixed where it comes from and noted under this task with the hypothesis it touches. Copy the counts into `docs/evidence/kicad-schematic.md`. Proof: `uv run pytest tests/kicad/schematic/test_own_netlist.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 7.3 Update `docs/schematic.md` with the guard, the grammar of the own netlist and the two sources of `fenolite netlist`. Proof: `uv run pytest tests/unit/test_repo_layout.py tests/residue`.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `make check` passes; `openspec validate c0063-netlist-compare --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 8.2 Update the evidence labels: `H-K-NETLIST-SHAPE` and `H-K-NETLIST-OWN` become `KICAD-VERIFIED (9.0.x, 10.0.x)` or are refuted with a successor and the fallback applied. Raise `netlist.EVIDENCE` and `sch_netlist.EVIDENCE` only for a hypothesis that holds on both majors. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite netlist`: components and nets of a KiCad project as JSON, from `kicad-cli` or from Fenolite's own reading of a generated schematic; `build` refuses a schematic whose netlist differs from the circuit; `check` compares the schematic's netlist with the model and the board". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
