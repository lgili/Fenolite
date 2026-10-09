# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracles of ``fenolite convert`` (change c0159): the triangle of KiCad to Altium
(``H-K-CONV-TRIANGLE``) and the re-target of a KiCad 9 project to KiCad 10 (``H-K-CONV-RETARGET``).

The triangle converts a KiCad board to Altium, imports the written PCB document with ``kicad-cli pcb
import`` (10.0) and compares the board that KiCad makes of it with the design that was written, at level 5
under the importer's profile ``kicad-import``. A difference that a lost item of the conversion's report
explains (``convert.report.Explainer``) is no fault of the triangle.

The re-target converts a project built for KiCad 9 to KiCad 10 and runs DRC on the source in 9.0.9 and on
the written board in 10.0.6; the two reports must name the same violation types. One major runs per
session, so the probe of each major records the types its runner gives in ``docs/evidence/conversion.md``
and the test compares them with the other major's recorded list.
"""

from __future__ import annotations

import shutil
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _resources import kicad_cli

from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import KicadCli, cli_for
from fenolite.checks.equivalence import (
    EquivalenceReport,
    Tolerances,
    compare_designs,
    load_profiles,
    max_level,
    select_profile,
)
from fenolite.checks.equivalence.model import Difference
from fenolite.convert import convert_project
from fenolite.convert.report import Explainer

ROOT = Path(__file__).resolve().parents[2]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
BLINK_T9 = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t9"
BLINK_T10 = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t10"
FORTY_T9 = ROOT / "tests" / "data" / "acceptance" / "board_40parts_t9"
SAMPLES = {"two_layer": TWO_LAYER, "blink": BLINK_T10}
"""The committed KiCad boards of the triangle."""
RETARGETS = {"blink": BLINK_T9, "board_40parts": FORTY_T9, "two_layer": TWO_LAYER}
"""The committed KiCad 9 sources of the re-target: two projects and a board without project files."""
DEMO_RETARGETS: dict[str, tuple[str, str | None]] = {
    "custom_pads_test": ("kicad-demo-9-0-9-1-pcb-01", "kicad-demo-9-0-9-1-pro-01"),
    "flat_hierarchy": ("kicad-demo-9-0-9-1-pcb-02", "kicad-demo-9-0-9-1-pro-02"),
    "pic_programmer": ("kicad-demo-9-0-9-1-pcb-03", "kicad-demo-9-0-9-1-pro-04"),
    "test_pads_inside_pads": ("kicad-demo-9-0-9-1-pcb-05", None),
    "carte_test": ("kicad-demo-9-0-9-1-pcb-06", None),
}
"""The KiCad 9.0.9.1 demo boards of the corpus (S-0058) with the project file of their stem where the
corpus holds one: name → (board row, project row)."""
TIMEOUT = 900


@cache
def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return cli_for(Path(path), timeout=TIMEOUT)


@dataclass(frozen=True)
class Triangle:
    """The comparison of a conversion with KiCad's import of it, and the differences no loss explains."""

    report: EquivalenceReport
    explained: tuple[tuple[Difference, str], ...]
    unexplained: tuple[Difference, ...]
    messages: tuple[str, ...]


@cache
def triangle(source: Path) -> Triangle:
    """Convert ``source`` to Altium, import its PCB document with ``kicad-cli`` and compare."""
    conversion = convert_project(source, to="altium", allow_lossy=True)
    with tempfile.TemporaryDirectory(prefix="fenolite-convtri-") as name:
        folder = Path(name)
        for key, data in conversion.files.items():
            (folder / key).write_bytes(data)
        imported = altium_import.import_design(runner(), folder / conversion.read_back)
    profiles = load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE)
    profile = select_profile(profiles, altium_import.PROFILE, imported.tool_version)
    assert profile is not None, imported.tool_version
    design, back = conversion.design, imported.read.design
    report = compare_designs(
        design,
        back,
        level=max_level(design, back),
        tolerances=Tolerances(profile.tolerance_nm, profile.tolerance_udeg, profile.tolerance_ppm),
        frame="relative",
        rules=profile.rules,
    )
    explainer = Explainer(design, conversion.report)
    explained: list[tuple[Difference, str]] = []
    unexplained: list[Difference] = []
    for difference in report.differences:
        kind = explainer.explain(difference.kind, difference.where, difference.a, difference.b)
        if kind is None:
            unexplained.append(difference)
        else:
            explained.append((difference, kind))
    return Triangle(report, tuple(explained), tuple(unexplained), imported.messages)


def triangle_outcome() -> str:
    """``equal`` when the import of each sample's conversion equals the source at level 5, every
    difference explained by the report; else ``different``."""
    for source in SAMPLES.values():
        found = triangle(source)
        if found.unexplained or found.report.levels[-1].level != 5:
            return "different"
    return "equal"


LIBRARY_FILES = ("fp-lib-table", "lib")
"""The footprint table of a committed project and the folder it names, given to both runs of the
re-target: a conversion writes no library table, and the user's libraries stay where they are."""


