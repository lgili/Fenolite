---
topic: rules
title: Design rules: classes, minimums and selectors
summary: Net classes against minimums, rules with selectors, the stack-up, whose numbers apply, and analyze for current, clearance and creepage.
---

# Design rules: classes, minimums and selectors

Fenolite ships no design-rule value. Every limit comes from the script, and the script's author takes
it from the fabricator's capabilities and from the requirements of the product. **Every number on this
page is an example**: it shows where a value goes, not what the value should be.

## Three kinds of statement

| call | says | who reads it |
|---|---|---|
| `design.rules.netclass(name, ...)` | what the copper of these nets should be | routers and script copper take its sizes |
| `design.rules.minimum(...)` | what the check must refuse, for the board or for one class | KiCad's design-rule check, `fenolite check` |
| `design.rules.rule(name, kind, ...)` | one rule of any kind, for the items a selector names | the same |

A class is a wish and a minimum is a limit. A track of a class with `track_width` 0.5 mm (example) is
drawn 0.5 mm wide; only a minimum makes a narrower one a finding.

## A script with rules

```fenolite-design
from fenolite.dsl import Design, Net, Part, connect, mm, select, stack

design = Design("ruled")
design.board(mm(30), mm(20))

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="LED")
design.add(j1, r1, d1)
vin, led_a, gnd = Net("VIN"), Net("LED_A"), Net("GND")
connect(vin, j1[1], r1[1])
connect(led_a, r1[2], d1[1])
connect(gnd, d1[2], j1[2])

# Every value below is an example: take yours from your fabricator and your product.
# What the copper of a net should be.
design.rules.netclass("PWR", clearance=mm(0.25), track_width=mm(0.5), nets=(vin, gnd))

# What the check must refuse, for the whole board.
design.rules.minimum(
    clearance=mm(0.2),
    track_width=mm(0.2),
    via_diameter=mm(0.6),
    via_drill=mm(0.3),
    hole_size=mm(0.3),
    edge_clearance=mm(0.3),
)
# And for one class: restate its clearance, or the board minimum governs it.
design.rules.minimum(clearance=mm(0.25), track_width=mm(0.4), netclass="PWR")

# Any other rule names its kind and, with a selector, the items it holds for.
design.rules.rule("ring", "annular_width", where=select.item("via"), min=mm(0.15))
design.rules.rule("holes", "hole_to_hole", min=mm(0.3))
design.rules.rule("court", "courtyard_clearance", where=select.ref(j1), min=mm(0.5))

# The build-up, top to bottom, from your fabricator's sheet.
design.stackup(
    stack.mask("10um"),
    stack.copper("35um"),
    stack.core("1.5mm", material="FR4", epsilon_r="4.5"),
    stack.copper("35um"),
    stack.mask("10um"),
)

j1.place(mm(6), mm(9))
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)
```

## Classes and minimums

- **`netclass(name, clearance=, track_width=, via_diameter=, via_drill=, nets=)`**: every value is
  optional, and a net belongs to at most one class. Nets without a class are in KiCad's `Default`.
- **`minimum(...)`** takes `clearance`, `track_width`, `via_diameter`, `via_drill`, `hole_size` (any
  drilled hole) and `edge_clearance` (copper to the board edge). Without `netclass=` it holds for the
  whole board; with it, for the nets of that class, which must be declared first. A kind is declared
  once per scope.
- **Board clearance against class clearance.** A board `clearance` minimum is applied over the
  clearance of a class. A class with a larger clearance is then checked against the board minimum
  only, and the build warns (`kicad.project.class-shadowed`). Restate the class value as a class
  minimum, as the script does for `PWR`.
- Declare the board minimums in every script: without them the check has no limit of yours to hold
  the copper against.

## Rules with selectors

`design.rules.rule(name, kind, where=, between=, min=, opt=, max=, severity=, priority=, layers=)`:

- **Kinds:** the six of `minimum()`, and `hole_to_hole`, `hole_clearance`, `annular_width`,
  `courtyard_clearance`, `silk_clearance` and `creepage`.
- **Selectors** come from `select`: `select.net(name)`, `select.netclass(name)`, `select.ref(part)`,
  `select.item("track")` (or `"via"`, `"pad"`, `"zone"`), and `select.ALL`, the default. `&`, `|` and
  `~` combine them, and a name may hold `*`.
