# c0447: a free pad of an Altium board comes back from KiCad as a free pad

## Why

Altium DRC on the public PcbDoc taken Altium → KiCad → Altium (c0441 base, `origin/cac/lote-26`
e55b7cd5e; altium-rounds-2, AD 24.5.2.23; S-2060, S-2061) reports Board Outline Clearance where the
sources report none: NG6011 0 → 4, DM6010_R2M2E2 0 → 28. Both boards come back with two more components
(15 → 17, 12 → 14).

- **Two extra components.** Each board holds two free pads (one non-plated pad `A`, no component). The
  import reads a free pad as a footprint with no reference, no link and one pad, and the Altium writer
  writes that form as a free pad. The Altium → KiCad conversion gives every footprint a link into the
  project library, a free pad `<project>:FREE_<footprint id>`. Read back from KiCad, the footprint has a
  link, so the writer's free-pad test (`not fp.lib_ref`) fails and it writes a component with designator
  `''`, pattern `FREE_fp_…`, and its Designator and Comment texts at (-1000, -1000) mil, off the board:
  2 texts × 2 components = the 4 hits of NG6011 and 4 of the 28 of DM6010.
- **Silk across the edge (the other 24 of DM6010).** The silk tracks of DM6010 cross the board edge on the
  source as on the round trip (same geometry; c0441 level 7 finds no difference). The source has two Board
  Outline Clearance rules: priority 1, `not InNet('GND')`, 10 mil, with an object matrix whose five entries
  set text to the five edge kinds to 0; priority 2, `All`, 5.9055 mil. With these rules Altium reports no
  silk track. The conversion to KiCad keeps the priority-1 record for an Altium write only (`OBJECTCLEARANCES`
  not empty: "the rule does not map onto a KiCad rule"), and a KiCad file cannot hold it, so the round trip
  has the `All` rule alone, at priority 1, and Altium reports the 24 silk tracks against it. NG6011's
  priority-1 rule has no matrix and comes back (`BoardOutlineClearance_not_net_GND`). Which objects the
  text row exempts (text only, or every overlay primitive, or the matrix alone checked) is not measured:
  the mapping of such a matrix waits for that measurement and is not part of this change.

## What Changes

- The Altium → KiCad conversion names the link of a free pad's footprint with `libnames.FREE_PAD_PREFIX`
  (`FREE_`), as before.
- The Altium writer also writes as a free pad a footprint with no reference, one pad, and a link whose item
  name starts with `FREE_PAD_PREFIX` (`lower.converted_free_pad`), counted changed with
  `lower.FREE_PAD_REASON`; no component, no Designator and no Comment text.
- `pcb-copper.md` records the fate of a Board Outline Clearance record with an object matrix through a
  KiCad round trip and what Altium reports on DM6010 (INFERRED: agent run in the VM).

## Impact

- `core/libnames.py`, `convert/altium_to_kicad.py`, `backends/altium/lower.py`.
- Bytes: a KiCad → Altium write of a footprint linked `…:FREE_…` with no reference and one pad. A build of
  a script that names such a footprint without a reference writes a free pad, as it would without a link.
- The silk hits of DM6010 stay until the object matrix is measured (follow-up).
