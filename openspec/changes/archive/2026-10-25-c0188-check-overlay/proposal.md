## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P1-8 of that analysis.

`fenolite check` reports DRC and ERC findings as JSON with positions. The viewer draws `analyze` replies as
overlays (c0176) but not `check` findings, so a person reads coordinates instead of seeing the violation, as
Altium's DRC markers and Messages panel show it.

## What Changes

- **`--check FILE`** (a `fenolite check --json` reply) or **`--check run`** (run the board's checks first,
  KiCad DRC when `kicad-cli` is present and Fenolite's own checks): every finding with a position is drawn as a
  marker on its layer, every finding in a Messages panel grouped by rule, sorted by severity; a click zooms.
- Findings on sheets (ERC) are drawn on their sheet.
- `result.check` counts findings by severity.

## Capabilities

### New Capabilities

- `check-overlay`: DRC and ERC findings drawn on boards and sheets, with a Messages panel.

### Modified Capabilities

- `cli-contract`: ADDED "View command draws check findings".

## Non-goals

- Fixing findings from the page.

## Evidence level required

- Findings keep the evidence level of their stage; the page shows it per finding.

## Impact

- **New:** `src/fenolite/view/check_overlay.py`, `tests/unit/view/test_check_overlay.py`.
- **Changed:** `cli/cmd_view.py`, `view/page.html`, `docs/viewer.md`, `docs/cli-contract.md`, agent guide.
- **Size:** 3 design-days.
