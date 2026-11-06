# Design: c0433

## Where the pads went

`lower.from_design` sent a pad without a number to `PcbDocSpec.free_pads` (`pcbdoc.FreePad`) with the
`changed` reason of c0160, and `pcblib.check_footprint` dropped it from every footprint it checks (the
library and the document's components both pass through it). Nothing keyed the pads by number: two such
pads were both written, but as two free pads, so the component lost them. The reader gives each free pad a
footprint of its own without a reference, which the comparison reports as missing pads and ambiguous
references.

## The fix

- `pcblib.check_footprint` keeps a pad without a number. The pad record already writes an empty name as a
  first subrecord of length 0 (`pcb-records.md`, "A pad without a name").
- `lower.from_design` writes it as a pad of its component; its net comes from `nets_by_pad`, keyed by pad
  id, so two unnumbered pads on different nets stay distinct. The free-pad branch and `FREE_PAD_REASON` go.
- `rta3._free_pad_view` and `_read_as_hole` existed only to expect detached pads where the reader puts
  them; with none detached they go, and RT-A3 compares the pads in their component.

## Evidence

Census of the public corpus on 2026-11-06 with the Altium reader (counts only): `PCB1.PcbDoc` (S-0172) holds
one component with two pads without a name, `DM6010_R2M2E2.PcbDoc` (S-0200) one with two, and
`DM3370.PcbDoc` (S-0601) six components with one each; every one of them is a non-plated hole without a
net. The form is therefore `CORPUS-VERIFIED` for non-plated pads; a copper pad without a name inside a
component is the same record with other layers and stays `INFERRED`.
