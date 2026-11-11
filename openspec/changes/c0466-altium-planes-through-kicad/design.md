# Design: c0466

## Context

- **KiCad.** A KiCad copper row has a type: `signal`, `power`, `mixed` or `jumper`. It may also have a user
  name (S-0038, INFERRED).
  - A `power` row loads on 9.0.9 and 10.0.6 and changes no check (`H-K-LAYER-POWER`, KICAD-VERIFIED,
    `board.md`, "Plane layers").
  - KiCad's own Altium import makes each plane of row `-01` a `power` row with the plane's name as its user
    name. It makes each Split Plane polygon an unfilled zone of its net (S-2201).
  - KiCad's file has no slot for a layer's net, so a plane's net, pull-back and splits must travel as a
    carried board property (`boardcarrier`, as c0450, c0463 and c0464 do).
- **The import.** It gives each copper layer an `altium` bag:
  - `layer_id` and `altium_name`;
  - `plane_net`, the `PLANE<k>NETNAME` text: a net name or `(Multiple Nets)`; a `(No Net)` plane has none;
  - `plane_cuts`.

  The import keeps the Split Plane polygons out of the model; c0461's `plane_losses` reads them from the
  source document.
- **The writer.**
  - `lower._stack` makes a layer an internal plane when its `plane_net` is a net of the design.
  - `pcbdoc.split_plane_records` writes one polygon per plane: the board outline on the plane's net.
  - `libboard._layer_fields` writes `PULLBACKDISTANCE=20mil` for every plane.
  - `docboard.board_text` names a layer only for mechanical ids (c0464).

## Decisions

### D1. Plane rows are `power` rows named after the plane

`altium_to_kicad.map_layers` gives each copper layer whose `layer_id` is 39 to 54 the row type `power`
(`layers.PLANE_ROW_TYPE`). When the plane's Altium name is a writable field, it also becomes the row's user
name, as KiCad's own import does (S-2201).

KiCad's items name copper by the row's canonical name (`In1.Cu`), so the user name renames nothing else.
Fenolite's equivalence pairs layers by user name only when a name is missing on one side
(`pairing.layer_aliases`).

### D2. The carrier `Fenolite.Altium.Planes`

The carrier is canonical JSON with schema `fenolite.altium-planes.v0`:
- `corner`: the low corner of the board's extent (`lower._extent`) in the frame of the KiCad target.
- `planes`: one entry per carried plane, in chain order, each with:
  - `layer`: the KiCad row;
  - `net`: the `plane_net` text;
  - `pullback`: nanometres;
  - `splits`: a list of `{net, points}`, each point `[x, y]` in nanometres, in the frame of the design.

The splits are the source's Split Plane polygons on the plane's layer, in `Polygons6` order. Each ring is
`arcring.record_outline`'s, which is exact for straight vertices.

The pull-back is the plane's `PLANE<k>PULLBACK`, else `20mil`.

A plane is carried only when all three hold:
- its net is a net of the design, or `(Multiple Nets)` with at least one split;
- each split's net index names a net of the design;
- no split holds an arc vertex.

A plane that is not carried keeps its `power` row and c0461's loss, and comes back as today.

### D3. The way back

`to_altium` reads the carrier (`altium_planes.read_carrier`), and `altium_planes.restore` checks each entry
against the KiCad design.
- **Restored.** The row still exists, is copper and is `power`, and the design holds every net the entry
  names. The layer's `altium` bag then takes `plane_net` again. `_stack` makes the layer a plane, numbered
  from 39 in stack order (`pcbrecords.copper_stack`).
- **Not restored.** Any other entry is counted lost under `plane`, with the reason. The layer is then
  written as a signal layer, as before this change.

The restored planes reach the writer as `write_design(planes=…)`, which passes to `PcbDocSpec`:
- `plane_splits`: by layer id, each split's net and points, moved by the board's translation, which is the
  current corner minus the carried one;
- `copper_names` (named `plane_names` until task 5.1): by layer id, the row's user name when it is a
  writable field; task 5.1 gives signal layers theirs too (D5);
- the pull-backs in `StackSpec.pullbacks`.

### D4. The writer

- **Polygons.** `split_plane_records` writes, for a plane with splits, one Split Plane polygon per split on
  the split's net, and for any other plane the outline polygon as before.
- **`(Multiple Nets)`.** `_stack` accepts it as a plane net when the plane has splits. `PLANE<k>NETNAME`
  then holds `(Multiple Nets)`.
- **Pull-back.** `_layer_fields` writes the plane's pull-back.
- **Name.** `board_text` replaces `Internal Plane <k>` by the plane's name, as c0464 does for mechanical
  layers.

### D5. Rules

The read-back holds the source's rule census. The ex-planes are no Mid-Layers once they come back, so
c0462's per-layer Width values make no rule for them. The test counts the read-back's `track_width` rules
against the source's.

## Risks

- **An edited board.** A board moved in KiCad moves its splits by the corner translation. A board reshaped
  in KiCad keeps the source's splits, which Altium clips with the outline.
- **The name.** The user name is what KiCad shows, so a rename in KiCad renames the plane in Altium.

### D5. Signal layer names (task 5.1)

The round trip of row `-04` wrote its inner signal layers `Internal Layer 1/2` as `Mid-Layer 1/2` (S-2191);
rows `-01` (`Component Side`, `Solder Side`) and `-07` (`Layer 1` to `Layer 4`) lost theirs the same way
(S-2254). KiCad's row user name is the slot: `copper_rows` (formerly `plane_rows`) gives a signal row its
Altium name when it differs from `written_name`, the name the writer gives that row anyway, so a board
whose names are Altium's defaults keeps bare rows. On the way back `lower._copper_names` reads the user name
of every copper row, not only of a converted board's: a KiCad board's own user names name its Altium
layers too, as its mechanical rows' names do (change c0412). A name a property record cannot hold, the
name of another Altium layer (`pcbrecords.LAYER_NAMES`) or one two layers take is left out, so no two
layers share a name. `docboard.board_text` replaces the default name in each key that holds it
(`LAYER<id>NAME`, `LAYER_V8_<k>NAME`, `V9_STACK_LAYER<k>_NAME`, `V9_CACHE_LAYER<k>_NAME`; S-2255).

KiCad names a row's Gerber file after its user name (S-2256): a converted board whose layers have their own
names plots `<board>-Internal Layer 1.g1` where it plotted `<board>-In1_Cu.g1`. The file function is
unchanged.

## Split boundaries

Altium 24.5.2.23 read the same split polygons, pad positions and Plane Connect rules on the two
public returns, but lost three native pad connections on the second plane. Adding the original
netless, unowned boundary tracks of row `-02` to a copy of its return restored both 3.3 V pads.
Adding only the tracks and arcs with polygon index 65534 did not. The plane carrier gains an
optional ordered `boundaries` list, each entry containing start, end and width in model nanometres.
It accepts positive-width, unflagged track records with no net, component or polygon, on a carried plane
with split polygons. The boundary positions follow the same board translation as split polygons.
Altium gets native boundary tracks on the restored plane, without a net or a polygon. The
pull-back strokes are outside this change. Older plane properties without boundaries still read.
