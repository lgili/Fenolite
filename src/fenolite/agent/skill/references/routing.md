---
topic: routing
title: Routing: routers, scripted copper and zones
summary: Which router does what, route with --nets and --rip, what unrouted means, copper written in the script, zones and fill.
---

# Routing: routers, scripted copper and zones

Copper reaches a board in three ways: a router draws it (`fenolite route`), the script declares it
(`design.track`, `design.via`, `design.stitch`, `design.zone`), or a person draws it in KiCad. All three
live on one board. Router copper and hand-drawn copper are kept across builds; script copper is written
again from the script at every build.

## The routers

`fenolite capabilities --brief --json` lists them under `routers`, each with `available` and, when it is
not, the `reason`.

| router | what it is | use it for |
|---|---|---|
| `direct` | built in; one straight track between the two pads of a net; checks nothing | the starter, and boards whose placement makes every straight track legal |
| `freerouting` | an external autorouter: a jar that needs Java 25 or newer | a board that needs a real router |
| `kicadroutingtools` | an external router in a checkout of its own, named by `FENOLITE_KRT` | the same, where it is installed |

```fenolite-cmd
fenolite fetch freerouting --dry-run --json
fenolite fetch freerouting --confirm --json
```

`fetch` downloads the pinned Freerouting jar once and checks its SHA-256. It opens a connection only
with `--confirm`; `--from FILE` installs a copy you already have, checked the same way.
`FENOLITE_FREEROUTING_JAR` names a jar of your own instead.

## route

```fenolite-cmd
fenolite route blink/build --router direct --dry-run --json
fenolite route blink/build --router direct --confirm --json
fenolite route blink/build --router freerouting --nets "LED_*" --nets VIN --confirm --json
fenolite route blink/build --router direct --rip --confirm --json
fenolite route blink/build --router freerouting --require-complete --timeout 600 --confirm --json
fenolite net blink/build --json
fenolite net blink/build GND --json
```

- **Selection.** `route` takes every net that still has an open connection, also one that already
  holds copper. `--nets GLOB` (repeatable) narrows it. A net with a zone is skipped
  (`route.zone-net-skipped`, info) unless `--include-zone-nets` is given.
- **`--rip`** removes the tracks and vias of the selected nets first. Locked copper and script copper
  stay. Use it after you moved a part, or when old copper is in the way.
- **`result.unrouted`** lists the nets that still have an open connection after the run, and
  `result.open` those connections with their two ends. `routed` and `unrouted` are computed from the
  board, not from what the router says. An empty `unrouted` is not yet a proof: `fenolite check` is.
- **When nets stay open:** run `route` again (the copper of the first run is kept and the second run
  continues from it); give the router room with `fenolite place --move`; choose another router; or
  declare the copper of those nets in the script.
- **`--require-complete`** makes an open net an error: exit 5, `route.incomplete`, nothing written.
- **`--timeout SECONDS`** bounds the whole step. When it ends, the copper of the finished runs is
  written with `route.budget-exhausted` (warning); run `route` again to go on.
- **`fenolite net BOARD`** lists the nets; with a name it gives one net's pads, copper, vias, zones and
  its open connections. It runs no tool.
- A router that is not installed exits 6 (page `recovery`).

## Copper in the script

