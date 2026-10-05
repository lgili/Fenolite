## 0. Entry check

- [ ] 0.1 Read the living `cli-contract` and `verification-loop` specs and `openspec list`. Write under this task, with the date: whether c0044 is archived (then "Model difference report" and "Diff command" exist: turn this change's two ADDED requirements into MODIFIED deltas that add sheets and the tree view, and start tasks 2.1 and 2.2 from its code); whether c0060 and c0062 are archived (else cut schematic inputs and `roundtrip --level rt2` for schematics, and say so); and that `src/fenolite/analysis/` holds c0047's modules, whose no-float test (`tests/unit/analysis/test_report.py -k no_float`) will also scan `views.py`. Proof: `openspec validate c0066-cli-inspection-commands --strict --no-interactive` passes after any re-base.

## 1. Registers and contract page

- [ ] 1.1 Add the row `H-K-FMT-IDEMPOTENT` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending`), and one section stub per new command in `docs/cli-contract.md` so the consistency suite's documentation checks have a target. Re-check every name consumed from archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`; `grep -c '^| H-K-FMT-IDEMPOTENT ' docs/hypotheses.md` prints `1`.

## 2. First half: `diff`, `roundtrip`, `fmt`

- [ ] 2.1 Write `src/fenolite/checks/diff.py` and `tests/unit/checks/test_diff.py` (scenarios of "Model difference report"), with property tests: a design against itself is equal whatever its ids; adding then removing an entity gives one `added` in one direction and one `removed` in the other. Proof: `uv run pytest tests/unit/checks/test_diff.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 2.2 Write `src/fenolite/cli/cmd_diff.py` with both views and `tests/unit/cli/test_diff_cmd.py` (scenarios of "Diff command", except the page scenario, which waits for task 6.1). Proof: `uv run pytest tests/unit/cli/test_diff_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
- [ ] 2.3 Write `src/fenolite/cli/cmd_roundtrip.py` and `tests/unit/cli/test_roundtrip_cmd.py` (scenarios of "Roundtrip command" for RT0 and RT1), and add `roundtrip` to `tests/unit/cli/test_check_readonly.py`. Proof: `uv run pytest tests/unit/cli/test_roundtrip_cmd.py tests/unit/cli/test_check_readonly.py tests/consistency`.
- [ ] 2.4 Add RT2 to `roundtrip` and write `tests/kicad/check/test_roundtrip_cmd.py`. Proof: `uv run pytest tests/kicad/check/test_roundtrip_cmd.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 2.5 Add `sexpr.canonical` and `sexpr.first_line_difference`, write `src/fenolite/cli/cmd_fmt.py` and `tests/unit/cli/test_fmt_cmd.py` (scenarios of "Fmt command" and the hermetic scenarios of "Canonical print check"). Proof: `uv run pytest tests/unit/cli/test_fmt_cmd.py tests/unit/backends/kicad/test_sexpr_dumps.py tests/consistency`.
- [ ] 2.6 Write `tests/corpus/test_fmt_idempotent.py` and copy its census into `docs/evidence/kicad-fmt-identity.md`. Proof: `FENOLITE_CENSUS_OUT=<file> uv run pytest tests/corpus/test_fmt_idempotent.py -rA` with the corpus cached; `git status --porcelain` lists no file under the cache.

## 3. `explain`

- [ ] 3.1 Write `src/fenolite/cli/explain.py` with `TABLES` and `all_codes`, and the completeness test of `tests/unit/cli/test_explain_cmd.py`, which fails until every code has an entry. Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -k tables` passes; the completeness test lists the missing entries.
- [ ] 3.2 Write `src/fenolite/cli/data/explain.toml`: `meaning`, `fix` and `see` for every FEN code and every issue code, and one family entry per tool family. Texts are written for Fenolite from the code and its docs; no vendor text is copied. Declare the data file as package data. Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -k complete tests/residue`; `uv build` lists `explain.toml` in the wheel.
- [ ] 3.3 Write `src/fenolite/cli/cmd_explain.py` (scenarios of "Explain command"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 4. `restore`

- [ ] 4.1 Add `id` and `undo` to `Receipt`, regenerate `schemas/fenolite.envelope.v0.json`, and extend `tests/unit/cli` for "Receipt identity". Proof: `uv run pytest tests/unit/cli tests/consistency tests/unit/test_schema_drift.py`; `uv run python tools/gen_schemas.py --check` exits 0.
- [ ] 4.2 Write `src/fenolite/cli/cmd_restore.py` and `tests/unit/cli/test_restore_cmd.py` (scenarios of "Restore command"), with a test that walks a folder before and after and proves that no file was deleted. Proof: `uv run pytest tests/unit/cli/test_restore_cmd.py tests/consistency`.

## 5. Board views

- [ ] 5.1 Write `src/fenolite/analysis/views.py` with `net_list` and `net_view`, leaving the package's `__init__.py` as c0047 wrote it, and `tests/unit/analysis/test_views.py` (net scenarios of "Board views"). Proof: `uv run pytest tests/unit/analysis tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 5.2 Add `region_view` with its property test against brute force. Proof: `uv run pytest tests/unit/analysis/test_views.py -k region`.
- [ ] 5.3 Add `neighbors_view` (neighbour scenarios). Proof: `uv run pytest tests/unit/analysis/test_views.py -k neighbors`.
- [ ] 5.4 Write `src/fenolite/cli/cmd_net.py`, `cmd_region.py` and `cmd_neighbors.py`, and `tests/unit/cli/test_views_cmd.py` (scenarios of "Net command", "Region command" and "Neighbors command"). Proof: `uv run pytest tests/unit/cli/test_views_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 6. Paging and concise output

- [ ] 6.1 Add `paged` and `default_limit` to `Command`, `--limit` and `--cursor` to the dispatcher, the `--issues N` option of the hidden `_echo` command, and `tests/unit/cli/test_paging.py` (scenarios of "Paged results"). Declare `paged` on `check`, `analyze` (its issues), `diff`, `net`, `region`, `neighbors` and, when they exist, `netlist`, `bom`, `pnp` and `manifest`; list the fields in `capabilities`. Proof: `uv run pytest tests/unit/cli/test_paging.py tests/unit/cli/test_capabilities.py tests/consistency`.
- [ ] 6.2 Add `--format concise|detailed` (scenarios of "Concise output"). Proof: `uv run pytest tests/unit/cli/test_paging.py -k concise tests/consistency`.

## 7. Documentation

- [ ] 7.1 Complete `docs/cli-contract.md`: one section per command with its result keys, the paging rule with the cursor's form, concise output, the receipt fields, the `roundtrip.*`, `fmt.*` and `restore.*` codes. Update the agent guide if it exists (`agent/SKILL.md`): `roundtrip` before editing a file Fenolite did not write, `--format concise` for one fix per iteration. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0066-cli-inspection-commands --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 8.2 Update the evidence labels: `H-K-FMT-IDEMPOTENT` becomes `CORPUS-VERIFIED` with the row counts, or records the rows that fail and why. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "New commands `diff`, `roundtrip`, `fmt`, `explain`, `restore`, `net`, `region` and `neighbors`; `--limit` and `--cursor` page a command's main list, `--format concise` keeps one issue per code; receipts carry an `id` and the `undo` command". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
