## Context

The DSL already holds every item a fit needs (`docs/dsl.md`):

- `design.board(outline=…)` takes a closed path of length pairs and `arc_to` steps; the frame has its origin
  at the top-left of the board and Y down (`docs/dsl.md`, "Frame and `BOARD_ORIGIN`").
- `design.hole(ref, x, y, *, drill, courtyard=None, locked=True)` makes a locked hole part in
  `Fenolite_Holes`; "an enclosure fixes a hole" is already its docstring.
- `design.rule_area(name, outline, *, layers, forbid=())`: a named area, or a keep-out with `forbid`
  (`footprints` included, c0113).
- `Part.place(…, locked=True, anchor=MechanicalIntent(…))` (c0096); by the maintainer's decision of
  2026-10-07 `hole()` and `rule_area()` carry no intent of their own.
- `design.height_limit` and `judge_heights` (c0140) judge parts under named areas by `outward_height`.
- Copper and role-copper intents are recorded by the script and resolved by the build.

The DSL may import only `model`, so it reads the derived `usable` and `zones` of c0307 as data and needs no
geometry.

## Goals / Non-Goals

**Goals**: one call that turns a box model into outline, holes, zones and face rules with existing items;
a fit record for c0309 and c0310; designs without a fit unchanged.

**Non-Goals**: judging (c0309), moving parts, height limits in `RuleSet.heights`, tilted or flipped boards.

## Decided

The six decided answers of c0306's `design.md` apply. Here in particular: the box is our own model
(CC0, provenance), never a vendor file; nothing needs a 3D kernel.

## Decisions

### 1. Today and proposed

Today a script copies numbers from a drawing by hand:

```python
design.board(outline=[(mm(0), mm(0)), (mm(110), mm(0)), (mm(110), mm(70)), (mm(0), mm(70))])
design.hole("H1", mm(10), mm(10), drill=mm(3.2), courtyard=mm(6))
design.rule_area("LID", [(mm(0), mm(0)), (mm(110), mm(0)), (mm(110), mm(70)), (mm(0), mm(70))])
design.height_limit("LID", max=mm(26))
```

Proposed:

```python
from fenolite.dsl import Aperture, Enclosure, mm

box = Enclosure.load(HERE / "boxes" / "fenolite-box-120x80x40.enclosure.json")
fit = design.fit(box, mount="bosses", at=(mm(60), mm(40)))
design.board(outline=fit.outline, copper=2)
fit.holes()  # H1..H4 at the bosses
fit.zones()  # enc.top.lid, enc.top.C1, enc.bottom.floor, enc.bottom.B1, …
fit.face(j1, "front", aperture=Aperture.rect(mm(9.4), mm(3.4), z=mm(1.7)), gap=mm(0.5))
fit.face(d1, "top", aperture=Aperture.circle(mm(3.2)))
fit.face(sw1, "top", aperture=Aperture.circle(mm(7), clearance=mm(0.3)))
```

### 2. `design.fit`

`design.fit(box, *, mount, at, rot=0) -> Fit`. `box` is an `Enclosure` (`Enclosure.load(path)` reads a file
with `load_enclosure`; a path object or text). `mount` names a mount option that has `usable` and `zones`
(else `DslError` "run `fenolite enclosure derive`"). `at` is the board-frame point of the box origin; `rot`
is 0, 90, 180 or 270. One fit per design (`DslError` on the second call).

Pose transform: a box point (x, y) goes to `at + (x', −y')`, where (x', y') is (x, y) turned by `rot`
counter-clockwise in the box's Y-up frame. Seen on screen the box turns counter-clockwise, the sense of a
footprint angle (`H-G-ROT-DIR`). With `rot=0` the `front` face is at the bottom of the board drawing.
`fit.to_board(x, y)` exposes the transform for the user's own items.

### 3. `fit.outline`

The usable ring of the mount, transformed, as a path of pairs with `arc_to` steps for its arcs. It is a
property: reading it changes nothing. A user who wants a smaller board writes their own outline; c0309
judges it against the usable area.

### 4. `fit.holes(prefix="H", pad=None)`

For each boss in name order: `design.hole(f"{prefix}{n}", x, y, drill=screw.drill, courtyard=screw.head +
2 × clearances.obstacle, pad=pad)` at the transformed boss centre, locked. The placement carries
`MechanicalIntent(key=f"enclosure/{box.id}/{mount}/{boss}", tolerance=<the larger tolerance of the boss's x
and y, else 0>, source=f"{box.id} {provenance.revision}", status=…)`, where `measured` and `local-step`
give `measured`, `datasheet` and `derived` give `estimated`, and `assumed` gives `proposed`. A `guides` or
`floor` mount has no bosses: `fit.holes()` then raises `DslError`.

### 5. `fit.zones()`

For each zone of the mount, `design.rule_area(f"enc.{side}.{zone}", ring, layers=("F.Cu",) or
("B.Cu",))`, the ring transformed (zones are polygons, c0307 decision 4). Its limit:

- top: `zone.z − (pcb_bottom_z + t) − clearances.lid`;
- bottom: `pcb_bottom_z − zone.z − clearances.floor`;

