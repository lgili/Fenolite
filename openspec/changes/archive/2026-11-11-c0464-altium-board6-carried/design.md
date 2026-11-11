# Design: c0464

## What the rows hold

Census of the public rows `-01` to `-08` with Fenolite's reader (S-2231):

| key | rows |
|---|---|
| `DISPLAYUNIT` 0 (metric) | `-02`, `-04`, `-06`, `-07`, `-08` |
| `DISPLAYUNIT` 1 (imperial) | `-01`, `-03`, `-05` |
| mechanical layers named other than `Mechanical <n>` | `-04` to `-08` |
| `HASHKEY<k>`/`HASHVALUE<k>` | all eight |
| `SITUSSTRATEGY*` | one row |
| `ROUTELASTVIA.TEMPLATE.*` | three rows |
| grids beside `GR0` | none |
| guides (`GU<k>_*`) | `-04` |

The record has 27 lines, and the writer's lines follow Altium's one for one. Keys that a record holds
twice: `RECORD` (each line from the second), the seven keys that open a property record (`SELECTION`,
`LAYER`, `LOCKED`, `POLYGONOUTLINE`, `USERROUTED`, `UNIONINDEX`, and `KEEPOUT` when present) and
`SPLITLINECOUNT`.

## Owned keys

`docboard.OWNED_KEY` names the keys the writer decides. They are never taken from the source:

| group | keys |
|---|---|
| identity | `FILENAME`, `KIND`, `VERSION`, `DATE`, `TIME`, `UNIQUEID` |
| keys held twice | `RECORD`, the seven opening keys, `PRIMITIVELOCK`, `SPLITLINECOUNT` |
| frame | `ORIGINX`, `ORIGINY`; the outline (`KIND<k>`, `VX`, `VY`, `CX`, `CY`, `SA`, `EA`, `R`); `SHEETX`, `SHEETY`, `SHEETWIDTH`, `SHEETHEIGHT`; `LOOKAT.*`, `EYEROTATION.*`, `ZOOMMULT`, `VIEWSIZE.*`, `VP.*`; `GR<k>_OX`, `GR<k>_OY`; `GU<k>_*`; `PLACEMARKERX/Y<k>`; `MOVIE*`, `3DMOVIESCOUNT`, `CURRENT3DMOVIEID` |
| stack | `LAYER<n>*`, `LAYERV<v>_*`, `LAYER_V<v>_*`, `LAYERMASTERSTACK_*`, `LAYERSUBSTACK_*`, `LAYERPAIR<k>*`, `LAYERSET*`, `LAYERSTACKSTYLE`, `LAYERCOUNT`, `V<v>_*` (stacks, caches, impedance profiles), `MECHPAIR*`, `PLANE<k>*`, `TOP/BOTTOM` `CONST`/`HEIGHT`/`MATERIAL`/`TYPE`, `SHOWTOP/BOTTOMDIELECTRIC` |
| layer-bound | `ROUTINGDIRECTION*`, `MIDLAYER<k>_MRLASTWIDTH`, `TOGGLELAYERS` |
| xSignals | `PINPAIR*` (c0461's `Board6.PinPairs`) |

The frame group is owned because the way back may move the board in Altium's frame (c0459). The stack
group is owned because the writer makes the stack again from the model, with its own ids.

Every other key is a setting: units, grids and snaps, electrical grid, object snapping, the board
polygon's pour settings, drill symbols, the hole-shape hash table (`HOLESHAPEHASHSIZE`, `HASHKEY`,
`HASHVALUE`), teardrop parameters, Situs strategy, last via and width, 2D and 3D view configurations,
selection memories, classifier fields.

## The carrier

`Board6.Settings` is a storage value like c0461's `Board6.PinPairs`: a count, then `|KEY=value` text. A run
of settings that follow each other in the source opens with `|@=<key>`, the source key before the run
(`@` is no Altium key). The names of mechanical layers 1 to 16 (`LAYER57NAME` … `LAYER72NAME`) are added
as fields; they are owned, so the merge skips them.

