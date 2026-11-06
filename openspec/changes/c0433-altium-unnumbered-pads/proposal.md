# c0433: unnumbered pads stay in their Altium component

## Why

A KiCad footprint can hold pads without a number, for example the exposed or mechanical copper pads of an IC
or the non-plated holes of a connector. Since c0160 the Altium writers took every such pad out of its
footprint: the PCB document wrote it as a free pad at its board position, the derived library left it out,
and the report counted it `changed`. The read-back footprint therefore misses those pads, and `equivalent`
gives `equiv.pad-missing` at level 3 for the footprint and `equiv.ref-ambiguous` at level 1 for the
anonymous footprints that the free pads become. A footprint with two such pads loses both from its
component, with no `lost` row to say so.

c0160 kept the pads apart because the public documentation (S-0302) only says that a *free* pad's
designator may be left empty, and its requirement asked for a public source before writing an empty
designator inside a component. The public corpus is that source: documents saved by Altium Designer hold
component pads whose name is empty, two of them in one component in two boards (S-0172, S-0200), and one
in each of six components in a third (S-0601).

## What

- The PCB document writes a pad without a number as a pad of its component with an empty designator, each
  pad its own record with its own net, so several in one footprint stay distinct (they are keyed by pad id,
  never by number).
- The derived library keeps such a pad in its footprint instead of leaving it out.
- The reason "the pad number is empty, so it is written as a free pad at its board position" is gone; a pad
  that a writer cannot hold is still counted `lost` under `pad` with its own reason.
- RT-A3 no longer needs its view of detached pads (c0168, c0171): the write detaches none, so the reading
  is compared with the model as it is.
- `docs/formats/altium/pcb-records.md` and `pcb-library.md` record the census of component pads without a
  name; `docs/evidence/conversion.md` and its census test follow the demo boards whose pads are no longer
  detached.

## Not in this change

- What Altium Designer does with a written component pad without a name (open, DRC, update from library) is
  not measured by the maintainer here; the census shows the form in documents Altium saved. A kit case can
  follow.
- The free pads that a design holds as footprints of their own (the import's reading of a free pad) and
  board holes are written as before.

## Impact

- Code: `backends/altium/lower.py`, `backends/altium/pcblib.py`, `backends/altium/rta3.py`.
- Specs: `altium-pcb-writer` ("Connector and free pads"), `design-conversion` ("Conversion report": its scenario now counts connector pads), `altium-verification` ("Detached hole pads in
  RT-A3" replaced by "Unnumbered pads in RT-A3").
- Docs: `docs/formats/altium/pcb-records.md`, `docs/formats/altium/pcb-library.md`,
  `docs/evidence/conversion.md`.
- Source ids S-1920 to S-1929 are not used: the census reads documents already declared.
