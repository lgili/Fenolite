# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0061 (capability kicad-oracle, "Schematic naming facts are probed" and "Generated
schematics pass ERC and parity"): the ``sch-pin-frame-*``, ``sch-unconnected-*``, ``sch-label-*``,
``sch-parity-slash-*``, ``sch-power-*``, ``sch-*-power-*``, ``sch-lib-*`` and ``sch-gen-*`` rows of
``_probes.PROBES``.

The naming probes run on sheets written here by hand, with the smallest token set both majors load, so
they measure KiCad and not Fenolite's writer. Their symbols are the authored CC0 mini library and probe
symbols written in this file; nothing comes from a KiCad library. The ``sch-lib-*``,
``sch-parity-slash-*`` and ``sch-gen-*`` probes run on projects that ``build`` wrote.
"""

from __future__ import annotations

import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _erc
from _buildhelp import LIBS, blink, build
from _schbuild import built_units

from fenolite.backends.kicad import netnames, sch, schlayout, symembed
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.core.coords import Point

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
NS = uuid.UUID("00000000-0000-4000-8000-0000000c0061")
FONT = "(effects (font (size 1.27 1.27)))"
HIDDEN = "(effects (font (size 1.27 1.27)) (hide yes))"
STEP = 2_540_000
MIRRORS = {"none": "", "x": "x", "y": "y"}
LABEL_TEXTS: tuple[str, ...] = (
    "LED_A", "Net 1", "A[0]", "A{1}", 'Q"x', "back\\slash", "Größe", "V+", "A.B", "A-B", "A_B", "A:B",
    "A,B", "#PWR", "$X", "(P)", "3V3", "a", "A~B", "N=1",
)  # fmt: skip
"""Label texts KiCad is expected to take as the net name: letters, digits, blank, brackets, braces, quote,
backslash, a non-ASCII letter and punctuation."""
SLASH_TEXT = "mod/LED_A"
CHAR_PINS: tuple[tuple[str, str], ...] = (
    ("1", "A B"), ("2", "A/B"), ("3", "V+"), ("4", "~"), ("5", "~{RST}"), ("6", "1WIRE"), ("7", "DUP"),
    ("8", "DUP"), ("9", "A-B_C.D"), ("10", "D{0}"),
)  # fmt: skip
"""Pin number and name of the probe symbol ``Probe:Chars``: one pin per character class."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


def uid(*parts: object) -> str:
    return str(uuid.uuid5(NS, ":".join(str(p) for p in parts)))


def mm(nm: int) -> str:
    sign = "-" if nm < 0 else ""
    whole, frac = divmod(abs(nm), 1_000_000)
    return f"{sign}{whole}" + (f".{frac:06d}".rstrip("0") if frac else "")


def quoted(text: str) -> str:
    return dumps(Atom.string(text)).strip()


# -- symbols


@cache
def mini(name: str) -> str:
    """The symbol ``name`` of the authored 9.0 mini library as an embedded definition ``Mini:<name>``."""
    root = parse((LIBS / "Mini_v9.kicad_sym").read_text(encoding="utf-8"))
    for item in root.nodes("symbol"):
        if item.atoms()[0].value == name:
            children = [Atom.string(f"Mini:{name}") if c is item.atoms()[0] else c for c in item.children]
            return dumps(item.with_children(children), style="compact")
    raise KeyError(name)


def probe_symbol(
    name: str, pins: Sequence[tuple[str, str, str]], *, hidden: bool = False, power: bool = False
) -> str:
    """An authored symbol ``Probe:<name>``: ``pins`` are (electrical type, number, name), one under the
    other on the left edge, 2.54 mm apart."""
    rows = []
    for index, (etype, number, pin_name) in enumerate(pins):
        hide = " (hide yes)" if hidden else ""
        rows.append(
            f"(pin {etype} line (at -5.08 {mm(-index * STEP)} 0) (length 2.54){hide} "
            f"(name {quoted(pin_name)} {FONT}) (number {quoted(number)} {FONT}))"
        )
    flag = "(power) " if power else ""
    fields = (
        f'(property "Reference" "X" (at 0 2.54 0) {FONT}) (property "Value" "{name}" (at 0 5.08 0) {FONT})'
    )
    return (
        f'(symbol "Probe:{name}" {flag}(exclude_from_sim no) (in_bom yes) (on_board yes) {fields} '
        f'(symbol "{name}_1_1" {" ".join(rows)}))'
    )


