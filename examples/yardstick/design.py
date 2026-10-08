# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The yardstick: an invented controller of eight identical 48 V buck channels with an isolated sense
of a high-voltage bus, about 390 parts of KiCad's official libraries on a six-layer board.

The circuit was invented for Fenolite to be large, not to be built: it mirrors no board, product or
reference design, and every value below is a round one chosen for this example. The board grows by
stages (``STAGE``, ``docs/evidence/yardstick.md``); ``tools/yardstick.py run`` takes it through the loop
every night and compares each step with a budget. The stages are cumulative, so the script holds what
every stage up to its own added: four copper layers, zones, classes and the high-voltage rules (stage 1);
six layers with a declared stack-up (stage 2); slots under the isolators, plated
mounting holes with keep-outs, a high-voltage rule area, the USB pair's rules and impedance target,
thermal via arrays, placement rules and a net tie (stage 3); plane layers for the router (stage 4); and
fiducials, tooling holes and test points (stage 5).

Build it with the official libraries of tag 10.0.6 (``tools/kicad_libs_fetch.py``)::

    FENOLITE_LIBS_CACHE=<cache> fenolite build examples/yardstick/design.py --out build/yard \
        --kicad-version 10 --confirm

The script places every part: the power input along the left edge, the controller with its USB and
CAN ports beside it, the eight channels in two rows of four, and the high-voltage strip along the
right edge. The script draws no track: the runner routes the board at stage 4.
"""

from fenolite.dsl import (
    USB2,
    Design,
    Module,
    Net,
    Part,
    Power,
    connect,
    mm,
    nm,
    no_connect,
    ohm,
    protect,
    select,
    shape,
    stack,
    trace,
)
from fenolite.dsl.assembly import clear_outline

STAGE = 5  # the stage of docs/evidence/yardstick.md this script is at; chosen for the example
COPPER = 6  # copper layers at stage 1, six from stage 2; chosen for the example
CHANNELS = 8  # identical buck channels; chosen for the example
SUPPLY = {"VIN48": "48V", "+12V": "12V", "+5V": "5V", "+3V3": "3.3V"}  # supply rails; chosen for the example

# The board and its floor plan, in millimetres; chosen for the example.
BOARD = (250, 110)  # width and height; chosen for the example
CELL = (36, 48)  # one channel cell, width and height; chosen for the example
CELLS_AT = (62, 8)  # the corner of the first channel cell; chosen for the example
STRIP = (223, 20, 246, 90)  # the high-voltage strip: left, top, right, bottom; chosen for the example
GAP = 8  # between the high-voltage strip and the low-voltage copper planes; chosen for the example
EDGE = 1  # from the board edge to a zone outline; chosen for the example
HOLE_INSET = 5  # from the board edge to the centre of a mounting hole; chosen for the example
SPLIT_X = 61  # where the +3V3 plane ends and the VIN48 plane begins; chosen for the example
SLOT_WIDTH = 1  # the milled slot under each isolator; chosen for the example
SLOTS = (  # each slot: x of its axis, then y of the centres of its two round ends; chosen for the example
    (219, 32, 38),  # under U6, the isolated amplifier
    (219, 54, 66),  # under U7, the isolated DC/DC converter
)
HOLE = {"drill": 3.2, "pad": 6, "keepout": 9}  # mounting holes and their keep-outs; chosen for the example

# The layers: what each inner layer carries, and the build-up of the board.
ZONE_LAYERS = {  # chosen for the example
    "ground": ("In1.Cu",),  # GND under the low-voltage area
    "supply": ("In4.Cu",),  # +3V3 under the controller, VIN48 under the channels
    "return": ("In1.Cu", "In4.Cu"),  # HV_RTN under the high-voltage strip
}
PLANES = {"In1.Cu": "GND", "In4.Cu": "VIN48"}  # the inner layers typed as planes; chosen for the example
STACKUP = "six-layer-1.6mm"  # the packaged stack-up preset of six layers, read from S-0722
FINISH = "ENIG"  # the surface finish; chosen for the example

# Clearances and widths, in millimetres; chosen for the example.
MINIMUMS = {  # what the board must never go below; chosen for the example
    "clearance": 0.15,
    "track_width": 0.15,
    "via_diameter": 0.45,
    "via_drill": 0.2,
    "hole_size": 0.3,
    "edge_clearance": 0.3,
}
CLASSES = {  # clearance and track width per net class; chosen for the example
    "PWR": (0.2, 0.5),
    "HV": (0.5, 0.5),
    "SIG": (0.15, 0.2),
    "USB": (0.15, 0.2),
}
HV_CLEARANCE = 7  # between the nets of class HV and every other net; chosen for the example
HV_CREEPAGE = 7.5  # along the surface, the same two groups: only the slots meet it; chosen for the example
HV_AREA_CLEARANCE = 0.6  # between two nets of class HV inside the high-voltage strip; chosen for the example
HOLE_KEEPOUT = ("tracks", "vias")  # what the keep-out round a mounting hole forbids; chosen for the example

# The USB pair: its class values, its rules and its impedance target; chosen for the example.
PAIR_CLASS = {
    "diff_pair_width": 0.2,
    "diff_pair_gap": 0.15,
    "diff_pair_via_gap": 0.25,
}  # chosen for the example
PAIR_RULES = {  # the limits of the pair, in millimetres; chosen for the example
    "gap_min": 0.15,
    "gap_max": 0.25,
    "clearance": 0.15,
    "uncoupled_max": 5,
    "skew_max": 0.5,
    "length_max": 60,
}
PAIR_PRIORITY = 2  # below the impedance target, which governs the gap on its layer; chosen for the example
IMPEDANCE = {"ohms": 90, "tolerance": 10, "layer": "F.Cu", "refs": "In1.Cu"}  # chosen for the example

# Copper that belongs to a part: thermal via arrays, filled and capped; chosen for the example.
THERMAL = {"pitch": 1.2, "diameter": 0.6, "drill": 0.3, "margin": 0.1}  # millimetres; chosen for the example
EXPOSED_PAD = 49  # the controller's exposed pad, its VSS pin; chosen for the example

# Placement rules: how far a part may lie from the pads it serves, in millimetres; chosen for the example.
NEAR = {"decoupling": 15, "crystal": 10, "gate": 15}  # chosen for the example
VDD_PINS = (1, 23, 35, 48)  # the controller's supply pins that the decoupling serves; chosen for the example

# Assembly and test features, in millimetres; chosen for the example.
FIDUCIALS = {"FID1": (15, 95), "FID2": (232, 8), "FID3": (232, 102)}  # chosen for the example
FIDUCIAL = {"copper": 1, "mask": 2, "clear": 3}  # chosen for the example
TOOLING = {"H5": (30, 4), "H6": (215, 105)}  # tooling holes, not plated; chosen for the example
TOOLING_HOLE = {"drill": 2, "clear": 4}  # chosen for the example
TEST_POINTS = {  # the net and the place of each test point; chosen for the example
    "TP1": ("GND", 32, 52),
    "TP2": ("+3V3", 36, 52),
    "TP3": ("+5V", 40, 52),
    "TP4": ("+12V", 44, 52),
    "TP5": ("VIN48", 48, 52),
}
TEST_PAD = 1.5  # the round pad of a test point; chosen for the example

# Part values; chosen for the example.
VALUES = {  # every resistor, capacitor and inductor value of the circuit; chosen for the example
    "bulk": "100u",
    "ceramic": "10u",
    "decoupling": "100n",
    "small": "1u",
    "load": "10p",
    "filter": "1n",
    "snubber_c": "1n",
    "inductor": "10u",
    "gate": "10R",
    "gate_source": "10k",
    "snubber_r": "10R",
    "shunt": "5m",
    "series": "100R",
    "pull": "10k",
    "divider_top": "100k",
    "divider_bottom": "10k",
    "led": "1k",
    "ntc": "10k",
    "termination": "120R",
    "slope": "10k",
    "hv_string": "1M",
    "hv_bottom": "1k",
    "shield_r": "1M",
    "shield_c": "10n",
    "fuse": "10A",
}

# Footprints of the official libraries, by the role a part plays; chosen for the example.
FOOTPRINTS = {  # chosen for the example
    "0603r": "Resistor_SMD:R_0603_1608Metric",
    "1206r": "Resistor_SMD:R_1206_3216Metric",
    "2512r": "Resistor_SMD:R_2512_6332Metric",
    "0603c": "Capacitor_SMD:C_0603_1608Metric",
    "0805c": "Capacitor_SMD:C_0805_2012Metric",
    "1210c": "Capacitor_SMD:C_1210_3225Metric",
    "bulk": "Capacitor_SMD:CP_Elec_10x10",
    "0805l": "Inductor_SMD:L_0805_2012Metric",
    "inductor": "Inductor_SMD:L_12x12mm_H8mm",
    "sma": "Diode_SMD:D_SMA",
    "sod123": "Diode_SMD:D_SOD-123",
    "led": "LED_SMD:LED_0603_1608Metric",
    "fuse": "Fuse:Fuse_2512_6332Metric",
    "dpak": "Package_TO_SOT_SMD:TO-252-2",
    "soic8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "soic16w": "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm",
    "terminal": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal",
    "crystal": "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    "header": "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
    "usb": "Connector_USB:USB_Micro-B_Molex-105017-0001",
    "net_tie": "NetTie:NetTie-2_SMD_Pad0.5mm",
}
DPAK_PADS = {
    "G": "1",
    "D": "2",
    "S": "3",
}  # gate, drain tab and source of the TO-252 land; chosen for the example

# The controller's pins, by number; chosen for the example.
CHANNEL_PINS = (  # per channel: its PWM output, current input and voltage input; chosen for the example
    (27, 8, 16),
    (28, 9, 17),
    (30, 10, 18),
    (31, 11, 19),
    (32, 12, 22),
    (41, 13, 24),
    (42, 14, 25),
    (43, 15, 26),
)
CONTROLLER_PINS = {  # every other signal of the controller; chosen for the example
    "LED1": 2,
    "LED2": 3,
    "LED3": 4,
    "OSC_IN": 5,
    "OSC_OUT": 6,
    "NRST": 7,
    "DRV_EN": 29,
    "USB_DN": 33,
    "USB_DP": 34,
    "SWDIO": 36,
    "SWCLK": 37,
    "VBUS_DET": 38,
    "HV_SENSE_HI": 39,
    "HV_SENSE_LO": 40,
    "CAN_RX": 45,
    "BOOT0": 46,
    "CAN_TX": 47,
}
CONTROLLER_SPARE = (44,)  # the one pin the circuit leaves open; chosen for the example

# Where each part of a channel lies in its cell: x, y and rotation; chosen for the example.
CHANNEL_PLAN = {  # millimetres from the cell's corner; chosen for the example
    "c_in1": (4, 4, 0),
    "c_in2": (9.5, 4, 0),
    "c_in3": (15, 4, 0),
    "d_tvs": (23, 4, 0),
    "r_shunt": (31, 4, 0),
    "q_high": (8, 11.5, 0),
    "q_low": (21, 11.5, 0),
    "r_gate_high": (28.5, 9, 0),
    "r_gate_low": (32.5, 9, 0),
    "r_gs_high": (28.5, 11.5, 0),
    "r_gs_low": (32.5, 11.5, 0),
    "r_snubber": (28.5, 14, 0),
    "c_snubber": (32.5, 14, 0),
    "driver": (5.5, 19.5, 0),
    "d_boot": (13, 18, 0),
    "c_boot": (13, 20.5, 0),
    "c_driver": (18.5, 18, 0),
    "r_pwm": (18.5, 20.5, 0),
    "ntc": (22.5, 18, 0),
    "r_enable": (22.5, 20.5, 0),
    "c_enable": (26.5, 18, 0),
    "r_sense": (26.5, 20.5, 0),
    "amplifier": (31.5, 19.5, 0),
    "c_sense": (3, 24.5, 0),
    "c_amplifier": (7, 24.5, 0),
    "r_current": (11, 24.5, 0),
    "c_current": (15, 24.5, 0),
    "r_fb_top": (19, 24.5, 0),
    "r_fb_bottom": (23, 24.5, 0),
    "c_fb": (27, 24.5, 0),
    "r_led": (31, 24.5, 0),
    "inductor": (8.5, 33.5, 0),
    "c_out1": (19.5, 28.5, 0),
    "c_out2": (19.5, 32.5, 0),
    "c_out3": (19.5, 36.5, 0),
    "d_led": (28, 29.5, 0),
    "terminal": (26, 39, 0),
}
SHARED_PLAN = {  # where the parts outside the channels lie on the board, by reference; chosen for the example
    # power input, along the left edge
    "J1": (8, 16, 0), "F1": (22, 14, 0), "D1": (22, 19, 0), "C1": (9, 30, 0), "C2": (22.5, 30, 0),
    "C3": (6, 39.5, 0), "C4": (12, 39.5, 0), "J2": (8, 50, 0), "D2": (22, 47, 0), "C5": (22, 51.5, 0),
    "U1": (9, 62, 0), "C6": (18, 60, 0), "C7": (18, 63.5, 0), "U2": (9, 72, 0), "C8": (18, 70, 0),
    "C9": (18, 73.5, 0), "D3": (6, 80, 0), "R1": (10.5, 80, 0), "FB1": (15.5, 80, 0), "C10": (20, 80, 0),
    # controller
    "U3": (45, 24, 0), "C11": (36, 14, 0), "C12": (40, 14, 0), "C13": (44, 14, 0), "C14": (48, 14, 0),
    "C15": (52, 14, 0), "C16": (56, 14, 0), "Y1": (34, 24, 0), "C17": (34, 20.5, 0), "C18": (34, 27.5, 0),
    "R2": (56, 20.5, 0), "C19": (56, 23, 0), "R3": (56, 25.5, 0), "R7": (56, 28, 0), "D4": (36, 34, 0),
    "R4": (40.5, 34, 0), "D5": (36, 37, 0), "R5": (40.5, 37, 0), "D6": (36, 40, 0), "R6": (40.5, 40, 0),
    "C20": (47, 34, 0), "J3": (52, 42, 0), "NT1": (54, 17, 0),
    # CAN port
    "U4": (42, 86, 0), "C21": (34, 85, 0), "R8": (34, 87.5, 0), "R9": (50, 85, 0), "C22": (50, 87.5, 0),
    "J4": (52, 100, 0),
    # USB port, at the bottom edge
    "J5": (40, 106, 0), "U5": (40, 97, 0), "R10": (33, 96, 0), "R11": (33, 98.5, 0), "R12": (46, 96, 0),
    "C23": (46, 98.5, 0),
    # high-voltage sense: the two isolators bridge the gap, the rest lies in the strip
    "U6": (219, 35, 180), "U7": (219, 60, 0), "C27": (210.5, 32, 0), "R23": (210.5, 34.5, 0),
    "R24": (210.5, 37, 0), "C29": (210.5, 39.5, 0), "C28": (210.5, 60, 0), "R22": (229, 33, 0),
    "C25": (229, 35.5, 0), "C24": (229, 38, 0), "C26": (229, 58, 0), "C30": (229, 62, 0), "J6": (236, 27, 0),
    "R13": (240, 36, 0), "R14": (240, 39, 0), "R15": (240, 42, 0), "R16": (240, 45, 0), "R17": (240, 48, 0),
    "R18": (240, 51, 0), "R19": (240, 54, 0), "R20": (240, 57, 0), "R21": (240, 60.5, 0),
    "D8": (239.5, 64.5, 0),
}  # fmt: skip
LOCKED = ("J",)  # the reference letter of the parts that never move, connectors; chosen for the example


def net(name: str, netclass: str) -> Net:
    """A net that joins the net class ``netclass`` when the rules are written."""
    found = Net(name)
    class_nets[netclass].append(found)
    return found


def resistor(ref: str, value: str, size: str = "0603r") -> Part:
    return Part(ref, "Device:R", footprint=FOOTPRINTS[size], value=VALUES[value])


def capacitor(ref: str, value: str, size: str = "0603c") -> Part:
    symbol = "Device:C_Polarized" if size == "bulk" else "Device:C"
    return Part(ref, symbol, footprint=FOOTPRINTS[size], value=VALUES[value])


def terminal(ref: str, value: str) -> Part:
    return Part(ref, "Connector:Screw_Terminal_01x02", footprint=FOOTPRINTS["terminal"], value=value)


def two_pin(part: Part, first: Net, second: Net) -> Part:
    """Join the two pins of a resistor, a capacitor or a connector: pin 1 to ``first``, 2 to ``second``."""
    connect(first, part[1])
    connect(second, part[2])
    return part


def diode(part: Part, anode: Net, cathode: Net) -> Part:
    connect(anode, part["A"])
    connect(cathode, part["K"])
    return part


def power_input() -> Module:
    """The 48 V input with its fuse and capacitors, the 12 V auxiliary input and the two regulators."""
    module = Module("power")
    vin_raw, aux_raw = net("VIN48_IN", "PWR"), net("V12_IN", "PWR")
    led = net("PWR_LED", "SIG")
    tvs = Part("D1", "Device:D_TVS", footprint=FOOTPRINTS["sma"], value="TVS")
    connect(vin48, tvs["A1"])
    connect(gnd, tvs["A2"])
    reg5 = Part("U1", "Regulator_Linear:AMS1117-5.0", value="5V")
    reg3 = Part("U2", "Regulator_Linear:AMS1117-3.3", value="3.3V")
    connect(v12, reg5["VI"])
    connect(v5, reg5["VO"], reg3["VI"])
    connect(v33, reg3["VO"])
    connect(gnd, reg5["GND"], reg3["GND"])
    module.add(
        two_pin(terminal("J1", SUPPLY["VIN48"]), vin_raw, gnd),
        two_pin(
            Part("F1", "Device:Fuse", footprint=FOOTPRINTS["fuse"], value=VALUES["fuse"]), vin_raw, vin48
        ),
        tvs,
        two_pin(capacitor("C1", "bulk", "bulk"), vin48, gnd),
        two_pin(capacitor("C2", "bulk", "bulk"), vin48, gnd),
        two_pin(capacitor("C3", "ceramic", "1210c"), vin48, gnd),
        two_pin(capacitor("C4", "ceramic", "1210c"), vin48, gnd),
        two_pin(terminal("J2", SUPPLY["+12V"]), aux_raw, gnd),
        diode(Part("D2", "Device:D_Schottky", footprint=FOOTPRINTS["sma"], value="D"), aux_raw, v12),
        two_pin(capacitor("C5", "ceramic", "1210c"), v12, gnd),
        reg5,
        two_pin(capacitor("C6", "ceramic", "0805c"), v12, gnd),
        two_pin(capacitor("C7", "ceramic", "0805c"), v5, gnd),
        reg3,
        two_pin(capacitor("C8", "ceramic", "0805c"), v5, gnd),
        two_pin(capacitor("C9", "ceramic", "0805c"), v33, gnd),
        diode(Part("D3", "Device:LED", footprint=FOOTPRINTS["led"], value="LED"), led, gnd),
        two_pin(resistor("R1", "led"), v33, led),
        two_pin(
            Part("FB1", "Device:FerriteBead_Small", footprint=FOOTPRINTS["0805l"], value="FB"), v33, v33a
        ),
        two_pin(capacitor("C10", "small"), v33a, gnd),
    )
    return module


def controller() -> Module:
    """The 48-pin QFN controller with its decoupling, crystal, reset and boot parts, the debug header
    and three status LEDs."""
    module = Module("controller")
    mcu = Part("U3", "MCU_ST_STM32G4:STM32G431CBUx", value="MCU")
    module.add(mcu)
    connect(v33, mcu["VDD"], mcu["VBAT"])
    connect(v33a, mcu["VDDA"], mcu["VREF+"])
    connect(gnd, mcu["VSS"])
    for name, pin in CONTROLLER_PINS.items():
        connect(signals[name], mcu[pin])
    for index, (pwm, current, voltage) in enumerate(CHANNEL_PINS, start=1):
        connect(signals[f"CH{index}_PWM"], mcu[pwm])
        connect(signals[f"CH{index}_ISENSE"], mcu[current])
        connect(signals[f"CH{index}_VSENSE"], mcu[voltage])
    no_connect(*(mcu[pin] for pin in CONTROLLER_SPARE))
    decoupling = [two_pin(capacitor(ref, "decoupling"), v33, gnd) for ref in ("C11", "C12", "C13", "C14")]
    decoupling.append(two_pin(capacitor("C20", "ceramic", "0805c"), v33, gnd))
    # The analogue supply returns to its own ground, which one net tie joins to GND beside the controller.
    tie = Part("NT1", "Device:NetTie_2", footprint=FOOTPRINTS["net_tie"], value="NetTie")
    connect(gnd, tie[1])
    connect(sgnd, tie[2])
    module.add(
        *decoupling,
        two_pin(capacitor("C15", "decoupling"), v33a, sgnd),
        two_pin(capacitor("C16", "small"), v33a, sgnd),
        tie,
    )
    crystal = Part("Y1", "Device:Crystal_GND24", footprint=FOOTPRINTS["crystal"], value="8MHz")
    connect(signals["OSC_IN"], crystal[1])
    connect(signals["OSC_OUT"], crystal[3])
    connect(gnd, crystal[2], crystal[4])
    loads = (
        two_pin(capacitor("C17", "load"), signals["OSC_IN"], gnd),
        two_pin(capacitor("C18", "load"), signals["OSC_OUT"], gnd),
    )
    module.add(
        crystal,
        *loads,
        two_pin(resistor("R2", "pull"), v33, signals["NRST"]),
        two_pin(capacitor("C19", "decoupling"), signals["NRST"], gnd),
        two_pin(resistor("R3", "pull"), signals["BOOT0"], gnd),
        two_pin(resistor("R7", "pull"), signals["DRV_EN"], gnd),
    )
    for index in (1, 2, 3):
        anode = net(f"LED{index}_A", "SIG")
        module.add(
            two_pin(resistor(f"R{index + 3}", "led"), signals[f"LED{index}"], anode),
            diode(Part(f"D{index + 3}", "Device:LED", footprint=FOOTPRINTS["led"], value="LED"), anode, gnd),
        )
    header = Part("J3", "Connector_Generic:Conn_02x05_Odd_Even", footprint=FOOTPRINTS["header"], value="SWD")
    connect(v33, header[1])
    connect(signals["SWDIO"], header[2])
    connect(signals["SWCLK"], header[4])
    connect(signals["NRST"], header[10])
    connect(gnd, header[3], header[5], header[9])
    no_connect(header[6], header[7], header[8])
    module.add(header)
    # A thermal array of filled and capped vias in the exposed pad, and the placement rules of the
    # decoupling and of the crystal.
    design.stitch("u3_thermal", net=gnd, region=mcu.pad(EXPOSED_PAD), **thermal())
    supply_pads = tuple(mcu.pad(pin) for pin in VDD_PINS)
    design.near("decoupling", tuple(decoupling), supply_pads, within=mm(NEAR["decoupling"]))
    oscillator = (mcu.pad(CONTROLLER_PINS["OSC_IN"]), mcu.pad(CONTROLLER_PINS["OSC_OUT"]))
    design.near("crystal", (crystal, *loads), oscillator, within=mm(NEAR["crystal"]))
    return module


def can_port() -> Module:
    """A CAN transceiver in SOIC-8 with its termination and a terminal block."""
    module = Module("can")
    can_h, can_l, slope = net("CANH", "SIG"), net("CANL", "SIG"), net("CAN_RS", "SIG")
    transceiver = Part("U4", "Interface_CAN_LIN:MCP2551-I-SN", value="CAN")
    connect(signals["CAN_TX"], transceiver["TXD"])
    connect(signals["CAN_RX"], transceiver["RXD"])
    connect(v5, transceiver["VDD"])
    connect(gnd, transceiver["VSS"])
    connect(can_h, transceiver["CANH"])
    connect(can_l, transceiver["CANL"])
    connect(slope, transceiver["Rs"])
    no_connect(transceiver["Vref"])
    module.add(
        transceiver,
        two_pin(capacitor("C21", "decoupling"), v5, gnd),
        two_pin(resistor("R8", "slope"), slope, gnd),
        two_pin(resistor("R9", "termination"), can_h, can_l),
        two_pin(capacitor("C22", "filter"), can_h, can_l),
        two_pin(terminal("J4", "CAN"), can_h, can_l),
    )
    return module


def usb_port() -> tuple[Module, USB2]:
    """A micro-B receptacle, an ESD array, a divider that senses VBUS and the shield's RC; with the
    module, the pair ``USB_DP``/``USB_DN`` that the rules below name."""
    module = Module("usb")
    vbus, shield = net("VBUS", "PWR"), net("USB_SHIELD", "SIG")
    dp, dn = signals["USB_DP"], signals["USB_DN"]
    bus = USB2(dp, dn, vbus=vbus, gnd=gnd)
    design.add(bus)
    receptacle = Part("J5", "Connector:USB_B_Micro", footprint=FOOTPRINTS["usb"], value="USB")
    bus.attach(receptacle, dp="D+", dn="D-", vbus="VBUS", gnd="GND")
    connect(shield, receptacle["Shield"])
    no_connect(receptacle["ID"])
    array = Part("U5", "Power_Protection:USBLC6-2SC6", value="ESD")
    connect(dp, array[1], array[6])
    connect(dn, array[3], array[4])
    connect(vbus, array[5])
    connect(gnd, array[2])
    module.add(
        receptacle,
        array,
        two_pin(resistor("R10", "divider_top"), vbus, signals["VBUS_DET"]),
        two_pin(resistor("R11", "divider_top"), signals["VBUS_DET"], gnd),
        two_pin(resistor("R12", "shield_r"), shield, gnd),
        two_pin(capacitor("C23", "shield_c"), shield, gnd),
    )
    return module, bus


def channel(n: int, x: float, y: float) -> Module:
    """One buck channel in the cell whose corner is (``x``, ``y``): a half-bridge driver with its
    bootstrap, two transistors, the inductor, the capacitors, a shunt with its amplifier, a feedback
    divider, a thermistor on the enable input, a TVS, an LED and the output terminal block.

    The references are ``n * 100 + k``, so ``R301`` is a resistor of channel 3."""
    base = n * 100
    module = Module(f"ch{n}")

    def local(name: str, netclass: str = "SIG") -> Net:
        return net(f"CH{n}_{name}", netclass)

    pwm, current, voltage = (signals[f"CH{n}_{name}"] for name in ("PWM", "ISENSE", "VSENSE"))
    enable, high, low, boot = local("EN"), local("HO"), local("LO"), local("BOOT")
    gate_high, gate_low, snubber, led = local("GH"), local("GL"), local("SNUB"), local("LED")
    switch, out, shunt = local("SW", "PWR"), local("OUT", "PWR"), local("CS", "PWR")
    sense, amplified = local("CSF"), local("IAMP")

    driver = Part(f"U{base + 1}", "Driver_FET:IR2104", footprint=FOOTPRINTS["soic8"], value="DRV")
    connect(v12, driver["VCC"])
    connect(pwm, driver["IN"])
    connect(enable, driver["~{SD}"])
    connect(gnd, driver["COM"])
    connect(low, driver["LO"])
    connect(switch, driver["VS"])
    connect(high, driver["HO"])
    connect(boot, driver["VB"])
    q_high = Part(
        f"Q{base + 1}", "Device:Q_NMOS", footprint=FOOTPRINTS["dpak"], value="NMOS", pad_map=DPAK_PADS
    )
    q_low = Part(
        f"Q{base + 2}", "Device:Q_NMOS", footprint=FOOTPRINTS["dpak"], value="NMOS", pad_map=DPAK_PADS
    )
    connect(vin48, q_high["D"])
    connect(gate_high, q_high["G"])
    connect(switch, q_high["S"], q_low["D"])
    connect(gate_low, q_low["G"])
    connect(shunt, q_low["S"])
    amplifier = Part(f"U{base + 2}", "Amplifier_Current:INA180A1", value="AMP")
    connect(amplified, amplifier[1])
    connect(gnd, amplifier[2], amplifier[4])
    connect(sense, amplifier[3])
    connect(v33, amplifier[5])
    tvs = Part(f"D{base + 2}", "Device:D_TVS", footprint=FOOTPRINTS["sma"], value="TVS")
    connect(out, tvs["A1"])
    connect(gnd, tvs["A2"])
    ntc = Part(f"TH{base + 1}", "Device:Thermistor_NTC", footprint=FOOTPRINTS["0603r"], value=VALUES["ntc"])
    coil = Part(f"L{base + 1}", "Device:L", footprint=FOOTPRINTS["inductor"], value=VALUES["inductor"])

    parts = {
        "driver": driver,
        "d_boot": diode(
            Part(f"D{base + 1}", "Device:D", footprint=FOOTPRINTS["sod123"], value="D"), v12, boot
        ),
        "c_boot": two_pin(capacitor(f"C{base + 1}", "decoupling"), boot, switch),
        "c_driver": two_pin(capacitor(f"C{base + 2}", "small", "0805c"), v12, gnd),
        "q_high": q_high,
        "q_low": q_low,
        "r_gate_high": two_pin(resistor(f"R{base + 1}", "gate"), high, gate_high),
        "r_gate_low": two_pin(resistor(f"R{base + 2}", "gate"), low, gate_low),
        "r_gs_high": two_pin(resistor(f"R{base + 3}", "gate_source"), gate_high, switch),
        "r_gs_low": two_pin(resistor(f"R{base + 4}", "gate_source"), gate_low, shunt),
        "r_snubber": two_pin(resistor(f"R{base + 5}", "snubber_r"), switch, snubber),
        "c_snubber": two_pin(capacitor(f"C{base + 3}", "snubber_c"), snubber, gnd),
        "inductor": two_pin(coil, switch, out),
        "c_in1": two_pin(capacitor(f"C{base + 4}", "ceramic", "1210c"), vin48, gnd),
        "c_in2": two_pin(capacitor(f"C{base + 5}", "ceramic", "1210c"), vin48, gnd),
        "c_in3": two_pin(capacitor(f"C{base + 6}", "ceramic", "1210c"), vin48, gnd),
        "c_out1": two_pin(capacitor(f"C{base + 7}", "ceramic", "1210c"), out, gnd),
        "c_out2": two_pin(capacitor(f"C{base + 8}", "ceramic", "1210c"), out, gnd),
        "c_out3": two_pin(capacitor(f"C{base + 9}", "ceramic", "1210c"), out, gnd),
        "r_shunt": two_pin(resistor(f"R{base + 6}", "shunt", "2512r"), shunt, gnd),
        "r_sense": two_pin(resistor(f"R{base + 7}", "series"), shunt, sense),
        "c_sense": two_pin(capacitor(f"C{base + 10}", "filter"), sense, gnd),
        "amplifier": amplifier,
        "c_amplifier": two_pin(capacitor(f"C{base + 11}", "decoupling"), v33, gnd),
        "r_current": two_pin(resistor(f"R{base + 8}", "series"), amplified, current),
        "c_current": two_pin(capacitor(f"C{base + 12}", "filter"), current, gnd),
        "r_fb_top": two_pin(resistor(f"R{base + 9}", "divider_top"), out, voltage),
        "r_fb_bottom": two_pin(resistor(f"R{base + 10}", "divider_bottom"), voltage, gnd),
        "c_fb": two_pin(capacitor(f"C{base + 13}", "filter"), voltage, gnd),
        "d_tvs": tvs,
        "terminal": two_pin(terminal(f"J{base + 1}", f"OUT{n}"), out, gnd),
        "r_led": two_pin(resistor(f"R{base + 11}", "led"), out, led),
        "d_led": diode(
            Part(f"D{base + 3}", "Device:LED", footprint=FOOTPRINTS["led"], value="LED"), led, gnd
        ),
        "r_enable": two_pin(resistor(f"R{base + 12}", "pull"), signals["DRV_EN"], enable),
        "ntc": two_pin(ntc, enable, gnd),
        "c_enable": two_pin(capacitor(f"C{base + 14}", "decoupling"), enable, gnd),
        "r_pwm": two_pin(resistor(f"R{base + 13}", "pull"), pwm, gnd),
    }
    for role, (dx, dy, rot) in CHANNEL_PLAN.items():
        part = parts[role]
        module.add(part)
        part.place(mm(x + dx), mm(y + dy), rot=rot, locked=part.ref.startswith(LOCKED))
    # The high-side transistor sheds its heat through its drain tab into the VIN48 plane, and the
    # driver stays near both gates.
    design.stitch(f"ch{n}_thermal", net=vin48, region=q_high.pad(DPAK_PADS["D"]), **thermal())
    gates = (q_high.pad(DPAK_PADS["G"]), q_low.pad(DPAK_PADS["G"]))
    design.near(f"ch{n}_gates", gates, driver, within=mm(NEAR["gate"]))
    return module


def high_voltage_sense() -> Module:
    """The isolated sense of a high-voltage bus: a divider of eight resistors, an isolated amplifier
    and an isolated DC/DC converter. The two isolators bridge the gap; everything on the far side is
    of the net class ``HV``."""
    module = Module("hv")
    bus, tap, input_ = net("HV_BUS", "HV"), net("HV_SENSE", "HV"), net("HV_VINP", "HV")
    # The outputs are named HI and LO, not P and N: KiCad would pair P and N by name, and the board has one
    # pair, the USB one.
    out_p, out_n = net("HV_OUT_HI", "SIG"), net("HV_OUT_LO", "SIG")
    module.add(two_pin(terminal("J6", "HV"), bus, hv_rtn))
    upper = bus
    for index in range(8):
        lower = tap if index == 7 else net(f"HV_DIV{index + 1}", "HV")
        module.add(two_pin(resistor(f"R{13 + index}", "hv_string", "1206r"), upper, lower))
        upper = lower
    tvs = Part("D8", "Device:D_TVS", footprint=FOOTPRINTS["sma"], value="TVS")
    connect(tap, tvs["A1"])
    connect(hv_rtn, tvs["A2"])
    amplifier = Part("U6", "Isolator_Analog:AMC1200BDWV", value="ISO")
    connect(hv_5v, amplifier["VDD1"])
    connect(input_, amplifier["VINP"])
    connect(hv_rtn, amplifier["VINN"], amplifier["GND1"])
    connect(gnd, amplifier["GND2"])
    connect(out_n, amplifier["VOUTN"])
    connect(out_p, amplifier["VOUTP"])
    connect(v33, amplifier["VDD2"])
    converter = Part("U7", "Converter_DCDC_Isolated:ADuM6000", footprint=FOOTPRINTS["soic16w"], value="DCDC")
    connect(v5, converter[1], converter[7], converter["RC_SEL"])
    connect(gnd, converter[2], converter[8], converter["RC_IN"])
    no_connect(converter["RC_OUT"])
    connect(hv_rtn, converter[9], converter[15])
    connect(hv_5v, converter[10], converter[16], converter["V_SEL"])
    module.add(
        two_pin(resistor("R21", "hv_bottom"), tap, hv_rtn),
        tvs,
        two_pin(resistor("R22", "series"), tap, input_),
        two_pin(capacitor("C24", "filter"), input_, hv_rtn),
        amplifier,
        converter,
        two_pin(capacitor("C25", "decoupling"), hv_5v, hv_rtn),
        two_pin(capacitor("C26", "ceramic", "0805c"), hv_5v, hv_rtn),
        two_pin(capacitor("C30", "ceramic", "0805c"), hv_5v, hv_rtn),
        two_pin(capacitor("C27", "decoupling"), v33, gnd),
        two_pin(capacitor("C28", "ceramic", "0805c"), v5, gnd),
        two_pin(resistor("R23", "series"), out_p, signals["HV_SENSE_HI"]),
        two_pin(resistor("R24", "series"), out_n, signals["HV_SENSE_LO"]),
        two_pin(capacitor("C29", "filter"), signals["HV_SENSE_HI"], signals["HV_SENSE_LO"]),
    )
    return module


def mounting_holes() -> None:
    """Four plated mounting holes on ground, one in each corner, each in a keep-out of tracks and vias."""
    width, height = BOARD
    corners = (
        (HOLE_INSET, HOLE_INSET),
        (width - HOLE_INSET, HOLE_INSET),
        (HOLE_INSET, height - HOLE_INSET),
        (width - HOLE_INSET, height - HOLE_INSET),
    )
    for index, (x, y) in enumerate(corners, start=1):
        hole = design.hole(f"H{index}", mm(x), mm(y), drill=mm(HOLE["drill"]), pad=mm(HOLE["pad"]))
        connect(gnd, hole[1])
        octagon = clear_outline(mm(x).nm, mm(y).nm, mm(HOLE["keepout"]).nm)  # integer nanometres
        outline = tuple((nm(point.x), nm(point.y)) for point in octagon)
        design.rule_area(f"keepout_H{index}", outline, forbid=HOLE_KEEPOUT)


def assembly_features() -> None:
    """Three global fiducials, two tooling holes and the test points of the supplies."""
    for ref, (x, y) in FIDUCIALS.items():
        design.fiducial(
            ref,
            mm(x),
            mm(y),
            copper=mm(FIDUCIAL["copper"]),
            mask=mm(FIDUCIAL["mask"]),
            clear=mm(FIDUCIAL["clear"]),
        )
    for ref, (x, y) in TOOLING.items():
        design.tooling_hole(
            ref, mm(x), mm(y), drill=mm(TOOLING_HOLE["drill"]), clear=mm(TOOLING_HOLE["clear"])
        )
    by_name = {found.name: found for found in (gnd, v33, v5, v12, vin48)}
    for ref, (name, x, y) in TEST_POINTS.items():
        design.test_point(ref, by_name[name], mm(x), mm(y), size=mm(TEST_PAD))


def thermal() -> dict[str, object]:
    """The arguments of a thermal array: pitch, via size, margin and the protection of a via in a pad."""
    return {
        "pitch": mm(THERMAL["pitch"]),
        "diameter": mm(THERMAL["diameter"]),
        "drill": mm(THERMAL["drill"]),
        "margin": mm(THERMAL["margin"]),
        "protection": protect(filling=True, capping=True),
    }


def rectangle(left: float, top: float, right: float, bottom: float) -> tuple[tuple[object, object], ...]:
    return ((mm(left), mm(top)), (mm(right), mm(top)), (mm(right), mm(bottom)), (mm(left), mm(bottom)))


design = Design("yardstick")
width, height = BOARD
# A rectangle: a board declared with outline= (a rounded one) takes no stack-up and no rule area on this
# base (docs/evidence/yardstick.md, "Stages").
design.board(mm(width), mm(height), copper=COPPER, planes=PLANES)
design.stackup(*stack.preset(STACKUP), finish=FINISH, impedance_controlled=True)
design.sheet("A3")
for axis, top, end in SLOTS:
    design.cutout(shape.slot((mm(axis), mm(top)), (mm(axis), mm(end)), mm(SLOT_WIDTH)))

class_nets: dict[str, list[Net]] = {name: [] for name in CLASSES}
gnd, vin48, v12 = net("GND", "PWR"), net("VIN48", "PWR"), net("+12V", "PWR")
v5, v33, v33a, sgnd = net("+5V", "PWR"), net("+3V3", "PWR"), net("+3V3A", "PWR"), net("SGND", "PWR")
hv_rtn, hv_5v = net("HV_RTN", "HV"), net("HV_5V", "HV")
# The nets between the controller and the rest of the board, by name; the USB pair has a class of its own.
signals = {name: net(name, "USB" if name.startswith("USB_") else "SIG") for name in CONTROLLER_PINS}
for number in range(1, CHANNELS + 1):
    for name in ("PWM", "ISENSE", "VSENSE"):
        signals[f"CH{number}_{name}"] = net(f"CH{number}_{name}", "SIG")

usb_module, usb = usb_port()
design.add(power_input(), controller(), can_port(), usb_module, high_voltage_sense())
for number in range(1, CHANNELS + 1):
    column, row = (number - 1) % 4, (number - 1) // 4
    design.add(channel(number, CELLS_AT[0] + column * CELL[0], CELLS_AT[1] + row * CELL[1]))
for supply in (vin48, v12, v5, v33, v33a):
    design.add(Power(supply, gnd))
design.add(Power(hv_5v, hv_rtn))
mounting_holes()
assembly_features()

# The parts outside the channels, each at its place of the floor plan.
for part in design.parts.values():
    if part.ref in SHARED_PLAN:
        px, py, rotation = SHARED_PLAN[part.ref]
        part.place(mm(px), mm(py), rot=rotation, locked=part.ref.startswith(LOCKED))

# Net classes, the board's minimums and the rules of the high-voltage gap.
for name, (clearance, track) in CLASSES.items():
    pair_values = {key: mm(value) for key, value in PAIR_CLASS.items()} if name == "USB" else {}
    design.rules.netclass(
        name, clearance=mm(clearance), track_width=mm(track), nets=tuple(class_nets[name]), **pair_values
    )
    design.rules.minimum(clearance=mm(clearance), netclass=name)
design.rules.minimum(**{kind: mm(value) for kind, value in MINIMUMS.items()})
low_voltage = select.netclass("PWR") | select.netclass("SIG") | select.netclass("USB")
design.rules.rule(
    "hv_clearance", "clearance", where=select.netclass("HV"), between=low_voltage, min=mm(HV_CLEARANCE)
)
design.rules.rule(
    "hv_creepage", "creepage", where=select.netclass("HV"), between=low_voltage, min=mm(HV_CREEPAGE)
)
# The high-voltage strip is a rule area: inside it, two nets of class HV keep a clearance of their own.
strip = design.rule_area("HV", rectangle(*STRIP))
design.rules.rule(
    "hv_area_clearance",
    "clearance",
    where=select.area(strip) & select.netclass("HV"),
    between=select.netclass("HV"),
    min=mm(HV_AREA_CLEARANCE),
)

# The USB pair: its limits and its impedance target, on the top layer over the ground plane.
design.rules.pair(usb, priority=PAIR_PRIORITY, **{key: mm(value) for key, value in PAIR_RULES.items()})
design.rules.impedance(
    "USB90",
    ohms=ohm(IMPEDANCE["ohms"]),
    pair=usb,
    tolerance=IMPEDANCE["tolerance"],
    layers=(
        trace(
            str(IMPEDANCE["layer"]),
            refs=str(IMPEDANCE["refs"]),
            width=mm(PAIR_CLASS["diff_pair_width"]),
            gap=mm(PAIR_CLASS["diff_pair_gap"]),
        ),
    ),
)

# Inner planes: ground under the whole low-voltage area (round the strip, so that the four holes reach it),
# +3V3 under the controller and VIN48 under the channels, and the high-voltage return on both inner
# layers under its strip, GAP away from the others.
low_right, right = STRIP[0] - GAP, width - EDGE
bottom = height - EDGE
around = (
    (EDGE, EDGE), (right, EDGE), (right, STRIP[1] - GAP), (low_right, STRIP[1] - GAP),
    (low_right, STRIP[3] + GAP), (right, STRIP[3] + GAP), (right, bottom), (EDGE, bottom),
)  # fmt: skip
design.zone(gnd, layers=ZONE_LAYERS["ground"], outline=tuple((mm(x), mm(y)) for x, y in around))
design.zone(v33, layers=ZONE_LAYERS["supply"], outline=rectangle(EDGE, EDGE, SPLIT_X - EDGE, bottom))
design.zone(vin48, layers=ZONE_LAYERS["supply"], outline=rectangle(SPLIT_X, EDGE, low_right, bottom))
design.zone(hv_rtn, layers=ZONE_LAYERS["return"], outline=rectangle(*STRIP))
