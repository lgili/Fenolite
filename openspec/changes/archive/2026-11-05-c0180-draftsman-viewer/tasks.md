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
- [x] 2.4 **Moved to c0389 (decided 2026-11-05), as 5.2.** The maintainer reviews a drawing of their own against Altium (round F0.5 of Part F). Proof: the record under this task.
  - 2026-11-04 (S-1587): agent-run on a public project at the maintainer's request; not the maintainer's own project. The two drawings of `PCB-PiDP11IOExpander` were compared with Altium 24.5.2.23. The page has the same views, tables, notes and title blocks, and the same drill counts. It differs in the assembly top view (no silkscreen, no hatching of not-fitted parts), the empty bottom view, the right view's height (`43.2` against `11.43mm`), and a BOM with fewer columns and no variant applied. Stays open: round F0.5 asks for the maintainer's own drawing. See `docs/evidence/viewer-public-project-2026-11-04.md`.
  - 2026-11-05, review on the maintainer's delegation of 2026-11-04 (the coordinator's decision: a recorded Claude-agent run in Altium 24.5.2.23 satisfies this task only when its proof criteria pass as written): stays open. The coordinator accepts the public project `PCB-PiDP11IOExpander` in place of the maintainer's own drawing, provided the comparison criteria pass. They do not: the assembly top view lacks silkscreen and hatching, the bottom view is empty, the right view's height reads `43.2` against `11.43mm`, and the BOM has fewer columns and no variant applied.

## 3. Docs and closing

- [x] 3.1 Update `docs/viewer.md` and the `view` section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/agent -q`.
  - 2026-10-25: proof passed (81 passed, 12 skipped). `tools/gen_agent_guide.py` was run for the `view` help, and the `files.md` line was shortened to keep the skill folder under its budget.
- [x] 3.2 Add the session row to `LEGAL-ANNEX.md` and run the fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 895 passed, 34 skipped). The first run found the reader without an `EVIDENCE` declaration; it now declares `INFERRED` (`H-A-DWF-GEOM`).
- [x] 3.3 Evidence labels. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: the page was regenerated with the new module; the check passed.
- [x] 3.4 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: the entry is under `## [0.5.0]` of `CHANGELOG.md`, not `[Unreleased]`: by the maintainer's decision of 2026-10-25 the change ships in 0.5.0 (c0171 task 1.15). Proof passed (`tests/unit/test_release_record_v05.py`).

## Continuation review — 2026-11-01

Altium Designer is unavailable per the maintainer, and no personal F0.5 drawing comparison was supplied. Task 2.4 remains open.
See `docs/evidence/altium-native-acceptance.md`, "Continuation inventory", for existing reports and exact remaining dependencies. No native, paid-agent or personal-review outcome is claimed.

Pending Altium observations may use the actual available Designer 24.5.2.23,
by the maintainer's explicit2026-11-03 approval recorded in c0166. Historical
26.5 observations remain unchanged; this version permission is not a personal
project review, a missing implementation or a passing native outcome.

## Maintainer review source choice — 2026-11-03

The maintainer explicitly selected “Preparar exemplos autorais do Fenolite para minha revisão”
for this pending visual comparison. Original Fenolite-authored examples are the authorized review
inputs. This is source selection only: prepare source-bound CAD/viewer comparisons and retain
the complete original review checklist. The maintainer has not yet reviewed or approved those
comparisons; the human-review task remains unchecked. Preparation and evidence requirements
are recorded in `docs/evidence/native-viewer-maintainer-review-plan.md`.

- [x] 2.4a Prepare an external source-bound Fenolite-authored comparison packet with actual viewer export, original input hashes, criterion checklist and precise native handoff. Keep missing native captures/theme creation/F0.5 measurements explicit; source choice is not human acceptance. Proof: export dry-run/exact confirmation, fixture provenance and packet manifest. The parent human-review task stays open.
  - 2026-11-04: a Claude agent prepared a second packet at the maintainer's request, outside the repository (`~/fenolite-altium-checks/claude-2026-11-04/c0180-packet`). It binds the native F0.5 drawing that Altium 24.5.2.23 wrote in the agent's round of c0172 (S-1574, `F0-05.PCBDwf` `972c4046…`) and its `blink_routed` project files. It holds the viewer export `F0-05.viewer.html` (`9c535f4a…`), written by `fenolite view input/F0-05.PCBDwf --export F0-05.viewer.html --seed 1 --timestamp 2026-11-04T00:00:00Z`, first with `--dry-run` and then with `--confirm --plan 56d47a851795a0ea`, at source `8bbba776`. It also holds both replies, an eight-point checklist and `SHA256SUMS`. The reply reports 1 sheet, 1 `BoardAssemblyViewData` and `INFERRED` (`H-G-VIEW-SCENE`). Still missing: a native capture and an Altium Designer 26 comparison. The drawing holds a VM path, so the packet cannot be published. This task and task 2.4 stay open, and no level changes.
  - 2026-11-05: ticked, run by a Claude agent on the maintainer's delegation of 2026-11-04 (the coordinator's decision that a recorded agent run satisfies the task when its proof passes as written). The proof passes: the packet holds the viewer export, written with `--dry-run` and then `--confirm --plan`. The native F0.5 drawing comes from S-1574 (Altium 24.5.2.23), with the input hashes. The `SHA256SUMS` manifest and the checklist name the missing native capture and the missing Altium Designer 26 comparison. The packet stays outside the repository because the drawing holds a VM path. Parent task 2.4 stays open.

  - 2026-11-03 partial preparation: source bfda2ac4 has local standalone candidate/default exports and exact native handoff;39focused controls passed. The real KiCad-written authored theme (c0178) and nativeF0.5 drawing (c0180) are missing, so this preparation and parent human-review task remain open. No UI/configuration or native outcome was invented.
