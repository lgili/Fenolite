## 0. Entry check

- [x] 0.1 Read `openspec list`, the living `altium-build`, `altium-project-reader`, `cli-contract`, `manufacturing-exports` and `altium-verification` specs, and the design. Write under this task, with the date:
  - whether another open change holds a delta of "Altium build outputs", "Output job in an Altium build" or "Drawing specification files" (this change adds requirements and modifies none; if one now must be modified, regenerate it from the living text);
  - that S-0772 to S-0786 and the family `H-A-DWF-*` are still free on `dev` and on the open branches;
  - the maintainer's answers to the open questions.

  Proof: `openspec validate c0172-altium-draftsman --strict --no-interactive` passes.

  Done on 2026-10-16:
  - `openspec list` shows ten active changes (c0081, c0092, c0105, c0146, c0160, c0166, c0168, c0170, c0171, c0172). No change under `openspec/changes/` other than this one holds a delta of "Altium build outputs", "Output job in an Altium build" or "Drawing specification files"; this change adds requirements and modifies none.
  - S-0772 to S-0786 and the family `H-A-DWF-*` are used by no other branch: checked on `origin/dev`, `origin/release-0.5.0` (`980bc6d`) and the open branches `c0151-repeat-bus-split`, `c0168-altium-slots-cutouts`, `c0170-convert-slots-obstacles`, `c0173-board-panels` (which holds S-0790 to S-0802), `codex/c0164-native-altium-template` and `dev-c0161`. New sources of this change start at S-0803.
  - The maintainer's answers of 2026-10-16 (design, "Open questions"): every recommended answer is accepted. Views are empty shells that Altium fills by Import Changes, with no board copy (1); `--altium-draftsman` is `off` by default (2); the write gate is a constant flipped by his kit run (3); the drawing specification gets no new key (4); do-not-populate parts are reported and drawn as fitted (6); the four public samples are fetched-only corpus rows, never committed (7). On question 5 he chose to hold release 0.5.0 until the native document passes his kit, so the fallback "ship route P in 0.5.0, the document in 0.5.x" does not apply; the stop rules (routes T and P) still apply when a gate fails. He builds his first kit (F0) now, and what does not depend on his files is implemented in parallel.

## 1. Facts and the container (gate G1)

- [x] 1.1 Write `docs/formats/altium/draftsman.md` with the rows of the public pages S-0772 to S-0781: files and templates, binding to a project and a PCB document, Import Changes, the shell of a template, the objects of Decision 3 and their documented properties, parameters, the `PCBDrawing` output. Add the corpus rows `altium-third-party-pcbdwf-01` to `-04` (S-0785, S-0786; `embeddable = false`, uses `altium`, `altium-draftsman`) to `tests/corpus/manifest.toml`. Admit the family `H-A-DWF-*` on the Altium pages in `tests/unit/test_format_facts.py`. No reader or writer code before this task is ticked. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/corpus/test_manifest.py -q`.

  Done on 2026-10-16: `draftsman.md` holds 27 rows, 25 from S-0772 to S-0781 and two from S-0187 and S-0786 (the project parameters and the `PCBDrawing` output), all `INFERRED`, each naming an `H-A-DWF-*` row. The manifest has the rows `altium-third-party-pcbdwf-01` to `-04` (uses `altium`, `altium-draftsman`, `origin:third-party`; `embeddable = false`; the id and note rules of `tests/corpus/test_manifest.py` gained the kind `pcbdwf`); `tools/corpus_fetch.py --uses altium-draftsman` fetched the four files into the cache and their SHA-256 matched. A cited id must be registered, so the nine rows of the design's table were registered in `docs/hypotheses.md` as `INFERRED` and pending, and the family `H-A-DWF-*` left the reserved table. Proof passed: 116 tests.
- [ ] 1.2 Measure the container on the four public samples with a measuring script, `tools/draftsman_census.py`:
  - the header and its second field;
  - where the text runs start and how long they are;
  - each candidate algorithm with a public specification (Decision 1), registering each specification used as a source.

  Write the rows "Container" with their labels, and the result per candidate, in `docs/evidence/altium-draftsman.md`, "Census". Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py -k container -rA` with the corpus cached.
