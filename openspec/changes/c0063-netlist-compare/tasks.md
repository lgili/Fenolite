## 0. Entry check

- [x] 0.1 c0060 and c0061 are archived: `KicadCli.export_netlist`, `read_schematic`, `generate_schematic`, `netnames` and `schlayout.pin_point` exist, and the living "Assignment compare stage" holds c0061's rule for pads on no net. If the living text differs from the base of this change's delta, re-base the delta first and note it under this task. Proof: `openspec list` shows both archived; `openspec validate c0063-netlist-compare --strict --no-interactive` passes.

  Note (2026-10-05): c0060 is archived; c0061 is implemented on dev and not archived yet. The names exist in the tree. The MODIFIED delta was re-based on the text of c0061's delta (design, Implementation notes); archive c0061 before this change.

## 1. Registers and fact rows

- [x] 1.1 Register the hypotheses and widen the sources. This is the first commit of the implementation.
  - Add the rows `H-K-NETLIST-SHAPE` and `H-K-NETLIST-OWN` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context", per major.
  - Widen the "used for" cell of S-0020 with the observed shape of the export per major, and of S-0022 and S-0037 with `sch export netlist` and its formats.
  - Re-check every name consumed from c0060, c0061 and archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-NETLIST-' docs/hypotheses.md` prints `2`.

  Note (2026-10-05): Divergences from the names the design consumes are listed in design, Implementation notes.
- [x] 1.2 Add to `docs/formats/kicad/schematic.md` the fact rows of the export: its root children per major, the parts the reader uses and those it ignores with the reason, `#` references, pin types and the flag suffix. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [x] 2.1 Write `tests/kicad/schematic/test_netlist_facts.py` with the three probes of "Schematic netlist through the package runner", reading the export with c0060's test helper until group 3 exists; add the probes to `PROBES` and regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task each outcome that differs from design "Context" and the fallback applied. Proof: `uv run pytest tests/kicad/schematic/test_netlist_facts.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Note (2026-10-05): Run on 10.0.6 (macOS) and on 9.0.9 (pinned image): netlist-shape equal, netlist-power-symbols absent, netlist-pintype equal on both; no outcome differs from design Context. Two details were added to the fact rows: an empty field has no text atom, and 9.0.9 writes the resolved path of a library where 10.0.6 writes the uri of the table. The probes read the export as a plain tree (sexpr.parse), not with c0060's helper, which reads components only. The two probe files were updated by running the netlist-* probes on each version and merging their rows; the other rows were not re-run (test_probe_results runs them all in the kicad-9 and kicad-10 jobs).

## 3. Reader and own netlist

- [x] 3.1 Write `src/fenolite/backends/kicad/netlist.py` and the two authored exports under `tests/data/kicad/netlist/` (declared in `tests/data/MANIFEST.toml`), and `tests/unit/backends/kicad/test_netlist.py` (scenarios of "Netlist export reading"). Proof: `uv run pytest tests/unit/backends/kicad/test_netlist.py tests/unit/test_repo_layout.py tests/residue`; `uv run pyright src`.
- [x] 3.2 Add `sch.opaque_heads`, write `src/fenolite/backends/kicad/sch_netlist.py` with `grammar_issues` and `own_netlist`, and `tests/unit/backends/kicad/test_sch_netlist.py` (scenarios of "Own netlist of a generated sheet" and "Netlist grammar check"), with one test per reason of the table. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py tests/unit/backends/kicad/test_sch_read.py`; `uv run pyright src`.

  Note (2026-10-05): The code lives in sch_netlist.ISSUE_CODES (the reader's closed set is pinned by a test of c0060), a ninth reason undefined-symbol was added, and shared-point also covers stacked pins without a label: design, Implementation notes. On 10.0.6 the own netlist of the blink and of the units design already equals the export (no difference, fields included).

## 4. Build guard

- [x] 4.1 Add the guard to `build_design` and `build.schematic-netlist-differs` to the build codes; write `tests/unit/lens/test_build_netlist_guard.py` (scenarios of "Schematic netlist guard in a build"). Proof: `uv run pytest tests/unit/lens tests/unit/cli/test_build_schematic_cmd.py tests/consistency`.

  Note (2026-10-05): The guard compares the members whose component has a symbol and takes the other pins from the sheet (a rebuild keeps footprints without a symbol), and two nets under one stored name are a difference of their own: design, Implementation notes. The scenario's defect was made an exchange of the two labels of R1; the label of pin 2 on pin 1 is a second scenario (grammar reason two-names).

## 5. Check

- [x] 5.1 Add `SchematicNetlistOracle` to `src/fenolite/backends/base.py` and `KicadOracle.schematic_netlist`; teach `tests/_fakecli.py` to write a given netlist for `sch export netlist`; extend `tests/unit/backends/kicad/test_oracle.py` and `tests/unit/backends/test_base_types.py` (scenarios of "Schematic netlist oracle" and of the oracle method). Proof: `uv run pytest tests/unit/backends`; `uv run pyright src`.

  Note (2026-10-05): tests/_fakecli.py already wrote a given netlist (c0060), so it was not changed. The run gets the copy set plus the schematic files the set lacks (oracle.schematic_files), because project_set lists no schematic until c0062; the protocol check is its own typed function, _schematic_protocol, so c0062 can extend _protocols.
- [x] 5.2 Add the `schematic` source and its pairs to `checks/assignment_compare.py`, name model elements by pad number, and add a `SchematicNetlistOracle` fake to `tests/unit/checks/fakes.py`; extend `tests/unit/checks/test_assignment_compare.py` (the five new scenarios of "Assignment compare stage"). Proof: `uv run pytest tests/unit/checks tests/unit/test_import_graph.py`.

  Note (2026-10-05): model_netlist already named elements by pad (c0061), so only the source and its pairs were added. The stage asks for the schematic beside the board as well as in the copy set (schematic_file). A fake kicad-cli that is given no netlist now fails the check of a project with a schematic: tests/_netexport.py writes an agreeing export for such tests, and the fixture of tests/unit/cli/test_manifest_cmd.py (c0065) passes one.
- [x] 5.3 Extend `tests/kicad/check/test_netlist_oracle.py`: the built blink and the units design give 0 differences in every pair on both majors, and the hidden-power sheet of c0061's probes gives a (`model`, `schematic`) difference when its symbol is embedded with the pins hidden. Proof: `uv run pytest tests/kicad/check/test_netlist_oracle.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Note (2026-10-05): Passed on 10.0.6 (macOS) and on 9.0.9 (pinned image, Python 3.11): the built blink and the units design give 0 differences in (model, board), (model, schematic) and (board, export), and in (schematic, board) without the .fenolite model; the hand sheet of c0061's power probe gives a (model, schematic) difference with its pins hidden and none with them shown. Two tests of c0061 and c0013 that pinned two pairs for a built blink now expect three. The 9.0.9 run found an unhashable dataclass default that Python 3.11 refuses; netlist.py uses a factory.

