---
topic: parts
title: Parts, pins, values and interfaces
summary: Where symbols and footprints come from, how a pin is named, pad_map, values with units, user properties, typed interfaces and blocks.
---

# Parts, pins, values and interfaces

A part needs two things: a symbol, which gives it pins, and a footprint, which gives it pads. Both are
named by a lib id of the form `Library:Name`: `Part("R1", "Fenolite:Resistor",
footprint="Fenolite:Chip_0603", value="330")`. A pad takes the net of the pin that has its number.

## Where lib ids come from

1. **The built-in catalog**, library `Fenolite`. It needs no KiCad installation and no file.

   ```fenolite-cmd
   fenolite catalog list --query 0603 --json
   fenolite catalog show Fenolite:Linear_Regulator --json
   fenolite catalog view --query resistor --out catalog.html --dry-run --json
   ```

   `list` gives each entry's `lib_id`, `kind` (`symbol` or `footprint`) and summary, which `--query`
   searches; `show` gives a symbol's pins (`number`, `name`, `etype`) or a footprint's pads. Every entry
   is `INFERRED`: a generic symbol, not a device's pinout, and a land pattern nobody checked against your
   part. Compare both with the datasheet before you order boards.

   `view --out FILE` plans an offline HTML browser: symbol and footprint side by side; a pad map confirmed
   against the datasheet gives a `Part` fragment, still `INFERRED`.
2. **KiCad's libraries.** Put an `fp-lib-table` and a `sym-lib-table` beside the script, and name parts
   as KiCad does (`Device:R`, `Resistor_SMD:R_0603_1608Metric`). The build copies what it places into the
   project.
3. **Definitions of your own**, written in the script (page `footprints`).

An id that nothing resolves stops the build with `FEN-3001`; `issues` lists each one.

## Pins

- `part[3]` or `part["3"]` is the pin with that number. `part["VDD"]` is every pin with that name.
- A number is looked up first: a text that is one pin's number and another's name gives
  `build.pin-ambiguous`. A name no pin has gives `build.unknown-pin`; ask `catalog show`, never guess.

## A script with values, a pad map and properties

```fenolite-design
from fenolite.dsl import Design, Net, Part, connect, farad, henry, hertz, mm, ohm, second, volt, watt

design = Design("supply")
design.board(mm(36), mm(20))
vin, vf, v33, gnd = Net("VIN"), Net("VIN_F"), Net("V3V3"), Net("GND")
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
l1 = Part("L1", "Fenolite:Inductor", footprint="Fenolite:Chip_0805", value=henry("4u7"))
# The symbol's pins are 1 IN, 2 GND, 3 OUT. Say this device has GND on pad 1, OUT on 2 and IN on 3.
u1 = Part(
    "U1",
    "Fenolite:Linear_Regulator",
    footprint="Fenolite:SOT89_3",
    value=volt("3.3"),
    pad_map={"1": "3", "2": "1", "3": "2"},
    properties={"Start-up": second("2m").text(), "Bandwidth": hertz("10k").text()},
)
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value=farad("10u"))
rated = {"Power": watt("100m").text(), "Part number": "PN-4700"}
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=ohm("4k7"), properties=rated)
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
  `second` take an `int` or a text with a prefix (`"4k7"`, `"100n"`), never a float. `ohm("4k7") ==
  ohm("4.7k")`, and `.text()` gives the printed form, `4.7kΩ`.
- **`pad_map`** maps a symbol pin number to the pad that carries it: `{"1": "3"}` puts the net of pin 1
  on pad 3, `{"2": ("2", "4")}` bonds a pin to two pads. Connections still name symbol pins. A map that
  leaves one pad to two pins is refused, so map the displaced pin as well.
- **`properties`** are user fields of the part, as text: a part number, a rating. `Reference`, `Value`,
  `Footprint`, `Datasheet` and `Description` are reserved names.

### Value ranges

A range is an exact interval of one unit, computed forwards with worst-case bounds; there is no solver.

```fenolite-design
from fenolite.dsl import Design, Net, Part, Range, Tolerance, amp, between, celsius, connect, kelvin, mm, ohm, pct, volt

