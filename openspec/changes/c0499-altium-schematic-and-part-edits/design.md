# Design: c0499

The schematic session edits the `FileHeader` frames of a binary sheet (`schematic._Sheet`). The PCB session
edits a `State` (`edit.state`). Both queue operations behind gates and commit through the same gates:
read back, the net-signature or connectivity guard, and an atomic write. This change adds operations to
both sessions and keeps those rules. It adds no new session kind and no project session.

## D1 A part copied into a sheet (`add_part`)

`SchematicSession.add_part(from_doc, designator, *, new_designator=None, at=None)` copies the part
`designator` of the binary sheet `from_doc` (a path or bytes; the same sheet is allowed). The part's records
are `schematic._owned(sheet, root)`: the component record and every record it owns, binary pins included.
They are appended at the end of the sheet in their order. Each `OWNERINDEX` is renumbered to the new index
of its owner. The header's `WEIGHT` becomes the new count, as `delete` already sets it. `at` moves the part
by whole 10-mil units, with the same key rule as `move` (`_LOCATION`, `_shift_pin`). Each record that holds
`UNIQUEID` gets a new one from `ops.new_id`, unique in the sheet. The designator record (34) gets
`new_designator`, or `designator` with its number replaced by `?` when none is given. A sheet already holding
`new_designator` refuses with `altium.edit.assertion`.

The copied part keeps its library link (`LIBREFERENCE`, `SOURCELIBRARYNAME`, the implementation records
44 to 48). A SchLib source is out of scope: its symbols are storages of another layout
(`schematic-library.md`), and Altium's own "place from library" is the user's route there.

Alternative rejected: a part built from Fenolite's symbol model through `schdoc.component_records`. It would
lose the source's graphics, parameters and implementation records, and Update PCB would then propose a
footprint change.

## D2 Annotation (`annotate`)

`annotate(part, designator, *, old)` sets the `TEXT` of the part's record 34, stating the old text, as
`set_property` does for a parameter. It refuses with `altium.edit.assertion` when another part of the sheet
holds `designator`. When the session was opened with `project=`, it also refuses when another part of any
sheet of the project holds it. The project's sheets are read with `read.sch.read_schematic` through the
document list of the project file (`prjpcb.documents_of`). A repeated sheet (`Repeat(...)`) is out of scope: its designators get a channel
suffix (`pcb-read.md`), and `annotate` refuses a part on such a sheet.

The net-signature guard does not see a rename. A part's pins are keyed by `(designator, pin)`, so `annotate`
changes the signature. `annotate` declares its own part's rename: the guard compares the signature with the
old designator mapped to the new one. No `declare_connectivity()` is needed for an annotation alone.

## D3 Wires, net labels and power ports

- `add_wire(points)`: two or more points, each in nanometres and a whole number of 10-mil units. Record 27
  with `LOCATIONCOUNT`, `X<n>`, `Y<n>`.
- `add_net_label(text, at, *, orientation=0)`: record 25.
- `add_power_port(text, at, *, orientation=0, style=None)`: record 17. `style=None` takes the style of the
  template.

Template, in order: a record of the same `RECORD` in the sheet (for a power port, one of the same `TEXT`
first), so its colour, font and line width match the sheet. With no template, the record is
`schdoc.py`'s written form, the form Fenolite's own builds write (`schematic-records.md`, "What the writer sets").
Only the location keys, `TEXT`, `ORIENTATION`, `STYLE` and a new `UNIQUEID` (where the template holds the
key) change. `_FRAC` keys are dropped from the clone because every new point is a whole unit.

A new wire end that lies inside a segment of another wire (not at its end) needs a junction for Altium to
join them. The session appends a record 29 cloned in the same way. Its row is
`H-A-EDIT-SCH-ADD`. The joint is checked by Fenolite's own connectivity (`adapter.connectivity.local_nets`),
which the net-signature guard already runs.

Wires and labels change the net signature on purpose: a session that adds them calls
`declare_connectivity()`, as today. A narrower declaration (by net name) is skipped: the schematic guard
has no net names before the compile.

## D4 Link a PCB component to its part (`link`)

`Session.link(component, *, project, part, sheet=None)`:

1. Read the project (`adapter.project`, the same reader as `fenolite import`). Its circuit builder
   (`adapter.circuit`) already maps each unique-id path to its component (`by_path`). Invert it and find the
   one part named `part`, on `sheet` when given. Zero or two matches refuse with `altium.edit.assertion`.
