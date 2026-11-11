# Design: c0479-altium-project-settings-carried

## D1: What is carried
`prjpcb.carried_settings(data)` reads a source `.PrjPcb` with `read.ini.parse_ini` and returns its settings
as INI text (`\n` line ends): every section in file order except `Document<n>` and
`GeneratedDocument<n>` (the written project lists its own documents), and `[Design]` without `Version`
(the writer writes its own). A project with nothing else carries `""`.

## D2: Where it rides
The root sheet's carrier fields already hold the reserved key `drawn_read.TOPS_KEY` (`"project"`); the
settings go to its field `PRJPCB` (`drawn_read.PROJECT_FIELD`). `convert.schematic.drawing_of` reads them
from the source project (`SourceDrawing.project`), and the KiCad conversion adds them to the root sheet's
carrier. The import's `schematic.toml` footer (`sheet_carrier.toml_footer`), `from_toml_text`,
`put_drawing` and `carried_fields` pass carrier fields through unchanged, so no other reader changes.

`backends.altium.drawn.lower_drawn` takes the field from the root sheet's fields into
`ProjectSheets.project` and leaves it out of the sheet fields it styles with, so a root sheet that carried
nothing else keeps its bytes.

## D3: How it is merged
`write_prjpcb(..., carried="")` writes its lines as before, then:
- `[Design]`: each carried key replaces the written key of that name in place; a carried key the writer
  did not write follows the written keys, in carried order.
- The carried sections of a family the writer writes (the name without trailing digits: `Parameter`,
  `PrjClassGen`) take the place of the first written section of that family, and the other written
  sections of the family are left out, so the source's numbering stays whole and a carried section equal
  to the written one keeps the bytes. Every other carried section comes last, in carried order.
- The encoding rule is unchanged: 7-bit ASCII, else UTF-8 with a byte-order mark.

## D4: Variants name the written components
A `[ProjectVariant<n>]` lists `Variation<k>=Designator=<ref>|UniqueId=\<sheet symbol ids>\<component id>|...`.
`lower_drawn` computes `sheet_links` for every drawn plan (before, a conversion only) and keeps each
component's written path in `ProjectSheets.paths`; `prjpcb.retarget_variants` sets each variation's
`UniqueId` to the path of its designator, and a designator without one keeps its id. The links that the
board uses stay those of a conversion only, so a build's PCB document keeps its bytes.

## D5: Net labels of an Altium source
`drawn.written_kind(label, ports, powers, native=...)` holds the rule of c0470 that `_Sheet.drawing`
applied inline; `native` is true when the sheet's carrier holds `label_at:local:<x>,<y>` for the label,
which `drawn_read` records for each net label of an Altium source. Such a label keeps its kind. A label
of a KiCad source keeps the rule of c0470.

`project.write_project` passes `planned_sheets.project` when it writes from a drawn plan. Without
carried settings the bytes do not change.