def drc_types(board: Path, libraries: Path) -> tuple[str, ...]:
    """The violation types, with their counts, of ``kicad-cli pcb drc`` on ``board`` with the project and
    rules files of its stem and the library table of the folder ``libraries``, sorted. Unconnected items
    count under their own type."""
    files = {
        path.name: path
        for path in (board.with_suffix(".kicad_pro"), board.with_suffix(".kicad_dru"))
        if path.is_file()
    }
    files.update({name: libraries / name for name in LIBRARY_FILES if (libraries / name).exists()})
    run = runner().drc(board, files=files)
    assert run.report is not None, run.run.stderr
    found = (*run.report.violations, *run.report.unconnected_items)
    counts = Counter(violation.type for violation in found)
    return tuple(f"{kind}={count}" for kind, count in sorted(counts.items()))


@cache
def _demo_folder() -> Path:
    return Path(tempfile.mkdtemp(prefix="fenolite-retarget-demos-"))


def source_of(name: str) -> Path:
    """The source ``name``: a committed one, or a demo board copied from the corpus cache with its project
    file into a folder of its own."""
    if name in RETARGETS:
        return RETARGETS[name]
    from _corpus import manifest_items, require

    rows = {item.id: item for use in ("rt0", "project") for item in manifest_items(use)}
    board_row, project_row = DEMO_RETARGETS[name]
    folder = _demo_folder() / name
    if not folder.is_dir():
        folder.mkdir(parents=True)
        shutil.copyfile(require(rows[board_row]), folder / f"{name}.kicad_pcb")
        if project_row is not None:
            shutil.copyfile(require(rows[project_row]), folder / f"{name}.kicad_pro")
    return folder


@cache
def source_types(name: str) -> tuple[str, ...]:
    """The DRC violation types of the source ``name`` on the running major (a KiCad 10 runner reads the
    board of 9 as it is)."""
    source = source_of(name)
    folder = source if source.is_dir() else source.parent
    return drc_types(folder / f"{name}.kicad_pcb", folder)


@cache
def converted_types(name: str) -> tuple[str, ...]:
    """The DRC violation types of the conversion of ``name`` to KiCad 10, on the running major (10)."""
    source = source_of(name)
    folder = source if source.is_dir() else source.parent
    conversion = convert_project(source, to="kicad", kicad_version=10)
    with tempfile.TemporaryDirectory(prefix="fenolite-retarget-") as tmp:
        written = Path(tmp) / name
        written.mkdir()
        for key, data in conversion.files.items():
            (written / key).write_bytes(data)
        return drc_types(written / f"{name}.kicad_pcb", folder)


def kinds(found: tuple[str, ...]) -> tuple[str, ...]:
    """The violation types of ``drc_types`` without their counts."""
    return tuple(entry.split("=", 1)[0] for entry in found)


SOURCE_TYPES_9: dict[str, tuple[str, ...]] = {
    "blink": (),
    "board_40parts": (),
    "two_layer": (
        "clearance=1", "hole_clearance=1", "isolated_copper=1", "lib_footprint_issues=2",
        "silk_over_copper=1", "solder_mask_bridge=1", "track_dangling=2", "unconnected_items=1",
        "via_dangling=1",
    ),
    "custom_pads_test": ("clearance=3",),
    "flat_hierarchy": ("lib_footprint_issues=64", "silk_edge_clearance=2"),
    "pic_programmer": ("lib_footprint_issues=63",),
    "test_pads_inside_pads": ("lib_footprint_issues=4",),
    "carte_test": (
        "copper_edge_clearance=1", "hole_clearance=1", "lib_footprint_issues=42", "silk_edge_clearance=4",
    ),
}  # fmt: skip
"""The DRC violation types of each source in ``kicad-cli`` 9.0.9 (measured on 2026-10-09 in the pinned
image): the record that a run on 10.0.6 compares the conversion with."""


def retarget_outcome() -> str:
    """``equal`` when each source gives, on a 9 runner, the recorded types, and on a 10 runner its
    conversion to 10 gives the recorded types of 9.0.9 and the same counts as the source read by 10.0.6;
    else ``different``."""
    for name in RETARGETS:
        if runner().major() == 9:
            if source_types(name) != SOURCE_TYPES_9[name]:
                return "different"
            continue
        converted = converted_types(name)
        if kinds(converted) != kinds(SOURCE_TYPES_9[name]) or converted != source_types(name):
            return "different"
    return "equal"


def conv_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    return {"convert-triangle": (triangle_outcome, (10,)), "convert-retarget": (retarget_outcome, (9, 10))}


__all__ = [
    "RETARGETS",
    "SAMPLES",
    "Triangle",
    "SOURCE_TYPES_9",
    "conv_probes",
    "DEMO_RETARGETS",
    "converted_types",
    "drc_types",
    "kinds",
    "source_of",
    "source_types",
    "runner",
    "triangle",
    "retarget_outcome",
    "triangle_outcome",
]