def probe_points(count: int) -> list[Point]:
    """The library positions of the pins of a ``probe_symbol`` with ``count`` pins."""
    return [Point(-5_080_000, -index * STEP) for index in range(count)]


# -- hand-written sheets


@dataclass(frozen=True)
class Inst:
    """A placed unit of a hand-written sheet; ``pins`` are the pin numbers of the unit."""

    lib_id: str
    ref: str
    at: Point
    pins: tuple[str, ...]
    rotation: int = 0
    mirror: str = ""
    unit: int = 1


def hand_sheet(
    target: int,
    libs: Sequence[str],
    insts: Sequence[Inst],
    labels: Sequence[tuple[str, Point]] = (),
    flags: Sequence[Point] = (),
    name: str = "probe",
) -> str:
    """A flat sheet in the format of KiCad ``target`` with the token set both majors load."""
    root = uid(name, "root")
    out = [
        f"(kicad_sch (version {FORMAT_VERSIONS[FileKind.SCHEMATIC][target]}) "
        f'(generator "fenolite-tests") (generator_version "{target}.0") (uuid "{root}") (paper "A3")',
        f"(lib_symbols {' '.join(libs)})",
    ]
    for index, at in enumerate(flags):
        out.append(f'(no_connect (at {mm(at.x)} {mm(at.y)}) (uuid "{uid(name, "nc", index)}"))')
    for index, (text, at) in enumerate(labels):
        out.append(
            f"(global_label {quoted(text)} (shape passive) (at {mm(at.x)} {mm(at.y)} 0) "
            f'(effects (font (size 1.27 1.27)) (justify left)) (uuid "{uid(name, "label", index)}"))'
        )
    for inst in insts:
        key = (name, inst.ref, inst.unit)
        mirror = f" (mirror {inst.mirror})" if inst.mirror else ""
        pins = " ".join(f'(pin {quoted(n)} (uuid "{uid(*key, "pin", n)}"))' for n in inst.pins)
        x, y = mm(inst.at.x), mm(inst.at.y)
        out.append(
            f"(symbol (lib_id {quoted(inst.lib_id)}) (at {x} {y} {inst.rotation}){mirror} "
            f"(unit {inst.unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) "
            f'(uuid "{uid(*key)}") '
            f'(property "Reference" {quoted(inst.ref)} (at {x} {y} 0) {FONT}) '
            f'(property "Value" "v" (at {x} {y} 0) {HIDDEN}) '
            f'(property "Footprint" "" (at {x} {y} 0) {HIDDEN}) '
            f'(property "Datasheet" "" (at {x} {y} 0) {HIDDEN}) '
            f"{pins} "
            f'(instances (project "{name}" (path "/{root}" (reference {quoted(inst.ref)}) '
            f"(unit {inst.unit})))))"
        )
    out.append('(sheet_instances (path "/" (page "1"))))')
    return dumps(parse("\n".join(out)))


def erc_types(text: str, name: str = "probe") -> Mapping[str, int] | None:
    """The violation types of ERC on a hand-written sheet, or ``None`` when ``kicad-cli`` did not load it."""
    report = _erc.run_erc(runner(), f"{name}.kicad_sch", {f"{name}.kicad_sch": text})
    return _erc.types(_erc.violations(report)) if report.loaded else None


def nets_of(text: str, name: str = "probe") -> dict[tuple[str, str], str]:
    """(reference, pin number) → net name, from the netlist of a hand-written sheet."""
    found = _erc.netlist(runner(), f"{name}.kicad_sch", {f"{name}.kicad_sch": text})
    return {node: net for net, nodes in found.items() for node in nodes}


# -- the pin frame (H-K-SCH-PINFRAME)

FRAME_ORIGIN = Point(127_000_000, 101_600_000)


def ic_pins() -> list[tuple[str, Point]]:
    (definition,) = sch.read_schematic(hand_sheet(10, [mini("Mini_QFP32_IC")], [])).lib_symbols
    return [(pin.number, pin.position) for pin in definition.pins]


def frame_sheet(target: int, rotation: int, mirror: str, labels_as: tuple[int, str] | None = None) -> str:
    """The 32-pin IC with ``rotation`` and ``mirror`` and one label per pin, at the points ``pin_point``
    gives for the frame ``labels_as`` (the instance's own frame by default)."""
    turn, flip = labels_as if labels_as is not None else (rotation, mirror)
    pins = ic_pins()
    labels = [(f"N{n}", schlayout.pin_point(FRAME_ORIGIN, at, turn, flip)) for n, at in pins]
    inst = Inst("Mini:Mini_QFP32_IC", "U1", FRAME_ORIGIN, tuple(n for n, _ in pins), rotation, mirror)
    return hand_sheet(target, [mini("Mini_QFP32_IC")], [inst], labels)


