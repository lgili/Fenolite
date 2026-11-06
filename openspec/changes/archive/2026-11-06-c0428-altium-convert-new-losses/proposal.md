# c0428: the new losses of an Altium conversion to KiCad

## Why

The reference sweep of 53 private cases on `5ab9d645` (descriptions only; no board data enters the
repository) found new `lost` kinds in `convert --to kicad`:

- **embedded-board**, 17 arrays in 16 cases:
  - 6 arrays whose referenced board's origin is not at its shape's lower-left corner;
  - 6 arrays whose referenced document is not at its path relative to the panel;
  - 4 arrays turned by 180 or 270 degrees.
- **zone**, 464 zones in 5 cases: the zones of an array's copies whose outline has arc vertices. The
  conversion reads the record's arcs for the board's own zones, not for the copies'.
- **model**, 5 cases: "the body names a model that the document does not embed".
- **graphic**, 1 case: an item on a drill drawing layer, which has no KiCad row.
- **schematic**, 5 cases: "the imported circuit has duplicate designators" drops the whole schematic.
- **text**, 182 changes in 24 cases: special strings that name no project parameter are written as typed.
  Some name an Altium predefined string that has a KiCad text variable of the same meaning. In others the
  board document was converted alone, so its project's parameters were not read.

## What

- **Arrays.**
  - Turn an array by 180 or 270 degrees with the measured quarter turn applied twice or three times.
  - Place the copies of a board whose origin is away from its shape's corner:
    - with Link Location to Embedded Board Origin on (`ORIGINMODE` 0), by the origin;
    - otherwise, by the shape's lower-left corner.
  - Both rules are INFERRED. The report names each one ("inferred, not measured").
  - Mirrored arrays and angles that are not multiples of 90 degrees stay refused.
- **Referenced documents.** Look for a document that is not at its relative path:
  - relative to the project's folder;
  - by its file name, beside the panel or in the project's folder;
  - at the absolute path that the array stores.

  The report names how each document was found. An absolute path is still named by its file name only.
- **Copies' contents.**
  - Copies take their zones' arc outlines from the referenced document's `Polygons6` records.
  - Copies take their models' placement from the referenced document's model records, in the original
    footprint's frame.
  - Copies carry the referenced board's cut-outs.
  - The ring check explains the copies' cut-outs, and the panel's own cut-outs that the written board
    merged with them.
- **Zones without area.** On the import side, the 13 `zone-outline` items of the sweep come from
  `Polygons6` records whose vertices coincide: they hold no arc, so there is nothing to rebuild. The
  import keeps them as outlines of 1 or 2 points, which the conversion used to write unchanged and
  unreported. It now rebuilds every outline under 3 points from its record. A record that encloses no
  area pours no copper, so the zone is left out as a `changed` zone with its own reason (`ZONE_NO_AREA`),
  not a loss: those conversions and imports need no `--allow-lossy` for it. `import --to
  python` already gets the rebuilt arc rings through the conversion, so one reconstruction (`_arc_ring`)
  serves both sides.
- **Drill layers.** `Altium.DrillGuide` and `Altium.DrillDrawing` take KiCad user rows after the
  mechanical layers.
- **Duplicate designators.**
  - The part on the board keeps its designator. Each other part with the same designator is written
    `<ref>_<n>`, as a `schematic` change.
  - The schematic is no longer dropped, unless several parts on the board share the designator.
- **Special strings.**
  - `.Layer_Name`, `.Pcb_File_Name`, `.Pcb_File_Name_No_Path` and `.Print_Date` (S-1871) are written as
    `${LAYER}`, `${FILEPATH}`, `${FILENAME}` and `${CURRENT_DATE}` (S-1870), in any letter case, as `text`
    changes. A project parameter of the same name wins.
  - A board document converted alone takes the parameters of the project that lists it. That project is
    searched up to three folders up; the board's own parameters win.
- **Models that the document does not embed.** No new code: c0423 generates each such body's model from
  the body record. The sweep ran before c0423. On the five cases this change smoke-tests, the `model`
  row has no loss.

## Not in this change

- **Not measured.** Altium's placement of a 180° or 270° array, and of a board whose origin is off its
  corner, linked or not. A maintainer kit case is needed (Part Q: turned 180 and 270, origin off the
  corner, linked and unlinked).
- **Still refused.** Mirrored arrays. Arrays whose document is missing on disk: 6 in the sweep are absent
  from the snapshot itself.
- **Still written as typed.** Predefined strings without a KiCad variable of the same meaning, among them
  `.Board_Name`, which Altium's list (S-1871) does not hold.

## Capabilities

- `design-conversion`:
  - MODIFIED "Copies of an embedded board array are placed only where measured";
  - MODIFIED "Project parameters and special strings";
  - MODIFIED "Layers of a converted Altium board";
  - ADDED "Contents of an embedded board array's copies";
  - ADDED "Zones without an outline of a converted Altium board";
  - ADDED "Duplicate designators of a converted Altium project".