```fenolite-design
from fenolite.dsl import Design, Net, Part, arc_to, connect, mm, protect, via_step

design = Design("routed")
design.board(mm(30), mm(20))
design.rules.minimum(clearance=mm(0.2), track_width=mm(0.2), edge_clearance=mm(0.3))  # examples

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="LED")
design.add(j1, r1, d1)
vin, led_a, gnd = Net("VIN"), Net("LED_A"), Net("GND")
connect(vin, j1[1], r1[1])
connect(led_a, r1[2], d1[1])
connect(gnd, d1[2], j1[2])
j1.place(mm(6), mm(9))
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)

# A track joins pads through points and takes the net of its pads. Every intent has its own key.
# The waypoint is an anchor: 4 mm to the left of pad 1 of R1, wherever R1 lies.
design.track("vin", j1.pad(1), r1.pad(1).at(dx=mm(-4)), r1.pad(1), width=mm(0.5))
# A via inside a path: the track goes on along the layer named by `to`.
design.track(
    "led_a",
    r1.pad(2),
    via_step(mm(18), mm(14), to="B.Cu", diameter=mm(0.6), drill=mm(0.3)),
    via_step(mm(18), mm(6), to="F.Cu", diameter=mm(0.6), drill=mm(0.3)),
    d1.pad(1),
    width=mm(0.25),
)
# An arc inside a path: from where the path is, through the first point, to the second.
design.track(
    "gnd",
    d1.pad(2),
    (mm(8), mm(6)),
    arc_to((mm("6.776705"), mm("6.506705")), (mm(6.27), mm(7.73))),
    j1.pad(2),
    width=mm(0.5),
)
# A zone pours copper on a net; `fenolite fill` fills it after the build.
design.zone(gnd, layers=("F.Cu", "B.Cu"), clearance=mm(0.3))
# One via, and a row of them, tie the pour of the top side to that of the bottom side.
design.via(
    "gnd_tie", mm(24), mm(10), net=gnd, diameter=mm(0.6), drill=mm(0.3), protection=protect(tenting=True)
)
design.stitch(
    "gnd_row",
    net=gnd,
    pitch=mm(4),
    along=((mm(4), mm(17)), (mm(26), mm(17))),
    diameter=mm(0.6),
    drill=mm(0.3),
    clearance=mm(0.2),
)
```

- **Ends and points.** A path holds pad ends (`part.pad(number)`), `(x, y)` points in the frame of
  `place()`, anchors, `via_step(...)` and `arc_to(mid, end)`. The script says what to join; the build
  finds where the pads are, also after a part moved. `fenolite pads` gives a pad's position (page
  `placement`).
- **Anchors.** `part.pad(number).at(dx, dy)` is the point at that offset from the pad, and
  `part.at(dx, dy)` the point at that offset from the origin of the part's footprint; a length left
  out is 0. The offset is in the footprint's own frame, as its library draws it (X to the right, Y
  down), so the point turns and moves with the part, and the build finds it again after the part
  moved. An anchor stands wherever a point does: in a path, in `arc_to`, in `via_step(anchor, to=)`,
  in `design.via(key, anchor, net=)` and in `along`, `region` and `origin` of a stitch. It is a point
  and not a connection: `r1.pad(1)` joins the pad, `r1.pad(1).at()` is only where the pad is.
- **Nets.** A track takes the net of its pads; `net=` is for a track without a pad end. A via and a
  stitch name their net.
- **Sizes.** A `width`, a via `diameter` or `drill` that the call leaves out comes from the net's class
  (page `rules`); when the class has none, the build reports `kicad.copper.size-missing`.
- **`via_step(x, y, to=)`** is a through via by default; `kind="blind"`, `"buried"` or `"micro"` on a
  board with inner layers. **`protect(tenting=True)`** says how a via is covered; KiCad 9 holds tenting
  only.
- **`design.stitch`** puts through vias every `pitch` along a line (`along=`) or on a grid (`region=`).
- **`locked=True`** on a track, a via or a stitch writes that copper locked in KiCad.
- **The build checks script copper.** Copper that shorts two nets or breaks a clearance stops the build
  (exit 5, `copper.short` or `copper.clearance`) and nothing is written. A pad the footprint does not
  have, or a pad on no net, stops it as well.
- Removing an intent from the script removes its copper at the next build. `route --rip` never does.
- The script above declares all its copper: after `fenolite fill`, `fenolite check` exits 0 for it
  with KiCad 10. Before the fill the zones join nothing, and the check reports open connections.

## Zones and fill

`design.zone(net, layers=(...))` pours copper over the whole board, or inside `outline=` (at least
three points). `clearance`, `min_thickness`, `connection` (`thermal`, `solid`, `none`,
`thru_hole_only`) and `priority` are optional; a second zone of one net needs its own `name=`. A build
writes the zone without its fill.

```fenolite-cmd
fenolite fill blink/build --dry-run --json
fenolite fill blink/build --confirm --json
```

`fenolite fill` refills every zone through `kicad-cli` (exit 6 without it). Run it after each change of
the copper or of the placement on a board with a zone, and before `check`: an unfilled zone joins
nothing. On a board without a zone it changes nothing.

Read next: `rules`, `checks`, `recovery`.
