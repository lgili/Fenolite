The first run (2026-10-05) implemented everything except the `kicad` source of the bill of materials, which needed a schematic that `kicad-cli` can export from. The second run (2026-10-06), after the schematic writer (c0061), implemented that source: tasks 2.1, 2.2, 4.2, 8.2 and group 9. Only 8.1 is open; see design, "Implementation notes".

## 1. Registers and fact rows

- [x] 1.1 Register the hypotheses and the sources. This is the first commit of the implementation.
  - Add the rows `H-K-BOM-CSV`, `H-K-BOM-MODEL` and `H-K-POS-ROWS` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed on 10.0.6 at proposal time (2026-10-04)` with the observation of design "Context".
  - Add the two CSV sources to `docs/evidence/sources.md` (S-0365 and S-0366: the ids S-0340 and S-0341 of the proposal were taken by c0076).
  - Re-check every name consumed from archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -cE '^\| H-K-(BOM|POS)-' docs/hypotheses.md` prints `3`.

  Done 2026-10-05. Divergences found: the source ids; `exports` may not import `templates`, so `TemplateError` is defined in `exports/assembly.py`; `place`, `route` and `fill` do not update `.fenolite/` (design, "Implementation notes", 3). The widening of S-0020, S-0022 and S-0037 for `sch export bom` moved to 9.1.
- [x] 1.2 Add to `docs/formats/kicad/cli.md` the fact rows of the position CSV as far as this change relies on it (quoting, `Val` and `Package`, DNP and excluded footprints, how `Rot` is printed). Add a row to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

  Done 2026-10-05. The rows are `INFERRED` under `H-K-POS-ROWS` until task 8.2. The fact rows of `sch export bom` moved to 9.1.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image; after c0061)

- [x] 2.1 Add `KicadCli.export_bom`, teach `tests/_fakecli.py` `sch export bom`, and extend `tests/unit/backends/kicad/test_cli_runner.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_cli_runner.py`; `uv run pyright src`.

  Done 2026-10-06. The call passes --fields, --labels and an empty --ref-range-delimiter; the field and string delimiters are left at the tool's defaults (design, Implementation notes, 11).
- [x] 2.2 Write `tests/kicad/assembly/test_bom_probes.py` with the six probes and their cases in `tests/kicad/assembly/_asmcases.py` (the file exists, with the placement cases); regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task each outcome that differs from design "Context" and what changed in Decision 4. Proof: `uv run pytest tests/kicad/assembly/test_bom_probes.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Done 2026-10-06. Six probes equal on 10.0.6 (local) and 9.0.9 (pytest inside the pinned image). Nothing differed from design Context; Decision 4 lost its two delimiter options for another reason (design, Implementation notes, 11 and 15). The eight keys were added to both probe files; test_probe_results.py passes on 10.0.6, and was not run as a whole on 9.0.9.

## 3. Template and rendering

- [x] 3.1 Write `src/fenolite/exports/assembly.py`: the template types, `read_template`, `DEFAULT` and the field vocabularies; author `tests/data/assembly/columns.toml`, `rotated.toml` and `invalid.toml` with invented column names and declare them in `tests/data/MANIFEST.toml`; write `tests/unit/exports/test_assembly.py` (scenarios of "Assembly template"). Proof: `uv run pytest tests/unit/exports/test_assembly.py tests/residue tests/unit/test_repo_layout.py`; `uv run pyright src`.
- [x] 3.2 Add `render_csv`, `format_length` and `format_angle` (scenarios of "CSV rendering"), with property tests: a rendered table parsed by the stdlib reader gives the cells back; lengths agree with exact `Fraction` arithmetic. Proof: `uv run pytest tests/unit/exports/test_assembly.py`.

## 4. Tables

- [x] 4.1 Write `src/fenolite/exports/bom.py` and `tests/unit/exports/test_bom.py` (scenarios of "Neutral BOM parts and lines" and "BOM difference"). Proof: `uv run pytest tests/unit/exports/test_bom.py tests/unit/test_import_graph.py`.

  Done 2026-10-05 without `bom.EVIDENCE_KICAD`, which belongs to the `kicad` source (9.2).
- [x] 4.2 Write `src/fenolite/backends/kicad/bom.py`, the authored `tests/data/assembly/bom_export.csv`, and `tests/unit/backends/kicad/test_bom_csv.py` (scenarios of "BOM parts from kicad-cli"). Proof: `uv run pytest tests/unit/backends/kicad/test_bom_csv.py`.

  Done 2026-10-06. backends may not import exports, so the reader returns BomRow and exports.bom has kicad_fields (the bom.field-unsupported check) and parts_from_kicad (design, Implementation notes, 12).
- [x] 4.3 Write `src/fenolite/exports/placement.py` and `tests/unit/exports/test_placement.py` (scenarios of "Neutral placement rows"), with property tests on the rotation rule (the result is in [0°, 360°), and sign 1 with offset 0 is the identity). Proof: `uv run pytest tests/unit/exports/test_placement.py`; `uv run pyright src`.

## 5. Commands

- [x] 5.1 Write `src/fenolite/cli/cmd_bom.py` with the `model` source, `--template`, `--out` and `--against`, and `tests/unit/cli/test_bom_cmd.py` (scenarios of "Bom command" except "From kicad-cli"); add the codes to `exports/codes.py`; add the section "bom" and the code table to `docs/cli-contract.md`; add `bom` to `tests/unit/cli/test_check_readonly.py`. Proof: `uv run pytest tests/unit/cli/test_bom_cmd.py tests/unit/cli/test_check_readonly.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

  Done 2026-10-05. The `kicad` source refuses and names `--source model` (design, "Implementation notes", 2); it is task 9.2. The code `bom.field-unsupported` comes with it.
