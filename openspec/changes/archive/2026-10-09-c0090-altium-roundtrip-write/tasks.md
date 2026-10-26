## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `altium-verification`, `backend-protocol`, `altium-pcb-writer` and `altium-build` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and whether c0084, c0085, c0086 and c0089 are archived (the tasks below need all four). Proof: `openspec validate c0090-altium-roundtrip-write --strict --no-interactive` passes.
  - 2026-10-06: none of the changes this one depends on is archived (c0083 part 1, c0084, c0085, c0086, c0087 and c0089 are implemented on the base commit `4ed96b20`; c0043 and c0044 are archived). Nothing is stopped: their code is on the base. Requirements that this change supersedes and that another unarchived change also modifies: "Altium build outputs" (c0087: its text is the base of the MODIFIED delta here, so c0087 is archived first) and "Document check pipeline" (c0088 adds stages in parallel). The MODIFIED deltas are six: three in `altium-verification`, and one each in `verification-loop`, `altium-import` and `altium-build`. They were written after the code showed what the proposal had wrong (design, "Found on 2026-10-06"), not before any code as this task says. `openspec validate c0090-altium-roundtrip-write --strict --no-interactive` passes.

## 1. Registers

- [x] 1.1 Add the four rows to `docs/hypotheses.md`; `H-A-VER-RTA2-3` is registered as the successor of `H-A-VER-RTA2-2`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - 2026-10-06: four rows added; `H-A-VER-RTA2-2` is marked `refuted; superseded by H-A-VER-RTA2-3`. Proof passed.

## 2. Lowering

- [x] 2.1 Write `lower.py` and `AltiumBackend.write` for a design with a board (scenarios of "Altium write of a model" and "Imported boards are written from the model"). Proof: `uv run pytest tests/unit/backends/altium/test_lower.py tests/unit/backends/test_evidence_declared.py`; `uv run pyright src`.
  - 2026-10-06: done, with the corrections of "Found" 2 and 5 (`write` was new; rounded pads of a KiCad design go through `lens.altium.write_model`). Proof passed (`test_lower.py` 12 tests; `pyright src` 0 errors).
- [x] 2.2 Route the build through `from_design` and store the written board in `.fenolite/` (scenario "Build and write agree"; the committed samples stay byte-equal). Proof: `uv run pytest tests/unit/lens -k altium tests/corpus/test_manifest.py`.
  - 2026-10-06: NOT done as written, and not ticked. The build is not routed through `from_design` ("Found" 1: it would drop the footprint graphics and the PCB library of every sample). Done instead: the build stores the board it wrote in `.fenolite/`, and the scenario "Build and write agree" is corrected to what `test_lower.py -k build_agrees` proves. The committed samples keep their bytes (`uv run pytest tests/unit/lens -k altium` passes). Decision of the maintainer (2026-10-06): the task stays open and is closed by change c0126 (footprint instance graphics, corner ratio and library in the model); c0090 lands with the two paths.
  - 2026-10-08: closed by change c0126. The model now holds the graphics of a footprint instance and the corner ratio of a pad; `lens.altium.build_altium` places the footprints into the model (`place_footprints`) and makes its PCB document with `lower.from_design(..., options=lower.LowerOptions(...))`, and `lens.altium.pcb_document` and `corner_ratios` are removed. The committed samples keep their bytes, and the PCB document of every example build has the SHA-256 the former path gave (`tests/unit/backends/altium/test_lower_build_spec.py`). The PCB library is still written from the resolved library footprints (`LowerOptions.library`): the library is no fact of an instance (design of c0126, Decision 3). `uv run pytest tests/unit/lens -k altium tests/corpus/test_manifest.py`: 495 passed, 3 skipped (the official KiCad libraries and the saved file of step X8.6 are absent on the machine of this run).

## 3. Round-trip levels

- [x] 3.1 Widen RT-A2 (scenario "Copper compared"). Proof: `uv run pytest tests/unit/lens/test_altium_rta2.py tests/unit/checks -k rta2`.
  - 2026-10-06: done; rules stay outside the scope ("Found" 4). Every example build holds RT-A2 with all kinds compared. Proof passed.
