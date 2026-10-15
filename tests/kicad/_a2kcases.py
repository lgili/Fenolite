# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracles of ``fenolite convert --to kicad`` from Altium (change c0161): the written board loads and
its DRC runs (``H-K-CONV-A2K-LOAD``), it agrees with ``kicad-cli pcb import`` of the same document at
level 5 (``H-K-CONV-A2K-IMPORT``), and the generated schematic passes ERC with its netlist equal to the
circuit (``H-K-CONV-A2K-SCH``).

The documents are the public PCB documents of the corpus (``altium-pcbdoc`` and ``altium`` rows
``altium-third-party-pcbdoc-01`` to ``-08``); each is converted for the running major with
``fenolite.api.convert(..., allow_lossy=True)`` and its files are written into a folder of their own.
"""

from __future__ import annotations

import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _resources import kicad_cli

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, cli_for
from fenolite.checks.equivalence import (
    EquivalenceReport,
    Tolerances,
    compare_designs,
    load_profiles,
    select_profile,
)
from fenolite.checks.equivalence.model import Difference
from fenolite.convert.report import Explainer

PREFIX = "altium-third-party-pcbdoc-"
DOCUMENTS = tuple(f"{PREFIX}{n:02d}" for n in range(1, 9))
TIMEOUT = 1200
IGNORED_REFS = ("", "[*]")
"""As the triangle of c0045: the empty reference of the pads without a component and the designator
``*`` cannot be paired by reference."""
KNOWN_IMPORT_FAILURES: dict[str, tuple[int, str]] = {
    "altium-third-party-pcbdoc-02": (255, "Unhandled exception class"),
}
"""As ``tests/_triangle.py``: the Linux build of ``kicad-cli`` 10.0.6 dies in its own importer on this
document; its agreement is not judged where the tool fails."""
SCHEMATIC_TYPES_OK = frozenset({
    "pin_not_connected", "pin_not_driven", "power_pin_not_driven", "lib_symbol_issues", "lib_symbol_mismatch",
    "footprint_link_issues", "single_global_label", "unconnected_wire_endpoint",
})  # fmt: skip
"""ERC types that say nothing of the connections the generator drew: open pins of generic symbols, which
the circuit leaves open too, pin types the generic symbols do not know, and library links."""


@cache
def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return cli_for(Path(path), timeout=TIMEOUT)


def source(row: str) -> Path:
    from _corpus import manifest_items, require

    items = {item.id: item for use in ("altium-pcbdoc", "altium") for item in manifest_items(use)}
    return require(items[row])


@cache
def converted(row: str, target: int) -> ConversionResult:
    return convert(source(row), to="kicad", kicad_version=target, allow_lossy=True)


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder.joinpath(*key.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder / result.conversion.read_back


@dataclass(frozen=True)
class Load:
    """What ``kicad-cli`` did with one written board: loaded (an SVG of ``Edge.Cuts``), the DRC report's
    violation types and counts (``None`` without a report), and the error text of a refused load."""

    loaded: bool
    drc: tuple[str, ...] | None
    message: str


@cache
def load(row: str, target: int) -> Load:
    result = converted(row, target)
    with tempfile.TemporaryDirectory(prefix="fenolite-a2k-") as tmp:
        board = _write(result, Path(tmp))
        files = {p.relative_to(Path(tmp)).as_posix(): p for p in Path(tmp).iterdir()}
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", board.name]
        run = runner().run(args, files=files)
        loaded = run.outcome == "exit" and run.returncode == 0 and "out.svg" in run.outputs
        drc = runner().drc(board, files=files)
    found = None
    if drc.report is not None:
        counts = Counter(v.type for v in (*drc.report.violations, *drc.report.unconnected_items))
        found = tuple(f"{kind}={count}" for kind, count in sorted(counts.items()))
    return Load(loaded, found, run.stderr.strip()[-300:])


def load_outcome(target: int) -> str:
    """``equal`` when every document's board written for ``target`` loads and its DRC writes a report."""
    for row in DOCUMENTS:
        found = load(row, target)
        print(f"{row} t{target}: loaded {found.loaded}, drc {found.drc} {found.message}")
        if not found.loaded or found.drc is None:
            return "different"
    return "equal"


@dataclass(frozen=True)
class Agreement:
    """The comparison of a conversion with KiCad's import of the same document, and the differences that
    no loss of the conversion's report explains; ``skipped`` holds the reason of a recorded tool failure."""

    report: EquivalenceReport | None
    explained: tuple[tuple[Difference, str], ...]
    unexplained: tuple[Difference, ...]
    skipped: str = ""