2. Set, in `Components6`, `SOURCEUNIQUEID` to that path, `SOURCEHIERARCHICALPATH` (empty on a flat project,
   `<top stem>\<sheet symbol designator>…` below, `pcb-document.md` rows `H-A-SCH-HIER-ECO`),
   `SOURCEDESIGNATOR`, `SOURCELIBREFERENCE` and `SOURCECOMPONENTLIBRARY` from the part.
   `CHANNELOFFSET` becomes one more than the largest of the components of the same hierarchical path.
3. When `Classes6` holds the component class of the part's sheet (the class named after the sheet symbol,
   `H-A-SCHX-ECO`), add the designator to its members. Without such a class nothing is added: the board
   was not made with sheet classes.
4. Refuse with `altium.edit.assertion` when the part's current footprint model (record 45 `MODELNAME`)
   differs from the component's `PATTERN`, or the part's `Comment` from the component's comment text.
   Update PCB would propose those changes. The refusal names both values.

The link is a separate operation, not a keyword of `add_component`: a component already on the board
(re-linked after a schematic copy) needs it too.

Not done: nets. `add_component(nets=...)` already refuses a net the document lacks. A new net that the
schematic adds needs a new `Nets6` record. That is a separate operation (named as an open question), and
Update PCB adds it when the user runs it.

## D5 Body and region forms (`_same_form`)

`_same_form` today compares `len(first subrecord)`. That length is fixed for tracks, arcs, vias, pads,
texts and fills, where it tells the saved short and long forms apart (`records.LONG_LAYER`). For
`Regions6`, `ShapeBasedRegions6`, `ComponentBodies6` and `ShapeBasedComponentBodies6` the subrecord is the
18-byte head, the property text and the outline (`pcb-bodies.md`, "Record"). Its length tells nothing
about the form.

For those four storages the form becomes: the 18-byte head is framed the same (layer byte, constants at
offsets 1 to 6 and 9 to 17), the text length at offset 18 is consistent, and the outline has the vertex size
of its storage (16 or 37 bytes). The key set of the property text is not part of the form. A body of an
older key set is copied as it is, and Altium writes its own form at the next save. This is
`H-A-EDIT-ADD` extended by J34. The kit case must show that Altium 24.5 opens such a body, shows it and
saves it.

A body with `MODEL.MODELTYPE=1` names a `MODELID`. When the target lacks that entry in `Models/Data`,
`add_component` appends the source's entry and its model stream (`Models/<n>`), renumbered to the next
stream index. This is the "Index upkeep" requirement for model-store entries. An entry the target already
holds (same `ID`) is shared, not copied.

## Hypotheses registered by this change

| id | statement | to be confirmed by |
|---|---|---|
| `H-A-EDIT-SCH-ADD` | A part's records appended with renumbered `OWNERINDEX` and new `UNIQUEID`s, and wires, net labels, power ports and junctions cloned from records of the sheet, open, compile and save in Altium with the netlist Fenolite reads | J34 |
| `H-A-EDIT-LINK` | A component whose five source keys and sheet class are written from the part's unique-id path is matched by Update PCB with no change proposed | J34 |

Both are `INFERRED` until J34 runs on Altium Designer 24.5.2.23, the version the VM holds.

## Format evidence needed

- Kit case J34 (`docs/evidence/altium-edit.md`). The kit project gets a part copied from another sheet of
  the kit, annotated, wired with one wire to a pin, one net label and one power port. The PCB gets the same
  part through `add_component` from a kit board, with a body in an older key set, and `link`. The person
  opens the project in Altium. Compile reports no new message. Update PCB proposes no change. The body
  shows in 3D. Saving and reopening keeps every one.
- A census of body key sets in the corpus, before the code: how many documents hold bodies of two key
  sets, recorded in `pcb-bodies.md` as `CORPUS-VERIFIED` with counts only.

## Risks

- Altium may also want the new part in the sheet's `Room`. Rooms are rules whose scope is the sheet
  class (`pcb-document.md`, change-order row), so adding the class member covers it. J34 checks it.
- Copying an implementation record that names a footprint library absent from the project is legal in
  Altium (the footprint is already on the board), but Compile may warn about it. J34 reports it.
