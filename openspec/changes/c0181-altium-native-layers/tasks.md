## 0. Entry check

- [x] 0.1 Read `pcb-records.md` ("Pad"), `read.pcbstack`, `read.rules` and `read.scope`. Note under this task which rule scopes `read.scope` evaluates and how many pads of the public boards use each mask mode. Proof: `openspec validate c0181-altium-native-layers --strict --no-interactive`.
  - 2026-10-25:
    - **Scopes:** `read.scope` parses `All`, `InNet`, `InNetClass` and `InComponent`, `IsTrack`, `IsVia` and `IsPad`, with `And`, `Or` and `Not`. The view evaluates them all except net classes, which it does not know.
    - **Census** (the two public boards of the cache, S-0174 and S-0187):
      - S-0174: 100 pads, all with mask mode 1; 32 with paste mode 2 (−65.35 mil).
      - S-0187: 2 136 pads; 950 with mask mode 2 and 365 with paste mode 2.
    - **Rules:** the boards hold `SolderMaskExpansion` and `PasteMaskExpansion` rules of scope `All`, and one of scope `IsVia`.
    - **Layer names:** S-0187's `Board6` renames its layers (`Top Copper`, `GND 1`, `Bottom Mask`, `Assembly Notes`).
    - The branch is `c0181-altium-native-layers`, from `viewer-roadmap-specs` (`28c2ece`). Proof passed.

## 1. Reader and labels

- [x] 1.1 Type the pad record's paste and mask expansions and modes in `read.pcb`. Proof: `uv run pytest tests/unit/backends/altium -k pad -q`.
  - 2026-10-25: already done before this change. `PadRecord` has `paste_expansion`, `solder_expansion`, `paste_mode` and `solder_mode`. The import keeps the mode and value of every pad whose mode is not 1 in the pad's `ext`. No code was needed; the proof passed.
- [x] 1.2 Add `view/altium_layers.py` with the names and the order (scenario "A board with renamed layers"). Proof: `uv run pytest tests/unit/view/test_altium_layers.py -k names -q`.
  - 2026-10-25: proof passed. The names come from the import's layer `ext` (`altium_name`); the masks and pastes the scene derives come from `Board6`. The outline is `Board Outline`, because S-0174 names a mechanical layer `Board Shape`.

## 2. Openings and page

- [x] 2.1 Draw the mask and paste openings from the expansions (scenario "Manual and rule expansions"). Proof: `uv run pytest tests/unit/view/test_altium_layers.py -q`.
  - 2026-10-25: proof passed (3). The test documents are `blink.PcbDoc` with a layer renamed in `Board6` and three rules added to `Rules6`. A filled pad's opening now includes its edge stroke; c0176 left half of it out.
- [x] 2.2 Use the names in the page and add the Properties rows. Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py -q`.
  - 2026-10-25: proof passed within `make check-fast`. The tabs sort by the scene's `tab`. A pad's layers read with their native names.
- [x] 2.3 Run the public boards (scenario "Public boards"). Proof: `uv run pytest tests/corpus/test_altium_layer_names.py -q`.
  - 2026-10-25: proof passed with `FENOLITE_HEAVY=1` (2). The manual counts equal the census: (0, 32) and (950, 365).

## 3. Review and closing

- [x] 3.1 Review in a browser two public Altium boards: layer names and order, and the openings of three pads. Record the date and what was checked. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on exported pages.
    - **S-0174:** the tabs read Top Layer, Bottom Layer, Top Overlay, Bottom Overlay, Top Paste, Top Solder, Bottom Solder, then the mechanical layers by name (Board Shape, Top Assembly, Top Courtyard), Board Outline and Drill.
    - **Pad J4-1:** mask 3.94 mil from the rule `SolderMaskExpansion`, paste −65.35 mil manual. The mask opening reads 73.23 mil, that is 65.35 + 2 × 3.94, in mil after `Q`. The black ring of the opening is drawn around the pad.
    - **S-0187** (from the scene): GND 1, PWR, Signal Layer 1 and GND 2 sit between Top Copper and Bottom Copper.
- [x] 3.2 Docs (`docs/viewer.md`, `pcb-records.md` rows), `LEGAL-ANNEX.md` row and the fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 898 passed, 34 skipped).
- [ ] 3.3 The maintainer compares a board of their own with Altium: the layer tabs and the mask openings. Proof: the record under this task.
