## 1. Registers and fact rows

- [ ] 1.1 Register the hypotheses and the sources. This is the first commit of the implementation.
  - Add the rows `H-K-BOM-CSV`, `H-K-BOM-MODEL` and `H-K-POS-ROWS` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed on 10.0.6 at proposal time (2026-10-04)` with the observation of design "Context".
  - Add S-0340 and S-0341 to `docs/evidence/sources.md`. Widen the "used for" cells of S-0020, S-0022 and S-0037 with `sch export bom`, its options per major and the observed CSV.
  - Re-check every name consumed from archived changes and from c0061 (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -cE '^\| H-K-(BOM|POS)-' docs/hypotheses.md` prints `3`.
- [ ] 1.2 Add to `docs/formats/kicad/cli.md` the fact rows of `sch export bom` (options per major, header, quoting, rows, the `${DNP}` cell, unknown fields) and of the position CSV as far as this change relies on it. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image; after c0061)

- [ ] 2.1 Add `KicadCli.export_bom`, teach `tests/_fakecli.py` `sch export bom`, and extend `tests/unit/backends/kicad/test_cli_runner.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_cli_runner.py`; `uv run pyright src`.
- [ ] 2.2 Write `tests/kicad/assembly/_asmcases.py` and `test_bom_probes.py` with the six probes; add `tests/kicad/assembly` to the `sys.path` list of `tests/kicad/conftest.py` and to the fake run of `tests/unit/test_kicad_probes.py`; regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task each outcome that differs from design "Context" and what changed in Decision 4. Proof: `uv run pytest tests/kicad/assembly/test_bom_probes.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 3. Template and rendering

- [ ] 3.1 Write `src/fenolite/exports/assembly.py`: the template types, `read_template`, `DEFAULT` and the field vocabularies; author `tests/data/assembly/columns.toml`, `rotated.toml` and `invalid.toml` with invented column names and declare them in `tests/data/MANIFEST.toml`; write `tests/unit/exports/test_assembly.py` (scenarios of "Assembly template"). Proof: `uv run pytest tests/unit/exports/test_assembly.py tests/residue tests/unit/test_repo_layout.py`; `uv run pyright src`.
- [ ] 3.2 Add `render_csv`, `format_length` and `format_angle` (scenarios of "CSV rendering"), with property tests: a rendered table parsed by the stdlib reader gives the cells back; lengths agree with exact `Fraction` arithmetic. Proof: `uv run pytest tests/unit/exports/test_assembly.py`.

## 4. Tables

- [ ] 4.1 Write `src/fenolite/exports/bom.py` and `tests/unit/exports/test_bom.py` (scenarios of "Neutral BOM parts and lines" and "BOM difference"). Proof: `uv run pytest tests/unit/exports/test_bom.py tests/unit/test_import_graph.py`.
- [ ] 4.2 Write `src/fenolite/backends/kicad/bom.py`, the authored `tests/data/assembly/bom_export.csv`, and `tests/unit/backends/kicad/test_bom_csv.py` (scenarios of "BOM parts from kicad-cli"). Proof: `uv run pytest tests/unit/backends/kicad/test_bom_csv.py`.
- [ ] 4.3 Write `src/fenolite/exports/placement.py` and `tests/unit/exports/test_placement.py` (scenarios of "Neutral placement rows"), with property tests on the rotation rule (the result is in [0°, 360°), and sign 1 with offset 0 is the identity). Proof: `uv run pytest tests/unit/exports/test_placement.py`; `uv run pyright src`.

## 5. Commands

- [ ] 5.1 Write `src/fenolite/cli/cmd_bom.py` and `tests/unit/cli/test_bom_cmd.py` (scenarios of "Bom command"); add the codes to `exports/codes.py`; add the section "bom" and the code table to `docs/cli-contract.md`; add `bom` to `tests/unit/cli/test_check_readonly.py`. Proof: `uv run pytest tests/unit/cli/test_bom_cmd.py tests/unit/cli/test_check_readonly.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
- [ ] 5.2 Write `src/fenolite/cli/cmd_pnp.py` and `tests/unit/cli/test_pnp_cmd.py` (scenarios of "Pnp command"); add the section "pnp" to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_pnp_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 6. Oracle proofs (both majors)

- [ ] 6.1 Write `tests/kicad/assembly/test_assembly_oracle.py` (requirement "Assembly tables agree with kicad-cli"), add its probes and regenerate the probe files. A difference between the sources corrects Decision 2's rule for parts, noted under this task. Proof: `uv run pytest tests/kicad/assembly tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 7. Guide

- [ ] 7.1 Write `docs/assembly.md` (requirement "Assembly issue codes and evidence"): the template reference, the worked example, the rotation keys with numbers, the two BOM sources, and the statement that no template of any assembly service ships. Link it from `README.md` and `docs/exports.md`. Proof: `uv run pytest tests/unit/test_repo_layout.py tests/residue`; `uv run python tools/residue/scan.py` exits 0.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `make check` passes; `openspec validate c0064-bom-pnp-templates --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 8.2 Update the evidence labels: `H-K-BOM-CSV`, `H-K-BOM-MODEL` and `H-K-POS-ROWS` become `KICAD-VERIFIED (9.0.x, 10.0.x)` or are refuted with a successor and the fallback applied. Raise `bom.EVIDENCE_KICAD`, `bom.EVIDENCE_MODEL` and `placement.EVIDENCE` only for rows that hold on both majors. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite bom` and `fenolite pnp`: the bill of materials and the placement table of a project as neutral tables, rendered to CSV through a user-written column template (names, order, grouping, units, origin, side names, rotation rules); no template of any assembly service ships". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
