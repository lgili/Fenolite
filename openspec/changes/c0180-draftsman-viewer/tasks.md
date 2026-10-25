## 0. Entry check

- [x] 0.1 Read c0172's specs and `draftsman.md`, and `pcb-document.md` on Embedded Board Arrays. Note under this task, with the date, the census of 2026-10-25 and the Part Q kit handed to the maintainer. Proof: `openspec validate c0180-draftsman-viewer --strict --no-interactive`.
  - 2026-10-25:
    - **Census:** the four public documents of S-0785 and S-0786 were read from the corpus cache with `read_draftsman`, and compared with the boards of S-0187 and S-0174 (design, "Context"). Counts, value forms and position comparisons only.
    - **Part Q:** the kit of phase A (panel variants saved in Altium) was handed to the maintainer on 2026-10-25. Until it returns, the Embedded Board Array stays `UNKNOWN` and this change only notes it.
    - The branch is `c0180-draftsman-viewer`, from `c0179-libraries-and-units` (`e689195`). Proof passed.

## 1. Facts and reader

- [x] 1.1 Record the facts of the census in `draftsman.md` ("Drawing geometry"), with the hypothesis `H-A-DWF-GEOM`, and the census in `docs/evidence/altium-draftsman.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-25: proof passed (60). Corrected the same day during task 2.3:
    - the sheet is Y up from its lower-left corner, and a view's or table's `Location` is its lower-left corner;
    - a font's `Size` is in 1/96 inch;
    - a part's assembly and silkscreen geometry are open strokes;
    - dimensions are measured from their snaps;
    - the view count is 12 of 12 top and bottom views. The first record counted the `Front` view and said 13. The proof passed again (60).
- [x] 1.2 Add `read.dwfdraw` (scenario "An authored document"). Proof: `uv run pytest tests/unit/backends/altium/test_dwfdraw.py -q`.
  - 2026-10-25: proof passed (8). The authored document is in `tests/_draftsman.py`. The view and drawing tests use it too.

## 2. Scene, page and command

- [x] 2.1 Add `fenolite.view.drawing` and the panel note (scenarios "Public drawings" and "A drawing of a panel"). Proof: `uv run pytest tests/unit/view tests/corpus/test_draftsman_draw.py -q`.
  - 2026-10-25: proof passed. With `FENOLITE_HEAVY=1` the corpus test ran all 13 cases:
    - 540 parts (239 bottom) of S-0785 and 23 of each S-0786 document land on their board pads;
    - 12 of 12 views lie on their sheets.
  - `holds_panel` reads the `EmbeddedBoards6` storage of an Altium board through `read.cfb`.
- [x] 2.2 Make `.PCBDwf` viewable and add the drawing summary (scenario "Summary of a drawing"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view tests/consistency -q`.
  - 2026-10-25: proof passed (466 passed, 24 skipped). The page's item list reads "Sheets". A sheet's notes list its item counts.
- [x] 2.3 Review in a browser the four public documents. Record the date, the browser and what was checked. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on exported standalone pages, read from screenshots.
    - **Sheet frame:** the first screenshots put the title blocks at the top, with their rows upside down. With Y up, every sheet reads as a drawing: the title block at the lower right, the notes at the upper right, and views and tables side by side without overlap. The facts were corrected (task 1.1).
    - **S-0786 assembly:** the top view with 23 parts and their designators, the empty bottom view, and the BOM table (13 rows, quantities summing to 23). The `Right` and `Front` views are named in the notes.
    - **S-0786 fabrication:** the layer stack legend, the board shape view, the drill view with three symbols, and the drill table (59, 32 and 4 holes). The two dimensions read 59.69 mm and 21.59 mm, the board's size, beside the board. The 12-element note wraps within its width.
    - **S-0785 assembly:** sheet 1 holds the outline with its arcs and 301 top parts; sheet 2 holds 239 bottom parts, mirrored. A click on U1 shows its comment, side and size. After `Q` the extent reads in mil.
    - **S-0785 fabrication:** six layer views of copper, the drill table of 15 sizes with their symbols, and the stack legend of 15 layers.
- [ ] 2.4 The maintainer reviews a drawing of their own against Altium (round F0.5 of Part F). Proof: the record under this task.

## 3. Docs and closing

- [x] 3.1 Update `docs/viewer.md` and the `view` section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/agent -q`.
  - 2026-10-25: proof passed (81 passed, 12 skipped). `tools/gen_agent_guide.py` was run for the `view` help, and the `files.md` line was shortened to keep the skill folder under its budget.
- [x] 3.2 Add the session row to `LEGAL-ANNEX.md` and run the fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 895 passed, 34 skipped). The first run found the reader without an `EVIDENCE` declaration; it now declares `INFERRED` (`H-A-DWF-GEOM`).
- [x] 3.3 Evidence labels. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: the page was regenerated with the new module; the check passed.
- [ ] 3.4 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