where `t` is the board thickness: the design's stack-up thickness when `stackup()` was called before,
else the mount's `thickness.max`, else 1.6 mm; its source is recorded (`stackup`, `mount`, `default`).
A zone whose limit is 0 or less gets `forbid=("footprints",)`: a real keep-out that `place`, the build's
guard and KiCad's DRC already judge. No `HeightLimit` is added: c0309's stage judges enclosure heights, so
`placement.rules` does not report the same part twice. Needs `board()` first, as `rule_area()` does.

### 6. `fit.face(part, face, *, aperture, gap=mm(1), protrude=0)`

Records a `FaceRule(part path, face, aperture, gap, protrude)`. `face` is one of the six. For a wall face,
`gap` is the largest allowed distance from the part's extent toward the wall to the wall's inner plane, and
`protrude` the largest allowed reach into the wall (a connector that sits in its opening). For `top` and
`bottom`, `gap` and `protrude` are unused and must stay at their defaults.

`Aperture` (frozen, `fenolite.dsl.aperture`, stored as `model.enclosure.ApertureShape`):

- `Aperture.rect(w, h, *, z=None, offset=0, radius=0, clearance=mm(0.2))`;
- `Aperture.circle(d, *, z=None, offset=0, clearance=mm(0.2))`;
- `Aperture.path(points, *, z=None, clearance=mm(0.2))`, a closed polygon in the face frame relative to
  the aperture centre.

For a wall the centre is at u = the part's position projected on the wall plus `offset`, and v =
`pcb_bottom_z + t + z` (`z` required). For `top` and `bottom` the centre is at the part's position (`z`
must be `None`), and `offset` is a `(du, dv)` pair. The opening drawn by c0310 is the shape grown by
`clearance`.

### 7. The fit record (`fenolite.enclosure-fit.v0`)

```json
{
  "schema": "fenolite.enclosure-fit.v0",
  "box": { "…": "the whole box document of c0307" },
  "box_sha256": "…",
  "mount": "bosses",
  "pose": {"x": 60000000, "y": 40000000, "rotation": 0},
  "thickness": {"value": 1600000, "source": "stackup"},
  "outline": true,
  "holes": [{"ref": "H1", "boss": "B1"}],
  "zones": [{"area": "enc.top.lid", "side": "top", "zone": "lid", "max": 26900000, "keepout": false}],
  "faces": [{"part": "J1", "face": "front", "aperture": {"shape": "rect", "w": 9400000, "h": 3400000,
             "z": 1700000, "offset": 0, "radius": 0, "clearance": 200000}, "gap": 500000, "protrude": 0}]
}
```

`dsl.fit_record(design) -> Fit | None` hands it over (as `dsl.heights` does). `fenolite build` writes it to
`.fenolite/enclosure.json` for both targets, beside the files of `dump_dir`, in the same plan; a design
without a fit writes none, and a rebuild after removing the call plans the file's removal. The box is
embedded so a check needs no other file and sees the box the board was designed for. `outline` says
whether the board outline equals `fit.outline`. The reader refuses a broken record with `FormatError`
(exit 3 `FEN-3009`, c0307).

### 8. Altium target

Outline, holes and areas are written as for any design. The footprint keep-outs are named in the existing
`altium.not-lowered` info of kind `keepout-footprints`. The fit record is written the same way.

## Hypotheses registered by this change

- `H-G-ENCL-POSE`: the pose transform maps each boss of the fixtures, for the four rotations, to the
  hand-computed board point, and `front` to the bottom of the drawing at `rot=0`.
- `H-K-ENCL-FIT-BUILD`: a board built with `fit` loads in 9.0.x and 10.0.x with no `invalid_outline`, and
  KiCad's DRC gives no violation type that the same board without `fit.holes()` and `fit.zones()` lacks,
  apart from the keep-outs' own intended findings.

## Evidence per behaviour

| behaviour | level |
|---|---|
| DSL records and pose | `INFERRED` (unit tests, `H-G-ENCL-POSE`) |
| KiCad board loads and DRC | `KICAD-VERIFIED` (9.0.x, 10.0.x, `H-K-ENCL-FIT-BUILD`) |
| Altium build | `INFERRED` (the existing writer; no new record) |

## Risks / Trade-offs

- **Arcs in the outline** from boss notches: the outline arcs of c0167 are supported by both writers.
- **Courtyard of a hole as head keep-out** covers only the top side; the bottom keep-out comes from the
  boss zone. Both sides are covered.
- **A stale box**: the record embeds the box, so a later edit of the box file does not change a built
  board until it is rebuilt; c0309 reports the digest it judged.

## Open Questions

1. Should `fit.zones()` also add `HeightLimit`s so `fenolite place` warns about heights? Recommended: no;
   c0309 adds the enclosure judge to the build's guard, and `place` gains it in a follow-up if asked.
2. Should `fit.holes()` take one drill per boss from the box or let the user override? Recommended: from
   the box, with `drill=` override applied to all.
3. Should `fenolite enclosure place` (c0306) gain `--box/--mount` here, using the record's pose?
   Recommended: yes, as a follow-up task once this lands.
4. Rotations other than multiples of 90°? Recommended: no; boxes are rectangular.

## Relation to the other changes

Reads c0307's model; writes the record that c0309 judges and c0310 draws. c0306's footprint can later take
its pose from the record.

## Size

About 6 design-days: `fit` and pose 1, outline and holes 1, zones and limits 1, faces and apertures 1,
record and build 1, KiCad probes, example and docs 1.