- [ ] 1.3 Build the F0 kit: the routed blink project and `README.md` with the steps F0.1 to F0.14 of Decision 8 into `~/fenolite-altium-checks/session-5/F-draftsman/f0/`, with `SHA256SUMS`. Write Part F, round F0, into `docs/evidence/altium-draftsman.md`. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f_f0 -q`.
- [ ] 1.4 **Maintainer, in Altium Designer 26.5.** Save F0.1 to F0.14 and send the folder. Then run `fenolite kit verify`'s path scan on it before anything is read, and record the report (date, version, file hashes) under "Reports". OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 1.5 Decide G1 (Decision 1). Does `read_draftsman` decode the four samples and every F0 file into well-formed XML, and is `H-A-DWF-FIELD` explained? Write the decision and the date here. If G1 fails after 2 design-days of tasks 1.2 to 1.5, tick 2.1 to 6.4 as cut with the reason, do 6.5 (route P), and tell the maintainer. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py -rA`; `FENOLITE_DWF_F0=<folder> uv run pytest tests/unit/backends/altium/test_draftsman_read.py -k f0`.

## 2. Reader and census

- [ ] 2.1 Write `backends/altium/read/draftsman.py` (scenarios "Public samples decode", "Not a document"). Proof: `uv run pytest tests/unit/backends/altium/test_draftsman_read.py -q`; `uv run pyright src`.
- [ ] 2.2 Run the census of the samples and of F0: element counts, the forms of sheets, views, tables, notes and parameters, and what each F0 step added. Write it into `docs/evidence/altium-draftsman.md` (counts and names only) and the fact rows into `draftsman.md`. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py -rA`; `uv run pytest tests/unit/test_format_facts.py -q`.

## 3. Writer and probes (gates G2, G3)

- [ ] 3.1 Write `backends/altium/draftsman.py`: `DraftsmanSpec`, `write_draftsman` for sheets, Texts, parameter texts and Notes, `written_scope`, `NATIVE_WRITE = False` (scenarios "Written document reads back", "Gate follows the report"). Proof: `uv run pytest tests/unit/backends/altium/test_draftsman_write.py tests/unit/backends/test_evidence_declared.py -q`.
- [ ] 3.2 Build the probes FP1 to FP5 (Decision 8) into `…/F-draftsman/fp/` with `README.md` and `SHA256SUMS`, and write round FP into Part F. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f_fp -q`.
- [ ] 3.3 **Maintainer, in Altium Designer 26.5.** Open FP1 to FP5 and report, per probe, whether it opens without a message and what it shows. Record the report and set `H-A-DWF-MINIMAL`, `-IMPORT` and `-TEMPLATE`. Decide G2 and G3 (Decision 9), write the route here, and tell the maintainer. One round of corrections is allowed before G2 fails. OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_verification_docs.py -k part_f -q`.

## 4. Content from the drawing specification

- [ ] 4.1 Add the views as shells, the Drill Table, the Layer Stack Legend, the BOM table, the board Table and the Linear Dimensions to the writer, each from its fact rows (cut order 1 to 5 applies). Proof: `uv run pytest tests/unit/backends/altium/test_draftsman_write.py -q`.
- [ ] 4.2 Write `lens/altium_draftsman.draftsman_spec` from the model, the drawing specification and c0117's layout (scenarios "Fabrication sheet of the routed blink", "No part on the bottom"). Proof: `uv run pytest tests/unit/lens/test_altium_draftsman.py tests/unit/test_import_graph.py -q`.

## 5. Build and command line

- [ ] 5.1 Plan the document in the build, list it in the project file, add the `PCBDrawing` output and the `[Parameter<n>]` sections, add `altium.draftsman-not-written` and `altium.draftsman-not-listed` to `ALTIUM_ISSUE_CODES` and `explain.toml`, and fill `result.draftsman` (scenarios of `altium-build`). Proof: `uv run pytest tests/unit/lens -k altium tests/unit/lens/test_altium_issues.py tests/unit/backends/altium/test_outjob_write.py -q`.
- [ ] 5.2 Add `--altium-draftsman` and `--drawing-spec` to `fenolite build` (scenarios of `cli-contract`). Prove that every committed Altium sample keeps its bytes. Proof: `uv run pytest tests/unit/cli/test_build_draftsman.py tests/unit/cli/test_build_altium.py tests/unit/lens/test_build_bytes_pinned.py -q`.
- [ ] 5.3 Teach the options (AGENTS.md rule 6): run `uv run python tools/gen_agent_guide.py` and add a tested line on the Draftsman document to `src/fenolite/agent/skill/references/altium.md`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.

## 6. Kit Part F and the gate

- [ ] 6.1 Build the acceptance kit: the routed blink with a drawing specification of two notes per page, built with `NATIVE_WRITE` set for the kit only, plus `expected.md` (drill counts per diameter from `drill_rows`, stack-up rows, parts), `README.md` with F1 to F8 and `SHA256SUMS`, into `…/F-draftsman/accept/`. Write round F1 to F8 into Part F. Proof: `uv run pytest tests/unit/backends/altium/test_part_f.py tests/unit/test_altium_verification_docs.py -k part_f -q`.
- [ ] 6.2 **Maintainer, in Altium Designer 26.5.** Run F1 to F8, save `saved.PCBDwf` (F8), and send the report. Record it in the form of the native acceptance inventory, register its source, run `FENOLITE_ALTIUM_F8=<file> uv run pytest tests/unit/backends/altium/test_part_f.py -k f8`, and set `H-A-DWF-KIT`, `-OUTJOB` and `-PARAMS`. OPEN until Altium was run; nothing is `ALTIUM-VERIFIED` before. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_verification_docs.py -k part_f -q`.
- [ ] 6.3 Only when FP1 to FP4 passed, set `draftsman.NATIVE_WRITE = True` and update the scenario "Gate off" to its new form. If F1 to F8 later fail, set it back and record why. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f tests/unit/cli/test_build_draftsman.py -q`.
- [ ] 6.4 Record the container, the reader, the writer and the build's document with their sources in `src/fenolite/backends/altium/PROVENANCE.md`, and the sessions in `LEGAL-ANNEX.md`. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
- [ ] 6.5 Only when a gate failed (Decision 9): ship route T or route P as decided, correct the specs, the design and the proposal under a heading "Found on <date>", and tick the cut tasks with their reason. Proof: `openspec validate c0172-altium-draftsman --strict --no-interactive`; `uv run pytest tests/unit/lens -k altium -q`.

## 7. Closing

- [ ] 7.1 Document the document, the options, the gate, the routes and the limits in `docs/altium.md` ("Draftsman document"). Replace the Altium sentence of `docs/drawings.md` with a pointer to it. Proof: `uv run pytest tests/consistency -q`.
- [ ] 7.2 Update the evidence: every `H-A-DWF-*` row holds its measured level, `draftsman.EVIDENCE` names them, and run `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 7.3 Run the residue scan and the fast checks. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes.
- [ ] 7.4 Add to `CHANGELOG.md` under `## [Unreleased]`: the Draftsman reader, the document behind its gate, the two build options, the job output and the project parameters, or the route that shipped. Proof: `grep -n "Draftsman" CHANGELOG.md`; `openspec validate c0172-altium-draftsman --strict --no-interactive` passes.
- [ ] 7.5 Publish the branch for CI and confirm the required jobs on the exact commit (AGENTS.md, workflow 4). Proof: `gh pr checks` shows `unit` and `wheel` passing.
