# Design: c0461

## What the public rows hold

| storage | `-01` | `-04` | `-07` |
|---|---|---|---|
| `Classes6`, no net class, no super class | 28 (27 of kind 1, `Cell` of kind 5) | 6 (kind 1) | 6 (5 of kind 1, `USB3` of kind 6) |
| `SignalClasses`, no super class | 0 | 5 (kind 10) | 5 (kind 10) |
| `Board6` xSignals (`PINPAIRNAME<k>`) | 0 | 10 | 12 |
| `DifferentialPairs6` | 0 | 0 | 5 |

Sources: S-2204, read with Fenolite's own reader.

- A kind-5 member names a component class. A kind-6 member names a differential pair (`NAME` of a
  `DifferentialPairs6` record). A kind-10 member names an xSignal.
- The xSignal keys sit on the last line of `Board6`, after `UNIQUEID`, where the writer puts
  `PINPAIRCOUNT=0`.

## Members are not mapped

The task was to map members. A member is a designator, a class name, a pair name or an xSignal name. A
conversion through KiCad changes none of these on the board:
- `distinct_designators` renames schematic components only;
- net names are kept.

The sources hold members and pins that name nothing on their boards (S-2204):
- `ACCESSORY` and `C?` in `-01`;
- pins of `D6`, `J10`, `U5` in `-04`;
- pins of `U1`, `J5` in `-07`.

Altium saved those documents, so it keeps such members. A first version dropped every member whose name the
written document lacked. It dropped all ten xSignals of `-04`. The members therefore travel byte for byte.

A differential pair is different: its record binds two nets. The writer keeps it only when both nets are
written. That rule is INFERRED; no row tests it. An xSignal whose text the `Board6` line cannot hold (a `|`
or a non-ASCII character) is dropped and counted, because `docboard.format_line` refuses it.

## Kind and name

`_kept_classes` skipped a kept class whose name any written class held, regardless of case. On `-01` the
net class `CELL` hid the class `Cell`. The key is now the pair of kind and casefolded name.

## The writer's own classes

KiCad always holds a `Default` net class, so the way back gave `Classes6` an empty `Default`. The writer also
gave its sheet classes (`component_class_records`). With the source's classes carried:
- the sheet classes are not written; the source's component classes stand for them;
- a net class without members is not written when no rule scope names it (`InNetClass('<name>')`).

Without carried classes, for example on a KiCad-born board, nothing changes.

## Split planes

Fenolite's import holds an internal plane as a copper layer with `plane_net` and `plane_cuts` in its
`altium` bag, and no zone. The conversion to KiCad writes that layer as a `signal` row with nothing on it,
and its report had no row. KiCad's import of `-01` (S-2201) gives:
- eight unfilled zones with their nets on two `power` rows;
- priority 34 on the six smaller regions.

Bringing them back would mean three steps:
1. make those zones in the import, which changes the import of every board with planes and the equivalence
   tests against KiCad;
2. type the layers `power`;
3. teach the Altium writer to write the zones of a plane with several nets as Split Plane polygons. Today
   `altium.plane-copper` refuses that for builds.

That is a change of its own. This change counts the planes lost instead:
- one `plane` item per Split Plane polygon on a plane of the chain (`<layer id>:polygon-<index>`);
- the plane layer itself when it holds none.

`plane` is a `refuse` kind, so the conversion asks for `--allow-lossy`. This is right: the KiCad board lacks
copper that the fabricated board has.
