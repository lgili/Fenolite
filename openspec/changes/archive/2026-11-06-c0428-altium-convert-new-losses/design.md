# c0428 design

## Decision 1: Arrays turned by 180 or 270 degrees (INFERRED)

S-1592 measured one thing: `ROTATION` 90 turns the whole array a quarter turn counter-clockwise about
(`X`, `Y`). For 180 and 270, `convert.arrays` applies that quarter turn two or three times.

- **Why not refuse them.** Altium's own rotation model is a single angle about the array's location. A
  half turn that is not two quarter turns would contradict that model, and no public source says it
  differs.
- **Why only quarter turns.** Rectangle graphics, pads and copper keep their exact form only under quarter
  turns.
- **Report.** The rule is named in the reason ("inferred, not measured (change c0428)") until a kit case
  measures it.

## Decision 2: The reference point of a copy (INFERRED)

S-1592 could not tell origin from corner: its fixture board has both at one point. The rule chosen:

- Link Location on (`ORIGINMODE` 0): the origin. S-0790 says that with this option on the array starts
  from the embedded board's origin.
- Otherwise: the board shape's lower-left corner. S-0790 says that with the option off the array starts
  from the bottom-left point of the board. S-1592 rules out the bottom-left of its copper and silkscreen,
  which leaves the shape's corner.

When the two lie within 1 µm, nothing is reported. Otherwise the reason names the rule taken.

## Decision 3: Looking for a referenced document

The private sweep's missing documents were of three forms:

- stored relative to another folder of the project;
- stored with another letter case;
- stored as an absolute path on another machine.

The lookup tries, in order:

1. the path relative to the panel;
2. the path relative to the project's folder;
3. the file name, in either folder;
4. the absolute path as stored.

It uses the project reader's case-insensitive `locate`. The first hit is read. An absolute path is named
by its file name only, so no machine path reaches a report.

## Decision 4: What a copy carries

A copy is the referenced board's design, moved rigidly. Three of its parts are completed before the move:

- **Zones.** Zones whose outline holds arc vertices are completed from the referenced document's
  `Polygons6` records, as the board's own zones already are (`arc_outlines`, shared with
  `zone_outlines`).
- **Models.** A copy's model placement is computed in the frame of the original footprint, with the
  referenced document's model and body records, keyed by the body's provenance file. A rigid move changes
  no model offset or rotation relative to its footprint.
- **Cut-outs.** Closed `Edge.Cuts` polygons are kept. The other `Edge.Cuts` items are not: the panel's
  outline replaces the board's.

The writer numbers its merged cut-out groups over all rings, copies included, so their `cutout/<k>` ids
do not name the source's rings. The ring check therefore explains a source cut-out that a free written
ring encloses, when copies carry cut-outs.

## Decision 5: Duplicate designators

The schematic generator resolves components by id from `design.circuit`. So the renaming is applied to
the circuit's components and to the parts alike:

- The part placed on the board keeps the designator, so the board and the schematic still pair.
- The others take `<ref>_<n>`, with the smallest free `n` from 2.
- The renaming runs after the board is written. It is applied to the design that the conversion
  verifies, so the read-back of the schematic finds the new designators.
- Two parts on the board that share a designator cannot be renamed without changing the board. The
  generator refuses two parts with one key, so the schematic stays a loss there, with its own reason.

## Decision 6: Predefined special strings (S-1871, S-1870)

Only strings with the same meaning in KiCad are mapped:

| Altium (S-1871) | KiCad (S-1870, 9.0 and 10.0) |
|---|---|
| `.Layer_Name` | `${LAYER}` |
| `.Pcb_File_Name` | `${FILEPATH}` |
| `.Pcb_File_Name_No_Path` | `${FILENAME}` |
| `.Print_Date` | `${CURRENT_DATE}` |

- `.Print_Date` is the date of the print. `${CURRENT_DATE}` is today's date, which is the date of a plot
  made today.
- `.Print_Time` has no KiCad variable of that meaning. `CURRENT_TIME_HH_MM_SS` (10.0 only) has another
  format.
- Matching ignores letter case, as Altium's list writes the names in mixed case.
- A board document read alone finds its project's parameters as a project read does. The project is the
  one `.PrjPcb` that lists the document, at most three folders up.