@cache
def agreement(row: str) -> Agreement:
    result = converted(row, 10)
    try:
        imported = altium_import.import_design(runner(), source(row))
    except KicadCliError as error:
        known = KNOWN_IMPORT_FAILURES.get(row)
        output = error.run.stdout + error.run.stderr
        if known is not None and error.run.returncode == known[0] and known[1] in output:
            return Agreement(None, (), (), f"kicad-cli pcb import exits {known[0]} in its own importer")
        raise
    profiles = load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE)
    profile = select_profile(profiles, altium_import.PROFILE, imported.tool_version)
    assert profile is not None, imported.tool_version
    design = result.conversion.design
    report = compare_designs(
        design,
        imported.read.design,
        level=5,
        tolerances=Tolerances(profile.tolerance_nm, profile.tolerance_udeg, profile.tolerance_ppm),
        frame=profile.frame,
        ignore_refs=IGNORED_REFS,
        rules=profile.rules,
    )
    explainer = Explainer(design, result.conversion.report)
    explained: list[tuple[Difference, str]] = []
    unexplained: list[Difference] = []
    for difference in report.differences:
        kind = explainer.explain(difference.kind, difference.where, difference.a, difference.b)
        if kind is None:
            unexplained.append(difference)
        else:
            explained.append((difference, kind))
    return Agreement(report, tuple(explained), tuple(unexplained))


def import_outcome() -> str:
    """``equal`` when every document that KiCad's importer takes agrees with the conversion at level 5,
    every difference explained by the report."""
    for row in DOCUMENTS:
        found = agreement(row)
        if found.skipped:
            print(f"{row}: skipped, {found.skipped}")
            continue
        assert found.report is not None
        print(f"{row}: level {found.report.levels[-1].level}, unexplained "
              f"{[(d.level, d.kind, d.where) for d in found.unexplained][:6]}")  # fmt: skip
        if found.unexplained or found.report.levels[-1].level != 5:
            return "different"
    return "equal"


@dataclass(frozen=True)
class SchematicRun:
    """ERC of the generated schematic (violation types and counts) and its netlist compared with the
    circuit at level 2 (the differences)."""

    erc: tuple[str, ...] | None
    differences: tuple[Difference, ...] | None


@cache
def schematic_run(row: str, target: int) -> SchematicRun | None:
    """``None`` for a document whose schematic the generator refused (the report names it lost)."""
    from fenolite.api.equivalence import equivalent

    result = converted(row, target)
    name = result.conversion.source.name
    if f"{name}.kicad_sch" not in result.conversion.files:
        return None
    with tempfile.TemporaryDirectory(prefix="fenolite-a2ks-") as tmp:
        folder = Path(tmp)
        _write(result, folder)
        files = {p.relative_to(folder).as_posix(): p for p in folder.iterdir()}
        erc = runner().erc(folder / f"{name}.kicad_sch", files=files)
        found = None
        if erc.report is not None:
            counts = Counter(v.type for v in erc.report.violations)
            found = tuple(f"{kind}={count}" for kind, count in sorted(counts.items()))
        compared = equivalent(result.conversion.design, folder / f"{name}.kicad_sch", level=2)
    differences = compared.report.differences if compared.report is not None else None
    return SchematicRun(found, differences)


def schematic_outcome(target: int) -> str:
    """``equal`` when each schematic the generator wrote passes ERC with no type outside
    ``SCHEMATIC_TYPES_OK`` and its netlist equals the circuit at level 2."""
    for row in DOCUMENTS:
        found = schematic_run(row, target)
        if found is None:
            print(f"{row} t{target}: no schematic (refused by the generator, reported lost)")
            continue
        bad = [entry for entry in found.erc or () if entry.split("=")[0] not in SCHEMATIC_TYPES_OK]
        print(f"{row} t{target}: erc {found.erc}, differences {len(found.differences or ())}")
        if found.erc is None or bad or found.differences is None or found.differences:
            return "different"
    return "equal"


def a2k_probes(major: Callable[[], int]) -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    return {
        "convert-a2k-load": (lambda: load_outcome(major()), (9, 10)),
        "convert-a2k-import": (import_outcome, (10,)),
        "convert-a2k-sch": (lambda: schematic_outcome(major()), (9, 10)),
    }


__all__ = [
    "DOCUMENTS",
    "Agreement",
    "Load",
    "SchematicRun",
    "a2k_probes",
    "agreement",
    "converted",
    "import_outcome",
    "load",
    "load_outcome",
    "schematic_outcome",
    "schematic_run",
]