design = Design("divider")
design.board(mm(24), mm(16))
tol: Tolerance = pct(1)  # ±1 %; pct(-20, 80) is asymmetric
r_top = ohm("100k").pct(tol)  # 100kΩ (99kΩ..101kΩ)
r_bot = ohm("31.6k").pct(tol)
v_in = volt("5").pct(5)  # 5V (4.75V..5.25V)
v_out: Range = v_in * (r_bot / (r_top + r_bot))  # Ω/Ω is a ratio; V·Ω is no unit
assert v_out.within(between(volt("1"), volt("1.5")))
assert (v_in / (r_top + r_bot)).within(amp("50u").max())  # at most 50 µA
assert celsius(25) - celsius(10) == kelvin(15) and celsius(70).temperature_text() == "70°C"
vin, mid, gnd = Net("VIN"), Net("MID"), Net("GND")
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r_top)
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r_bot)
design.add(j1, r1, r2)
connect(vin, j1[1], r1[1])
connect(mid, r1[2], r2[1])
connect(gnd, j1[2], r2[2])
j1.place(mm(5), mm(8), rot=90)
r1.place(mm(13), mm(5))
r2.place(mm(13), mm(11))
```

- `q.pct(p)`, `q.pct(lo, hi)` and `q.pct(pct(...))` give a range with nominal `q`; `q.max()` is `0..q`,
  `q.min()` is `q..`; `between(a, b, nominal=None)` takes two quantities of one unit.
- `+ - * /` mix ranges, quantities and exact numbers; a result may be wider than the truth, never narrower.
  Units follow a closed table (V/Ω is A, V·A is W, V·V/Ω is W); another pair raises `TypeError`, a divisor
  that holds zero `DslError`. A one-sided range enters while the result keeps a bound. `a.within(b)`: every value of `a` lies in `b`.
- A ranged part value writes the nominal text (`100kΩ`); `.fenolite/circuit.json` keeps the range.

## Parts from devices

A device joins a symbol, a footprint, the pin map, the MPN, the datasheet and ratings in one record
(`docs/devices.md`). `design.part(ref, device=...)` creates and adds the part; pins are named by function.

```fenolite-cmd
fenolite catalog list --kind device --json
fenolite catalog import --symbol Fenolite:Resistor --footprint Fenolite:Chip_0603 --id Proj:R_0603 --out devices/r_0603.toml --dry-run --json
```

```fenolite-design
from fenolite.dsl import Design, Net, PinNameError, connect, mm, ohm

design = Design("indicator")
design.board(mm(20), mm(10))
j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="5V")
r1 = design.part("R1", device="Fenolite:R_0603", value=ohm("1k"))
d1 = design.part("D1", device="Fenolite:LED_0603")
vin, gnd, led = Net("VIN"), Net("GND"), Net("LED_A")
connect(vin, j1.P1, r1.P1)
connect(led, r1.P2, d1.A)  # the anode, wherever its pad is
connect(gnd, j1.P2, d1["K"])
try:
    d1.ANODE
except PinNameError as error:
    print(error)  # part D1 (device Fenolite:LED_0603) has no pin 'ANODE'; pins: A, K
j1.place(mm(4), mm(5), rot=90)
r1.place(mm(10), mm(5))
d1.place(mm(15), mm(5))
```

- The shipped devices are generic (`INFERRED`, no MPN). Your own records go in `devices/` beside the
  script; `catalog import` writes an `UNVERIFIED` template; `<device id>@<mpn>` is an orderable part.
- A grammar family (`fenolite.family.v1`) in `devices/` gives queries exact MPNs; `family`, page `files`.
- A wrong pin name raises `PinNameError` with the closest names. A device that disagrees with its symbol or
  footprint is `build.device-mismatch`; `result.devices` lists each device, `device.edited` an edited one.
- `mcu.take(I2C, option=, pins=, name=)` takes an interface the device's `[[options]]` offer; the build
  picks free pins, lists them in `result.pins`, keeps them in the lock; none left: `pins.unsatisfiable`.

## Typed interfaces

An interface names a group of nets and gives each a role; `attach()` connects one part's pins by role.

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
- The script builds with warnings: `build.i2c-pullup-missing` (no two-pin part from a bus line to the
  high net of a `Power`) and `model.dangling-net` for a net joining no pin yet.

## Blocks

A block is a circuit written once and used many times: a function marked `@block`, its ports typed.

```fenolite-design
from fenolite.dsl import Design, Net, block, connect, mm, ohm, schematic_group

design = Design("blocks")
design.board(mm(40), mm(20))


@block
def divider(b, *, r_top=ohm("10k")):  # keyword-only, recorded
    vin = b.port("VIN", direction="in")
    gnd = b.port("GND", direction="in")
    mid = b.net("MID")  # a local net: div0/MID
    top = b.part("R_TOP", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r_top)
    low = b.part("R_LOW", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
    connect(vin, top[1])  # wired like a net
    connect(mid, top[2], low[1])
    connect(gnd, low[2]); b.schematic(schematic_group("chain", top, low))  # sheet order, all instances


vin, gnd = Net("VIN"), Net("GND")
for n in range(2):
    div = design.use(divider, f"div{n}", r_top=ohm("22k"))  # the paths div0/R_TOP, div1/R_TOP
    connect(vin, div.VIN)  # the port net is VIN
    connect(gnd, div.GND)
    div.part("R_TOP").place(mm(10 + 15 * n), mm(6))
    div.part("R_LOW").place(mm(10 + 15 * n), mm(14))
```

- `design.use(block, name, **params)` runs the function once with a fresh block `b`; refs come from the
  lock and never collide; `b.part(name, ...)` names a local part.
- `b.port(name, kind=Net, direction=...)` takes `Net` or an interface class (`I2C` gives `.sda`, `.scl`);
  unwired, its net is `<instance>/<port>` (`out` first); its sheet pin is `<port>` or `I2C_sda`.
- Warnings: `build.port-unused`, a port with nothing outside (`optional=True` when meant), and
  `build.block-net-escape`, a global net joining pins inside and outside a block without a port.

## What the checks still say

No script here is a finished board: nothing is routed. KiCad 10 reports
`kicad.erc.power-pin-not-driven` (passive pins feed the regulator) and `kicad.erc.pin-not-connected`.

Read next: `footprints`, `placement`, `rules`.
