## Why

Package 10 of change c0175 ("Library fidelity"), tasks 10.1 to 10.3, split into a change of its own as
c0175's design allows ("Cut order": each package may be split with the next free id when its turn comes).
Three defects of a board's footprints remain after a conversion or an edit:

- pads read from Altium and converted to KiCad have no mask and no paste opening: the converted pad lists
  only its copper layers, and `docs/conversion.md` records it;
- the 3D model that an Altium document embeds for a body is dropped by the conversion ("the imported body
  has no portable KiCad model file"), although `models3d.body_models` (c0193) reads it and its placement;
- a footprint edited on the board (silkscreen clipped, a pad moved) drifts from its library, and nothing
  makes the library again from the board or says how far the two differ.

## What Changes

- **Openings after conversion.** An imported pad gets its mask and paste layers by its kind, and its mask
  and paste expansion as the margins of two new optional fields of `Pad`, `mask_margin` and
  `paste_margin`, which the KiCad writers write for a pad that has no KiCad slots. A margin the conversion
  cannot tell is a loss of the new report kind `pad-margin`.
- **Model placement.** A new value `ModelPlacement` (path, offset, rotation, scale) and the field
  `FootprintDef.placements`; the KiCad footprint writer writes one `model` child for each. The conversion
  from Altium extracts each embedded model beside the derived library and places it; a model it cannot
  place is a loss of the new report kind `model`.
- **Library from a board.** The command `fenolite library BOARD --out LIB.pretty [--diff LIBRARY]`
  writes each footprint of a KiCad board as placed, brought back to its origin, rotation 0 and the top
  side, into a footprint library; `--diff` reports per footprint how a library differs from the board's
  instances and writes nothing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-conversion`: ADDED "Mask and paste of imported pads", "Model placement of imported footprints"
  and "Library made from a board" (moved from c0175 and narrowed), "Pad margins in the KiCad writers" and
  "Library command result".

## Non-goals

- Task 10.4 of c0175 (body copy by pad fit, one model-store entry per rotation, the coverage report
  against a house library): it stays in c0175.
- The paste `Enabled` switch and the solder `Tented` option of an Altium pad: no source read says which
  bytes hold them (`docs/formats/altium/pcb-library.md`, unknowns U1 and U2), so they are not read.
- A solder-mask or paste expansion rule whose scope is not `All`: its scope is not evaluated; the pads it
  may govern are reported (`pad-margin`).
- Models of bottom-side parts and models turned about X or Y: the flip and the order of KiCad's turns
  are not measured; each is a `model` loss.
- Models on the converted board's footprints: the derived library holds them, and KiCad's "update
  footprints from library" brings them to the board.
- `fenolite library` for an Altium board: the command reads KiCad boards; an Altium board is converted
  first.

## Evidence level required

- Pad layers and margins: `INFERRED` (`H-A-CONV-PADMASK`) until the oracle test
  `tests/kicad/convert/test_library_fidelity.py` passes on 9.0.9 and 10.0.6 in CI.
- Model placement: the KiCad frame of `offset` and `rotate` is measured with `kicad-cli pcb export vrml`
  (`H-K-MODEL-PLACE`); the Altium placement is c0193's `H-A-BODY-MODEL-PLACE`.
- `fenolite library`: `INFERRED` (`H-K-LIB-FROM-BOARD`), `KICAD-VERIFIED` once the oracle test loads the
  written library and its footprints export.

## Impact

- `src/fenolite/model/board.py` (`Pad.mask_margin`, `Pad.paste_margin`), `model/library.py`
  (`ModelPlacement`, `FootprintDef.placements`), `backends/kicad/_fpmap.py`, `mod.py`, `pcb.py`.
- `src/fenolite/convert/altium_to_kicad.py`, `convert/openings.py`, `convert/models.py`,
  `convert/report.py`, `convert/to_kicad.py`.
- New: `src/fenolite/library/` (`derive.py`, `codes.py`), `src/fenolite/cli/cmd_library.py`.
- Docs: `docs/conversion.md`, `docs/cli-contract.md`, `docs/formats/kicad/libraries.md`,
  `docs/formats/altium/import.md`, `docs/hypotheses.md`, the guide's `footprints` page and generated
  command page, `explain.toml`, `CHANGELOG.md`.