- [x] 5.2 Write `src/fenolite/cli/cmd_pnp.py` and `tests/unit/cli/test_pnp_cmd.py` (scenarios of "Pnp command"); add the section "pnp" to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_pnp_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

  Done 2026-10-05. The rows come from the board file for every input; the spec delta was corrected (design, "Implementation notes", 3).

## 6. Oracle proofs (both majors)

- [x] 6.1 Write `tests/kicad/assembly/_asmcases.py` and `test_assembly_oracle.py` for the placement rows (requirement "Assembly tables agree with kicad-cli", "Placement rows"), add the probe `pos-rows` and its outcome to both probe files. Proof: `uv run pytest tests/kicad/assembly tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6.

  Done 2026-10-05: 9 tests pass on 10.0.6 and `test_probe_results.py` passes with the added key. On 9.0.9 the four subjects were measured through the package's `docker:` runner on the pinned image (`equal`), and the one key was added to `9.0.9.json`; pytest was not run inside the image, so the `kicad-9` job is the first full run there (task 8.2). Measured on both majors and written in `docs/assembly.md`: KiCad lists DNP parts and prints 270° as `-90.000000`. The BOM half of this requirement is task 9.3.

## 7. Guide

- [x] 7.1 Write `docs/assembly.md` (requirement "Assembly issue codes and evidence"): the template reference, the worked example, the rotation keys with numbers, the two BOM sources, and the statement that no template of any assembly service ships. Link it from `README.md` and `docs/exports.md`. Proof: `uv run pytest tests/unit/exports/test_assembly_guide.py tests/unit/test_repo_layout.py tests/residue`; `uv run python tools/residue/scan.py` exits 0.

  Done 2026-10-05. `test_assembly_guide.py` renders the worked example and compares it with the two files the guide prints. The guide says that the `kicad` source is not available yet (9.4 updates it).

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `make check` passes; `openspec validate c0064-bom-pnp-templates --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.

  Open: the coordinator runs the one full `make check` at the merge, and the two KiCad jobs run in CI. Passed on 2026-10-06 in the worktree: `make check-fast`, the residue scan, `openspec validate --strict`, `tests/kicad/assembly` on 10.0.6 and inside the pinned 9.0.9 image, and `tests/kicad/test_probe_results.py` on 10.0.6.
- [x] 8.2 Update the evidence labels: `H-K-BOM-CSV`, `H-K-BOM-MODEL` and `H-K-POS-ROWS` become `KICAD-VERIFIED (9.0.x, 10.0.x)` or are refuted with a successor and the fallback applied. Raise `bom.EVIDENCE_KICAD`, `bom.EVIDENCE_MODEL` and `placement.EVIDENCE` only for rows that hold on both majors. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.

  Done 2026-10-06 from local runs on both majors (design, Implementation notes, 16): the three rows, bom.EVIDENCE_KICAD, bom.EVIDENCE_MODEL, placement.EVIDENCE and the fact rows are KICAD-VERIFIED (9.0.x, 10.0.x); docs/evidence/matrix.md is regenerated.
- [x] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite bom` and `fenolite pnp`: the bill of materials and the placement table of a project as neutral tables, rendered to CSV through a user-written column template (names, order, grouping, units, origin, side names, rotation rules); no template of any assembly service ships". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.

## 9. The `kicad` BOM source (after c0061)

- [x] 9.1 Widen the "used for" cells of S-0020, S-0022 and S-0037 with `sch export bom`, its options per major and the observed CSV; add to `docs/formats/kicad/cli.md` the fact rows of `sch export bom` (options per major, header, quoting, rows, the `${DNP}` cell, unknown fields). Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py`.

  Done 2026-10-06 from running the binary only: S-0020 is widened and docs/formats/kicad/cli.md has the section Bill of materials. S-0022 and S-0037 are not widened: the manual pages were not read for this.
- [x] 9.2 Give `fenolite bom` its `kicad` source: `--kicad-cli` and `--timeout`, the parts from `KicadCli.export_bom` on the copy set read with `read_bom_csv`, `bom.EVIDENCE_KICAD` with the oracle `kicad-cli <version>`, the code `bom.field-unsupported` in `exports/codes.py` and in `docs/cli-contract.md`, and the scenario "From kicad-cli" in `tests/unit/cli/test_bom_cmd.py`; remove the refusal of design "Implementation notes", 2, and its test. Proof: `uv run pytest tests/unit/cli/test_bom_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

  Done 2026-10-06. The refusal of the first run is gone; counts.left_out is null for this source (design, Implementation notes, 13 and 14).
- [x] 9.3 Add `test_bom_sources` and the command comparison to `tests/kicad/assembly/test_assembly_oracle.py` (requirement "Assembly tables agree with kicad-cli", "BOM sources" and "Commands"), with the probes `bom-model-blink` and `bom-model-units`; regenerate both probe files. A difference between the sources corrects Decision 2's rule for parts, noted under this task. Proof: `uv run pytest tests/kicad/assembly tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Done 2026-10-06. bom-model-blink and bom-model-units are equal on both majors; Decision 2's rule for parts needed no correction. The command comparison runs with the default template and with columns.toml.
- [x] 9.4 Update `docs/assembly.md`, "The two sources of a bill of materials", and the "bom" section of `docs/cli-contract.md` for the `kicad` source; update the CHANGELOG entry. Proof: `uv run pytest tests/unit/exports/test_assembly_guide.py tests/consistency`.

  Done 2026-10-06.
