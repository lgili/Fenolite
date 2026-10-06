# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Offline, Fenolite-authored reusable schematic symbols and footprint definitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import pairwise

from fenolite.catalog._symbol_expansion import SYMBOL_SPECS, symbol_graph
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic, Pad, Padstack
from fenolite.model.circuit import PinType
from fenolite.model.library import FootprintDef, SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit

_NM = 1_000_000
_STROKE = 254_000
_GRID = 2_540_000
_HALF_GRID = 1_270_000


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Stable metadata for one catalog definition."""

    lib_id: str
    kind: str
    category: str
    summary: str
    evidence: str
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SymbolSpec:
    name: str
    category: str
    reference: str
    summary: str
    sources: tuple[str, ...]


_SYMBOL_SPECS = (
    _SymbolSpec("Resistor", "Passive", "R", "Generic two-terminal resistor", ("S-0314", "S-0343")),
    _SymbolSpec("Capacitor", "Passive", "C", "Generic non-polarized capacitor", ("S-0314",)),
    _SymbolSpec("Capacitor_Polarized", "Passive", "C", "Generic polarized capacitor", ("S-0314",)),
    _SymbolSpec("Capacitor_Ceramic", "Passive", "C", "Generic ceramic capacitor", ("S-0314", "S-0328")),
    _SymbolSpec(
        "Capacitor_Electrolytic",
        "Passive",
        "C",
        "Generic polarized electrolytic capacitor",
        ("S-0314", "S-0329"),
    ),
    _SymbolSpec(
        "Capacitor_Film", "Passive", "C", "Generic non-polarized film capacitor", ("S-0314", "S-0329")
    ),
    _SymbolSpec("Inductor", "Passive", "L", "Generic inductor", ("S-0314",)),
    _SymbolSpec("Common_Mode_Choke", "Passive", "L", "Conceptual two-winding common-mode choke", ("S-0345",)),
    _SymbolSpec("Ferrite_Bead", "Passive", "FB", "Generic two-terminal ferrite bead", ("S-0318",)),
    _SymbolSpec("Diode", "Discrete semiconductor", "D", "Generic two-terminal rectifier diode", ("S-0319",)),
    _SymbolSpec("Zener_Diode", "Discrete semiconductor", "D", "Generic Zener diode", ("S-0319", "S-0344")),
    _SymbolSpec("LED", "Optoelectronic semiconductor", "D", "Generic light-emitting diode", ("S-0319",)),
    _SymbolSpec(
        "Dual_LED_Common_Cathode",
        "Optoelectronic semiconductor",
        "D",
        "Conceptual common cathode dual LED; not a package pinout",
        ("S-0347",),
    ),
    _SymbolSpec(
        "Bridge_Rectifier",
        "Discrete semiconductor",
        "BR",
        "Generic four-terminal bridge rectifier",
        ("S-0329", "S-0342"),
    ),
    _SymbolSpec(
        "Optocoupler",
        "Optoelectronic semiconductor",
        "U",
        "Generic LED-to-photodetector coupler block",
        ("S-0325",),
    ),
    _SymbolSpec("Fuse", "Protection", "F", "Generic two-terminal fuse", ("S-0326",)),
    _SymbolSpec(
        "Varistor", "Protection", "RV", "Generic two-terminal voltage-dependent resistor", ("S-0320",)
    ),
    _SymbolSpec("Surge_Suppressor", "Protection", "D", "Generic two-terminal surge suppressor", ("S-0320",)),
    _SymbolSpec(
        "Gas_Discharge_Tube",
        "Protection",
        "SA",
        "Generic non-polar two-electrode discharge tube",
        ("S-0346",),
    ),
    _SymbolSpec(
        "Operational_Amplifier",
        "Power and control IC",
        "U",
        "Conceptual five-function op amp; not a device pinout",
        ("S-0317", "S-0341"),
    ),
    _SymbolSpec(
        "Comparator", "Power and control IC", "U", "Conceptual comparator; not a device pinout", ("S-0317",)
    ),
    _SymbolSpec(
        "Linear_Regulator",
        "Power and control IC",
        "U",
        "Conceptual three-function linear regulator; not a device pinout",
        ("S-0316", "S-0332"),
    ),
    _SymbolSpec(
        "Offline_Power_Controller",
        "Power and control IC",
        "U",
        "Conceptual offline power-controller block; not a device pinout",
        ("S-0316", "S-0330"),
    ),
    _SymbolSpec(
        "Microcontroller",
        "Power and control IC",
        "U",
        "Conceptual controller block; not a device pinout",
        ("S-0316",),
    ),
    _SymbolSpec(
        "Power_Module",
        "Power and control IC",
        "U",
        "Conceptual power-module block; not a device pinout",
        ("S-0316", "S-0331"),
    ),
    _SymbolSpec(
        "Connector_2", "Electromechanical interface", "J", "Generic two-circuit connector", ("S-0324",)
    ),
    _SymbolSpec(
        "Connector_3", "Electromechanical interface", "J", "Generic three-circuit connector", ("S-0324",)
    ),
    _SymbolSpec(
        "Connector_4", "Electromechanical interface", "J", "Generic four-circuit connector", ("S-0324",)
    ),
    _SymbolSpec(
        "Terminal_1Pin", "Electromechanical interface", "J", "Generic single-circuit terminal", ("S-0324",)
    ),
) + tuple(_SymbolSpec(*spec) for spec in SYMBOL_SPECS)

_FOOTPRINT_SPECS = (
    (
        "SW_Tact_Wurth_430181038816",
        "Switch land",
        "Wurth 4.5 mm SMT tact switch, terminals 1-2 and 3-4 internally common",
        ("S-0417",),
    ),
    (
        "SW_Tact_Wurth_430186043716",
        "Switch land",
        "Wurth 6 mm THT tact switch, terminals 1-3 and 2-4 internally common",
        ("S-0418",),
    ),
    (
        "C_Electrolytic_Panasonic_FR_D5_P2",
        "Through-hole passive",
        "Panasonic FR 5 mm nominal body and 2 mm straight-lead pitch, pad 1 positive",
        ("S-0419",),
    ),
    (
        "C_Electrolytic_Panasonic_FR_D6.3_P2.5",
        "Through-hole passive",
        "Panasonic FR 6.3 mm nominal body and 2.5 mm straight-lead pitch, pad 1 positive",
        ("S-0419",),
    ),
    (
        "MountingHole_M2_D2.4",
        "Mechanical",
        "Generic non-plated 2.4 mm M2 clearance hole with inferred 5 mm hardware guide",
        ("S-0420",),
    ),
    (
        "MountingHole_M3_D3.4",
        "Mechanical",
        "Generic non-plated 3.4 mm M3 clearance hole with inferred 7 mm hardware guide",
        ("S-0420",),
    ),
    (
        "TestPoint_SMD_D1.0",
        "Test access",
        "Generic 1 mm circular exposed test pad without solder paste",
        ("S-0421",),
    ),
    (
        "LED5050_Worldsemi_WS2812B_V6",
        "LED land",
        "Worldsemi WS2812B-V6 four-terminal addressable LED, manufacturer suggested lands",
        ("S-0422",),
    ),
    (
        "LED0603_Kingbright_APT1608SURCK",
        "LED land",
        "Kingbright APT1608SURCK LED suggested land, pin 1 cathode",
        ("S-0412",),
    ),
    (
        "LED0805_Kingbright_APT2012SURCK",
        "LED land",
        "Kingbright APT2012SURCK LED suggested land, pin 1 cathode",
        ("S-0413",),
    ),
    (
        "R_Axial_Vishay_MRS16_P7.62",
        "Through-hole passive",
        "Vishay MRS16 with inferred 7.62 mm formed-lead pitch",
        ("S-0414",),
    ),
    (
        "R_Axial_Vishay_MRS25_P10.16",
        "Through-hole passive",
        "Vishay MRS25 with inferred 10.16 mm formed-lead pitch",
        ("S-0414",),
    ),
    (
        "C_Film_Wima_MKS02_L4.6_W2.5_P2.5",
        "Through-hole passive",
        "Wima MKS02 4.6 by 2.5 mm nominal body, 2.5 mm lead pitch",
        ("S-0415",),
    ),
    (
        "C_Film_Wima_MKS2_L7.2_W2.5_P5",
        "Through-hole passive",
        "Wima MKS2 7.2 by 2.5 mm nominal body, 5 mm lead pitch",
        ("S-0415",),
    ),
    (
        "Crystal_3225_Abracon_ABM8",
        "Crystal land",
        "Abracon ABM8 four-pad crystal suggested land",
        ("S-0416",),
    ),
    (
        "Header_1x1_P2.54",
        "Through-hole connector",
        "1-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_1x2_P2.54",
        "Through-hole connector",
        "2-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_1x3_P2.54",
        "Through-hole connector",
        "3-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_1x4_P2.54",
        "Through-hole connector",
        "4-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_1x6_P2.54",
        "Through-hole connector",
        "6-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_1x8_P2.54",
        "Through-hole connector",
        "8-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_1x10_P2.54",
        "Through-hole connector",
        "10-position generic 2.54 mm single-row header",
        ("S-0408",),
    ),
    (
        "Header_2x3_P2.54",
        "Through-hole connector",
        "6-position generic 2.54 mm double-row header",
        ("S-0409",),
    ),
    (
        "Header_2x5_P2.54",
        "Through-hole connector",
        "10-position generic 2.54 mm double-row header",
        ("S-0409",),
    ),
    (
        "JST_XH_B2B_XH_A",
        "Through-hole connector",
        "JST B2B-XH-A vertical header without locating boss",
        ("S-0410",),
    ),
    (
        "JST_XH_B4B_XH_A",
        "Through-hole connector",
        "JST B4B-XH-A vertical header without locating boss",
        ("S-0410",),
    ),
    (
        "MicroUSB_B_Wurth_629105150521",
        "Mixed-mount connector",
        "Wurth 629105150521 micro-B with slotted shell anchors and two locating pegs",
        ("S-0411",),
    ),
    ("Chip_0201_Vishay_Draloric", "Chip passive", "0201 Vishay Draloric reflow resistor land", ("S-0333",)),
    ("Chip_0402", "Chip passive", "Generic two-terminal 0402 chip land", ("S-0315", "S-0333")),
    ("Chip_0603", "Chip passive", "Generic two-terminal 0603 chip land", ("S-0315", "S-0333")),
    ("Chip_0805", "Chip passive", "Generic two-terminal 0805 chip land", ("S-0315", "S-0333")),
    ("Chip_1206", "Chip passive", "Generic two-terminal 1206 chip land", ("S-0315", "S-0333")),
    ("Chip_1210_Vishay_Draloric", "Chip passive", "1210 Vishay Draloric reflow resistor land", ("S-0333",)),
    (
        "Chip_1812_TDK_CGA8",
        "Chip capacitor",
        "1812 TDK CGA8 MLCC land at recommended range midpoints",
        ("S-0358",),
    ),
    ("Chip_2010_Vishay_RCWP", "Chip passive", "2010 Vishay RCWP resistor land", ("S-0353", "S-0357")),
    ("Chip_2512_Vishay_RCWP", "Chip passive", "2512 Vishay RCWP resistor land", ("S-0353", "S-0357")),
    (
        "MELF_0102_Vishay_MMU",
        "Cylindrical resistor",
        "0102 Vishay MMU MELF reflow resistor land",
        ("S-0333", "S-0354"),
    ),
    ("DO214AA_Diodes_SMB", "Diode package", "Diodes SMB / DO-214AA reference land", ("S-0359", "S-0446")),
    ("DO214AB_Diodes_SMC", "Diode package", "Diodes SMC / DO-214AB reference land", ("S-0441", "S-0446")),
    ("SOD123_Diodes", "Diode package", "Diodes SOD123 suggested land", ("S-0442",)),
    ("SOD123F_Diodes_Standard", "Diode package", "Diodes SOD123F Standard suggested land", ("S-0443",)),
    ("SOD323_Diodes", "Diode package", "Diodes SOD323 suggested land", ("S-0444",)),
    ("SOD523_Diodes", "Diode package", "Diodes SOD523 suggested land", ("S-0445",)),
    ("SOD128_Nexperia_CFP5", "Diode package", "Nexperia SOD128 / CFP5 reflow land", ("S-0375",)),
    (
        "DO35_P10.16_Diodes",
        "Axial diode",
        "Diodes DO-35 body at an authored 10.16 mm bend pitch",
        ("S-0370",),
    ),
    (
        "DO41_P10.16_Diodes",
        "Axial diode",
        "Diodes DO-41 body at an authored 10.16 mm bend pitch",
        ("S-0371",),
    ),
    ("SOT23_3", "Small-outline semiconductor", "Three-lead SOT-23 package land", ("S-0322", "S-0334")),
    ("SOT23_5", "Small-outline IC", "Five-lead SOT-23 package land", ("S-0323", "S-0335")),
    ("SOT23_6_TI_DBV0006A", "Small-outline IC", "Six-lead TI DBV0006A SOT-23 package land", ("S-0355",)),
    ("SC70_5", "Small-outline IC", "Five-lead SC-70 package land", ("S-0323", "S-0335")),
    ("SC70_6_TI_DCK0006A", "Small-outline IC", "Six-lead TI DCK0006A SC-70 package land", ("S-0356",)),
    (
        "SOT323_3_Diodes_Standard",
        "Small-outline semiconductor",
        "Three-lead Diodes SOT323 Standard land",
        ("S-0447",),
    ),
    ("SOT523_3_Diodes", "Small-outline semiconductor", "Three-lead Diodes SOT523 land", ("S-0448",)),
    ("SOT563_6_Diodes", "Small-outline semiconductor", "Six-lead Diodes SOT563 land", ("S-0449",)),
    ("SOT89_3", "Small-outline semiconductor", "Three-lead SOT89 package land", ("S-0322", "S-0338")),
    ("SOT143_4_Diodes", "Small-outline semiconductor", "Diodes SOT143 four-lead suggested land", ("S-0369",)),
    ("SOT223_3_Diodes", "Power semiconductor", "Diodes SOT223-3 suggested land", ("S-0372",)),
    (
        "SOT883_3_Nexperia_DFN1006",
        "Leadless semiconductor",
        "Nexperia SOT883-2 / DFN1006-3 reflow land",
        ("S-0376",),
    ),
    ("TO252_3_Diodes_Standard", "Power semiconductor", "Diodes TO252 Standard suggested land", ("S-0373",)),
    ("TO263_3_Diodes_Standard", "Power semiconductor", "Diodes TO263AB Standard suggested land", ("S-0374",)),
    (
        "TO220_3_Diodes_Vertical",
        "Through-hole semiconductor",
        "Diodes TO220-3 vertical inferred through-hole land",
        ("S-0377",),
    ),
    (
        "SOIC_8",
        "Small-outline IC",
        "Eight-lead 1.27 mm-pitch small-outline package land",
        ("S-0323", "S-0336"),
    ),
    ("SOIC14_TI_D0014A", "Small-outline IC", "TI D0014A narrow 14-lead SOIC land", ("S-0378",)),
    ("SOIC16_TI_D0016A", "Small-outline IC", "TI D0016A narrow 16-lead SOIC land", ("S-0379",)),
    ("SOIC20_TI_DW0020A", "Small-outline IC", "TI DW0020A wide 20-lead SOIC land", ("S-0380",)),
    ("SOIC24_Microchip_K3X", "Small-outline IC", "Microchip K3X wide 24-lead SOIC land", ("S-0381",)),
    ("SOIC28_MPS_Wide", "Small-outline IC", "MPS wide 28-lead SOIC land", ("S-0382",)),
    ("TSSOP8_Diodes", "Small-outline IC", "Diodes eight-lead TSSOP land", ("S-0383",)),
    ("TSSOP14_Diodes", "Small-outline IC", "Diodes fourteen-lead TSSOP land", ("S-0384",)),
    ("TSSOP16_Diodes_A1", "Small-outline IC", "Diodes sixteen-lead TSSOP Type A1 land", ("S-0385",)),
    ("TSSOP20_Diodes", "Small-outline IC", "Diodes twenty-lead TSSOP land", ("S-0386",)),
    ("TSSOP24_TI_PW0024A", "Small-outline IC", "TI PW0024A TSSOP land", ("S-0387",)),
    ("TSSOP28_Microchip_NRB", "Small-outline IC", "Microchip NRB TSSOP28 land", ("S-0388",)),
    ("MSOP8_Diodes", "Small-outline IC", "Diodes eight-lead MSOP land", ("S-0389",)),
    ("MSOP10_Diodes", "Small-outline IC", "Diodes ten-lead MSOP land", ("S-0390",)),
    ("SSOP16_Diodes_CJ", "Small-outline IC", "Diodes sixteen-lead SSOP Type CJ land", ("S-0391",)),
    (
        "QFN16_Diodes_W3030_A1",
        "Leadless IC",
        "Diodes W-QFN3030-16 Type A1 land with EP",
        ("S-0392", "S-0397"),
    ),
    ("QFN20_Diodes_U4040", "Leadless IC", "Diodes U-QFN4040-20 land with EP", ("S-0393", "S-0397")),
    (
        "QFN24_Diodes_W4040_SWP_A1",
        "Leadless IC",
        "Diodes W-QFN4040-24 SWP Type A1 land with EP",
        ("S-0394", "S-0397"),
    ),
    (
        "QFN28_Diodes_W5050_A1",
        "Leadless IC",
        "Diodes W-QFN5050-28 Type A1 land with EP",
        ("S-0395", "S-0397"),
    ),
    ("QFN32_Diodes_W5050", "Leadless IC", "Diodes standard W-QFN5050-32 land with EP", ("S-0396", "S-0397")),
    (
        "DO214AC",
        "Diode package",
        "Two-terminal DO-214AC / SMA land from manufacturer suggested layout",
        ("S-0321",),
    ),
    (
        "QFN48_TI_RGZ0048A",
        "Leadless IC",
        "TI RGZ0048A VQFN48 land with EP",
        (
            "S-0398",
            "S-0397",
        ),
    ),
    (
        "DFN6_Diodes_W2020_US",
        "Leadless IC",
        "Diodes W-DFN2020-6 Type US land with EP",
        (
            "S-0399",
            "S-0397",
        ),
    ),
    (
        "DFN8_Diodes_W3030_UXF",
        "Leadless IC",
        "Diodes W-DFN3030-8 Type UXF land with EP",
        (
            "S-0400",
            "S-0397",
        ),
    ),
    ("TQFP44_Microchip_PT", "Leaded IC", "Microchip PT thin QFP44 land", ("S-0401",)),
    ("LQFP48_TI_PT0048A", "Leaded IC", "TI PT0048A low-profile QFP48 land", ("S-0402",)),
    ("LQFP64_TI_PM0064A", "Leaded IC", "TI PM0064A low-profile QFP64 land", ("S-0403",)),
    ("LQFP100_TI_PZ0100A", "Leaded IC", "TI PZ0100A low-profile QFP100 land", ("S-0404",)),
    (
        "DIP4_Vishay_VO617A",
        "Through-hole IC",
        "4-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0405",),
    ),
    (
        "DIP6_Vishay_CNY17",
        "Through-hole IC",
        "6-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0406",),
    ),
    (
        "DIP8_Microchip_P",
        "Through-hole IC",
        "8-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0407",),
    ),
    (
        "DIP14_Microchip_P",
        "Through-hole IC",
        "14-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0407",),
    ),
    (
        "DIP16_Microchip_P",
        "Through-hole IC",
        "16-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0407",),
    ),
    (
        "DIP20_Microchip_P",
        "Through-hole IC",
        "20-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0407",),
    ),
    (
        "DIP28_Microchip_SP",
        "Through-hole IC",
        "28-lead manufacturer body with inferred 7.62 mm through-hole land",
        ("S-0407",),
    ),
    ("LQFP32_P0.8", "Leaded IC", "32-lead LQFP package with 0.8 mm pitch", ("S-0327", "S-0337")),
    (
        "Header_1x2_P2.5",
        "Through-hole connector",
        "Two-position 2.5 mm-pitch generic header land",
        ("S-0324",),
    ),
    (
        "Header_1x3_P2.5",
        "Through-hole connector",
        "Three-position 2.5 mm-pitch generic header land",
        ("S-0324",),
    ),
    (
        "Header_1x4_P2.5",
        "Through-hole connector",
        "Four-position 2.5 mm-pitch generic header land",
        ("S-0324",),
    ),
)

_FOOTPRINT_NAMES = tuple(spec[0] for spec in _FOOTPRINT_SPECS)
ENTRIES = tuple(
    sorted(
        [
            CatalogEntry(
                f"Fenolite:{spec.name}", "symbol", spec.category, spec.summary, "INFERRED", spec.sources
            )
            for spec in _SYMBOL_SPECS
        ]
        + [
            CatalogEntry(f"Fenolite:{name}", "footprint", category, summary, "INFERRED", sources)
            for name, category, summary, sources in _FOOTPRINT_SPECS
        ],
        key=lambda entry: entry.lib_id,
    )
)


def list_entries(*, kind: str | None = None, query: str | None = None) -> tuple[CatalogEntry, ...]:
    """List entries in stable ID order, optionally filtering by kind and case-insensitive text."""
    found = ENTRIES
    if kind is not None:
        found = tuple(entry for entry in found if entry.kind == kind)
    if query:
        needle = query.casefold()
        found = tuple(
            entry
            for entry in found
            if needle in (entry.lib_id + " " + entry.category + " " + entry.summary).casefold()
        )
    return tuple(sorted(found, key=lambda entry: entry.lib_id))


def _pin(
    number: str,
    name: str,
    x: int,
    y: int,
    *,
    etype: PinType = "passive",
    rotation: int = 0,
    length: int = _GRID,
) -> SymbolPin:
    return SymbolPin(number, name, etype, Point(x, y), rotation=rotation, length=length, unit=1, body_style=1)  # type: ignore[arg-type]


def _line(a: tuple[int, int], b: tuple[int, int], width: int = _STROKE) -> SymbolGraphic:
    return SymbolGraphic("line", (Point(*a), Point(*b)), width)


def _rect(x1: int, y1: int, x2: int, y2: int, width: int = _STROKE, *, filled: bool = False) -> SymbolGraphic:
    return SymbolGraphic("rect", (Point(x1, y1), Point(x2, y2)), width, filled)


def _coil_path(start_x: int, baseline: int, direction: int) -> tuple[SymbolGraphic, ...]:
    heights = (
        0,
        248_000,
        486_000,
        705_000,
        898_000,
        1_057_000,
        1_174_000,
        1_246_000,
        1_270_000,
        1_246_000,
        1_174_000,
        1_057_000,
        898_000,
        705_000,
        486_000,
        248_000,
        0,
    )
    return tuple(
        _line(
            (start_x + coil * _HALF_GRID + step * 79_375, baseline + direction * heights[step]),
            (start_x + coil * _HALF_GRID + (step + 1) * 79_375, baseline + direction * heights[step + 1]),
        )
        for coil in range(4)
        for step in range(16)
    )


def _symbol_graph(name: str) -> tuple[tuple[SymbolPin, ...], tuple[SymbolGraphic, ...]]:
    expanded = symbol_graph(name)
    if expanded is not None:
        return expanded

    def left(
        number: str,
        label: str,
        y: int = 0,
        etype: PinType = "passive",
        *,
        outer: int = 2 * _GRID,
        length: int = _GRID,
    ) -> SymbolPin:
        return _pin(number, label, -outer, y, etype=etype, rotation=0, length=length)

    def right(
        number: str,
        label: str,
        y: int = 0,
        etype: PinType = "passive",
        *,
        outer: int = 2 * _GRID,
        length: int = _GRID,
    ) -> SymbolPin:
        return _pin(number, label, outer, y, etype=etype, rotation=180_000_000, length=length)

    two = (left("1", "A"), right("2", "B"))
    if name in {
        "Resistor",
        "Capacitor",
        "Capacitor_Polarized",
        "Capacitor_Ceramic",
        "Capacitor_Electrolytic",
        "Capacitor_Film",
        "Inductor",
        "Ferrite_Bead",
        "Fuse",
        "Varistor",
        "Surge_Suppressor",
    }:
        if name == "Resistor":
            vertices = (
                (-_GRID, 0),
                (-1_905_000, 1_050_000),
                (-1_270_000, -1_050_000),
                (-635_000, 1_050_000),
                (0, -1_050_000),
                (635_000, 1_050_000),
                (1_270_000, -1_050_000),
                (1_905_000, 1_050_000),
                (_GRID, 0),
            )
            return two, tuple(_line(a, b) for a, b in pairwise(vertices))
        if name in {
            "Capacitor",
            "Capacitor_Ceramic",
            "Capacitor_Film",
            "Capacitor_Polarized",
            "Capacitor_Electrolytic",
        }:
            polarized = name in {"Capacitor_Polarized", "Capacitor_Electrolytic"}
            graphics = (
                _line((-_HALF_GRID, -_GRID), (-_HALF_GRID, _GRID)),
                _line((_HALF_GRID, -_GRID), (_HALF_GRID, _GRID), 635_000 if polarized else _STROKE),
            )
            if polarized:
                graphics += (
                    _line((-2_200_000, 1_500_000), (-2_200_000, 2_300_000)),
                    _line((-2_600_000, 1_900_000), (-1_800_000, 1_900_000)),
                )
            labels = ("+", "-") if polarized else ("A", "B")
            return (
                left("1", labels[0], length=3 * _HALF_GRID),
                right("2", labels[1], length=3 * _HALF_GRID),
            ), graphics
        if name == "Inductor":
            return two, _coil_path(-_GRID, 0, 1)
        if name == "Ferrite_Bead":
            return two, (
                _rect(-_GRID, -_HALF_GRID, _GRID, _HALF_GRID),
                _line((-900_000, 800_000), (500_000, -800_000)),
                _line((-100_000, 800_000), (1_300_000, -800_000)),
            )
        if name == "Fuse":
            vertices = (
                (-_GRID, 0),
                (-2_100_000, 300_000),
                (-1_650_000, 650_000),
                (-1_200_000, 800_000),
                (-750_000, 680_000),
                (-350_000, 340_000),
                (0, 0),
                (350_000, -340_000),
                (750_000, -680_000),
                (1_200_000, -800_000),
                (1_650_000, -650_000),
                (2_100_000, -300_000),
                (_GRID, 0),
            )
            return two, tuple(_line(a, b) for a, b in pairwise(vertices))
        if name == "Varistor":
            return two, (
                _rect(-_GRID, -_HALF_GRID, _GRID, _HALF_GRID),
                _line((-1_700_000, 1_800_000), (1_700_000, -1_800_000)),
                _line((1_700_000, -1_800_000), (2_100_000, -1_800_000)),
            )
        if name == "Surge_Suppressor":
            return two, (
                _rect(-_GRID, -_HALF_GRID, _GRID, _HALF_GRID),
                _line((-1_200_000, 650_000), (0, 0)),
                _line((-1_200_000, -650_000), (0, 0)),
                _line((0, 0), (1_200_000, 650_000)),
                _line((0, 0), (1_200_000, -650_000)),
            )
    if name == "Common_Mode_Choke":
        pins = (
            left("1", "A1", 2 * _GRID, outer=3 * _GRID),
            left("2", "A2", -2 * _GRID, outer=3 * _GRID),
            right("3", "B1", 2 * _GRID, outer=3 * _GRID),
            right("4", "B2", -2 * _GRID, outer=3 * _GRID),
        )
        return pins, (
            _line((-2 * _GRID, 2 * _GRID), (-_GRID, 2 * _GRID)),
            *_coil_path(-_GRID, 2 * _GRID, 1),
            _line((_GRID, 2 * _GRID), (2 * _GRID, 2 * _GRID)),
            _line((-2 * _GRID, -2 * _GRID), (-_GRID, -2 * _GRID)),
            *_coil_path(-_GRID, -2 * _GRID, -1),
            _line((_GRID, -2 * _GRID), (2 * _GRID, -2 * _GRID)),
            _line((-_GRID, 750_000), (_GRID, 750_000)),
            _line((-_GRID, -750_000), (_GRID, -750_000)),
        )
    if name == "Gas_Discharge_Tube":
        return two, (
            SymbolGraphic("circle", (Point(0, 0), Point(_GRID, 0)), _STROKE),
            _line((-_GRID, 0), (-1_400_000, 0)),
            _line((-1_400_000, -850_000), (-600_000, 0)),
            _line((-1_400_000, 850_000), (-600_000, 0)),
            _line((_GRID, 0), (1_400_000, 0)),
            _line((1_400_000, -850_000), (600_000, 0)),
            _line((1_400_000, 850_000), (600_000, 0)),
        )
    if name in {"Diode", "Zener_Diode", "LED"}:
        pins = (left("1", "A", length=3 * _HALF_GRID), right("2", "K", length=3 * _HALF_GRID))
        diode_body = SymbolGraphic(
            "polygon",
            (Point(-_HALF_GRID, -1_700_000), Point(_HALF_GRID, 0), Point(-_HALF_GRID, 1_700_000)),
            _STROKE,
            True,
        )
        if name == "Zener_Diode":
            graphics = (
                diode_body,
                _line((900_000, -1_900_000), (_HALF_GRID, -1_400_000)),
                _line((_HALF_GRID, -1_400_000), (_HALF_GRID, 1_400_000)),
                _line((_HALF_GRID, 1_400_000), (1_640_000, 1_900_000)),
            )
        else:
            graphics = (diode_body, _line((_HALF_GRID, -1_900_000), (_HALF_GRID, 1_900_000)))
        if name == "LED":
            graphics += (
                _line((-400_000, 2_000_000), (800_000, 3_200_000)),
                _line((800_000, 2_000_000), (2_000_000, 3_200_000)),
                _line((800_000, 3_200_000), (400_000, 3_100_000)),
                _line((800_000, 3_200_000), (700_000, 2_800_000)),
                _line((2_000_000, 3_200_000), (1_600_000, 3_100_000)),
                _line((2_000_000, 3_200_000), (1_900_000, 2_800_000)),
            )
        return pins, graphics
    if name == "Bridge_Rectifier":

        def diode_branch(start: tuple[int, int], end: tuple[int, int]) -> tuple[SymbolGraphic, ...]:
            sx = 1 if end[0] > start[0] else -1
            sy = 1 if end[1] > start[1] else -1
            base = (start[0] + sx * 1_905_000, start[1] + sy * 1_905_000)
            cathode = (start[0] + sx * 3_175_000, start[1] + sy * 3_175_000)
            side = (-sy * 450_000, sx * 450_000)
            return (
                _line(start, base),
                SymbolGraphic(
                    "polygon",
                    (
                        Point(base[0] + side[0], base[1] + side[1]),
                        Point(*cathode),
                        Point(base[0] - side[0], base[1] - side[1]),
                    ),
                    _STROKE,
                ),
                _line(
                    (cathode[0] + side[0], cathode[1] + side[1]),
                    (cathode[0] - side[0], cathode[1] - side[1]),
                ),
                _line(cathode, end),
            )

        pins = (
            left("1", "~", outer=3 * _GRID),
            right("2", "~", outer=3 * _GRID),
            _pin("3", "+", 0, 3 * _GRID, rotation=270_000_000),
            _pin("4", "-", 0, -3 * _GRID, rotation=90_000_000),
        )
        left_ac, right_ac = (-2 * _GRID, 0), (2 * _GRID, 0)
        positive, negative = (0, 2 * _GRID), (0, -2 * _GRID)
        return pins, (
            *diode_branch(left_ac, positive),
            *diode_branch(right_ac, positive),
            *diode_branch(negative, left_ac),
            *diode_branch(negative, right_ac),
        )
    if name == "Optocoupler":
        pins = (
            left("1", "A", _GRID, outer=3 * _GRID),
            left("2", "K", -_GRID, outer=3 * _GRID),
            right("3", "C", _GRID, outer=3 * _GRID),
            right("4", "E", -_GRID, outer=3 * _GRID),
        )
        return pins, (
            _rect(-2 * _GRID, -2 * _GRID, 2 * _GRID, 2 * _GRID, filled=True),
            _line((-2 * _GRID, _GRID), (-4_250_000, _GRID)),
            _line((-4_250_000, _GRID), (-4_250_000, 0)),
            _line((-4_250_000, 0), (-3_250_000, 0)),
            SymbolGraphic(
                "polygon",
                (Point(-3_250_000, -900_000), Point(-1_750_000, 0), Point(-3_250_000, 900_000)),
                _STROKE,
                True,
            ),
            _line((-1_750_000, -1_100_000), (-1_750_000, 1_100_000)),
            _line((-1_750_000, 0), (-1_750_000, -_GRID)),
            _line((-1_750_000, -_GRID), (-2 * _GRID, -_GRID)),
            _line((-900_000, 1_100_000), (1_000_000, 1_100_000)),
            _line((1_000_000, 1_100_000), (550_000, 1_400_000)),
            _line((1_000_000, 1_100_000), (550_000, 800_000)),
            _line((-900_000, 300_000), (1_000_000, 300_000)),
            _line((1_000_000, 300_000), (550_000, 600_000)),
            _line((1_000_000, 300_000), (550_000, 0)),
            _line((1_900_000, -1_150_000), (1_900_000, 1_150_000)),
            _line((1_900_000, 700_000), (3_200_000, _GRID)),
            _line((3_200_000, _GRID), (2 * _GRID, _GRID)),
            _line((1_900_000, -700_000), (3_200_000, -_GRID)),
            _line((3_200_000, -_GRID), (2 * _GRID, -_GRID)),
        )
    if name == "Dual_LED_Common_Cathode":
        pins = (
            left("1", "A1", _GRID, "input", outer=3 * _GRID),
            left("2", "A2", -_GRID, "input", outer=3 * _GRID),
            right("3", "K", 0, "passive", outer=3 * _GRID),
        )
        graphics = [_rect(-2 * _GRID, -2 * _GRID, 2 * _GRID, 2 * _GRID, filled=True)]
        for y in (_GRID, -_GRID):
            graphics.extend(
                (
                    _line((-2 * _GRID, y), (-1_100_000, y)),
                    SymbolGraphic(
                        "polygon",
                        (Point(-1_100_000, y - 650_000), Point(0, y), Point(-1_100_000, y + 650_000)),
                        _STROKE,
                        True,
                    ),
                    _line((0, y - 750_000), (0, y + 750_000)),
                    _line((0, y), (1_400_000, y)),
                )
            )
        graphics.extend(
            (
                _line((1_400_000, -_GRID), (1_400_000, _GRID)),
                _line((1_400_000, 0), (2 * _GRID, 0)),
            )
        )
        return pins, tuple(graphics)
    if name in {"Operational_Amplifier", "Comparator"}:
        pins = (
            right("1", "", etype="output", outer=3 * _GRID),
            left("2", "+", _GRID, "input", outer=3 * _GRID, length=3 * _HALF_GRID),
            left("3", "-", -_GRID, "input", outer=3 * _GRID, length=3 * _HALF_GRID),
            _pin("4", "V+", 0, 3 * _GRID, etype="power_in", rotation=270_000_000, length=2 * _GRID),
            _pin("5", "V-", 0, -3 * _GRID, etype="power_in", rotation=90_000_000, length=2 * _GRID),
        )
        return pins, (
            SymbolGraphic(
                "polygon",
                (
                    Point(-3 * _HALF_GRID, -2 * _GRID),
                    Point(-3 * _HALF_GRID, 2 * _GRID),
                    Point(3 * _HALF_GRID, 0),
                ),
                _STROKE,
            ),
            _line((3 * _HALF_GRID, 0), (2 * _GRID, 0)),
        )
    if name == "Linear_Regulator":
        pins = (
            left("1", "IN", etype="power_in", outer=3 * _GRID, length=3 * _HALF_GRID),
            _pin("2", "GND", 0, -3 * _GRID, etype="power_in", rotation=90_000_000, length=3 * _HALF_GRID),
            right("3", "OUT", etype="power_out", outer=3 * _GRID, length=3 * _HALF_GRID),
        )
        return pins, (_rect(-3 * _HALF_GRID, -3 * _HALF_GRID, 3 * _HALF_GRID, 3 * _HALF_GRID, filled=True),)
    if name == "Offline_Power_Controller":
        pins = (
            left("1", "VIN", _GRID, "power_in", outer=3 * _GRID),
            left("2", "GND", -_GRID, outer=3 * _GRID),
            right("3", "SW", _GRID, "output", outer=3 * _GRID),
            right("4", "FB", -_GRID, "input", outer=3 * _GRID),
        )
        return pins, (_rect(-2 * _GRID, -2 * _GRID, 2 * _GRID, 2 * _GRID, filled=True),)
    if name == "Microcontroller":
        ys = (2 * _GRID, _GRID, -_GRID, -2 * _GRID)
        pins = tuple(
            left(str(i + 1), label, y, outer=4 * _GRID)
            for i, (label, y) in enumerate(zip(("VDD", "VSS", "RESET", "IO1"), ys, strict=True))
        ) + tuple(
            right(str(i + 5), label, y, outer=4 * _GRID)
            for i, (label, y) in enumerate(zip(("IO2", "CLK", "ADC", "UART"), ys, strict=True))
        )
        return pins, (_rect(-3 * _GRID, -3 * _GRID, 3 * _GRID, 3 * _GRID, filled=True),)
    if name == "Power_Module":
        labels = ("DC+", "DC-", "U", "V", "W", "IN1", "IN2", "IN3")
        ys = (2 * _GRID, _GRID, -_GRID, -2 * _GRID)
        pins = tuple(
            left(str(i + 1), label, ys[i], outer=4 * _GRID) for i, label in enumerate(labels[:4])
        ) + tuple(right(str(i + 5), label, ys[i], outer=4 * _GRID) for i, label in enumerate(labels[4:]))
        return pins, (_rect(-3 * _GRID, -3 * _GRID, 3 * _GRID, 3 * _GRID, filled=True),)
    if name.startswith("Connector_"):
        count = int(name.rsplit("_", 1)[1])
        ys = tuple(((count - 1 - 2 * i) * _GRID) // 2 for i in range(count))
        pins = tuple(left(str(i + 1), "Passive", y) for i, y in enumerate(ys))
        graphics = (
            _rect(-_GRID, ys[-1] - _HALF_GRID, _HALF_GRID, ys[0] + _HALF_GRID, filled=True),
            *(_rect(-_GRID, y - 635_000, -_HALF_GRID, y + 635_000) for y in ys),
        )
        return pins, graphics
    if name == "Terminal_1Pin":
        return (left("1", "Passive", length=4_130_000),), (
            _rect(-950_000, -950_000, 950_000, 950_000),
            _line((100_000, -450_000), (100_000, 450_000)),
        )
    raise KeyError(name)


def _symbol(spec: _SymbolSpec) -> SymbolDef:
    pins, graphics = _symbol_graph(spec.name)
    return SymbolDef(
        id=derived_id("sym", "fenolite.catalog", f"Fenolite:{spec.name}"),
        native_ids={"fenolite": f"Fenolite:{spec.name}"},
        name=spec.name,
        library="Fenolite",
        properties={"Reference": spec.reference, "Value": spec.name, "Description": spec.summary},
        units=(SymbolUnit(1, 1),),
        pins=pins,
        graphics=graphics,
        pin_names_hidden=(
            spec.category in {"Passive", "Protection", "Electromechanical interface"}
            or spec.name in {"Diode", "Zener_Diode", "LED"}
        )
        and spec.name not in {"Potentiometer", "Transformer", "Switch_SPDT", "Pushbutton_NO", "Relay_SPDT"},
    )


def _pad(
    name: str,
    number: str,
    x: int,
    y: int,
    sx: int,
    sy: int,
    *,
    drill: int | None = None,
    pad_id: str | None = None,
) -> Pad:
    kind = "thru_hole" if drill is not None else "smd"
    layers = ("*.Cu", "*.Mask") if drill is not None else ("F.Cu", "F.Paste", "F.Mask")
    return Pad(
        id=derived_id("pad", "fenolite.catalog", f"{name}:{pad_id or number}"),
        number=number,
        shape="circle" if drill is not None else "rect",
        size=Size(sx, sy),
        position=Point(x, y),
        kind=kind,  # type: ignore[arg-type]
        drill=drill,
        layers=layers,
    )


def _outline(name: str, half_x: int, half_y: int, *, courtyard: bool = False) -> tuple[Graphic, ...]:
    layer = "F.CrtYd" if courtyard else "F.Fab"
    width = 50_000 if courtyard else 100_000
    return (
        Graphic(
            id=derived_id("gfx", "fenolite.catalog", f"{name}:{layer}"),
            kind="rect",
            layer=layer,
            points=(Point(-half_x, -half_y), Point(half_x, half_y)),
            width=width,
        ),
    )


def _make_footprint(
    name: str,
    pads: tuple[Pad, ...],
    body_x: int,
    body_y: int,
    *,
    through_hole: bool = False,
    cathode_marker: bool = False,
    cathode_on_left: bool = False,
    cathode_inset: int = 200_000,
    body_center_y: int = 0,
) -> FootprintDef:
    desc = next(spec[2] for spec in _FOOTPRINT_SPECS if spec[0] == name)
    extent_x = max((body_x // 2, *(abs(p.position.x) + p.size.w // 2 for p in pads)))
    extent_y = max((abs(body_center_y) + body_y // 2, *(abs(p.position.y) + p.size.h // 2 for p in pads)))
    fab = _outline(name, body_x // 2, body_y // 2)
    if body_center_y:
        fab = tuple(
            Graphic(
                id=graphic.id,
                kind=graphic.kind,
                layer=graphic.layer,
                points=tuple(Point(point.x, point.y + body_center_y) for point in graphic.points),
                width=graphic.width,
            )
            for graphic in fab
        )
    courtyard = _outline(name, extent_x + 500_000, extent_y + 500_000, courtyard=True)
    if body_center_y:
        lower = (
            min((body_center_y - body_y // 2, *(pad.position.y - pad.size.h // 2 for pad in pads))) - 500_000
        )
        upper = (
            max((body_center_y + body_y // 2, *(pad.position.y + pad.size.h // 2 for pad in pads))) + 500_000
        )
        courtyard = (
            Graphic(
                id=courtyard[0].id,
                kind="rect",
                layer="F.CrtYd",
                points=(Point(-extent_x - 500_000, lower), Point(extent_x + 500_000, upper)),
                width=50_000,
            ),
        )
    graphics = fab + courtyard
    if cathode_marker:
        graphics += (
            Graphic(
                id=derived_id("gfx", "fenolite.catalog", f"{name}:cathode"),
                kind="line",
                layer="F.Fab",
                points=(
                    Point(
                        (-body_x // 2 + cathode_inset) if cathode_on_left else (body_x // 2 - cathode_inset),
                        -(body_y // 2) + 150_000,
                    ),
                    Point(
                        (-body_x // 2 + cathode_inset) if cathode_on_left else (body_x // 2 - cathode_inset),
                        body_y // 2 - 150_000,
                    ),
                ),
                width=100_000,
            ),
        )
    return FootprintDef(
        id=derived_id("fpd", "fenolite.catalog", f"Fenolite:{name}"),
        native_ids={"fenolite": f"Fenolite:{name}"},
        name=name,
        library="Fenolite",
        description=f"{desc}; land pattern remains INFERRED and requires part-specific review",
        kind="through_hole" if through_hole else "smd",
        pads=pads,
        graphics=graphics,
    )


def _chip_footprint(size_name: str) -> FootprintDef:
    # Yageo bodies and Vishay IPC-7351 reflow resistor-land example; generic use remains INFERRED.
    body_um = {"0402": (1000, 500), "0603": (1600, 800), "0805": (2000, 1250), "1206": (3100, 1600)}
    land_um = {
        "0402": (400, 550, 600),
        "0603": (700, 900, 1000),
        "0805": (1000, 900, 1450),
        "1206": (1750, 1150, 1800),
    }
    length_um, width_um = body_um[size_name]
    gap_um, pad_length_um, pad_width_um = land_um[size_name]
    center = (gap_um + pad_length_um) * 1000 // 2
    pads = tuple(
        _pad(f"Chip_{size_name}", number, x, 0, pad_length_um * 1000, pad_width_um * 1000)
        for number, x in (("1", -center), ("2", center))
    )
    return _make_footprint(f"Chip_{size_name}", pads, length_um * 1000, width_um * 1000)


_NEW_TWO_TERMINAL_LANDS_UM = {
    # name: (body length, body width, copper gap, pad length, pad width).
    # Vishay document 28950 uses G/Y/X; document 31545 uses A/B/C/D.
    "Chip_0201_Vishay_Draloric": (600, 300, 270, 430, 420),
    "Chip_1210_Vishay_Draloric": (3100, 2500, 1750, 1150, 2650),
    "Chip_1812_TDK_CGA8": (4500, 3200, 3400, 1300, 2800),
    "Chip_2010_Vishay_RCWP": (5000, 2490, 4060, 1020, 2540),
    "Chip_2512_Vishay_RCWP": (6350, 3150, 5330, 1020, 3180),
    "MELF_0102_Vishay_MMU": (2200, 1100, 950, 1050, 1250),
    "DO214AA_Diodes_SMB": (4300, 3600, 1800, 2500, 2300),
    "DO214AB_Diodes_SMC": (6900, 5900, 4400, 2500, 3300),
    "SOD123_Diodes": (2650, 1550, 2250, 900, 950),
    "SOD123F_Diodes_Standard": (2700, 1800, 1900, 1000, 1500),
    "SOD323_Diodes": (1700, 1300, 1520, 590, 450),
    "SOD523_Diodes": (1200, 800, 800, 600, 700),
}

_SMALL_OUTLINE_LANDS_UM = {
    # name: (pins, body length, body width, pin pitch, row centers, pad length, pad width).
    "SOIC14_TI_D0014A": (14, 8750, 3900, 1270, 5400, 1550, 600),
    "SOIC16_TI_D0016A": (16, 10000, 3900, 1270, 5400, 1550, 600),
    "SOIC20_TI_DW0020A": (20, 12800, 7500, 1270, 9300, 2000, 600),
    "SOIC24_Microchip_K3X": (24, 15400, 7500, 1270, 9400, 2000, 600),
    "SOIC28_MPS_Wide": (28, 17900, 7500, 1270, 9400, 2000, 610),
    "TSSOP8_Diodes": (8, 3025, 4425, 650, 5940, 1780, 450),
    "TSSOP14_Diodes": (14, 5000, 4400, 650, 5900, 1450, 450),
    "TSSOP16_Diodes_A1": (16, 5000, 4400, 650, 5400, 1400, 350),
    "TSSOP20_Diodes": (20, 6500, 4400, 650, 5940, 1780, 420),
    "TSSOP24_TI_PW0024A": (24, 7800, 4400, 650, 5800, 1500, 450),
    "TSSOP28_Microchip_NRB": (28, 9700, 4400, 650, 5900, 1500, 450),
    "MSOP8_Diodes": (8, 3000, 3000, 650, 3950, 1350, 450),
    "MSOP10_Diodes": (10, 3000, 3000, 500, 3950, 1350, 300),
    "SSOP16_Diodes_CJ": (16, 4900, 3900, 635, 5040, 1500, 410),
}


def _two_terminal_footprint(name: str) -> FootprintDef:
    length, width, gap, pad_length, pad_width = _NEW_TWO_TERMINAL_LANDS_UM[name]
    center = (gap + pad_length) * 500
    pads = tuple(
        _pad(name, number, x, 0, pad_length * 1000, pad_width * 1000)
        for number, x in (("1", -center), ("2", center))
    )
    return _make_footprint(
        name,
        pads,
        length * 1000,
        width * 1000,
        cathode_marker=name.startswith(("DO214", "SOD")),
    )


def _row_pads(
    name: str, count: int, pitch: int, row_spacing: int, sx: int, sy: int, *, drill: int | None = None
) -> tuple[Pad, ...]:
    """Create counter-clockwise numbered dual-row pads starting at the upper-left position."""
    per_side = count // 2
    offsets = tuple(((per_side - 1 - 2 * i) * pitch) // 2 for i in range(per_side))
    coords: list[tuple[int, int]] = []
    coords.extend((-row_spacing // 2, y) for y in offsets)
    coords.extend((row_spacing // 2, y) for y in reversed(offsets))
    return tuple(_pad(name, str(i + 1), x, y, sx, sy, drill=drill) for i, (x, y) in enumerate(coords))


_QFN_LANDS_UM = {
    # Count, square body, opposing pad centers, pad length/width, square exposed copper.
    "QFN16_Diodes_W3030_A1": (16, 3000, 3000, 700, 300, 1700),
    "QFN20_Diodes_U4040": (20, 4000, 3700, 600, 350, 2500),
    "QFN24_Diodes_W4040_SWP_A1": (24, 4000, 3850, 750, 300, 2500),
    "QFN28_Diodes_W5050_A1": (28, 5000, 4700, 900, 300, 3250),
    "QFN32_Diodes_W5050": (32, 5000, 4700, 600, 350, 3800),
    "QFN48_TI_RGZ0048A": (48, 7000, 6800, 600, 240, 5150),
}


def _quad_pads(name: str, count: int, pitch: int, row: int, length: int, width: int) -> tuple[Pad, ...]:
    """Number four sides counter-clockwise in the PCB top view, from upper left."""
    per_side = count // 4
    offsets = tuple((per_side - 1 - 2 * i) * pitch // 2 for i in range(per_side))
    coordinates = (
        *((-row // 2, y) for y in offsets),
        *((x, -row // 2) for x in reversed(offsets)),
        *((row // 2, y) for y in reversed(offsets)),
        *((x, row // 2) for x in offsets),
    )
    return tuple(
        _pad(name, str(i + 1), x, y, *((length, width) if i // per_side in (0, 2) else (width, length)))
        for i, (x, y) in enumerate(coordinates)
    )


def _paste_grid(
    name: str, count: int, width: int, height: int, pitch_x: int, pitch_y: int
) -> tuple[Graphic, ...]:
    """Create separate zero-stroke stencil windows without adding copper terminals."""
    return tuple(
        Graphic(
            id=derived_id("gfx", "fenolite.catalog", f"{name}:paste:{i * count + j}"),
            kind="rect",
            layer="F.Paste",
            points=(Point(x - width // 2, y - height // 2), Point(x + width // 2, y + height // 2)),
            width=0,
            filled=True,
        )
        for i in range(count)
        for j in range(count)
        for x, y in [((2 * i - count + 1) * pitch_x // 2, (2 * j - count + 1) * pitch_y // 2)]
    )


def _thermal_paste(name: str, width: int, height: int) -> tuple[Graphic, ...]:
    """Fenolite-authored four-window stencil: 64% coverage, subject to process review."""
    return _paste_grid(name, 2, width * 2 // 5, height * 2 // 5, width // 2, height // 2)


def _pin1_index(name: str, body_x: int, body_y: int) -> Graphic:
    return Graphic(
        id=derived_id("gfx", "fenolite.catalog", f"{name}:pin1"),
        kind="line",
        layer="F.Fab",
        points=(Point(-body_x // 2, body_y // 2 - 400_000), Point(-body_x // 2 + 400_000, body_y // 2)),
        width=100_000,
    )


_DFN_LANDS_UM = {
    # Count, square body, pitch, row centers, pad length/width, exposed copper x/y.
    # Rotate the source rows 90 degrees and mirror the underside into the PCB top view.
    "DFN6_Diodes_W2020_US": (6, 2000, 650, 1805, 545, 350, 850, 1550),
    "DFN8_Diodes_W3030_UXF": (8, 3000, 650, 2650, 550, 400, 1750, 2350),
}

_QFP_LANDS_UM = {
    # Count, square body, pitch, row centers, pad length/width.
    "TQFP44_Microchip_PT": (44, 10000, 800, 11400, 1500, 550),
    "LQFP48_TI_PT0048A": (48, 7000, 500, 8200, 1600, 300),
    "LQFP64_TI_PM0064A": (64, 10000, 500, 11400, 1500, 300),
    "LQFP100_TI_PZ0100A": (100, 14000, 500, 15400, 1500, 300),
}


_DIP_BODIES_UM = {
    "DIP4_Vishay_VO617A": (4, 7000, 4880),
    "DIP6_Vishay_CNY17": (6, 7000, 7800),
    "DIP8_Microchip_P": (8, 7112, 10160),
    "DIP14_Microchip_P": (14, 7112, 19685),
    "DIP16_Microchip_P": (16, 7112, 19685),
    "DIP20_Microchip_P": (20, 7112, 26924),
    "DIP28_Microchip_SP": (28, 7493, 35560),
}


def _body_circle(name: str, diameter: int) -> Graphic:
    return Graphic(
        id=derived_id("gfx", "fenolite.catalog", f"{name}:body-circle"),
        kind="circle",
        layer="F.Fab",
        points=(Point(0, 0), Point(diameter // 2, 0)),
        width=100_000,
    )


def _footprint(name: str) -> FootprintDef:
    if name in ("SW_Tact_Wurth_430181038816", "SW_Tact_Wurth_430186043716"):
        smd = name == "SW_Tact_Wurth_430181038816"
        centers = (
            (
                (-3_500_000, 1_500_000),
                (3_500_000, 1_500_000),
                (-3_500_000, -1_500_000),
                (3_500_000, -1_500_000),
            )
            if smd
            else (
                (-3_250_000, 2_250_000),
                (-3_250_000, -2_250_000),
                (3_250_000, 2_250_000),
                (3_250_000, -2_250_000),
            )
        )
        pads = tuple(
            _pad(
                name,
                str(i + 1),
                x,
                y,
                2_000_000 if smd else 1_800_000,
                1_400_000 if smd else 1_800_000,
                drill=None if smd else 1_000_000,
            )
            for i, (x, y) in enumerate(centers)
        )
        body = 4_500_000 if smd else 6_400_000
        footprint = _make_footprint(name, pads, body, body, through_hole=not smd)
        actuator = replace(
            _body_circle(name, 2_500_000 if smd else 3_500_000),
            id=derived_id("gfx", "fenolite.catalog", f"{name}:actuator"),
        )
        return replace(footprint, graphics=(*footprint.graphics, actuator))
    if name in ("C_Electrolytic_Panasonic_FR_D5_P2", "C_Electrolytic_Panasonic_FR_D6.3_P2.5"):
        diameter, pitch = (5_000_000, 2_000_000) if name.endswith("D5_P2") else (6_300_000, 2_500_000)
        pads = tuple(
            _pad(name, str(i + 1), side * pitch // 2, 0, 1_600_000, 1_600_000, drill=800_000)
            for i, side in enumerate((-1, 1))
        )
        footprint = _make_footprint(name, pads, diameter + 500_000, diameter + 500_000, through_hole=True)
        graphics = (_body_circle(name, diameter), footprint.graphics_on("F.CrtYd")[0])
        for key, a, b in (
            (
                "plus-h",
                Point(-diameter // 4 - 200_000, diameter // 4),
                Point(-diameter // 4 + 200_000, diameter // 4),
            ),
            (
                "plus-v",
                Point(-diameter // 4, diameter // 4 - 200_000),
                Point(-diameter // 4, diameter // 4 + 200_000),
            ),
            (
                "minus",
                Point(diameter // 4 - 200_000, diameter // 4),
                Point(diameter // 4 + 200_000, diameter // 4),
            ),
        ):
            graphics += (
                Graphic(
                    id=derived_id("gfx", "fenolite.catalog", f"{name}:{key}"),
                    kind="line",
                    layer="F.Fab",
                    points=(a, b),
                    width=100_000,
                ),
            )
        return replace(footprint, graphics=graphics)
    if name in ("MountingHole_M2_D2.4", "MountingHole_M3_D3.4"):
        drill, guide = (
            (2_400_000, 5_000_000) if name.startswith("MountingHole_M2") else (3_400_000, 7_000_000)
        )
        hole = replace(_pad(name, "", 0, 0, drill, drill, drill=drill, pad_id="hole"), kind="np_thru_hole")
        footprint = _make_footprint(name, (hole,), guide, guide, through_hole=True)
        return replace(
            footprint,
            kind="unspecified",
            flags=("exclude_from_bom", "exclude_from_pos_files"),
            graphics=(_body_circle(name, guide), footprint.graphics_on("F.CrtYd")[0]),
        )
    if name == "TestPoint_SMD_D1.0":
        pad = replace(_pad(name, "1", 0, 0, 1_000_000, 1_000_000), shape="circle", layers=("F.Cu", "F.Mask"))
        footprint = _make_footprint(name, (pad,), 1_000_000, 1_000_000)
        return replace(
            footprint,
            flags=("exclude_from_bom", "exclude_from_pos_files"),
            graphics=(_body_circle(name, 1_000_000), footprint.graphics_on("F.CrtYd")[0]),
        )
    if name == "LED5050_Worldsemi_WS2812B_V6":
        pads = tuple(
            _pad(name, str(i + 1), x, y, 1_500_000, 1_000_000)
            for i, (x, y) in enumerate(
                (
                    (-2_450_000, 1_650_000),
                    (-2_450_000, -1_650_000),
                    (2_450_000, -1_650_000),
                    (2_450_000, 1_650_000),
                )
            )
        )
        footprint = _make_footprint(name, pads, 5_000_000, 5_000_000)
        corner = Graphic(
            id=derived_id("gfx", "fenolite.catalog", f"{name}:pin3-corner"),
            kind="line",
            layer="F.Fab",
            points=(Point(1_800_000, -2_500_000), Point(2_500_000, -1_800_000)),
            width=100_000,
        )
        lens = replace(
            _body_circle(name, 4_000_000), id=derived_id("gfx", "fenolite.catalog", f"{name}:lens")
        )
        return replace(footprint, graphics=(*footprint.graphics, corner, lens))
    if name in ("LED0603_Kingbright_APT1608SURCK", "LED0805_Kingbright_APT2012SURCK"):
        body_x, body_y, gap, width, height = (
            (1_600_000, 800_000, 850_000, 800_000, 800_000)
            if name.startswith("LED0603")
            else (2_000_000, 1_250_000, 1_100_000, 1_250_000, 1_100_000)
        )
        pads = tuple(
            _pad(name, str(i + 1), side * (gap + width) // 2, 0, width, height)
            for i, side in enumerate((-1, 1))
        )
        return _make_footprint(name, pads, body_x, body_y, cathode_marker=True, cathode_on_left=True)
    tht_passives = {
        "R_Axial_Vishay_MRS16_P7.62": (7620, 3600, 1600, 800, 1600),
        "R_Axial_Vishay_MRS25_P10.16": (10160, 6500, 2500, 900, 1800),
        "C_Film_Wima_MKS02_L4.6_W2.5_P2.5": (2500, 4600, 2500, 700, 1400),
        "C_Film_Wima_MKS2_L7.2_W2.5_P5": (5000, 7200, 2500, 800, 1600),
    }
    if name in tht_passives:
        pitch, body_x, body_y, drill, copper = tht_passives[name]
        pads = tuple(
            _pad(name, str(i + 1), side * pitch * 500, 0, copper * 1000, copper * 1000, drill=drill * 1000)
            for i, side in enumerate((-1, 1))
        )
        return _make_footprint(name, pads, body_x * 1000, body_y * 1000, through_hole=True)
    if name == "Crystal_3225_Abracon_ABM8":
        pads = tuple(
            _pad(name, str(i + 1), x, y, 1_300_000, 1_050_000)
            for i, (x, y) in enumerate(
                ((-1_150_000, -875_000), (1_150_000, -875_000), (1_150_000, 875_000), (-1_150_000, 875_000))
            )
        )
        return _make_footprint(name, pads, 3_200_000, 2_500_000)
    if name.endswith("_P2.54") and name.startswith("Header_"):
        columns, rows = (int(value) for value in name.split("_")[1].split("x"))
        pads = tuple(
            _pad(
                name,
                str(row * columns + column + 1),
                (2 * column - columns + 1) * 1_270_000,
                (rows - 1 - 2 * row) * 1_270_000,
                1_800_000,
                1_800_000,
                drill=1_100_000,
            )
            for row in range(rows)
            for column in range(columns)
        )
        body_x, body_y = columns * 2_540_000, rows * 2_540_000
        footprint = _make_footprint(name, pads, body_x, body_y, through_hole=True)
        return replace(footprint, graphics=(*footprint.graphics, _pin1_index(name, body_x, body_y)))
    if name in ("JST_XH_B2B_XH_A", "JST_XH_B4B_XH_A"):
        count = 2 if name == "JST_XH_B2B_XH_A" else 4
        pads = tuple(
            _pad(
                name,
                str(i + 1),
                (count - 1 - 2 * i) * 1_250_000,
                0,
                1_800_000,
                1_800_000,
                drill=1_000_000 if count == 2 else 900_000,
            )
            for i in range(count)
        )
        body_x = (count * 2500 + 2400) * 1000
        footprint = _make_footprint(name, pads, body_x, 5_750_000, through_hole=True, body_center_y=525_000)
        index = Graphic(
            id=derived_id("gfx", "fenolite.catalog", f"{name}:pin1"),
            kind="line",
            layer="F.Fab",
            points=(Point(body_x // 2 - 700_000, -2_350_000), Point(body_x // 2, -1_650_000)),
            width=100_000,
        )
        return replace(footprint, graphics=(*footprint.graphics, index))
    if name == "MicroUSB_B_Wurth_629105150521":
        pads = tuple(
            _pad(name, str(i + 1), (i - 2) * 650_000, 5_500_000, 450_000, 1_300_000) for i in range(5)
        )
        for row, x, y, width, height, drill, length in (
            ("rear", 3_725_000, 5_600_000, 1_450_000, 2_000_000, 850_000, 1_400_000),
            ("front", 3_875_000, 1_800_000, 1_150_000, 1_800_000, 550_000, 1_300_000),
        ):
            for side in (-1, 1):
                key = f"shell:{row}:{side}"
                pad = _pad(name, "SH", side * x, y, width, height, drill=drill, pad_id=key)
                pads += (
                    replace(
                        pad,
                        shape="oval",
                        padstack=Padstack(
                            id=derived_id("pst", "fenolite.catalog", f"{name}:{key}"),
                            hole_shape="slot",
                            hole_length=length,
                            hole_rotation=90_000_000,
                        ),
                    ),
                )
        for side in (-1, 1):
            peg = _pad(
                name, "", side * 2_500_000, 4_550_000, 800_000, 800_000, drill=800_000, pad_id=f"peg:{side}"
            )
            pads += (replace(peg, kind="np_thru_hole"),)
        footprint = _make_footprint(name, pads, 8_000_000, 6_600_000, body_center_y=2_700_000)
        edge = Graphic(
            id=derived_id("gfx", "fenolite.catalog", f"{name}:pcb-edge-guide"),
            kind="line",
            layer="F.Fab",
            points=(Point(-4_000_000, 0), Point(4_000_000, 0)),
            width=100_000,
        )
        return replace(footprint, graphics=(*footprint.graphics, edge))
    if name in _DIP_BODIES_UM:
        count, body_x, body_y = _DIP_BODIES_UM[name]
        pads = _row_pads(name, count, 2_540_000, 7_620_000, 1_800_000, 1_800_000, drill=900_000)
        footprint = _make_footprint(name, pads, body_x * 1000, body_y * 1000, through_hole=True)
        return replace(
            footprint, graphics=(*footprint.graphics, _pin1_index(name, body_x * 1000, body_y * 1000))
        )
    if name in _QFN_LANDS_UM:
        count, body, row, length, width, exposed = _QFN_LANDS_UM[name]
        pads = _quad_pads(name, count, 500_000, row * 1000, length * 1000, width * 1000)
        ep = replace(_pad(name, "EP", 0, 0, exposed * 1000, exposed * 1000), layers=("F.Cu", "F.Mask"))
        footprint = _make_footprint(name, (*pads, ep), body * 1000, body * 1000)
        index = _pin1_index(name, body * 1000, body * 1000)
        paste = (
            _paste_grid(name, 4, 1_060_000, 1_060_000, 1_260_000, 1_260_000)
            if name == "QFN48_TI_RGZ0048A"
            else _thermal_paste(name, exposed * 1000, exposed * 1000)
        )
        return replace(footprint, graphics=(*footprint.graphics, index, *paste))
    if name in _DFN_LANDS_UM:
        count, body, pitch, row, length, width, exposed_x, exposed_y = _DFN_LANDS_UM[name]
        pads = _row_pads(name, count, pitch * 1000, row * 1000, length * 1000, width * 1000)
        ep = replace(_pad(name, "EP", 0, 0, exposed_x * 1000, exposed_y * 1000), layers=("F.Cu", "F.Mask"))
        footprint = _make_footprint(name, (*pads, ep), body * 1000, body * 1000)
        return replace(
            footprint,
            graphics=(
                *footprint.graphics,
                _pin1_index(name, body * 1000, body * 1000),
                *_thermal_paste(name, exposed_x * 1000, exposed_y * 1000),
            ),
        )
    if name in _QFP_LANDS_UM:
        count, body, pitch, row, length, width = _QFP_LANDS_UM[name]
        pads = _quad_pads(name, count, pitch * 1000, row * 1000, length * 1000, width * 1000)
        footprint = _make_footprint(name, pads, body * 1000, body * 1000)
        return replace(footprint, graphics=(*footprint.graphics, _pin1_index(name, body * 1000, body * 1000)))
    if name in _NEW_TWO_TERMINAL_LANDS_UM:
        return _two_terminal_footprint(name)
    if name == "SOD128_Nexperia_CFP5":
        # This package calls its left cathode terminal pad 1, unlike Fenolite's
        # generic diode symbol; callers must provide the device pin-to-pad map.
        pads = (
            _pad(name, "1", -2_200_000, 0, 1_400_000, 2_100_000),
            _pad(name, "2", 2_200_000, 0, 1_400_000, 2_100_000),
        )
        return _make_footprint(
            name, pads, 3_800_000, 2_600_000, cathode_marker=True, cathode_on_left=True, cathode_inset=600_000
        )
    if name.startswith("Chip_"):
        return _chip_footprint(name.rsplit("_", 1)[1])
    if name in _SMALL_OUTLINE_LANDS_UM:
        count, body_length, body_width, pitch, row, pad_length, pad_width = _SMALL_OUTLINE_LANDS_UM[name]
        pads = _row_pads(name, count, pitch * 1000, row * 1000, pad_length * 1000, pad_width * 1000)
        return _make_footprint(name, pads, body_width * 1000, body_length * 1000)
    if name in {"SOT23_6_TI_DBV0006A", "SC70_6_TI_DCK0006A"}:
        sot23 = name.startswith("SOT23")
        pitch, row, sx, sy = (
            (950_000, 2_600_000, 1_100_000, 600_000) if sot23 else (650_000, 2_200_000, 900_000, 400_000)
        )
        pads = _row_pads(name, 6, pitch, row, sx, sy)
        return _make_footprint(
            name, pads, 1_600_000 if sot23 else 1_250_000, 2_900_000 if sot23 else 2_000_000
        )
    if name in {"SOT323_3_Diodes_Standard", "SOT523_3_Diodes"}:
        sot323 = name.startswith("SOT323")
        pitch, row, sx, sy = (
            (650_000, 1_900_000, 600_000, 470_000) if sot323 else (700_000, 1_290_000, 510_000, 400_000)
        )
        pads = (
            _pad(name, "1", -row // 2, pitch // 2, sx, sy),
            _pad(name, "2", -row // 2, -pitch // 2, sx, sy),
            _pad(name, "3", row // 2, 0, sx, sy),
        )
        return _make_footprint(
            name, pads, 1_250_000 if sot323 else 800_000, 2_000_000 if sot323 else 1_600_000
        )
    if name == "SOT563_6_Diodes":
        pads = _row_pads(name, 6, 500_000, 1_270_000, 670_000, 300_000)
        return _make_footprint(name, pads, 1_200_000, 1_600_000)
    if name == "SOT883_3_Nexperia_DFN1006":
        pads = (
            _pad(name, "1", -350_000, 225_000, 400_000, 250_000),
            _pad(name, "2", -350_000, -225_000, 400_000, 250_000),
            _pad(name, "3", 350_000, 0, 400_000, 700_000),
        )
        return _make_footprint(name, pads, 1_000_000, 600_000)
    if name == "SOT143_4_Diodes":
        # The larger terminal is pin 1; the small-pad width is an authored
        # approximation because the suggested layout only dimensions X for pin 1.
        pads = (
            _pad(name, "1", -760_000, -1_000_000, 1_000_000, 700_000),
            _pad(name, "2", 960_000, -1_000_000, 600_000, 700_000),
            _pad(name, "3", 960_000, 1_000_000, 600_000, 700_000),
            _pad(name, "4", -960_000, 1_000_000, 600_000, 700_000),
        )
        return _make_footprint(name, pads, 2_900_000, 1_720_000)
    if name == "SOT223_3_Diodes":
        pads = (
            _pad(name, "1", -2_300_000, -3_100_000, 1_200_000, 1_400_000),
            _pad(name, "2", 0, 3_100_000, 3_500_000, 1_400_000),
            _pad(name, "3", 2_300_000, -3_100_000, 1_200_000, 1_400_000),
        )
        return _make_footprint(name, pads, 6_500_000, 3_500_000)
    if name in {"TO252_3_Diodes_Standard", "TO263_3_Diodes_Standard"}:
        small = name.startswith("TO252")
        pitch, lead_width, lead_length, tab_width, tab_length, tab_y, lead_y, body_x, body_y = (
            (
                4_572_000,
                1_060_000,
                2_600_000,
                5_632_000,
                5_700_000,
                2_500_000,
                -4_050_000,
                6_580_000,
                6_100_000,
            )
            if small
            else (
                5_080_000,
                1_100_000,
                3_500_000,
                10_410_000,
                7_010_000,
                4_490_000,
                -6_245_000,
                10_160_000,
                9_020_000,
            )
        )
        pads = (
            _pad(name, "1", -pitch // 2, lead_y, lead_width, lead_length),
            _pad(name, "2", 0, tab_y, tab_width, tab_length),
            _pad(name, "3", pitch // 2, lead_y, lead_width, lead_length),
        )
        return _make_footprint(name, pads, body_x, body_y)
    if name in {"DO35_P10.16_Diodes", "DO41_P10.16_Diodes"}:
        small = name.startswith("DO35")
        land, drill, body_x, body_y = (
            (1_600_000, 800_000, 4_000_000, 2_000_000)
            if small
            else (2_200_000, 1_100_000, 5_210_000, 2_720_000)
        )
        pads = (
            _pad(name, "1", -5_080_000, 0, land, land, drill=drill),
            _pad(name, "2", 5_080_000, 0, land, land, drill=drill),
        )
        return _make_footprint(name, pads, body_x, body_y, through_hole=True, cathode_marker=True)
    if name == "TO220_3_Diodes_Vertical":
        pads = tuple(
            _pad(name, str(i + 1), x, 0, 2_200_000, 2_200_000, drill=1_500_000)
            for i, x in enumerate((-2_540_000, 0, 2_540_000))
        )
        return _make_footprint(name, pads, 10_700_000, 4_850_000, through_hole=True, body_center_y=3_500_000)
    if name == "SOT23_3":
        pads = (
            _pad(name, "1", -1_050_000, 950_000, 1_300_000, 600_000),
            _pad(name, "2", -1_050_000, -950_000, 1_300_000, 600_000),
            _pad(name, "3", 1_050_000, 0, 1_300_000, 600_000),
        )
        return _make_footprint(name, pads, 1_300_000, 2_900_000)
    if name in {"SOT23_5", "SC70_5"}:
        small = name == "SC70_5"
        pitch = 650_000 if small else 950_000
        row = 2_200_000 if small else 2_600_000
        sx, sy = (950_000, 400_000) if small else (1_100_000, 600_000)
        ys = (pitch, 0, -pitch)
        pads = tuple(_pad(name, str(i + 1), -row // 2, y, sx, sy) for i, y in enumerate(ys)) + tuple(
            _pad(name, str(i + 4), row // 2, y, sx, sy) for i, y in enumerate((-pitch, pitch))
        )
        if small:
            return _make_footprint(name, pads, 1_250_000, 2_000_000)
        return _make_footprint(name, pads, 1_600_000, 2_900_000)
    if name == "SOT89_3":
        # Diodes SOT89 reference T-shaped terminal 2, split into overlapping same-number rectangles.
        pads = (
            _pad(name, "1", -1_500_000, -1_450_000, 580_000, 1_630_000),
            _pad(name, "2", 0, -1_490_000, 760_000, 1_550_000),
            _pad(name, "3", 1_500_000, -1_450_000, 580_000, 1_630_000),
            _pad(name, "2", 0, 750_000, 1_933_000, 3_030_000, pad_id="tab"),
        )
        return _make_footprint(name, pads, 4_500_000, 2_500_000)
    if name == "SOIC_8":
        pads = _row_pads(name, 8, 1_270_000, 5_400_000, 1_550_000, 600_000)
        return _make_footprint(name, pads, 3_900_000, 4_900_000)
    if name == "DO214AC":
        # Diodes Inc. suggested reference land dimensions; verify against the exact device and process.
        pads = (
            _pad(name, "1", -1_800_000, 0, 2_000_000, 2_100_000),
            _pad(name, "2", 1_800_000, 0, 2_000_000, 2_100_000),
        )
        return _make_footprint(name, pads, 4_500_000, 2_600_000)
    if name == "LQFP32_P0.8":
        count, pitch = 8, 800_000
        half_span = (count - 1) * pitch // 2
        coords: list[tuple[int, int]] = []
        coords.extend((-4_200_000, y) for y in range(half_span, -half_span - 1, -pitch))
        coords.extend((x, -4_200_000) for x in range(-half_span, half_span + 1, pitch))
        coords.extend((4_200_000, y) for y in range(-half_span, half_span + 1, pitch))
        coords.extend((x, 4_200_000) for x in range(half_span, -half_span - 1, -pitch))
        pads = tuple(
            _pad(
                name,
                str(i + 1),
                x,
                y,
                1_500_000 if abs(x) == 4_200_000 else 550_000,
                550_000 if abs(x) == 4_200_000 else 1_500_000,
            )
            for i, (x, y) in enumerate(coords)
        )
        return _make_footprint(name, pads, 7_000_000, 7_000_000)
    if name.startswith("Header_1x"):
        count = int(name.split("x", 1)[1].split("_", 1)[0])
        pitch = 2_500_000
        pads = tuple(
            _pad(
                name, str(i + 1), 0, ((count - 1 - 2 * i) * pitch) // 2, 1_800_000, 1_800_000, drill=1_000_000
            )
            for i in range(count)
        )
        return _make_footprint(
            name, pads, 2_500_000, max(2_500_000, (count - 1) * pitch + 2_000_000), through_hole=True
        )
    raise KeyError(name)


def get_symbol(lib_id: str) -> SymbolDef:
    """Return a built-in generic symbol by stable ``library:name`` ID."""
    if not lib_id.startswith("Fenolite:"):
        raise KeyError(lib_id)
    name = lib_id.split(":", 1)[1]
    spec = next((spec for spec in _SYMBOL_SPECS if spec.name == name), None)
    if spec is None:
        raise KeyError(lib_id)
    return _symbol(spec)


def get_footprint(lib_id: str) -> FootprintDef:
    """Return a built-in generic footprint by stable ``library:name`` ID."""
    if not lib_id.startswith("Fenolite:"):
        raise KeyError(lib_id)
    name = lib_id.split(":", 1)[1]
    if name not in _FOOTPRINT_NAMES:
        raise KeyError(lib_id)
    return _footprint(name)


__all__ = ["CatalogEntry", "ENTRIES", "get_footprint", "get_symbol", "list_entries"]
