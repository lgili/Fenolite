# c0498: `fenolite check` on a PCB document agrees with Altium's own DRC

Found on: editing a private maintainer board, a dense two-layer power board, in November 2026 (codes only;
nothing from the board is in this change).

## Why

Three gaps showed up when the user compared `fenolite check` on a `.PcbDoc` with Altium's DRC on the same
document:

- **F25: silkscreen rules are not checked.** The document declares `SilkToSilkClearance`,
  `SilkToSolderMaskClearance` and `SilkToBoardRegionClearance` rules. `check` judges none of them:
  `read.rules` maps `SilkToSilkClearance` to the neutral kind `silk_clearance`, which no document stage
  reads, and keeps the other two as carried-only kinds ("no copper geometry"). A hand-written silk checker
  was needed. It matched every silk finding of Altium only once it measured a stroke text by its box the
  way Altium does. That is the model c0493 records as `H-A-SILK-DRC-MODEL` for placement.
- **F40: copper next to a cut-out or a keep-out passed.** A pour lay 0.03 mm from a slot under a 0.5 mm
  board-outline-clearance rule, and no finding said so. Reading the code gives two holes:
  - `checks.copper._Edges.findings` counts an item whose edge limit is unset in `summary.edge.unset_items`
    and says nothing else. An edge rule that the resolver does not apply to an item (a scope it does not
    select, a matrix cell it does not hold) is silent. Which case the field board hit is not known yet;
    task 1.1 reproduces each on authored boards.
  - A `Clearance` rule whose scope is `IsKeepOut`, `IsBoardCutoutRegion` or the Keep-Out layer is refused
    by the import (`rule-scope`). The pour reads it since c0463 (`pour._keepout_rule`), the copper check
    does not. Copper near a keep-out object is judged only for overlap (`copper.keepout`), never for distance.
- **F26: Altium's own results cannot be read.** A PCB document saved after a DRC holds the violations in
  `T…Violation` storages (`pcb-records.md` already names them as index-based storages that a round trip
  drops). Altium also writes a text report, `Design Rule Check - <doc>.drc` (`pcb-document.md`, "Native DRC
  report creation"). Fenolite reads neither, so the user ran DRC in Altium and the assistant compared the
  two lists by hand.

## What Changes

- **Stored violations.** A new reader, `backends.altium.read.violations`, reads the `T…Violation` storages
  of a PCB document with the existing compound reader, and the `WaivedViolations` storage. It gives one
  `NativeFinding` per violation: rule kind, rule name, the primitives it names (as the model's `where`
  texts) and a location in the model's frame. Waived violations are marked. The record layout is taken
  from public documents and from authored boards saved by Altium in a kit run. Nothing is assumed before
  that census (task 1.1).
- **Text report.** The same reader parses Altium's `.drc` text report into the same rows. The HTML report
  is not read (design D2).
- **`check --compare-native [REPORT]`.** On Altium input, an opt-in stage `altium.native-drc` reads the
  stored violations, or the report given, and pairs them with the findings of the stages that ran.
  `result.native` gives the pairs matched, Fenolite-only and Altium-only findings per rule kind, and the
  kinds Fenolite does not judge. Each unmatched finding is one warning (`check.native-only` or
  `check.fenolite-only`). Violations that point at primitives the document no longer holds give
  `check.native-stale`. Without `--compare-native` nothing changes.
- **Silk rules.** Two new neutral rule kinds, `silk_mask_clearance` and `silk_edge_clearance`, which take
  `SilkToSolderMaskClearance` and `SilkToBoardRegionClearance`. A new opt-in document stage
  `silk.clearance` judges `silk_clearance`, `silk_mask_clearance` and `silk_edge_clearance` with the
  `altium` model of c0493: `silk.clearance`, `silk.mask-clearance` and `silk.edge-clearance` findings.
  `--compare-native` selects it.
- **Cut-outs and keep-outs.**
  - Copper whose edge limit is unset while the board has an edge rule gives `copper.rules-incomplete`
    (`where` = `edge`) with the count. That count is no longer silent.
  - Each case task 1.1 finds missed is fixed in the resolver or in `frame.board_edges`.
  - The Altium rules view gives the keep-out `Clearance` rule to the copper check as the pour reads it
    (one shared function). The copper check judges copper against keep-out areas by distance:
    `copper.keepout-clearance`.

## Impact

- New: `src/fenolite/backends/altium/read/violations.py`, `src/fenolite/checks/native.py`.
- `src/fenolite/backends/base.py` (protocol `NativeDrcSource`), `src/fenolite/backends/altium/backend.py`
  (`design_rules`, `native_findings`), `src/fenolite/backends/altium/pour.py` (`_keepout_rule` moves to
  `read/rules.py`), `src/fenolite/backends/altium/read/rules.py` (two kinds leave `CARRIED_KINDS`).
- `src/fenolite/model/rules.py` (`RuleKind` +2: model minor version bump, schemas regenerated);
  `backends/kicad/rulemap.py` declares both kinds unsupported for KiCad.
- `src/fenolite/checks/copper.py` (`_Edges`, keep-out distance), `src/fenolite/checks/documents.py` (two
  opt-in stages), `src/fenolite/silk/board.py` (a whole-board judge built on c0493's `altium` model),
  `src/fenolite/cli/cmd_check.py` (`--compare-native`).
- Docs: `docs/formats/altium/pcb-records.md` (violation records), `docs/formats/altium/pcb-document.md`
  (the text report), `docs/formats/altium/rule-file.md` (the two kinds), `docs/cli-contract.md` ("check"),
  `docs/hypotheses.md`, the agent guide page `checks.md`.
- **Depends on c0493** for the `altium` silk model. If c0493 is not merged first, task 3.1 waits for it.
  c0490 (unit tolerance) and c0491 (hole and same-net copper) are not touched. Their verdicts show up in
  the comparison as they land.
- Existing output: unchanged without `--compare-native` and the opt-in stages, except
  `copper.keepout-clearance` and the edge `copper.rules-incomplete`. Both can appear on boards that passed
  before (counted on the public corpus by task 4.3).
