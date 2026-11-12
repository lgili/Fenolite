# c0499: add a part to an existing Altium project through the edit sessions

Found on: adding two parts to an existing Altium project of a private two-layer power board on 2026-11-11
(codes only; nothing from the board is in this change).

## Why

Two new parts were added to an existing Altium project with
`fenolite.backends.altium.edit` (one `SchematicSession` on the sheet, one `Session` on the PCB document).
Three operations were missing, and each workaround used a private name:

- **F35, schematic.** `edit.schematic.SchematicSession` has `move`, `set_property` and `delete` only. It
  cannot copy a part in, annotate it, draw a wire, place a net label or place a power port. The script
  appended raw frames to `s.queued` and made new `UNIQUEID`s by hand.
- **F36, link.** Nothing links a PCB component to its schematic part. Altium's Design » Update PCB matches
  them by `SOURCEUNIQUEID` (`connectivity.md`, "Component link", `H-A-IMP-LINK`). A component added by
  `Session.add_component` keeps the link of its source board, which names a part of another project. The
  script used `set_property` on `SOURCEUNIQUEID` and `SOURCEHIERARCHICALPATH` with values it computed by
  hand from the sheet symbols.
- **F34, bodies.** `Session.add_component` refused the source's 3D bodies with `altium.edit.no-template`.
  `ops._same_form` compares the length of a record's first subrecord with the records of its kind and layer
  in the document. For a body (and a region) that subrecord holds the property text and the outline
  (`pcb-bodies.md`, "Record"), so its length differs between any two bodies. A body of an older key set
  never matches. The script monkeypatched `ops.component_primitives` with `ops._same_form` off.
  `add_component` also copies no `Models` entry, so a model body would name a model the document lacks
  (`H-A-INTEG-MODEL`).

## What Changes

- `SchematicSession` gains `add_part`, `annotate`, `add_wire`, `add_net_label` and `add_power_port`
  (design D1 to D3). New records are cloned from a record of the same kind in the sheet, or else in the
  form the schematic writer writes (`schdoc.py`), and get new `UNIQUEID`s from `ops.new_id`. A wire end that
  lies inside another wire gets a junction. The net-signature guard stays: a session that adds wires or
  labels declares it with `declare_connectivity()`.
- `edit.open(sheet, project=PRJPCB)` lets `annotate` refuse a designator that any sheet of the project
  holds.
- `Session` (PCB) gains `link(component, project=, part=)`. It writes the five source keys of the
  component from the part in the project's hierarchy, and adds the component to its sheet's component
  class when the document holds one (design D4). It refuses a link when the part's footprint or comment
  differs from the component's, because Update PCB would propose that change.
- `ops._same_form` compares the fixed head of a body or region record, not its whole length (design D5).
  `add_component` copies the `Models` entry and stream of a model body that the document lacks.
- New gates `annotate`, `add_part`, `create` (schematic) and `link` (PCB), all off, on new hypotheses
  `H-A-EDIT-SCH-ADD` and `H-A-EDIT-LINK`. Kit case J34: an authored project gets a new part in both
  documents, and Altium's Compile and Update PCB propose no change.

## Impact

- `src/fenolite/backends/altium/edit/schematic.py`, `edit/ops.py` (`link`, `_same_form`, `add_component`),
  `edit/session.py` (`OPERATIONS`, `ROWS`, `link`), `edit/__init__.py` (`open(..., project=)`).
- `docs/formats/altium/schematic-records.md` and `pcb-document.md` (written forms of the new records,
  the link), `docs/hypotheses.md` (two rows), `docs/evidence/altium-edit.md` (case J34).
- Agent guide page `altium.md`; `CHANGELOG.md`.
- No CLI change. No change to c0479 or c0483: those carry a project through a conversion, and this
  change edits the saved project in place.
