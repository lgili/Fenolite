# c0386: place the copies of Altium embedded board arrays

## Why

c0374 reads each Embedded Board Array of a PCB document (`backends/altium/read/arrays.py`: referenced
document, location, rotation, mirror, counts, pitches, Link Location; S-1422, `INFERRED`) and names each
array in the conversion report, but it still refuses the loss: no saved file shows where Altium puts the
copies. Three facts are missing: the corner of the first copy with Link Location off (Altium's page says
the bottom-left point of the referenced board's objects, S-0790, not measured), the centre of a turned
array, and the axis of a mirrored one. c0374 task 2.2 moved here on 2026-11-04 because these could not be
proved by its deadline.

Evidence at hand: the Gerber and drill outputs that Altium Designer 24.5.2.23 made of `panel-a` in the
Part Q phase A run (S-1422, kept outside the repository) fix the plain case. The phase B run of the cases
Q7 to Q12 (c0173 task 7.4, agent runs of 2026-11-04) adds the Gerber and drill outputs of Fenolite's own
array (Q9) and Altium's dump of the copies' places; its Q12 save stores the array's location with the
document's 1000 mil offset (the user interface shows 0, 5 mm, the record 25.4, 30.4 mm), which the
reader's test checks.

## What Changes

- Measure the placement of the copies from Altium's own outputs of saved panels: the plain array first
  (`panel-a`), then the turned, mirrored and linked variants when their outputs exist. Record each fact
  in `docs/formats/altium/pcb-document.md`, "Embedded board arrays", with its source and label.
- Read each referenced document (the path relative to the panel document); a missing or unreadable
  document is named in the report.
- Place the copies' components, pads, copper and holes for each proved variant, keeping each copy's
  designators and nets apart, and lift the refusal for those variants only; an unproved variant stays
  the refused `embedded-board` loss of c0374.

## Impact

Altium PCB reader and adapter, conversion report, `docs/formats/altium/pcb-document.md`,
`docs/conversion.md`; no new public name until a variant is proved.