## 6. Command

- [x] 6.1 Write `src/fenolite/cli/cmd_netlist.py`, add `EXAMPLE_SCHEMATIC` to `src/fenolite/cli/_examples.py`, and write `tests/unit/cli/test_netlist_cmd.py` (scenarios of "Netlist command"); add `netlist` to `tests/unit/cli/test_check_readonly.py`. Add the section "netlist" to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_netlist_cmd.py tests/unit/cli/test_check_readonly.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

  Note (2026-10-05): The fakes of the two example suites are given the authored export (EXAMPLE_NETLIST), and test_hermetic_examples lists netlist among the tool-backed commands. A schematic alone is exported with its sheets and project file; a timeout exits 6 with FEN-6001, retryable. agent/SKILL.md names the command. On 10.0.6 both sources give equal nets, counts and components for the built blink and the units design (test_netlist_oracle.py -k command).

## 7. Acceptance

- [x] 7.1 Write `tests/_gendesigns.py` and `tests/unit/test_gendesigns.py`. Proof: `uv run pytest tests/unit/test_gendesigns.py tests/residue`.

  Note (2026-10-05): The 25 designs of seed 20261004 hold 1 to 12 parts; 19 have the multi-unit part, 18 a pin-pad map, 21 a no-connect mark, 16 a power interface, 18 a net name with a slash, 18 a module and 20 an open pin. Every one builds for target 10 without an error and passes the netlist guard.
- [x] 7.2 Write `tests/kicad/schematic/test_own_netlist.py` (requirement "Own netlists equal kicad-cli's"), add its probes and regenerate the probe files. Each difference is fixed where it comes from and noted under this task with the hypothesis it touches. Copy the counts into `docs/evidence/kicad-schematic.md`. Proof: `uv run pytest tests/kicad/schematic/test_own_netlist.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Note (2026-10-05): `test_own_netlist.py` passed on 10.0.6 (macOS) and on 9.0.9 (pinned image), 31 tests each. No difference was found, pin types included: the blink, the units design, the four examples that build for the KiCad target with the repository's libraries (`altium_hier_board`, `blink_2layer`, `blink_routed`, `board_40parts`) and the 25 generated designs. No hypothesis of c0061 was touched. `netlist-own-blink`, `netlist-own-units` and `netlist-own-generated` are `equal` in both probe files; as in task 2.1 only the `netlist-*` probes were run and merged, so `tests/kicad/test_probe_results.py`, which runs every probe of a major, was not run here and is left to the `kicad-9` and `kicad-10` jobs.
- [x] 7.3 Update `docs/schematic.md` with the guard, the grammar of the own netlist and the two sources of `fenolite netlist`. Proof: `uv run pytest tests/unit/test_repo_layout.py tests/residue`.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `make check` passes; `openspec validate c0063-netlist-compare --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.

  Note (2026-10-05): Left open. The rules of this implementation run leave the full suite (make check, uv run pytest -q) to the coordinator at the merge, and nothing is pushed, so gh pr checks has no run to show. Done here instead: make check-fast, the residue scan, openspec validate --strict, and the oracle tests of this change on 10.0.6 and in the pinned 9.0.9 image (tasks 2.1, 5.3, 7.2).
- [x] 8.2 Update the evidence labels: `H-K-NETLIST-SHAPE` and `H-K-NETLIST-OWN` become `KICAD-VERIFIED (9.0.x, 10.0.x)` or are refuted with a successor and the fallback applied. Raise `netlist.EVIDENCE` and `sch_netlist.EVIDENCE` only for a hypothesis that holds on both majors. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [x] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite netlist`: components and nets of a KiCad project as JSON, from `kicad-cli` or from Fenolite's own reading of a generated schematic; `build` refuses a schematic whose netlist differs from the circuit; `check` compares the schematic's netlist with the model and the board". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
