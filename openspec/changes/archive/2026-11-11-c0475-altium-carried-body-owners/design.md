# Design: c0475-altium-carried-body-owners

## Context
`schdoc.component_records(placed)` builds one component's record template with a private writer whose
`add` numbers records from 0, "so children can name their owner": the component itself is position 0,
and the footprint chain's owners are template positions (`RECORD=45` names the position of the
`RECORD=44`, `RECORD=46`/`48` the position of the 45, the `RECORD=47` maps the position of the 46).
`drawn.component` writes that template into the sheet with a second writer whose `add` numbers records
in the sheet's index space, so it patches every template `OWNERINDEX` with one fixed offset
(`offset = len(self.records) + 1`, the index the component record itself will take).

## Root cause
With a carried body (change c0473), the template's own body records (`RECORD` 6, 7, 8, 13, 14) are
skipped and the carrier's `RECORDS` lines are written instead, right after the component record. The
fixed offset is right for the component (every child whose template owner is 0), but the chain owners
name template positions **past the body**, where the written block now holds a different number of
records. The chain can consequently name a parameter or other unrelated record instead of the
implementation list. An Altium compiler warning about a missing footprint was reported for affected
components. The original reported project was unavailable for the follow-up.

## Decision
Resolve owners through a position map, not an offset: `drawn.component` walks the template with
`enumerate`, and for every record it writes remembers `{template position: live index}` (the `add`
return). An `OWNERINDEX` of any value resolves through that map — 0 through the component's entry,
which equals the old offset — and an owner that no written record provides raises `FormatError`
("the component template names unwritten owner N"), since a forward or dangling owner would
silently corrupt the document exactly like this defect. The carried gfx loop keeps replacing `@0`
with the component's own index (`offset`), which the map also holds as position 0's value.

Sheets without a carried body write the same bytes as before: without skips or extra records the
written indexes equal the template positions plus the offset, which is what the old arithmetic
computed.

## Alternatives rejected
- Adding the carried-body delta (`carried_count - skipped_count`) to owner indexes past the body:
  correct only while the chain is the sole owner past the body and the skip set stays closed; the map
  needs no rule about which owners shift.
- Writing the chain with live `add` returns outside the template loop: duplicates the chain layout in
  two places (`schdoc.component` and `drawn.component`) and diverges from the template again.
- Refusing carried bodies whose record count differs from the template's body: loses the drawing the
  source document holds, the exact thing c0473 restores.

## Consequences
- The footprint chain of a component with a carried body names the records actually written. The
  matched authored reference and carried-body control have identical Altium compiler diagnostics
  and native pin and net exports (S-2299). Restoring the old offsets in an authored negative control
  reproduces the missing-footprint warning without changing the pin and net exports (S-2305).
- The map covers the `RECORD=47` pin-map owners too (they name the 46 past the body, same shift).
- A template that ever names a forward or skipped owner fails loudly at build time.
