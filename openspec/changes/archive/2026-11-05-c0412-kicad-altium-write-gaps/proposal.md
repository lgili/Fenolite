# Close four gaps of the KiCad to Altium write

## Why

A conversion of a KiCad board to Altium (`convert --to altium`), and the Altium build of a design
(`build --target altium`), drop or refuse four kinds of item that a real board holds. The maintainer met
all four while rebuilding a board. The reports are descriptions only: every case in this change is
authored for Fenolite, and nothing from that board enters the repository.

- **B12 (fabrication).** A filled `gr_poly` on a copper layer, with or without a net, is not written:
  `copper-shape: a shape on a copper layer has no record written`. `FEN-7001` then refuses the write
  without `--allow-lossy`. The copper is part of the board that gets made.
- **B14.** Clearance rules scoped by a reference and an item kind (`ref & item(pad)`), by a disjunction
  of nets, by a class against the zones of other classes (`zone & ~netclass`), and by a pad-on-a-net
  composite are dropped as `scope-unsupported`. The Altium reader's closed scope grammar already reads
  `InComponent`, `IsPad`, `IsTrack`, `IsVia`, `Or` and `Not`; only the writer refuses them.
- **B13.** A `User.N` layer that came from an Altium mechanical layer is lost when the board's user
  layers do not fall on `User.1`..`User.8` (`the layer User.N has no layer in the document for a
  graphic`). Fenolite's own Altium to KiCad conversion keeps the Altium name (`Mech.13`) as the row's
  user name (`board.md`, "User layers for conversion"), and the writer ignores it.
- **B15.** `build --target altium` of a design from `import --to python` fails with `FEN-3004`, because
  the import pins each part's geometry with `footprint_definition`, which Altium builds refuse.

## What Changes

- **Copper shapes (B12).** A filled rectangle or polygon on a signal layer of the written stack is one
  region record on that layer, with the net index of its net in the common prefix (`pcb-read.md`,
  "Fields", the common prefix of the geometry subrecord of a region), in `Regions6` and
  `ShapeBasedRegions6`. A drawn copper line, arc, circle, rectangle or polygon outline becomes tracks and
  arcs of its width on that layer and net, as the copper records of `pcb-copper.md` hold them. A shape on
  a plane, a filled circle, and a shape that `graphic_problem` refuses stay a reported `copper-shape`
  loss. A fill record is not written: a saved fill is 46 or 50 bytes, and `docs/formats/altium` records
  no field after offset 37.
- **Rule scopes (B14).** `rulemap` writes every selector made of `net`, `netclass`, `ref` and `item_kind`
  leaves joined by `and`, `or` and `not`, provided `read.scope.parse_scope` reads the written query back
  as the same selector: `InComponent('R1') And IsPad`, `InNet('A') Or InNet('B')`,
  `InNetClass('HV') And (Not IsVia)`. The item kind `zone` is written as `InPolygon`. Altium's Object
  Type Checks page (new source S-1702) states that a clearance rule for a polygon pour names
  `InPolygon`, because clearance applies to the primitives of the pour. The reader's grammar gains
  `InPolygon` (and its alias `InPoly`) as `item_kind zone`. Globs, layer selectors, `area` and
  `diff_pair` leaves stay `scope-unsupported`.
- **Rule values (B14).** The value refusals stay as they are unless the record holds the rule exactly
  (design.md, "Rule values").
- **Mechanical user layers (B13).** A user layer whose KiCad user name is `Mech.<n>` or
  `Mechanical <n>` (n from 1 to 16) is written on Mechanical n, whatever its `User.<k>` number, and that
  name takes precedence over the fixed `KICAD_MECHANICAL` position. A user layer without such a name
  keeps the fixed map. A user layer above `User.8` without a name stays a reported loss: the 16
  mechanical layers of the record are all assigned.
- **Imported designs in an Altium build (B15).** The Altium build honours `footprint_definition`. The
  part's footprint is resolved and written from the definition (geometry and footprint name), as the
  KiCad build resolves it. A part whose written footprint name differs from its native footprint name
  gets one `altium.footprint-definition` info, because one Altium library cannot hold two geometries
  under one name. `FEN-3004` for this override is gone.

## Capabilities

### Modified Capabilities

- `altium-pcb-writer`: "Board graphics and keep-out records" (copper shapes), "Scoped rule records"
  (written scope forms), "Mechanical layers of KiCad drawings" (named user layers).
- `altium-project-reader`: "Closed scope grammar" (`InPolygon`).
- `native-footprint-identity`: "Optional definition override" (Altium builds honour it).

## Impact

- Code: `backends/altium/lower.py`, `pcbdoc.py`, `rulemap.py`, `read/scope.py`, `cli/cmd_build.py`,
  `lens/altium.py`.
- Docs: `docs/formats/altium/pcb-records.md` (copper regions and copper graphics),
  `docs/formats/altium/rule-file.md` (grammar row), `pcb-copper.md` (written scope forms),
  `docs/evidence/sources.md` (S-1702), `docs/altium.md`, CHANGELOG, agent guide.
- Byte-compatible for every board without copper graphics, rules of the new forms, or named user layers;
  `tests/data/build_bytes.json` is unchanged.
- Out of scope: the Altium import side (c0409, c0410, c0411).
