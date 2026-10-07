---
topic: parts
title: Parts, pins, values and interfaces
summary: Where symbols and footprints come from, how a pin is named, pad_map, values with units, user properties and typed interfaces.
---

# Parts, pins, values and interfaces

A part needs two things: a symbol, which gives it pins, and a footprint, which gives it pads. Both are
named by a lib id of the form `Library:Name`: `Part("R1", "Fenolite:Resistor",
footprint="Fenolite:Chip_0603", value="330")`. A pad takes the net of the pin that has its number.

## Where lib ids come from

1. **The built-in catalog**, library `Fenolite`. It needs no KiCad installation and no file.

   ```fenolite-cmd
   fenolite catalog list --query 0603 --json
   fenolite catalog list --kind symbol --json
   fenolite catalog show Fenolite:Linear_Regulator --json
   ```

   `list` gives each entry's `lib_id`, `kind` (`symbol` or `footprint`) and a summary; `--query` searches
   the id, the category and the summary. `show` gives the pins of a symbol (`number`, `name`, `etype`)
   or the pads of a footprint. Every catalog entry is `INFERRED`: a symbol is a generic or conceptual
   shape, not a device's pinout, and a footprint is a land pattern that nobody checked against your
   part. Compare both with the datasheet before you order boards.
2. **KiCad's libraries.** Put an `fp-lib-table` and a `sym-lib-table` beside the script, and name parts
   as KiCad does (`Device:R`, `Resistor_SMD:R_0603_1608Metric`). The build copies what it places into the
   project, so the built folder opens anywhere.
3. **Definitions of your own**, written in the script (page `footprints`).

An id that nothing resolves stops the build with `FEN-3001`, and `issues` lists every one of them.

## Pins

- `part[3]` or `part["3"]` is the pin with that number. `part["VDD"]` is every pin with that name.
- A number is looked up first. A text that is both one pin's number and another pin's name gives
  `build.pin-ambiguous`, and the number wins.
- A name that no pin has gives `build.unknown-pin`. Ask `catalog show` before you guess.

## A script with values, a pad map and properties

```fenolite-design
from fenolite.dsl import Design, Net, Part, amp, connect, farad, henry, hertz, mm, ohm, second, volt, watt

design = Design("supply")
design.board(mm(36), mm(20))
vin, vf, v33, gnd = Net("VIN"), Net("VIN_F"), Net("V3V3"), Net("GND")

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
l1 = Part(
    "L1",
    "Fenolite:Inductor",
    footprint="Fenolite:Chip_0805",
    value=henry("4u7"),
    properties={"Rated current": amp("500m").text(), "Self resonance": hertz("40M").text()},
)
# The symbol's pins are 1 IN, 2 GND, 3 OUT. Say this device has GND on pad 1, OUT on 2 and IN on 3.
u1 = Part(
    "U1",
    "Fenolite:Linear_Regulator",
    footprint="Fenolite:SOT89_3",
    value=volt("3.3"),
    pad_map={"1": "3", "2": "1", "3": "2"},
    properties={"Start-up": second("2m").text()},
)
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value=farad("10u"))
r1 = Part(
    "R1",
    "Fenolite:Resistor",
    footprint="Fenolite:Chip_0603",
    value=ohm("4k7"),
    properties={"Power": watt("100m").text(), "Part number": "PN-4700"},
)
design.add(j1, l1, u1, c1, r1)

connect(vin, j1[1], l1[1])
connect(vf, l1[2], u1["IN"])
connect(v33, u1["OUT"], c1[1], r1[1])
connect(gnd, j1[2], u1["GND"], c1[2], r1[2])

j1.place(mm(5), mm(10), rot=90)
l1.place(mm(12), mm(6))
u1.place(mm(20), mm(10))
c1.place(mm(29), mm(6), rot=90)
r1.place(mm(29), mm(14), rot=90)
```

