# c0480: an imported Altium project builds back for Altium without loss

## Why

The maintainer's board (private; codes and counts only) goes Altium → Python → Altium (`import --to
python`, then `build --target altium`, flow F2) and Altium → KiCad → Altium (flow F5). F5 comes back
equivalent to the source; F2 does not. On the board, F2 lost:

| loss | count |
|---|---|
| board lines, arcs and texts on user layers named `Mech.<n>` | 678 |
| footprint primitives on user layers named `Mech.<n>` | 21 |
| design rules of the source (Routing Via Style, pairs, silk, component clearance) | 14 |
| rules added from net-class values | 31 |
| `equiv.footprint-name` errors (footprints renamed `_<n>`) | 215 |
| board carriers skipped (`altium.verbatim-skipped`) | 10 |

It also reported the script's own drawings as `script copper: N graphics are not copied`, which they
are not.

Three causes:

1. `lens.altium_copper.lower_items` and `lens.altium._document_holds` check a drawing against the fixed
   board layers and `lower.KICAD_MECHANICAL` (User.1 to User.8). They do not use the user layer names
   that `lower.named_mechanical` maps to the source's mechanical layers, which the document writer
   itself uses (`built_mechanical`). The lens result replaces the writer's (`with_copper`), so the
   drawings are dropped.
2. `source_not_lowered` counts every item of a `script` copper source. Those are the script's own items,
   which the build writes from the design's board.
3. An import of an Altium project goes through an in-memory conversion to KiCad, and the script keeps
   that conversion's board carriers (`Fenolite.Altium.Rules6`, storages, unions, fonts, frame) as
   `kicad_pcb` verbatim items. `convert --to altium` reads them back; `build --target altium` skips them.

## What Changes

- `lower_items` takes the document's drawing layers (`layer_ids`). `lower_copper` passes
  `lower.built_mechanical` (now public). A text or drawing on a named user layer is written on its
  mechanical layer.
- `_document_holds` takes the board's drawing layers (`lower.kicad_mechanical(board)`), so a footprint
  drawing on a named user layer is a component item of the document.
- `source_not_lowered` leaves out the items the design's own board holds.
- `build --target altium` of a script that carries `Fenolite.Altium.*` board properties
  (`cmd_build.altium_carried`) builds the KiCad project of the script in memory. It converts that
  project as `convert --to altium` does and plans the conversion's files under `--out`. The result names
  `"through": "conversion"` and holds the conversion's report and equivalence.

- A conversion to Altium puts a pad on no net when its KiCad net `unconnected-(…)` holds that one pad
  and no copper (`to_altium.open_pads`), as the build lens already does (c0061). The KiCad build of a
  script names such nets, and the source held those pads on no net.

## Impact

- `src/fenolite/lens/altium_copper.py`, `src/fenolite/lens/altium.py`,
  `src/fenolite/backends/altium/lower.py`, `src/fenolite/cli/cmd_build.py`.
- A script without the carriers builds as before.
- On the board, F2 then equals F5: 124 of 124 rules, no `equiv.footprint-name`. The two
  `equiv.route-vias` that both flows share are the computed pour's (c0463).
