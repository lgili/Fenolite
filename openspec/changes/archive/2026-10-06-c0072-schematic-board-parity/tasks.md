## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `verification-loop`, `cli-contract` and `kicad-oracle` specs. Write under this task, with the date: whether c0060, c0062 and c0063 are archived (without c0060 the change waits; without c0062 the stage reports Fenolite's findings only and the comparison task 3.2 waits; without c0063 only `--netlist kicad` exists); whether c0070 is archived (own netlist over a sheet tree); and the demos of each tag that the corpus manifest lists with a board and a schematic. Proof: `openspec validate c0072-schematic-board-parity --strict --no-interactive` passes.
  - 2026-10-06: c0060, c0062 and c0063 are on `dev` (363b6738); c0060 is archived, c0062 and c0063 have every task but their CI run. c0070 is not archived (another agent implements it), so the own netlist covers one flat generated sheet and a tree of several sheets takes the tool. Every delta of this change is ADDED, so nothing was re-based on a MODIFIED text; the ADDED texts were corrected to what the tree and KiCad give (see the design, "Measured on 2026-10-06"). Demos with a board and a schematic: 14 of tag 10.0.6 (2 more have no schematic of the board's stem) and, of the boards that the `kicad-9` job fetches, 5 of tag 9.0.9.1 (the sixth, `RoyalBlue54L-Feather`, is malformed as published).

## 1. Probes and registers

- [x] 1.1 Add the rows `H-K-PARITY-TYPES` and `H-K-PARITY-OWN` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - 2026-10-06: both rows added; they were settled the same day (task 6.2).
- [x] 1.2 Write `tests/kicad/check/test_parity_probes.py` (scenarios of "Parity types are probed"), record the outcomes and write the facts to `docs/formats/kicad/drc.md`. When an outcome is `different`, change Decision 2's table to the measured types before task 2.1, and say so under this task. Proof: `uv run pytest tests/kicad/check/test_parity_probes.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.
  - 2026-10-06: every `parity-type-*` probe is `equal` on 10.0.6 and on 9.0.9 (pinned image, local run); both probe files hold the nine rows. The probes run on the built blink, and the `pic_programmer` demo repeats them as a `needs_corpus` test. Decision 2's table was changed before task 2.1: one duplicate per further footprint, `board_only` rules, the `attributes` field, and a pin without a pad as KiCad's `net_conflict` (design, "Measured on 2026-10-06"). Facts: `docs/formats/kicad/drc.md`, "Schematic parity".

## 2. Comparison

- [x] 2.1 Write `src/fenolite/checks/parity.py` and `tests/unit/checks/test_parity.py` (scenarios of "Parity comparison" and "Parity issue codes"), with authored sides and boards. Proof: `uv run pytest tests/unit/checks/test_parity.py tests/unit/test_import_graph.py`; `uv run pyright src`.
  - 2026-10-06: done; `SchematicSide` and `SideComponent` are defined in `backends/base.py` and re-exported.
- [x] 2.2 Write `src/fenolite/backends/kicad/parity_inputs.py`: components and pins from the sheets, nodes from the own netlist or from a netlist export; author `tests/data/kicad/parity/agree/`. Proof: `uv run pytest tests/unit/backends/kicad/test_parity_inputs.py`.
  - 2026-10-06: done; `tests/data/kicad/parity/agree/` holds the blink board and schematic of a target-10 build, kept equal to a fresh build by `tests/unit/cli/test_parity_cmd.py::test_example_is_a_fresh_build`.

## 3. Command and stage

- [x] 3.1 Write `src/fenolite/cli/cmd_parity.py` and `tests/unit/cli/test_parity_cmd.py` (scenarios of "Parity command"). Proof: `uv run pytest tests/unit/cli/test_parity_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_check_readonly.py`.
  - 2026-10-06: done.
- [x] 3.2 Add the stage `parity` with the comparison against KiCad's entries (scenarios of "Parity stage"). Proof: `uv run pytest tests/unit/checks/test_parity_stage.py tests/unit/checks tests/unit/cli/test_check_cmd.py`.
  - 2026-10-06: done; the default stages of `check` now hold `parity`, so the stage lists of `test_check_cmd.py`, `test_manifest_cmd.py` and `test_stages.py` gained it.

## 4. Oracle agreement

- [x] 4.1 Write `tests/kicad/check/test_parity_agreement.py` (scenarios of "Own parity agrees with kicad-cli") and record `parity-own-agreement`. A mismatch is fixed in `checks/parity.py`, never in the test. Proof: `uv run pytest tests/kicad/check/test_parity_agreement.py -rA` on both majors with the corpus cached.
  - 2026-10-06: `parity-own-agreement` is `equal` on both majors; the counts agree on the 14 demos of tag 10.0.6 and on the 5 of tag 9.0.9.1. Four mismatches found on the way were fixed in `checks/parity.py` and its KiCad adapter: `{slash}` against `/`, the `_<n>` net of a further pad, duplicates per further footprint, and pins without a number.

## 5. Documentation

- [x] 5.1 Document the command, the stage, the codes and the summary counts in `docs/cli-contract.md`, and the comparison and its agreement with KiCad in `docs/verification.md` (or the page that describes `check`). Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
  - 2026-10-06: `docs/cli-contract.md` ("parity", the stage under "check", the codes) and `docs/formats/kicad/drc.md` ("Schematic parity"); the repository has no `docs/verification.md`, and `check` is described in the contract page.

## 6. Closing

- [x] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0072-schematic-board-parity --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - 2026-10-06: the coordinator ran the full `make check` on `dev` 2e826017 (10878 passed, 60 skipped, KiCad 10.0.6), and every job of the CI run on that commit passed, `unit`, `kicad-9` and `kicad-10` among them (https://github.com/lgili/Fenolite/actions/runs/37395886697). The first run with this change, 37369162366 on 949d1f0c, failed on one test: the two files of `tests/data/kicad/parity/agree/` were not declared in `tests/data/MANIFEST.toml`; 527cfd7f declares them.
- [x] 6.2 Update the evidence: both rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with the runs, or record what failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
  - 2026-10-06: both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)` from the local runs of both majors; the CI run is to be cited when the jobs pass.
  - 2026-10-06: the `kicad-9` and `kicad-10` jobs passed on `dev` 2e826017 (https://github.com/lgili/Fenolite/actions/runs/37395886697); the run is cited in both rows.
- [x] 6.3 Add to `CHANGELOG.md` under Unreleased: "New command `parity` and `check` stage `parity`: schematic against board and symbol pins against footprint pads, without KiCad for generated projects, cross-checked with KiCad's parity test when it runs". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - 2026-10-06: done.
