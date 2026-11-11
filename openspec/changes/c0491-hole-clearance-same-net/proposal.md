# c0491: `copper.hole-clearance` leaves out copper of the hole's own net

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

`copper.hole-clearance` reports the pour and the vias of a net beside the hole of an unplated pad of that
same net. Neither KiCad nor Altium reports this by default. Both state the hole clearance between
different nets:

- KiCad's board-setup hole clearance is "the clearance between a drilled hole of a pad or a via and copper
  of another net" (`docs/formats/kicad/project.md`, S-0010, S-0038).
- Altium's Clearance rule holds `NETSCOPE=DifferentNets` (`docs/formats/altium/pcb-copper.md`, S-0172 …
  S-0176).

The check already leaves out copper of the hole's net, but only for a plated hole.
`checks.copper._holes` sets `net_id = None` for every `np_thru_hole` pad, so an unplated hole never has a
net and every copper item near it is "another net". The spec says the same ("copper of the same net as a
plated hole"). An unplated pad with a net is common in Altium, for example a mounting hole tied to a
ground. So the check reports a fault that neither tool has.

## What Changes

- An unplated pad's hole carries the pad's net when the pad has one. Copper of that net is left out of
  `copper.hole-clearance`, as for a plated hole. An unplated pad without a net keeps today's behaviour: all
  copper near it is judged.
- A `hole_clearance` rule whose condition selects same-net pairs still applies, so a design can ask for
  the check. Task 1.1 records whether the KiCad and Altium rule languages can say this, from public
  sources.
- Task 1.1 also checks with `kicad-cli` that KiCad's DRC gives no `hole_clearance` for an NPTH pad with a
  net beside copper of that net. If KiCad does report it, the KiCad rules view keeps today's verdict and only
  Altium documents change.

## Impact

- `src/fenolite/checks/copper.py` (`_holes`, `_hole_clearance_findings`).
- `openspec/specs/copper-check/spec.md`, requirement "Copper against drilled holes".
- `docs/formats/kicad/rules.md` and `docs/formats/altium/pcb-copper.md`: one fact row each on the net scope
  of the hole clearance.
