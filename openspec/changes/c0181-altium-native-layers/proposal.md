## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P0-1 of that analysis.

An Altium board opens in the viewer with the neutral model's layer names (`F.Cu`, `B.SilkS`, `Mech.1`), not
the ones its designer knows (Top Layer, Top Overlay, Mechanical 1, or the names given in the board's layer
stack). The layer tabs are in the model's order, not Altium's. On the public board of S-0174 the solder mask
and paste are derived from the pads with no expansion, as the neutral model holds no mask layer for an Altium
board (`docs/formats/altium/import.md`, `H-A-IMP-PADSTACK`), so the openings a reviewer checks are wrong
wherever the board uses an expansion.

## What Changes

- **Native layer names.** For an Altium board the scene names every layer as the board's `Board6` record
  does: the user's name of a numbered layer (`LAYER<i>NAME`), else Altium's default name (`Top Layer`,
  `Mid-Layer 1`, `Bottom Layer`, `Top Overlay`, `Top Paste`, `Top Solder`, `Mechanical 1`, `Multi-Layer`,
  `Drill Drawing`, `Keep-Out Layer`). The model name stays as the layer's id, so overlays, the 3D view and the
  KiCad boards are unchanged.
- **Altium's order and colours.** The layer tabs follow Altium's order: signal layers top to bottom, planes,
  overlays, pastes, solders, mechanical layers by number, then Multi-Layer and the drill layers. The colours are
  the authored Altium palette of c0178 for each native layer kind.
- **Solder mask and paste from the pads.** Each pad's paste and solder-mask expansion and their modes (none,
  from the rules, manual) are read from the pad record (`pcb-records.md`, "Pad"). A manual value is used as it
  is. A value from the rules uses the `SolderMaskExpansion` and `PasteMaskExpansion` rules of `Rules6` whose
  scope Fenolite evaluates (`read.scope`), by priority. A pad whose rule scope Fenolite cannot evaluate uses
  the rule of scope `All` and is counted in a note.
- **Vias.** A via's opening uses its tenting flags (c0112) and its own solder-mask expansion.
- **Properties.** A click on a pad shows its paste and mask expansions, their source (manual, rule name, or
  default) and the opening size in the chosen unit.

## Capabilities

### New Capabilities

- `altium-board-view`: the native layer names, order and colours of an Altium board scene, and its mask and paste openings.

### Modified Capabilities

- None.

## Non-goals

- KiCad boards: their names (`F.Cu`, user names of the board file) are already their tool's.
- Layer sets and view configurations of Altium (`.PCBSysConfig`).
- Evaluating every query of the Altium query language: only what `read.scope` evaluates.

## Evidence level required

- Layer names and order: `CORPUS-VERIFIED` against the boards of S-0170 to S-0176, S-0187 and S-0188 where
  their `Board6` holds the keys; the default names come from `read.pcbstack` (c0041).
- Mask and paste expansion: `INFERRED` (pad record offsets, `H-A-PCB-PAD`). The maintainer's review against
  Altium (task 3.3) confirms what the page shows.

## Impact

- **New:** `src/fenolite/view/altium_layers.py`; `tests/unit/view/test_altium_layers.py`;
  `tests/corpus/test_altium_layer_names.py`.
- **Changed:** `read/pcb.py` (pad mask fields), `view/scene.py` (layer labels and pad openings),
  `view/page.html` (labels, Properties rows), `cli/cmd_view.py`, `docs/viewer.md`,
  `docs/formats/altium/pcb-records.md`.
- **Size:** 3 design-days.
