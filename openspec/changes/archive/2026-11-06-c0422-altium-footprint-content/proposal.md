# Keep everything an Altium footprint draws

## Why

An Altium to KiCad conversion of a real board (`convert --to kicad` and `import --to python`) does not keep
all that the board's footprints draw. The maintainer met it while converting a board. The reports are
descriptions only: every case in this change is authored for Fenolite, and nothing from that board enters
the repository.

1. **Footprint texts.** A component's own free texts (neither its designator nor its comment) are counted
   and reported lost, all of them: "a text of the footprint itself (not a designator or comment field) is
   not written" (change c0409, B8). KiCad holds such a text as an `fp_text user` child of the footprint.
2. **Footprint silkscreen in `equivalent`.** After c0409 wrote the footprints' drawings, level 7 of
   `equivalent SOURCE.PcbDoc CONVERTED.kicad_pcb` still reports hundreds of footprint silkscreen drawings as
   missing on the KiCad side.
3. **Footprint mechanical drawings in `equivalent`.** The drawings of the footprints on mechanical layers
   have no counterpart at level 7, on every mechanical layer the board uses.
4. **Silkscreen texts.** The texts missing on silkscreen at level 7 should close with 1 and 2.

Measured on the public corpus (rows `altium-third-party-pcbdoc-01` to `-08`): the conversion's own ledger
already writes every footprint drawing (c0409), so items 2 and 3 are not losses of the conversion. They come
from `equivalent`: the KiCad board reader keeps a footprint's `fp_*` children in their slots, so the KiCad
side holds no footprint drawing and no footprint text at all, and the conversion names the user layer of
Altium mechanical layer n `User.<k>` with the user name `Mech.<n>`, while the Altium side names it `Mech.<n>`.
On row `-06`, level 7 found 1 027 `graphic-missing` and 27 `text-missing`; with both causes fixed, only the
two keep-out drawings that the conversion reports as changed into rule areas remain. (Measured with a prototype of the
completion, withdrawn when c0421 was found to hold it.)

## What Changes

- **Footprint texts.** A created KiCad footprint writes its own texts as
  `(fp_text user "…" (at X Y A) (layer "L") (uuid "U") (effects …))` after its drawings and before its pads,
  the place KiCad 10.0.6 saves them in (census of the demo boards, S-0058): the angle on the board, the size,
  stroke and justification of the text, `(justify mirror)` on a back layer, as a created board text has it.
  The conversion no longer drops them; its `footprint-text` row counts each as written. The derived library
  and the footprints `import --to python` vendors hold them too, since both derive from the board footprint.
- **`equivalent` across an Altium and a KiCad side: left to c0421.** Change c0421
  (`equivalent-pairing-noise`) completes the KiCad side of a cross-backend comparison with its projected
  footprint items and pairs a layer with the layer of the other side whose user name is its name, which
  closes items 2 and 3. This change adds a test that the KiCad side of a conversion projects every drawing
  and text of the source on the expected layer, and the footprint texts without which item 4 cannot close.
- **Census.** `tests/corpus/test_convert_altium_census.py` loses its `footprint-text` losses and pins the
  written counts per public row.

## Impact

- Code: `backends/kicad/pcb.py` (created footprint texts), `convert/to_kicad.py` (no blanket drop).
- Docs: `docs/conversion.md`, `docs/formats/kicad/board.md` (two fact rows).
- Specs: design-conversion (requirement added).
- No model change, no schema change, no new command, DSL name or `FEN-` code.
- Not in scope: the Altium import's anchor of a text (centred, as for a free text) and its mirror flag (taken
  from the layer side, as for a free text); a PcbLib's free texts, which `FootprintDef` does not hold.