@cache
def frame_unconnected(rotation: int, mirror: str, labels_as: tuple[int, str] | None = None) -> int | None:
    """The number of ``pin_not_connected`` violations of ``frame_sheet`` (``None``: not loaded)."""
    found = erc_types(frame_sheet(major(), rotation, mirror, labels_as))
    return None if found is None else found.get("pin_not_connected", 0)


def frame_outcome(rotation: int, mirror: str) -> str:
    count = frame_unconnected(rotation, mirror)
    if count is None or not frame_unconnected(0, "", (90, "")):  # the control must report open pins
        return "inconclusive"
    return "absent" if count == 0 else "present"


# -- names of unconnected pins (H-K-SCH-UNCONNECTED)


def _units_sheet(target: int) -> str:
    insts = [
        Inst("Mini:Mini_DualGate", "U2", Point(50_800_000, 50_800_000), ("1", "2", "3"), unit=1),
        Inst("Mini:Mini_DualGate", "U2", Point(101_600_000, 50_800_000), ("4", "5", "6"), unit=2),
        Inst("Mini:Mini_DualGate", "U2", Point(152_400_000, 50_800_000), ("7", "14"), unit=3),
    ]
    return hand_sheet(target, [mini("Mini_DualGate")], insts)


def unconnected_sheet(kind: str, target: int) -> str:
    """A sheet whose symbols have every pin on no net: the 32-pin IC, a symbol with two pins without a
    name, the three units of the dual gate, or the probe symbol with one pin name per character class."""
    if kind == "units":
        return _units_sheet(target)
    if kind == "chars":
        chars = probe_symbol("Chars", [("passive", number, name) for number, name in CHAR_PINS])
        inst = Inst("Probe:Chars", "X1", FRAME_ORIGIN, tuple(n for n, _ in CHAR_PINS))
        return hand_sheet(target, [chars], [inst])
    if kind == "unnamed":
        bare = probe_symbol("Bare", [("passive", "1", ""), ("passive", "16", "")])
        return hand_sheet(target, [bare], [Inst("Probe:Bare", "U1", FRAME_ORIGIN, ("1", "16"))])
    numbers = tuple(n for n, _ in ic_pins())
    return hand_sheet(
        target, [mini("Mini_QFP32_IC")], [Inst("Mini:Mini_QFP32_IC", "U1", FRAME_ORIGIN, numbers)]
    )


@cache
def unconnected_names(kind: str) -> dict[tuple[str, str], tuple[str, str, str]]:
    """(reference, pin number) → (pin name, the name ``netnames.unconnected_name`` gives, KiCad's net name)
    for every pin of ``unconnected_sheet``. The pin names are those Fenolite reads from the sheet."""
    text = unconnected_sheet(kind, major())
    sheet = sch.read_schematic(text)
    definitions = {f"{d.library}:{d.name}": d for d in sheet.lib_symbols}
    theirs = nets_of(text)
    found: dict[tuple[str, str], tuple[str, str, str]] = {}
    for symbol in sheet.symbols:
        definition = definitions[symbol.lib_ref]
        for pin in definition.pins_of(symbol.unit, 1):
            ours = netnames.unconnected_name(
                symbol.ref,
                unit=symbol.unit,
                unit_count=definition.unit_count,
                pin_name=pin.name,
                pad_number=pin.number,
            )
            found[(symbol.ref, pin.number)] = (pin.name, ours, theirs.get((symbol.ref, pin.number), ""))
    return found


def unconnected_outcome(kind: str) -> str:
    rows = unconnected_names(kind)
    if kind == "plain":
        rows = {k: v for k, v in rows.items() if v[0]}
    elif kind == "unnamed":
        rows = {k: v for k, v in rows.items() if not v[0]}
    if not rows:
        return "inconclusive"
    return "equal" if all(ours == theirs for _, ours, theirs in rows.values()) else "different"


# -- label texts (H-K-SCH-SLASH)


