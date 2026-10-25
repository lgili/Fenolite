## 0. Entry check

- [x] 0.1 Read `diff`'s matching and the scenes; record the matching keys under this task. Proof: `openspec validate c0184-visual-diff --strict --no-interactive`.
  - 2026-10-25: `fenolite diff` compares models (`diff_designs`, `diff_libraries`, `diff_sheets`). This change compares scenes, as the design says, so it works for every format the viewer draws.
  - **Keys:**
    - Parts match by reference: place, rotation and side; value and footprint.
    - Primitives match as a multiset of (layer, kind, geometry, net name, part reference); their numbered labels are left out.
    - Zone fills (filled, on a net, of no part) match by area per (layer, zone, net), within 0.5 %.
    - Sheets match parts by reference (box, comment, library, parameters) and nets by name (pins).
  - **Agent guide:** it held 149 999 of its 150 000 bytes. The generated page now leaves out the type "string" of arguments, and its head says so, which brought it to 148 554 bytes.
  - The branch is `c0184-visual-diff`, from `c0183-board-rule-areas`. Proof passed.

## 1. Compare

- [x] 1.1 Add `view/compare.py` for boards (scenario "A moved part and a new track"). Proof: `uv run pytest tests/unit/view/test_compare.py -k board -q`.
  - 2026-10-25: proof passed. A moved part's primitives stay out of the added and removed lists.
- [x] 1.2 Add sheets. Proof: `uv run pytest tests/unit/view/test_compare.py -q`.
  - 2026-10-25: proof passed (4).
- [x] 1.3 Add `--compare` to `fenolite view` (scenario "Compare counts"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -q`.
  - 2026-10-25: proof passed. A board against a sheet is exit 2, `FEN-2001`. `--serve` compares again when the document is saved.

## 2. Page and closing

- [x] 2.1 Diff layer, OLD/NEW toggle and the Changes panel. Browser review of two commits of a public board. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless). The test pair was the board of S-0175's repository at commits `e58838c` (new) and `62a53c1` (old), downloaded to a scratch folder.
    - **Reply:** 40 added, 17 removed, 6 changed, 3 zones; for example `U101 value: SYM-0017 → MLX90640`, `P1 added`, `via 1 added on F.Cu, B.Cu, Drill`, `U101: 6 primitive(s) added, 6 removed`, and `zone GND_L02_P009 (GND) on B.Cu: 531.73 → 468.77 mm²`.
    - **Fewer lines:** the first version listed 164 lines, one per pad, mask opening and via layer. Grouping by part and by label gives 66.
    - **Colours:** removed copper was drawn red, the colour of Altium's Top Layer, so it now reads magenta over a board dimmed to 35 %.
    - **Toggle:** the design replaced the OLD/NEW toggle with `X`, which shows or hides the changes (design, decision 3).
    - **Panel:** a click on a line zooms to it.
- [x] 2.2 Docs, agent guide, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 916 passed, 34 skipped).
  - Changed: `docs/viewer.md` ("Comparing two revisions"), the `view` section of `docs/cli-contract.md`, and a line in `references/files.md`.
  - The guide holds 148 731 bytes.