- [x] 3.2 Write `rt_a3`, its stage and the two codes with their `explain.toml` entries (scenarios "Own sample" and "A writer defect is caught"). Proof: `uv run pytest tests/unit/checks/test_rta3.py tests/unit/checks tests/unit/cli/test_explain_cmd.py`.
  - 2026-10-06: done; `rt_a3` lives in `backends/altium/rta3.py` and the trip in `AltiumBackend.model_roundtrip` ("Found" 3). Proof passed.
- [x] 3.3 Accept Altium input in `fenolite roundtrip`. Proof: `uv run pytest tests/unit/cli -k "roundtrip and altium" tests/consistency`.
  - 2026-10-06: done. Proof passed.

## 4. Corpus and oracle

- [x] 4.1 Write `tests/corpus/test_altium_rta3.py`; record the documents, the result and the unwritten counts per kind in `docs/evidence/altium-roundtrip.md`. A difference inside the scope is fixed in the writer or the reader, never in the test. Proof: `uv run pytest tests/corpus/test_altium_rta3.py -rA` with the corpus cached.
  - 2026-10-06: done. With `FENOLITE_HEAVY=1`: 15 passed. Seven of eight PCB documents are equal; the heavy one differs in 7 arcs and is listed with its cause (`NOT_EQUAL`); two of five sets are equal and three are not judged (`UNJUDGED_SETS`). No difference was fixed by a change of a test; the three limits are in the evidence page and in "Found" 10. Decisions of the maintainer (2026-10-06): the arcs are closed by change c0127, the vias whose drill equals their diameter by c0128 (rewrites only), and the sets 01, 02 and 04 stay not judged in v0.3 (a tolerant schematic write belongs to v0.5a). Measured again after the rebase onto `0e1a6f4e`: 15 passed, no verdict and no count moved; modules and one pin-to-pad map are counted as not written.
- [x] 4.2 Write `tests/kicad/altium/test_rta3_oracle.py` and record the probe. Proof: `uv run pytest tests/kicad/altium/test_rta3_oracle.py tests/kicad/test_probe_results.py -rA` on KiCad 10.0.6.
  - 2026-10-06: done on `kicad-cli` 10.0.6, with the hypothesis restated ("Found" 9); the probe `altium-rta3-kicad` is `equal` and recorded in `docs/evidence/kicad/probes/10.0.6.json`. Proof passed (10 tests; `test_probe_results.py` passed).

## 5. Claims and documentation

- [x] 5.1 Update `claims.py` and regenerate the matrix (scenario "Matrix follows the run"); write "Round trips" and "Written scope" in `docs/altium.md`. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/backends/test_evidence_declared.py tests/consistency tests/unit/test_repo_layout.py`.
  - 2026-10-06: done; the notes are `claims.ROUND_TRIP_NOTES` ("Found" 8). Proof passed.

## 6. Closing

- [x] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0090-altium-roundtrip-write --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - 2026-10-06: partly. `make check-fast`, the residue and manifest tests and `openspec validate` pass. `make check` and `gh pr checks` are the coordinator's: the rules of this session forbid the full suite and a push.
  - 2026-10-09: closed by the full `make check` of 2026-10-08 on the release branch (c0154 task 4.3: exit 0, ruff clean, 1772 files formatted, pyright 0 errors, residue 0 hits with 11 waivers, `13828 passed, 2374 skipped` on Python 3.11.15; the residue and manifest tests are part of it) and the CI runs of `release-0.4.0` and its pull request #17, every job green (`unit` on Ubuntu with 3.11, 3.12 and 3.13, on macOS and on Windows, `kicad-9`, `kicad-10`, `routing` on KiCad 9 and 10, `wheel`, `dco`): 37836186018 (`32a19b3`), 37860490303 and 37860486308 (`acba81b`, whose tree is the released `591dc00` and `dev` at `a8732fc`); `openspec validate --all --strict --no-interactive` on 2026-10-09 reports only the known errors (c0084, c0085 twice, c0086, c0128) and long-requirement warnings, none for this change.
- [x] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
  - 2026-10-06: done; the four rows hold their measured results, all `INFERRED`. Proof passed.
- [x] 6.3 Add to `CHANGELOG.md` under Unreleased: "A model with a board can be written as Altium documents; RT-A2 compares footprints and copper, and the new level RT-A3 measures an import, write and re-import over the public corpus". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - 2026-10-06: done. `git diff --stat` lists both files.