## The merge

`docboard.with_settings(lines, settings)` walks the carried fields in order:
- `@=<key>`: the anchor moves to `<key>` when the writer wrote it once; otherwise it stays.
- an owned key, or one the written record holds twice: skipped.
- a key the writer wrote once: its value becomes the source's; the anchor moves to it.
- any other key: inserted after the anchor, on the anchor's line; the anchor moves to it. With no anchor
  yet it goes at the end of the first line.

Keys keep their source line because each run's anchor is on that line. A key the writer writes and the
source lacks keeps the writer's value (KiCad-born settings, such as the writer's teardrop keys, stay).

## Solder mask colour

No `Board6` key names the mask colour. The 3D view configuration (`3DCONFIGURATION`, a backquote-separated
list) holds `CFG3D.TOPSOLDERMASKCOLOR` and `CFG3D.BOTSOLDERMASKCOLOR` (BGR integers; row `-05`: 0, black)
and their opacities. It is a setting, so the source's configuration comes back whole: the round trip of
row `-05` gives its 2D and 3D configurations back unchanged (S-2231).

## Mechanical names

The import names a mechanical layer `Mech.<n>`. The conversion to KiCad compacts the used ones onto
`User.1`, `User.2`, … with KiCad user name `Mech.<n>`, and the way back puts the layer named `Mech.<n>`
on Mechanical n again (c0412). The ids were right; the names were not: `pcbdoc` named each mechanical id
after the KiCad layer that reached it.

The spec gains `named_layers`: the mechanical ids that a KiCad user name `Mech.<n>` or `Mechanical <n>`
placed (`lower.named_mechanical`). A mechanical id takes the source's name when the id is in
`named_layers`, or when no written primitive lies on it. An id that a KiCad layer of the fixed map reaches
and that holds primitives keeps the KiCad name: it is not the source's layer.

## Empty slots

The maintainer's flow A (S-2235) and public rows `-02`, `-04` and `-06` (S-2236) gave back mechanical slots
that nothing lies on with another name or flag:

- the writer enables Mechanical 13 to 16 always and 1 to 12 when used, so an unused enabled slot came back
  disabled (rows `-04` slots 3 and 5, `-06` slot 12);
- a drawing on Altium's drill drawing layer goes to the KiCad row `Altium.DrillDrawing` (c0428), and the
  way back mapped that row by the fixed map to Mechanical 8, which then took the KiCad name `User.8` and was
  enabled (row `-02`);
- a body on a mechanical layer above 16 comes back on the writer's body layer, Mechanical 13 or 14, and its
  slot took the KiCad name of that id (row `-06` slot 14: `B.Fab` for `Bottom Courtyard`).

The carrier also holds `LAYER57MECHENABLED` … `LAYER72MECHENABLED`. The writer enables a mechanical layer
that something of the written document lies on and gives every other one the source's flag
(`pcbdoc._mechanical_enabled`, through `docboard.board_records` into the legacy keys, the stack lists and
the layer sets). A slot takes the source's name unless a primitive lies on it: a body on a layer the writer
chose does not make it the KiCad layer's. `lower.drill_rows` sends the rows named `Altium.DrillDrawing` and
`Altium.DrillGuide` back to layers 73 and 55. The body's own layer above Mechanical 16 is not carried here.

## Evidence

The public kit confirms metric units, mechanical names and flags on row `-04`, native superclass
recreation on rows `-04` and `-05`, and the black mask in row `-05`'s native 3D view (S-2292, S-2294).

The acceptance control for the unavailable S-2235 board uses authored settings and two drill tracks.
The historical writer maps the tracks to mechanical slots 3 and 4, renames both and enables them.
It also disables two unused slots whose source enables them. This recreates the historical two-name,
four-flag regression at `332b79837`. The corrected return keeps all sixteen slots, the metric display
and both drill tracks through native open, Save As and reopen (S-2297).