- **`between=`** names the second item of a `clearance` or `creepage` rule: the distance between the
  nets of one class and those of another.
- **`severity`** is `error`, `warning` or `ignore`.
- What a target cannot check stops the build with exit 7 instead of being dropped in silence. A
  `creepage` rule is written for KiCad 10 only (page `recovery`, exit 7).

## The stack-up

`design.stackup(...)` declares the build-up from the top face to the bottom face, with entries of
`stack`: `stack.mask`, `stack.copper`, `stack.core`, `stack.prepreg`, `stack.silkscreen`. There is one
`stack.copper` per copper layer of `board(copper=...)`, with a core or a prepreg between two of them. A
thickness is a length with a unit (`"35um"`). `epsilon_r` and `loss_tangent` are decimal texts, never
floats. Fenolite supplies no thickness and no material; a script without `stackup()` builds without one.

## Impedance targets

`design.rules.impedance(name, ohms=, netclass= or pair=, layers=(trace(...), ...), tolerance=)` states
the impedance a class or a differential pair must have, with the geometry that makes it on each layer.
**The geometry is yours**, from your fabricator's stack-up table: Fenolite computes no width into a
design. The build adds, per trace, a width rule on that layer (and a gap rule for a pair) that KiCad's
check holds the copper to, and on KiCad 10 a tuning profile.

```fenolite-design
from fenolite.dsl import Design, Net, Part, connect, mm, ohm, stack, trace

design = Design("matched")
design.board(mm(30), mm(20), copper=4)

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="CLK")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="33")
design.add(j1, r1)
clk, gnd = Net("CLK"), Net("GND")
connect(clk, j1[1], r1[1])
connect(gnd, r1[2], j1[2])

# Every value below is an example: take yours from your fabricator's stack-up table.
design.rules.netclass("SE50", clearance=mm(0.2), track_width=mm(0.35), nets=(clk,))
design.rules.impedance(
    "SE50",
    ohms=ohm(50),
    netclass="SE50",
    tolerance=10,
    layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.35)), trace("B.Cu", refs="In2.Cu", width=mm(0.35))),
)
design.stackup(
    stack.copper("35um"),
    stack.prepreg("0.2mm", epsilon_r="4.3"),
    stack.copper("35um"),
    stack.core("1.065mm", epsilon_r="4.3"),
    stack.copper("35um"),
    stack.prepreg("0.2mm", epsilon_r="4.3"),
    stack.copper("35um"),
    impedance_controlled=True,
)

j1.place(mm(6), mm(10))
r1.place(mm(18), mm(10))
```

- `pair=` takes a `DiffPair` or `USB2`; each trace of a pair gives its `gap=` too.
- `impedance_controlled=True` on the stack-up makes the job file tell the fabricator; without it the
  build warns (`build.impedance-stackup`).
- `fenolite impedance` lists the targets for the fabricator; `--estimate` adds rough `INFERRED`
  estimates of single-ended lines, never written into the design:

```fenolite-cmd
fenolite impedance blink/build --estimate --json
```

## Measuring a board

```fenolite-cmd
fenolite analyze blink/build/blink.kicad_pcb --pair VIN GND --json
fenolite analyze blink/build/blink.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um --json
fenolite analyze blink/build/blink.kicad_pcb --within 1mm --requirements blink/requirements.toml --json
fenolite analyze blink/build/blink.kicad_pcb --kinds length --json
```

`analyze` measures and you decide. It reports the current capacity of tracks and vias, and the
clearance and creepage between pairs of nets; it runs no tool and writes nothing. It assumes no
thickness and no temperature rise: an input that is not given leaves items out, and the reply counts
them (`analysis.input-missing`). A finding exists only against a requirement of a file of yours
(`--requirements`). No reply claims conformance to a standard. `--kinds length` gives the length of
each net as KiCad's DRC counts it for the major of `--kicad-version` (tracks, arcs, via heights, die
lengths); `--net` names the nets and `--from REF-PAD` adds the length along copper from that pad to
every other pad of its net.

Read next: `checks`, `routing`, `fabrication`.
