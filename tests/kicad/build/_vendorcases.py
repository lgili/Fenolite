# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Vendoring and user-property probes (c0027 Decision 16; capability kicad-oracle, "Vendored projects and
user properties pass the oracle").

A session folder holds a fake global library (copies of the CC0 ``Mini_v9.pretty`` and
``Mini_v9.kicad_sym``) named by the rows ``Mini`` of the global tables of a configuration folder ``D``
(``<D>/<M>.0/fp-lib-table`` and ``sym-lib-table``), and ``D_alt``, the same with ``Mini_R_0603`` pad ``1``
moved 0.05 mm along X. The blink is built from a folder without project tables with ``config_home=D``.
Configuration folders reach ``kicad-cli`` only as the ``KICAD_CONFIG_HOME`` entry of ``KicadCli.run``;
every other run uses the runner's empty configuration folder. Verdicts come from the DRC JSON report.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _buildcases import PROJECT, _folder, upgraded
from _buildhelp import LIBS, blink, build
from _probe_boards import probe_board

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import DRC_REPORT, KicadCli
from fenolite.backends.kicad.drc import read_drc_report
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.lens.build import BuildOutput

BOARD = "blink.kicad_pcb"
USED = ("Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603")
PROPERTIES: Mapping[str, Mapping[str, str]] = {
    "R1": {"Part number": "PN-330", "Supplier code": 'S-1 "q" \\ µ'},
    "D1": {"Part number": "PN-LED"},
}
"""The user properties of the property board: two on ``R1`` (one value with ``"``, ``\\`` and ``µ``) and
one on the bottom part ``D1``."""
DUPNAMES = (("Datasheet", "inserted-datasheet"), ("datasheet", "lower-case"), ("reference", "lower-ref"))
LIBRARY_TYPES = ("lib_footprint_issues", "lib_footprint_mismatch")


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


# --- the session bench ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Bench:
    root: Path
    config: Path
    config_alt: Path
    empty_project: Path


def _move_pad(text: str) -> str:
    """``Mini_R_0603`` with pad ``1`` moved 0.05 mm along X (the ``D_alt`` control)."""
    moved, count = re.subn(r'(\(pad "1" [^\n]*\n\s*\(at )(-?[0-9.]+)', lambda m: f"{m.group(1)}-0.75", text)
    assert count == 1 and "(at -0.8 0)" in text
    return moved


def _library(folder: Path, *, alt: bool) -> tuple[Path, Path]:
    pretty = folder / "Mini.pretty"
    shutil.copytree(LIBS / "Mini_v9.pretty", pretty)
    if alt:
        path = pretty / "Mini_R_0603.kicad_mod"
        path.write_text(_move_pad(path.read_text(encoding="utf-8")), encoding="utf-8")
    symbols = folder / "Mini.kicad_sym"
    shutil.copyfile(LIBS / "Mini_v9.kicad_sym", symbols)
    return pretty, symbols


def _config(folder: Path, pretty: Path, symbols: Path) -> Path:
    for major_ in (9, 10):
        sub = folder / f"{major_}.0"
        sub.mkdir(parents=True)
        fp = LibTable("footprint", (LibRow("Mini", "KiCad", str(pretty)),))
        sy = LibTable("symbol", (LibRow("Mini", "KiCad", str(symbols)),))
        (sub / "fp-lib-table").write_text(write_lib_table(fp, target=major_), encoding="utf-8")
        (sub / "sym-lib-table").write_text(write_lib_table(sy, target=major_), encoding="utf-8")
    return folder


@cache
def bench() -> Bench:
    """The fake global libraries and configuration folders, made once per session."""
    root = Path(tempfile.mkdtemp(prefix="fenolite-vendor-"))
    main = _library(root / "global", alt=False)
    alt = _library(root / "global_alt", alt=True)
    empty = root / "project"
    empty.mkdir()
    return Bench(root, _config(root / "D", *main), _config(root / "D_alt", *alt), empty)


# --- builds and variants ----------------------------------------------------------------------------


@cache
def built(target: int, vendor: str | None = None) -> BuildOutput:
    """The blink built from the fake global library; ``vendor`` is passed to ``build_design`` when set
    (this change's code), else the build keeps c0011's rule."""
    kwargs: dict[str, object] = {"project_dir": bench().empty_project, "config_home": bench().config}
    if vendor is not None:
        kwargs["vendor"] = vendor
    return build(blink(), target, **kwargs)


def _plain(output: BuildOutput) -> dict[str, str | bytes]:
    return {
        rel: data
        for rel, data in output.files.items()
        if not rel.startswith(".fenolite/") and not rel.startswith("lib/") and rel != "fp-lib-table"
    }


