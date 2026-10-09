## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `altium-verification`, `altium-build` and `verification-loop` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and whether c0084 is archived (else the rules source maps three kinds and the task says so). Proof: `openspec validate c0088-altium-light-drc --strict --no-interactive` passes.
  - **2026-10-06.** Archived: c0029, c0043, c0044, c0068. Not archived, implemented on the base commit `4ed96b20`: c0072 (parity; 11/12 tasks), c0084 (rules; 11/13) and c0122 (zone holes). Their code is what this change wires, so no task stops; c0072's parity requirements are not in the living specs, so none of them is MODIFIED here. c0084 is in: the rule table maps seven kinds.
  - No other active change modifies a requirement that this one supersedes (searched the `specs/` of every active change for the five names).
  - MODIFIED from the living text: `altium-verification` "Check on Altium inputs" and "Altium check stage evidence"; `verification-loop` "Document check pipeline" (it spells the stage tuple, so the design's "no delta" was wrong); `backend-protocol` "Design rules source"; `design-dsl` "Copper guard before writing". The deltas are generated from the living text with the stated replacements only. `openspec validate c0088-altium-light-drc --strict --no-interactive`: valid.

## 1. Registers

- [x] 1.1 Add the three rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - **2026-10-06.** `H-A-DRC-SAME`, `H-A-DRC-PARITY`, `H-A-DRC-ALTIUM` registered; S-0530 and S-0531 in `docs/evidence/sources.md`; the family `DRC` added to the pattern of `tests/unit/test_format_facts.py`. Passed.

## 2. Copper

- [x] 2.1 Implement `design_rules` and the board frame (`board_pads`, `placed_extents`) on the Altium backend. Proof: `uv run pytest tests/unit/backends/altium -k "rules_source or frame"`; `uv run pyright src`.
  - **2026-10-06.** `backends/altium/frame.py` is new (the backend had no frame; "Found on 2026-10-06", point 2). `design_rules` reads `Rules6/Data` alone (`read.pcb.read_rule_fields`). 10 passed; pyright clean.
- [x] 2.2 Add `copper.clearance` to the document pipeline (scenarios of "Document stage order" and "Copper check on Altium boards"). Proof: `uv run pytest tests/unit/checks/test_document_copper.py tests/unit/checks tests/unit/cli/test_check_altium_copper.py tests/unit/test_import_graph.py`.
  - **2026-10-06.** `checks.documents.document_copper`. The short of the scenario is planted in the design script and written by the build in warn mode, not by a record edit. Passed.
- [x] 2.3 (added 2026-10-06) Source the clearance of a pour from the Clearance rules, never from the model's default; count what cannot be judged. Re-measure `altium-third-party-pcbdoc-03`. Proof: `uv run pytest tests/unit/checks/test_document_copper.py -k "default or unjudged" tests/corpus/test_altium_copper.py -k copper -rA`.
  - **2026-10-06.** Where the value came from: `Zone.settings.clearance` (the model default 500 000 nm, which the import leaves) reaches `ClearanceResolver.resolve` as `zone_clearance` and wins over nothing when no rule governs. `AltiumBackend.design_rules` gives every zone the clearance 0, which the resolver reads as none. A filled zone that no clearance applies to is counted (`summary.zones_unjudged`, one `copper.rules-incomplete`), and the stage is `UNVERIFIED`.
  - Row 03 re-measured: 0 shorts, **0 clearance findings (266 before)**, 954 pairs judged for shorts only, 1 zone (6 fills) unjudged, 3 Clearance records opaque (two layer scopes, one matrix key). The 266 are gone because no clearance is in force, not because a smaller one was found: mapping those records is c0084's table.
  - Found on the way and handled, each with its fact row: the lines of internal planes (71 false shorts on two documents) and the rounding of the unit (1 088 findings 1 to 4 nm short). Counts per document: `docs/evidence/altium-roundtrip.md`, "Light DRC over the corpus".

## 3. Parity

- [x] 3.1 Write `adapter/parity.py` and the backend's `parity_side` (scenario "Agreeing project"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_parity_side.py`.
  - **2026-10-06.** The method is `parity_side(schematic, board)` of the new protocol `DocumentParity`, not `schematic_side` of `ParityInputs` ("Found on 2026-10-06", point 7). The committed samples `blink`, `routed` and `board6` give no finding (`tree` holds no PCB document). On the public sets the library of every footprint and 189 net names differed in spelling alone (129 after c0083's channel names, and 10 more on `altium-set:01`), so both are read as one (point 8). The side uses `Component.pin_pad_map` when the component holds one; this change does not fill it. 9 passed.
- [x] 3.2 Add `parity` to the document pipeline and Altium input to `fenolite parity` (scenarios of "Parity on Altium projects"). Proof: `uv run pytest tests/unit/checks/test_document_parity.py tests/unit/cli/test_check_altium_copper.py tests/unit/cli/test_parity_cmd.py tests/consistency`.
  - **2026-10-06.** The renamed designator of the scenario is the PCB document of a second build of the script, not a record edit. Passed.

## 4. Guard

- [x] 4.1 Add the copper guard to the Altium build (scenario "Short refused"). Proof: `uv run pytest tests/unit/cli/test_build_altium_guard.py tests/unit/cli/test_build_copper_guard.py tests/unit/cli/test_build_altium.py`.
  - **2026-10-06.** In `cli/cmd_build.py` (`altium_copper_guard`), not in `lens/altium.py`: `lens` may not import `checks`. The option is `--copper-check`, as for KiCad; there is no `--no-copper-guard`. The result of an Altium build gains `copper_check` after `copper` (`tests/unit/cli/test_build_altium.py` holds the key order). 6 passed.

## 5. Agreement and evidence

- [x] 5.1 Write `tests/kicad/altium/test_copper_same.py` and `tests/corpus/test_altium_copper.py`; record the boards and their counts in `docs/evidence/altium-roundtrip.md`. Proof: `uv run pytest tests/kicad/altium/test_copper_same.py tests/corpus/test_altium_copper.py -rA` with the corpus cached.
  - **2026-10-06.** `test_copper_same.py`: 4 passed (the routed blink as built, with a short, with a clearance fault, with both; equal by code, nets, layer and place within 2 nm). It runs no tool. `test_altium_copper.py`: 13 passed, 1 skipped (`altium-set:01` is heavy); 14 passed with `FENOLITE_HEAVY=1` on the tree that holds c0083, where the parity counts are pinned (`PARITY`).
  - **Not done:** the comparison of the public documents with KiCad's own import of them. `kicad-cli pcb import` writes no rules, so only shorts could be compared, and none remains on the Altium reading. `H-A-DRC-SAME` therefore stays `INFERRED`, not `CORPUS-VERIFIED`.
- [ ] 5.2 Document the stages in `docs/cli-contract.md` and `docs/altium.md`; hand Part D to the maintainer when c0084's sample exists and record his report. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/unit/test_hypotheses_register.py`.
  - **2026-10-06.** The two pages are written ("check on Altium input", "Copper guard of an Altium build", "parity"; `docs/altium.md`, "Checks") and the proof passes. **Open: Part D.** It is optional and only Altium can run it: steps D1 to D3 of the design, on the project `rules` of `~/fenolite-altium-checks/c0084-part-u/`. No file was built for it and nothing is marked `ALTIUM-VERIFIED`.

## 6. Closing

- [x] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0088-altium-light-drc --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - **2026-10-06.** `make check-fast`, the residue tests, the manifest test and `openspec validate --all --strict` pass on the branch. **Open:** `make check` and the pull-request checks are the coordinator's, once, at the merge (the rules of this wave).
  - 2026-10-09: closed by the full `make check` of 2026-10-08 on the release branch (c0154 task 4.3: exit 0, ruff clean, 1772 files formatted, pyright 0 errors, residue 0 hits with 11 waivers, `13828 passed, 2374 skipped` on Python 3.11.15; the residue and manifest tests are part of it) and the CI runs of `release-0.4.0` and its pull request #17, every job green (`unit` on Ubuntu with 3.11, 3.12 and 3.13, on macOS and on Windows, `kicad-9`, `kicad-10`, `routing` on KiCad 9 and 10, `wheel`, `dco`): 37836186018 (`32a19b3`), 37860490303 and 37860486308 (`acba81b`, whose tree is the released `591dc00` and `dev` at `a8732fc`); `openspec validate --all --strict --no-interactive` on 2026-10-09 reports only the known errors (c0084, c0085 twice, c0086, c0128) and long-requirement warnings, none for this change.
- [x] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
  - **2026-10-06.** The three rows hold their results. `claims.py` is unchanged: this change adds no operation and writes no file kind (the backend's operations stay `detect` and `read`). The matrix was regenerated.
- [x] 6.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite check` on Altium input runs the copper check (shorts, clearance, zone overlaps) and the parity comparison without a tool, and an Altium build refuses a board with a short", as a change of behaviour. Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - **2026-10-06.** Done; the entry says that a check that exited 0 can exit 5, and that `--stages` selects the former set.
