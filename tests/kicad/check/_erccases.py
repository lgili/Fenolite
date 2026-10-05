# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0062 (capability kicad-oracle, "ERC facts proved per major", "Parity in the DRC run"
and "ERC oracle"): the ``erc-*`` and ``drc-parity-*`` rows of ``_probes.PROBES``.

Every case starts from the blink that ``build`` writes for the running major, a project whose ERC and
parity reports are empty, and changes one thing by token edit: a label, a power flag, the symbol library
table, the project's severities or a pad's net. Reports are read through ``KicadCli.erc``,
``KicadCli.drc`` and the product readers, so the probes also prove the readers on real reports.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

from _buildhelp import blink_text, build
from _schbuild import design_of

from fenolite.backends.base import DrcReport, ErcReport
from fenolite.backends.kicad import canary, schlayout
from fenolite.backends.kicad import erc as ercmod
from fenolite.backends.kicad.cli import ERC_REPORT, DrcRun, ErcRun, KicadCli
from fenolite.backends.kicad.projectset import project_set
from fenolite.backends.kicad.sch import read_schematic
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = Mapping[str, bytes]
STEM = "blink"
SHEET = f"{STEM}.kicad_sch"
BOARD = f"{STEM}.kicad_pcb"
PROJECT = f"{STEM}.kicad_pro"
RULES = f"{STEM}.kicad_dru"
SYMBOL_TABLE = "sym-lib-table"
UDEG = 1_000_000
POSITION_PINS: tuple[tuple[str, str], ...] = (("D1", "1"), ("D1", "2"), ("R1", "1"), ("R1", "2"), ("U1", "1"))
"""The five pins whose labels the position probe removes: two parts at rotation 0 and one pin of the IC."""
SINGLE_PIN_LABEL: Mapping[int, str] = {9: "global_label_dangling", 10: "isolated_pin_label"}
"""The type each major reports for a global label that is alone on one pin (``H-K-ERC-TYPES``)."""
INPUT_PINS = ("11", "12")
"""Two input pins of ``U1`` (``NRST`` and ``OSC_IN``): on a net of their own, nothing drives them."""
CONTROL_TYPES: tuple[str, ...] = (
    "pin_not_connected",
    "pin_not_driven",
    "power_pin_not_driven",
    "lib_symbol_issues",
    "single_pin_label",
)
"""The five controls of ``H-K-ERC-TYPES``; ``single_pin_label`` stands for ``SINGLE_PIN_LABEL[major]``."""
INVENTED_CHILD = "(fenolite_invented_child 1)"
"""A root child no KiCad version knows: a schematic that does not load."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


def workdir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"fenolite-{prefix}-"))


# -- the built blink and its variants


def _built(text: str, target: int) -> dict[str, bytes]:
    output = build(design_of(text), target)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


@cache
def blink_files(target: int) -> Files:
    """The files ``build`` writes for the blink, without its ``.fenolite/`` cache."""
    return _built(blink_text(), target)


@cache
def undriven_files(target: int) -> Files:
    """The blink with the input pins ``INPUT_PINS`` of ``U1`` on a net ``NRST`` that nothing drives."""
    marked = "if pin not in (1, 9, 10)"
    text = blink_text()
    assert marked in text
    pins = ", ".join(INPUT_PINS)
    text = text.replace(marked, f"if pin not in (1, 9, 10, {pins})")
    return _built(text + f'\nconnect(Net("NRST"), {", ".join(f"u1[{p}]" for p in INPUT_PINS)})\n', target)


def write(files: Files, folder: Path) -> Path:
    """``files`` written under ``folder``; the folder."""
    for rel, data in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def tops(folder: Path, *, without: str = "") -> dict[str, Path]:
    """The top-level entries of ``folder`` as the ``files`` of a runner call, ``without`` one name."""
    return {p.name: p for p in sorted(folder.iterdir()) if p.name != without}


def run_erc(files: Files, sheet: str = SHEET) -> ErcRun:
    """``KicadCli.erc`` on ``files`` written to a fresh folder."""
    folder = write(files, workdir("erc"))
    try:
        return runner().erc(folder / sheet, files=tops(folder, without=sheet))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def run_drc(files: Files, *, parity: bool, board: str = BOARD) -> DrcRun:
    """``KicadCli.drc`` on ``files`` written to a fresh folder, with or without the parity flag."""
    folder = write(files, workdir("parity"))
    try:
        return runner().drc(folder / board, files=tops(folder, without=board), schematic_parity=parity)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


# -- token edits


def pin_points(sheet_text: str) -> dict[tuple[str, str], Point]:
    """``(reference, pin number)`` → the sheet position at which that pin connects, from the symbol
    instances and their embedded definitions (``schlayout.pin_point``)."""
    sheet = read_schematic(sheet_text, file=SHEET)
    definitions = {(f"{d.library}:{d.name}" if d.library else d.name): d for d in sheet.lib_symbols}
    found: dict[tuple[str, str], Point] = {}
    for symbol in sheet.symbols:
        definition = definitions.get(symbol.lib_name or symbol.lib_ref)
        if definition is None:
            continue
        for pin in definition.pins:
            if pin.unit not in (0, symbol.unit):
                continue
            point = schlayout.pin_point(symbol.position, pin.position, symbol.rotation // UDEG, symbol.mirror)
            found[(symbol.ref, pin.number)] = point
    return found


def _at(node: Node) -> Point | None:
    at = node.find("at")
    if at is None or len(at.atoms()) < 2:
        return None
    x, y = at.atoms()[:2]
    return Point(x.to_nm(), y.to_nm())


def _edited(files: Files, keep: Callable[[Node], bool]) -> tuple[dict[str, bytes], int]:
    tree = parse(files[SHEET].decode("utf-8"))
    children = [c for c in tree.children if not isinstance(c, Node) or keep(c)]
    edited = dict(files)
    edited[SHEET] = dumps(tree.with_children(children)).encode("utf-8")
    return edited, len(tree.children) - len(children)


def without_labels(files: Files, *pins: tuple[str, str]) -> dict[str, bytes]:
    """``files`` without the global label at the connection point of each of ``pins``."""
    points = pin_points(files[SHEET].decode("utf-8"))
    wanted = {points[pin] for pin in pins}
    edited, removed = _edited(files, lambda c: not (c.name == "global_label" and _at(c) in wanted))
    assert removed == len(pins), (removed, pins)
    return edited


def without_power_flag(files: Files, net: str = "VIN") -> dict[str, bytes]:
    """``files`` without the power flag symbol that sits on the label ``net``."""
    tree = parse(files[SHEET].decode("utf-8"))
    labels = {_at(c) for c in tree.nodes("global_label") if c.atoms()[0].value == net}

    def flag(node: Node) -> bool:
        lib = node.find("lib_id")
        named = lib is not None and lib.atoms()[0].value.endswith(":PWR_FLAG")
        return node.name == "symbol" and named and _at(node) in labels

    edited, removed = _edited(files, lambda c: not flag(c))
    assert removed == 1, removed
    return edited


def with_severity(files: Files, kind: str, level: str) -> dict[str, bytes]:
    """``files`` with ``/erc/rule_severities/<kind>`` of the project set to ``level``."""
    data = json.loads(files[PROJECT].decode("utf-8"))
    severities = data.setdefault("erc", {}).setdefault("rule_severities", {})
    severities[kind] = level
    edited = dict(files)
    edited[PROJECT] = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    return edited


def unloadable(files: Files) -> dict[str, bytes]:
    """``files`` whose schematic holds a root child that no KiCad knows."""
    text = files[SHEET].decode("utf-8")
    assert "\t(lib_symbols" in text
    edited = dict(files)
    edited[SHEET] = text.replace("\t(lib_symbols", f"\t{INVENTED_CHILD}\n\t(lib_symbols", 1).encode("utf-8")
    return edited


def _renet(node: Node, net: str, numbers: Mapping[str, str]) -> Node:
    """The ``net`` child of a pad on ``net``: ``(net "<name>")``, or ``(net <number> "<name>")`` on 9.0."""
    name = dumps(Atom.string(net)).strip()
    if len(node.atoms()) == 2:
        return parse(f"(net {numbers[net]} {name})")
    return parse(f"(net {name})")


def pad_on_net(files: Files, ref: str, pad: str, net: str) -> dict[str, bytes]:
    """``files`` whose board has pad ``pad`` of footprint ``ref`` on ``net`` (a net the board holds)."""
    tree = parse(files[BOARD].decode("utf-8"))
    numbers = {n.atoms()[1].value: n.atoms()[0].value for n in tree.nodes("net") if len(n.atoms()) == 2}
    done = 0

    def moved(node: Node) -> Node:
        nonlocal done
        if node.name != "pad" or node.atoms()[0].value != pad:
            return node
        children: list[Node | Atom] = []
        for child in node.children:
            if isinstance(child, Node) and child.name == "net":
                children.append(_renet(child, net, numbers))
                done += 1
            else:
                children.append(child)
        return node.with_children(children)

    def footprint(node: Node) -> Node:
        reference = [p for p in node.nodes("property") if p.atoms()[0].value == "Reference"]
        if node.name != "footprint" or not reference or reference[0].atoms()[1].value != ref:
            return node
        return node.with_children([moved(c) if isinstance(c, Node) else c for c in node.children])

    board = tree.with_children([footprint(c) if isinstance(c, Node) else c for c in tree.children])
    assert done == 1, f"pad {ref}-{pad} was found {done} times"
    edited = dict(files)
    edited[BOARD] = dumps(board).encode("utf-8")
    return edited


# -- H-K-ERC-JSON


@cache
def clean() -> ErcRun:
    return run_erc(blink_files(major()))


@cache
def one_open_pin() -> ErcRun:
    """The blink without the label of pin 1 of ``R1``."""
    return run_erc(without_labels(blink_files(major()), ("R1", "1")))


def _raw(run: ErcRun) -> dict[str, object] | None:
    data = run.run.outputs.get(ERC_REPORT)
    return None if data is None else json.loads(data.decode("utf-8"))


def report_keys() -> str:
    """``equal`` when both runs exit 0 and their reports hold every key of ``erc.REQUIRED_KEYS``."""
    for run in (clean(), one_open_pin()):
        raw = _raw(run)
        if raw is None or run.report is None:
            return "inconclusive"
        if run.run.returncode != 0:
            return "different"
        sheets = raw.get("sheets")
        if not isinstance(sheets, list) or not sheets:
            return "different"
        if any(key not in raw for key in ercmod.REQUIRED_KEYS["report"]):
            return "different"
        for sheet in sheets:
            if any(key not in sheet for key in ercmod.REQUIRED_KEYS["sheet"]):
                return "different"
            for violation in sheet["violations"]:
                if any(key not in violation for key in ercmod.REQUIRED_KEYS["violation"]):
                    return "different"
    found = one_open_pin().report
    assert found is not None
    return "equal" if found.of_type("pin_not_connected") else "different"


def ignored_checks() -> str:
    raw = _raw(clean())
    if raw is None:
        return "inconclusive"
    return "present" if "ignored_checks" in raw else "absent"


@cache
def unloadable_run() -> ErcRun:
    return run_erc(unloadable(blink_files(major())))


def unloadable_outcome() -> str:
    """``absent`` when a schematic that does not load gives no report and exit 3."""
    run = unloadable_run()
    if run.run.outcome == "timeout":
        return "timeout"
    if run.report is not None:
        return "present"
    return "absent" if run.run.returncode == 3 else "different"


def writes_settings() -> str:
    """``present`` when the run writes ``<stem>.kicad_prl`` beside its input, ``absent`` when it writes
    nothing but its report."""
    run = clean()
    if run.report is None:
        return "inconclusive"
    others = sorted(name for name in run.run.outputs if name != ERC_REPORT)
    if not others:
        return "absent"
    return "present" if others == [f"{STEM}.kicad_prl"] else "different"


# -- H-K-ERC-POS


@cache
def open_pins() -> tuple[ErcReport | None, dict[tuple[str, str], Point]]:
    """The report of the blink without the labels of ``POSITION_PINS``, and where those pins connect."""
    files = blink_files(major())
    points = pin_points(files[SHEET].decode("utf-8"))
    report = run_erc(without_labels(files, *POSITION_PINS)).report
    return report, {pin: points[pin] for pin in POSITION_PINS}


def reported_pins(report: ErcReport, files: Files) -> dict[str, Point]:
    """``REF-PIN`` → the position of each ``pin_not_connected`` item, located by uuid in the sheet."""
    locations = ercmod.item_locations({SHEET: parse(files[SHEET].decode("utf-8"))}, STEM)
    done = ercmod.located(report, locations)
    return {i.where: i.position for v in done.of_type("pin_not_connected") for i in v.items}


def position_scale() -> str:
    """``equal`` when each of the five open pins is reported at the point where it connects."""
    report, expected = open_pins()
    if report is None:
        return "inconclusive"
    found = reported_pins(report, blink_files(major()))
    wanted = {f"{ref}-{pin}": point for (ref, pin), point in expected.items()}
    return "equal" if found == wanted else "different"


# -- H-K-ERC-TYPES


def control_type(control: str) -> str:
    return SINGLE_PIN_LABEL[major()] if control == "single_pin_label" else control


def control_files(control: str) -> dict[str, bytes]:
    """The files of one control of ``CONTROL_TYPES``."""
    files = blink_files(major())
    if control == "pin_not_connected":
        return without_labels(files, ("R1", "1"))
    if control == "pin_not_driven":
        return dict(undriven_files(major()))
    if control == "power_pin_not_driven":
        return without_power_flag(files)
    if control == "lib_symbol_issues":
        return {rel: data for rel, data in files.items() if rel != SYMBOL_TABLE}
    if control == "single_pin_label":
        return without_labels(files, ("D1", "2"))
    raise KeyError(control)


@cache
def control_report(control: str, level: str = "") -> ErcReport | None:
    files = control_files(control)
    if level:
        files = with_severity(files, control_type(control), level)
    return run_erc(files).report


def type_present(kind: str, control: str) -> str:
    report = control_report(control)
    if report is None:
        return "inconclusive"
    return "present" if report.of_type(kind) else "absent"


def type_ignored(control: str) -> str:
    """``absent`` when the control reports its type by default and nothing of it once it is ignored."""
    default, ignored = control_report(control), control_report(control, "ignore")
    if default is None or ignored is None or not default.of_type(control_type(control)):
        return "inconclusive"
    return "absent" if not ignored.of_type(control_type(control)) else "present"


def type_warning(control: str) -> str:
    """``equal`` when every entry of the type has severity ``warning`` once the project says so."""
    report = control_report(control, "warning")
    if report is None:
        return "inconclusive"
    found = report.of_type(control_type(control))
    if not found:
        return "inconclusive"
    return "equal" if all(v.severity == "warning" for v in found) else "different"


# -- H-K-PARITY-RUN


def parity_types(report: DrcReport | None) -> list[str]:
    return [] if report is None else sorted(v.type for v in report.schematic_parity)


def parity_entries(report: DrcReport) -> list[tuple[str, str, bool, tuple[str, ...]]]:
    return sorted(
        (v.type, v.severity, v.excluded, tuple(sorted(i.uuid for i in v.items)))
        for v in report.schematic_parity
    )


@cache
def conflict_files() -> Files:
    """The blink whose pad 2 of ``R1`` is on ``GND``: the board disagrees with the schematic."""
    return pad_on_net(blink_files(major()), "R1", "2", "GND")


@cache
def conflict_run(parity: bool) -> DrcRun:
    return run_drc(conflict_files(), parity=parity)


def parity_flag() -> str:
    """``present`` when the flagged run reports the conflict and the clean blink reports nothing."""
    control = run_drc(blink_files(major()), parity=True).report
    report = conflict_run(True).report
    if report is None or control is None or control.schematic_parity:
        return "inconclusive"
    return "present" if report.schematic_parity else "absent"


def parity_noflag() -> str:
    report = conflict_run(False).report
    if report is None:
        return "inconclusive"
    return "absent" if not report.schematic_parity else "present"


def canary_parity() -> str:
    """``equal`` when the run on the canary's staged board and rules gives the parity entries of the plain
    run, and no parity entry names a canary track."""
    files = dict(conflict_files())
    rule = canary.canary_rule_text(major())
    assert rule is not None, "the net selector is unproven on this major"
    staged = dict(files)
    staged[BOARD] = canary.inject_board(files[BOARD], file=BOARD)
    staged[RULES] = canary.append_rule(files[RULES], rule, major=major())
    plain, with_canary = conflict_run(True).report, run_drc(staged, parity=True).report
    if plain is None or with_canary is None or not plain.schematic_parity:
        return "inconclusive"
    if not canary.canary_fired(with_canary):
        return "inconclusive"
    named = {i.uuid for v in with_canary.schematic_parity for i in v.items}
    if named & set(canary.CANARY_UUIDS):
        return "different"
    return "equal" if parity_entries(with_canary) == parity_entries(plain) else "different"


@cache
def unloadable_parity() -> DrcRun:
    return run_drc(unloadable(blink_files(major())), parity=True)


def parity_unloadable() -> str:
    """What the flagged run writes when the schematic does not load: ``absent`` for no report,
    ``present`` for a report with parity entries, ``equal`` for a report without any."""
    run = unloadable_parity()
    if run.run.outcome == "timeout":
        return "timeout"
    if run.report is None:
        return "absent"
    return "present" if run.report.schematic_parity else "equal"


# -- H-K-ERC-COPYSET


def hierarchy_folder() -> str:
    """The authored hierarchy at a format the running major loads."""
    return "hier" if major() >= 10 else "hier_v9"


def with_decoys(root: Path, sheet: str) -> Path:
    """``root`` with files that an ERC run must not need: notes, another schematic that the hierarchy
    does not reach, a symbol library that no table names, and the local settings KiCad itself writes."""
    (root / "notes.txt").write_text("not a KiCad file\n", encoding="utf-8", newline="\n")
    (root / "unrelated.kicad_sch").write_bytes((root / sheet).read_bytes())
    (root / "unnamed.kicad_sym").write_text(
        "(kicad_symbol_lib (version 20241209) (generator fenolite-test))\n", encoding="utf-8", newline="\n"
    )
    first = runner().erc(root / sheet, files=tops(root, without=sheet))
    written = {name: data for name, data in first.run.outputs.items() if name.endswith(".kicad_prl")}
    for name, data in written.items():
        (root / name).write_bytes(data)
    if not written:  # 9.0.9 writes none: an authored one stands in
        from _projects import PRL

        (root / f"{Path(sheet).stem}.kicad_prl").write_text(PRL, encoding="utf-8", newline="\n")
    return root


def erc_entries(report: ErcReport | None) -> object:
    return None if report is None else report.entries()


def copyset_of(root: Path, sheet: str) -> str:
    """``equal`` when ERC on the planned copy set gives the entries of ERC on a copy of the whole folder.

    The reference runs twice: when its two runs differ, the outcome is ``inconclusive`` and never a false
    ``different`` (``H-K-ERC-REPEAT``)."""
    cli = runner()
    project = project_set(root / f"{Path(sheet).stem}.kicad_pcb")
    if sheet not in project.files:
        return "inconclusive"
    planned = cli.erc(root / sheet, files={k: v for k, v in project.files.items() if k != sheet}).report
    first = cli.erc(root / sheet, files=tops(root, without=sheet)).report
    second = cli.erc(root / sheet, files=tops(root, without=sheet)).report
    if planned is None or first is None or second is None or first.entries() != second.entries():
        return "inconclusive"
    return "equal" if planned.entries() == first.entries() else "different"


@cache
def copyset_roots() -> tuple[tuple[Path, str], ...]:
    """The built blink and the authored hierarchy of the running major, each with decoys."""
    from _projects import built_blink_project, hierarchy_project

    folder = workdir("erc-copyset")
    blink = with_decoys(built_blink_project(folder / "blink", target=major()), SHEET)
    hier = with_decoys(
        hierarchy_project(folder / "hier", folder=hierarchy_folder(), major=major()), "top.kicad_sch"
    )
    return (blink, SHEET), (hier, "top.kicad_sch")


def erc_copyset() -> str:
    outcomes = {copyset_of(root, sheet) for root, sheet in copyset_roots()}
    for outcome in ("different", "inconclusive"):
        if outcome in outcomes:
            return outcome
    return "equal"


def drc_copyset() -> str:
    """``H-K-CHECK-COPYSET`` with a schematic in the folder: DRC with the parity test on the copy set
    equals DRC on a copy of the whole folder, for the blink whose board disagrees with its schematic."""
    import _checkcases

    cli = runner()
    root = with_decoys(write(conflict_files(), workdir("drc-copyset") / STEM), SHEET)
    project = project_set(root)
    others = {k: v for k, v in project.files.items() if k != BOARD}

    def found(report: DrcReport | None) -> object:
        return None if report is None else (_checkcases.violations(report), parity_entries(report))

    planned = found(cli.drc(root / BOARD, files=others, schematic_parity=True).report)
    whole = [
        found(cli.drc(root / BOARD, files=tops(root, without=BOARD), schematic_parity=True).report)
        for _ in range(2)
    ]
    if planned is None or None in whole or whole[0] != whole[1]:
        return "inconclusive"
    if not planned[1]:  # type: ignore[index]
        return "inconclusive"  # no parity entry: the schematic was not compared
    return "equal" if planned == whole[0] else "different"


def erc_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {
        "erc-report-keys": (report_keys, both),
        "erc-ignored-checks": (ignored_checks, both),
        "erc-unloadable": (unloadable_outcome, both),
        "erc-writes-prl": (writes_settings, both),
        "erc-position-scale": (position_scale, both),
        "erc-copyset": (erc_copyset, both),
        "check-copyset-schematic": (drc_copyset, both),
        "drc-parity-flag": (parity_flag, both),
        "drc-parity-noflag": (parity_noflag, both),
        "drc-parity-canary": (canary_parity, both),
        "drc-parity-unloadable": (parity_unloadable, both),
    }
    for control in CONTROL_TYPES:
        if control == "single_pin_label":
            for kind in sorted(set(SINGLE_PIN_LABEL.values())):
                name = kind.replace("_", "-")
                probes[f"erc-type-{name}"] = (lambda kind=kind: type_present(kind, "single_pin_label"), both)
            name = "single-pin-label"
        else:
            name = control.replace("_", "-")
            probes[f"erc-type-{name}"] = (lambda control=control: type_present(control, control), both)
        probes[f"erc-type-{name}-ignored"] = (lambda control=control: type_ignored(control), both)
        probes[f"erc-sev-{name}-warning"] = (lambda control=control: type_warning(control), both)
    return probes


__all__ = [
    "BOARD",
    "CONTROL_TYPES",
    "POSITION_PINS",
    "SHEET",
    "SINGLE_PIN_LABEL",
    "STEM",
    "blink_files",
    "canary_parity",
    "clean",
    "conflict_files",
    "conflict_run",
    "control_files",
    "control_report",
    "control_type",
    "drc_copyset",
    "copyset_of",
    "copyset_roots",
    "erc_copyset",
    "erc_entries",
    "erc_probes",
    "hierarchy_folder",
    "one_open_pin",
    "open_pins",
    "pad_on_net",
    "parity_entries",
    "parity_types",
    "pin_points",
    "reported_pins",
    "run_drc",
    "run_erc",
    "tops",
    "unloadable",
    "unloadable_parity",
    "unloadable_run",
    "undriven_files",
    "with_decoys",
    "with_severity",
    "without_labels",
    "without_power_flag",
    "writes_settings",
    "workdir",
    "write",
]