def vendored_files(target: int, *, without: str = "") -> dict[str, str | bytes]:
    """The plain build plus copies of its placed footprints in ``lib/Mini.pretty/`` and one project row
    (file copies, as the probes run before this change's build code)."""
    files = _plain(built(target))
    pretty = bench().root / "global" / "Mini.pretty"
    for name in USED:
        if name != without:
            files[f"lib/Mini.pretty/{name}.kicad_mod"] = (pretty / f"{name}.kicad_mod").read_bytes()
    table = LibTable("footprint", (LibRow("Mini", "KiCad", "${KIPRJMOD}/lib/Mini.pretty"),))
    files["fp-lib-table"] = write_lib_table(table, target=target)
    return files


def plain_files(target: int) -> dict[str, str | bytes]:
    """The build without vendoring: no ``lib/`` and a table without rows."""
    files = _plain(built(target))
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", ()), target=target)
    return files


def drc(files: Mapping[str, str | bytes], *, config: Path | None = None) -> DrcReport | None:
    """``pcb drc`` on a copy of ``files``, with ``config`` as ``KICAD_CONFIG_HOME`` when given."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        args = ["pcb", "drc", "--format", "json", "--severity-all", "-o", DRC_REPORT, BOARD]
        env = {"KICAD_CONFIG_HOME": str(config)} if config is not None else None
        run = runner().run(args, files=tops, env=env)
    data = run.outputs.get(DRC_REPORT)
    return None if data is None else read_drc_report(data.decode("utf-8"), file=DRC_REPORT)


def library_violations(report: DrcReport, kind: str) -> list[str]:
    """The descriptions of the ``kind`` violations (``lib_footprint_issues`` or ``…_mismatch``)."""
    return [v.description for v in report.violations if v.type == kind]


def counts(report: DrcReport | None) -> tuple[int, int] | None:
    if report is None:
        return None
    return tuple(len(library_violations(report, kind)) for kind in LIBRARY_TYPES)  # type: ignore[return-value]


# --- probes -----------------------------------------------------------------------------------------


@cache
def global_case(target: int) -> str:
    plain, vendored = drc(plain_files(target)), drc(vendored_files(target))
    if plain is None or vendored is None:
        return "reject"
    plain_issues, _ = counts(plain)  # type: ignore[misc]
    issues, mismatch = counts(vendored)  # type: ignore[misc]
    if plain_issues == 0:
        return "inconclusive"
    if issues:
        return "absent"
    if mismatch or plain_issues != len(USED):
        return "different"
    return "equal"


@cache
def shadow_case(target: int) -> str:
    control = drc(plain_files(target), config=bench().config_alt)
    vendored = drc(vendored_files(target), config=bench().config_alt)
    if control is None or vendored is None:
        return "reject"
    if counts(control) != (0, 1):
        return "inconclusive"
    return "present" if counts(vendored) == (0, 0) else "absent"


@cache
def hide_case(target: int) -> str:
    control = drc(plain_files(target), config=bench().config)
    hidden = drc(vendored_files(target, without="Mini_LED_THT_3mm"), config=bench().config)
    if control is None or hidden is None:
        return "reject"
    if counts(control) != (0, 0):
        return "inconclusive"
    found = counts(hidden)
    if found == (0, 0):
        return "absent"
    (issue,) = [v for v in hidden.violations if v.type == "lib_footprint_issues"] or [None]
    on_d1 = issue is not None and any(i.description == "Footprint D1" for i in issue.items)
    return "present" if found == (1, 0) and on_d1 else "different"


def property_board_text(target: int) -> str:
    return write_board(probe_board(target, properties=PROPERTIES), target=target).text


def property_files(target: int) -> dict[str, str | bytes]:
    files: dict[str, str | bytes] = {BOARD: property_board_text(target), "blink.kicad_pro": PROJECT}
    pretty = LIBS / "Mini_v9.pretty"
    for name in USED:
        files[f"lib/Mini.pretty/{name}.kicad_mod"] = (pretty / f"{name}.kicad_mod").read_bytes()
    table = LibTable("footprint", (LibRow("Mini", "KiCad", "${KIPRJMOD}/lib/Mini.pretty"),))
    files["fp-lib-table"] = write_lib_table(table, target=target)
    return files


@cache
def props_case(target: int) -> str:
    report = drc(property_files(target))
    if report is None:
        return "reject"
    return "equal" if counts(report) == (0, 0) else "different"


def _user_nodes(text: str) -> dict[str, list[Node]]:
    """Reference → the property nodes of its footprint (the reader's view of names)."""
    out: dict[str, list[Node]] = {}
    for fp in parse(text).nodes("footprint"):
        props = fp.nodes("property")
        ref = next(p.atoms()[1].value for p in props if p.atoms()[0].value == "Reference")
        out[ref] = props
    return out


@cache
def resave_case(target: int) -> str:
    try:
        text = upgraded(property_files(target), BOARD)
    except Exception:  # noqa: BLE001 - any failure of the upgrade is the probe's reject
        return "reject"
    back = {c.ref: c.properties for c in read_board(text).circuit.components}
    nodes = _user_nodes(text)
    for ref, props in PROPERTIES.items():
        for key, value in props.items():
            if back.get(ref, {}).get(key) != value:
                return "absent"
            wanted = [p for p in nodes.get(ref, []) if p.atoms()[0].value == key]
            if len(wanted) != 1 or wanted[0].find("hide") is None:
                return "absent"
        if back[ref].get(PATH_PROPERTY) != ref:
            return "absent"
    return "present"


def _insert_after_last_property(text: str, ref: str, extra: tuple[tuple[str, str], ...]) -> str:
    root = parse(text)
    children: list[Node | Atom] = []
    for index, child in enumerate(root.children):
        if isinstance(child, Node) and child.name == "footprint":
            props = child.nodes("property")
            if any(p.atoms()[0].value == "Reference" and p.atoms()[1].value == ref for p in props):
                kids = list(child.children)
                last = max(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "property")
                new = [
                    parse(
                        f'(property "{name}" "{value}" (at 0 0 0) (layer "F.Fab") (hide yes) '
                        f'(uuid "00000000-0000-4000-8000-{index * 10 + n:012d}") '
                        "(effects (font (size 1 1) (thickness 0.15))))"
                    )
                    for n, (name, value) in enumerate(extra, start=1)
                ]
                kids[last + 1 : last + 1] = new
                child = child.with_children(kids)
        children.append(child)
    return dumps(root.with_children(children), style="kicad")


@cache
def dupname_case() -> str:
    files = vendored_files(10)
    board = files[BOARD]
    files[BOARD] = _insert_after_last_property(
        board if isinstance(board, str) else board.decode("utf-8"), "R1", DUPNAMES
    )
    try:
        text = upgraded(files, BOARD)
    except Exception:  # noqa: BLE001 - any failure of the upgrade is the probe's outcome
        return "different"
    nodes = [p for p in _user_nodes(text)["R1"]]
    names = [p.atoms()[0].value for p in nodes]
    datasheets = [p for p in nodes if p.atoms()[0].value == "Datasheet"]
    kept = "datasheet" in names and "reference" in names
    if len(datasheets) == 2:
        return "absent"
    if len(datasheets) == 1 and datasheets[0].atoms()[1].value == DUPNAMES[0][1] and kept:
        return "present"
    return "different"


# --- builds of this change's code (task 6.1) ----------------------------------------------------------


def built_files(target: int, vendor: str, properties: bool = False) -> dict[str, str | bytes]:
    """The files of the blink built from the fake global library by ``build_design(vendor=…)``, without
    ``.fenolite/``; ``properties`` gives ``R1`` and ``D1`` the user properties of ``PROPERTIES``."""
    design = blink()
    if properties:
        for ref, values in PROPERTIES.items():
            design.parts[ref].properties = dict(sorted(values.items()))
    output = build(
        design, target, project_dir=bench().empty_project, config_home=bench().config, vendor=vendor
    )
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def without(files: Mapping[str, str | bytes], name: str) -> dict[str, str | bytes]:
    return {rel: data for rel, data in files.items() if rel != f"lib/Mini.pretty/{name}.kicad_mod"}


def vendor_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)``: target-10 cases on major 10, target-9 cases on both."""
    probes: dict[str, tuple[object, tuple[int, ...]]] = {}
    for target, majors in ((9, (9, 10)), (10, (10,))):
        probes[f"vendor-global-t{target}"] = (lambda t=target: global_case(t), majors)
        probes[f"vendor-shadow-t{target}"] = (lambda t=target: shadow_case(t), majors)
        probes[f"vendor-hide-t{target}"] = (lambda t=target: hide_case(t), majors)
        probes[f"vendor-props-t{target}"] = (lambda t=target: props_case(t), majors)
        probes[f"vendor-resave-t{target}"] = (lambda t=target: resave_case(t), (10,))
    probes["vendor-dupname-t10"] = (dupname_case, (10,))
    return probes


__all__ = [
    "DUPNAMES",
    "PROPERTIES",
    "USED",
    "bench",
    "built",
    "counts",
    "drc",
    "dupname_case",
    "global_case",
    "hide_case",
    "plain_files",
    "property_board_text",
    "property_files",
    "props_case",
    "resave_case",
    "shadow_case",
    "built_files",
    "vendor_probes",
    "vendored_files",
    "without",
]
