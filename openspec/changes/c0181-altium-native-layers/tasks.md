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

## Continuation review — 2026-11-01

Altium Designer is unavailable per the maintainer; no personal layer-tab/mask comparison was supplied. Task 3.3 remains open.
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

- [x] 3.3a Prepare an external source-bound Fenolite-authored comparison packet with actual viewer export, original input hashes, criterion checklist and precise native handoff. Keep missing native captures/theme creation/F0.5 measurements explicit; source choice is not human acceptance. Proof: export dry-run/exact confirmation, fixture provenance and packet manifest. The parent human-review task stays open.

  - 2026-11-03: source bfda2ac4 local input/standalone-export packet passed reviewed-plan writes and input-hash checks; existing focused viewer/writer controls39passed. Native version/captures and the parent human review remain absent. No UI/configuration was operated and no native or evidence promotion is claimed.


## 4. Configurable order — maintainer decision, 2026-11-03

The maintainer chose "Permitir configurar a ordem das abas no visualizador". This replaces only the
unproved universal ordering claim, not names, openings or task 3.3 acceptance. No empty native layers,
filter or draw-order change is authorized. Source 723183a1 and central-fast source ad8cbf2e stay frozen.

- [x] 4.1 Implement browser-local, document/hash-scoped order of available layers with an accessible draft editor: selected layer, Move up/down, Alt+Up/Down, Apply, Cancel/Escape and Reset. Preserve the existing default list and all original data/selections/visibility. Keep visibility-group controls available in custom mode. Proof: focused Chromium interaction cases for apply/cancel/reset/persistence, document/hash separation, invalid values and unavailable storage; unchanged geometry/data comparisons.
- [x] 4.2 Prove the real v6 scene's 14 available layers and a separately labelled authored 17-layer case, with keyboard stepping following custom order and the default restored. Do not claim equality with the native 17-tab set or complete human review. Proof: source-bound external v6 browser receipt and focused authored interaction tests.
- [x] 4.3 Document Order layers and the preference/reset limits in docs/viewer.md and the relevant agent UI guidance. Update CHANGELOG; regenerate the committed viewer assets and check them. Proof: focused Python/viewer tests, nominal TypeScript build, `uv run python tools/build_viewer.py --check`, OpenSpec strict, diff check and private staged residue scan. No new CLI/DSL/FEN code; no full/fast/native/CI/push in this task.


## Configurable-order focused proof — 2026-11-03

The user decision was implemented on isolated base ad8cbf2e. The original ranking
is retained as Default viewer order, without claiming a universal Altium order.
Thirteen Chromium cases passed (the separate authored 17-layer UI fixture and
three existing Layers regressions); 136 focused Python/viewer/agent-guide cases
passed. The guide's first run correctly rejected a misplaced Read next footer;
it was restored to the end without changing any test expectation.

Additional RED controls caught reset against a live replacement scene and a
missing-hash preference crossing document identity. Both were fixed and each
control passed before the final focused run. No helper, source board or fixture
was rewritten to make a check pass. TS compile, ruff/format, viewer bundle check,
and guide generator check passed.

The actual retained v6 scene has 14 available layers; it is distinct from the
native application's 17 tabs. A source-bound headless browser used 20 real
Alt+Up actions to configure those 14, checked real Escape/focus, Apply, reload,
Reset/Cancel and Reset/Apply. Scene JSON, selection, visibility, draw order and
canvas pixels stayed identical through application/reset; the original v6 bytes
remain SHA256 97d3339c991840960aabf48fa72a3ad12010a6d1292cf3210c98d1f39498c64c.
No empty native layer, global preference interpretation, CAD operation or human
approval was invented. Task 3.3 remains open. configurable-order-proof.json
binds the actual receipts; later central integration/CI stays separate.

The final browser run also proves stepping from Bottom Layer to the newly ordered
Mechanical13 (not its former next layer); the real v6 replay explicitly shows
that existing layer before the invariant snapshot, without adding a native layer.
Final strict validation, diff checks and the staged residue scan passed with
private gate on; no integration, release or task 3.3 approval is implied.