- **`value`** is a text, or a quantity: `ohm`, `farad`, `henry`, `volt`, `amp`, `watt`, `hertz` and
  `second` take an `int` or a text with a prefix (`"4k7"`, `"4.7k"`, `"100n"`, `"3.3"`), never a float.
  Two spellings of one value are one value: `ohm("4k7") == ohm("4.7k")`. `.text()` gives the printed
  form, `4.7kΩ`. Fenolite supplies no value.
- **`pad_map`** maps a symbol pin number to the pad that carries it, when the footprint numbers its
  pads otherwise: `{"1": "3"}` puts the net of pin 1 on pad 3. A pin bonded to several pads lists them:
  `{"2": ("2", "4")}`. Connections still name symbol pins. A map that leaves one pad to two pins is
  refused, so map the displaced pin as well.
- **`properties`** are user fields of the part, as text: a part number, a rating. `Reference`, `Value`,
  `Footprint`, `Datasheet` and `Description` are reserved names.

## Typed interfaces

An interface names a group of nets and gives each a role. `attach()` connects the pins of one part by
role, with the rules of `connect`.

```fenolite-design
from fenolite.dsl import I2C, SPI, UART, USB2, Design, DiffPair, Harness, Interface, Net, Part, mm

design = Design("buses")
design.board(mm(30), mm(20))
u1 = Part("U1", "Fenolite:Microcontroller", footprint="Fenolite:SOIC_8", value="MCU")
j1 = Part("J1", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="DBG")
design.add(u1, j1)

uart = UART(Net("MCU_TX"), Net("MCU_RX"))  # the nets are named from side a
bus = I2C(Net("SDA"), Net("SCL"))
design.add(uart, bus)
uart.attach(u1, side="a", tx="UART", rx="IO1")  # a pin by its name, or a handle such as u1[8]
uart.attach(j1, side="b", tx=j1[1], rx=j1[2])  # side b is crossed: J1-1 joins MCU_RX
bus.attach(u1, sda="IO2", scl="CLK")
bus.attach(j1, sda=j1[3], scl=j1[4])

# The other kinds are declared the same way. SPI and USB2 have attach() too.
design.add(
    SPI(Net("SCK"), Net("MOSI"), Net("MISO"), cs=(Net("CS0"),)),
    USB2(Net("USB_DP"), Net("USB_DN")),
    DiffPair(Net("CLK_P"), Net("CLK_N")),
    Harness("SENSE", {"TEMP": Net("TEMP"), "FAN": Net("FAN")}),
    Interface("AUX", "gpio", {"led": Net("AUX_LED")}),
)

u1.place(mm(10), mm(10))
j1.place(mm(22), mm(10), rot=90)
```

- `UART.attach(part, side=, tx=, rx=)`: side `a` is straight and side `b` is crossed.
- `SPI.attach(part, role=, sck=, mosi=, miso=, cs=)`: a `controller` gives one `cs` pin per chip-select
  net; a `peripheral` gives one `cs` pin and `cs_index`.
- `USB2.attach(part, dp=, dn=)`. `DiffPair(p, n)` records a pair. KiCad pairs two net names that differ
  only in the last character, `P` and `N` or `+` and `-`; other names give `build.diff-pair-name`.
- `Harness(name, members)` and `Interface(name, kind, members)` record any group of nets.
- The script above builds with warnings, and they are worth reading: `build.i2c-pullup-missing` (no
  two-pin part between a bus line and the high net of a `Power`), and `model.dangling-net` for each net
  that joins no pin yet.
- Interfaces are kept in the design data (`.fenolite/`); the board and the schematic do not change.

## What the checks still say

Both scripts build, and neither is a finished board. With KiCad 10, `fenolite check` reports for the
first one `kicad.erc.power-pin-not-driven`: the supply pins of the regulator are fed by a connector,
whose pins are passive, and KiCad's electrical check asks for a power output on such a net. For the
second one it reports `kicad.erc.pin-not-connected`: pins of `U1` are neither connected nor marked with
`no_connect`. Both have open connections until they are routed. The pin types come from the symbols:
`fenolite catalog show` gives them.

Read next: `footprints`, `placement`, `rules`.