@cache
def label_nets(texts: tuple[str, ...]) -> dict[str, str]:
    """Label text → the name of the net it makes: resistor ``R<i>`` has the i-th text on pin 1."""
    (definition,) = sch.read_schematic(hand_sheet(10, [mini("Mini_R")], [])).lib_symbols
    points = {pin.number: pin.position for pin in definition.pins}
    insts, labels = [], []
    for index, text in enumerate(texts):
        origin = Point(25_400_000 + (index % 10) * 25_400_000, 50_800_000 + (index // 10) * 50_800_000)
        insts.append(Inst("Mini:Mini_R", f"R{index + 1}", origin, ("1", "2")))
        labels.append((text, schlayout.pin_point(origin, points["1"])))
        labels.append(("COMMON", schlayout.pin_point(origin, points["2"])))
    nets = nets_of(hand_sheet(major(), [mini("Mini_R")], insts, labels))
    return {text: nets.get((f"R{index + 1}", "1"), "") for index, text in enumerate(texts)}


def label_outcome(texts: tuple[str, ...], expected: Callable[[str], str] = lambda text: text) -> str:
    found = label_nets(texts)
    return "equal" if all(found[text] == expected(text) for text in texts) else "different"


# -- power (H-K-SCH-POWER)

POWER_AT = Point(50_800_000, 50_800_000)
FLAG_AT = Point(101_600_000, 50_800_000)


def power_sheet(target: int, *, flag: bool) -> str:
    """One power-input pin on the net ``VDD``; with ``flag`` also ``fenolite:PWR_FLAG`` on that net."""
    libs = [probe_symbol("Load", [("power_in", "1", "VDD")])]
    insts = [Inst("Probe:Load", "X1", POWER_AT, ("1",))]
    labels = [("VDD", schlayout.pin_point(POWER_AT, probe_points(1)[0]))]
    if flag:
        libs.append(dumps(symembed.power_flag(target).node, style="compact"))
        insts.append(Inst("fenolite:PWR_FLAG", "#FLG01", FLAG_AT, ("1",)))
        labels.append(("VDD", FLAG_AT))
    return hand_sheet(target, libs, insts, labels)


def power_flag_outcome() -> str:
    bare, flagged = (erc_types(power_sheet(major(), flag=flag)) for flag in (False, True))
    if bare is None or flagged is None or not bare.get("power_pin_not_driven"):
        return "inconclusive"
    return "absent" if not flagged.get("power_pin_not_driven") else "present"


@cache
def supply_nets(hidden: bool) -> tuple[str, str]:
    """The nets of two power-input pins named ``VSS``, labelled ``GND`` and ``OTHER``."""
    pins = [("power_in", "1", "VSS"), ("power_in", "2", "VSS")]
    points = probe_points(2)
    inst = Inst("Probe:Supply", "X1", POWER_AT, ("1", "2"))
    labels = [
        ("GND", schlayout.pin_point(POWER_AT, points[0])),
        ("OTHER", schlayout.pin_point(POWER_AT, points[1])),
    ]
    nets = nets_of(hand_sheet(major(), [probe_symbol("Supply", pins, hidden=hidden)], [inst], labels))
    return nets.get(("X1", "1"), ""), nets.get(("X1", "2"), "")


def hidden_joined_outcome() -> str:
    first, second = supply_nets(True)
    return "present" if first and first == second else "absent"


def shown_separate_outcome() -> str:
    return "equal" if supply_nets(False) == ("GND", "OTHER") else "different"


# -- built projects


@cache
def built(name: str, target: int) -> Mapping[str, bytes]:
    """The files that ``build`` writes for the blink or the units design, without the ``.fenolite/`` cache."""
    output = build(blink(), target) if name == "blink" else built_units(target)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def stem(name: str) -> str:
    return "blink" if name == "blink" else "units"


@cache
def built_erc(name: str, without: tuple[str, ...] = (), exit_code: bool = False) -> _erc.Report:
    files = {rel: data for rel, data in built(name, major()).items() if rel not in without}
    return _erc.run_erc(runner(), f"{stem(name)}.kicad_sch", files, exit_code=exit_code)


def library_outcome(name: str, without: tuple[str, ...] = ()) -> str:
    """``present`` when ERC reports a symbol whose library is missing or differs from the embedded copy."""
    report = built_erc(name, without)
    if not report.loaded:
        return "inconclusive"
    found = _erc.types(_erc.violations(report))
    return "present" if found.get("lib_symbol_issues") or found.get("lib_symbol_mismatch") else "absent"


def guarded_library(name: str) -> str:
    """A library outcome counts only when the control without a table reports the missing libraries."""
    if library_outcome("blink", ("sym-lib-table",)) != "present":
        return "inconclusive"
    return library_outcome(name)


@cache
def built_parity(name: str, old: str = "", new: str = "") -> _erc.Report:
    """The parity report of a built project, with ``old`` replaced by ``new`` in its board text."""
    files = dict(built(name, major()))
    board = f"{stem(name)}.kicad_pcb"
    if old:
        text = files[board].decode("utf-8")
        assert old in text, old
        files[board] = text.replace(old, new).encode("utf-8")
    return _erc.run_parity(runner(), board, files)


def slash_outcome(*, raw: bool) -> str:
    stored = netnames.stored_name("mod/LED_A")
    report = built_parity("units", stored, "mod/LED_A") if raw else built_parity("units")
    if not report.loaded:
        return "inconclusive"
    return "present" if _erc.types(_erc.parity(report)).get("net_conflict") else "absent"


def generated_erc_outcome(name: str) -> str:
    report = built_erc(name, exit_code=True)
    if not report.loaded:
        return "inconclusive"
    return "equal" if report.returncode == 0 and not _erc.violations(report) else "different"


def resave(text: bytes, files: Mapping[str, bytes], sheet: str = "blink.kicad_sch") -> bytes:
    """``sheet`` with the bytes ``text``, re-saved by ``sch upgrade --force`` (10.0) beside ``files``."""
    with tempfile.TemporaryDirectory() as tmp:
        entries = _erc.tops({**files, sheet: text}, Path(tmp))
        others = {name: path for name, path in entries.items() if name != sheet}
        return runner().upgrade_schematic(Path(tmp) / sheet, files=others)


def resave_outcome() -> str:
    """``equal`` when a second re-save of the built blink is byte-identical to the first and ERC still
    reports nothing on the re-saved sheet."""
    files = built("blink", 10)
    first = resave(files["blink.kicad_sch"], files)
    second = resave(first, files)
    report = _erc.run_erc(runner(), "blink.kicad_sch", {**files, "blink.kicad_sch": first})
    clean = report.loaded and not _erc.violations(report)
    return "equal" if second == first and clean else "different"


def gen_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {}
    for rotation in schlayout.ROTATIONS:
        for label, mirror in MIRRORS.items():
            probes[f"sch-pin-frame-{rotation}-{label}"] = (
                lambda rotation=rotation, mirror=mirror: frame_outcome(rotation, mirror),
                both,
            )
    for kind in ("plain", "unnamed", "units", "chars"):
        probes[f"sch-unconnected-{kind}"] = (lambda kind=kind: unconnected_outcome(kind), both)
    probes["sch-label-plain"] = (lambda: label_outcome(LABEL_TEXTS[:1]), both)
    probes["sch-label-chars"] = (lambda: label_outcome(LABEL_TEXTS), both)
    probes["sch-label-slash"] = (lambda: label_outcome((SLASH_TEXT,), netnames.stored_name), both)
    probes["sch-parity-slash-stored"] = (lambda: slash_outcome(raw=False), both)
    probes["sch-parity-slash-raw"] = (lambda: slash_outcome(raw=True), both)
    probes["sch-power-flag"] = (power_flag_outcome, both)
    probes["sch-hidden-power-joined"] = (hidden_joined_outcome, both)
    probes["sch-shown-power-separate"] = (shown_separate_outcome, both)
    probes["sch-lib-missing"] = (lambda: library_outcome("blink", ("sym-lib-table",)), both)
    probes["sch-lib-vendored"] = (lambda: guarded_library("blink"), both)
    probes["sch-lib-variant"] = (lambda: guarded_library("units"), both)
    probes["sch-gen-erc-blink"] = (lambda: generated_erc_outcome("blink"), both)
    probes["sch-gen-erc-units"] = (lambda: generated_erc_outcome("units"), both)
    probes["sch-gen-resave"] = (resave_outcome, (10,))
    return probes


__all__ = [
    "CHAR_PINS",
    "LABEL_TEXTS",
    "SLASH_TEXT",
    "Inst",
    "built",
    "built_erc",
    "built_parity",
    "frame_outcome",
    "frame_sheet",
    "frame_unconnected",
    "gen_probes",
    "hand_sheet",
    "label_nets",
    "label_outcome",
    "power_sheet",
    "probe_symbol",
    "resave",
    "resave_outcome",
    "supply_nets",
    "unconnected_names",
    "unconnected_outcome",
]
