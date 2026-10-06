# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The corpus demos that have a board and a schematic at one tag, as projects in a temporary folder, and
the two sides of a parity comparison of a project: KiCad's report and Fenolite's findings (change c0072;
capability kicad-oracle, "Own parity agrees with kicad-cli"). Nothing derived from the corpus is kept."""

from __future__ import annotations

import re
import shutil
import tomllib
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import _schcorpus
from _corpus import MANIFEST
from _resources import corpus_cache_dir

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import parity_inputs
from fenolite.backends.kicad.cli import NETLIST, KicadCli
from fenolite.backends.kicad.netlist import KicadNetlist, read_netlist
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.checks import parity

TAG_OF_MAJOR = {10: "10.0.6", 9: "9.0.9.1"}
_BOARD = re.compile(r"/-/raw/([^/]+)/(demos/.+\.kicad_pcb)$")
TYPES: tuple[str, ...] = tuple(dict.fromkeys(parity.KICAD_TYPES.values()))
"""The KiCad parity types that Fenolite's comparison has a code for."""


@dataclass(frozen=True)
class DemoProject:
    """A demo at one tag: the id of its board row, and its board and root schematic in the temporary tree
    (the sheets of the hierarchy lie beside the root, as in the source tree)."""

    id: str
    name: str
    board: Path
    schematic: Path


def board_rows(tag: str) -> dict[str, tuple[str, Path]]:
    """Source path → (row id, cached file) of the demo boards at ``tag``."""
    cache = corpus_cache_dir()
    found: dict[str, tuple[str, Path]] = {}
    for row in tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", []):
        match = _BOARD.search(row["url"])
        uses = row.get("uses", [])
        # a board that is malformed as published is read by neither side
        if match and match.group(1) == tag and "heavy" not in uses and "malformed" not in uses:
            path = urllib.parse.unquote(match.group(2))
            found[path] = (row["id"], cache / row["id"] / Path(path).name)
    return found


def demo_projects(folder: Path, tag: str, *, newest: int) -> tuple[list[DemoProject], dict[str, int]]:
    """The demos of ``tag`` with a cached board and a root schematic of its stem, laid out under ``folder``
    with a ``{}`` project file, and the number of demos left out per reason. ``newest`` is the newest
    schematic format the running ``kicad-cli`` reads."""
    rows = [r for r in _schcorpus.rows() if tag in r.tags]
    placed = _schcorpus.layout(folder, tag, rows)
    by_path = _schcorpus.at_tag(tag, rows)
    by_file = {str(path): by_path[name] for name, path in placed.items()}
    left = {"no-schematic": 0, "not-cached": 0, "sch-old": 0, "newer-than-the-running-major": 0}
    found: list[DemoProject] = []
    for path, (row_id, cached) in sorted(board_rows(tag).items()):
        root = str(Path(path).with_suffix(".kicad_sch"))
        if root not in by_path:
            left["no-schematic"] += 1
            continue
        if not cached.is_file() or root not in placed:
            left["not-cached"] += 1
            continue
        sheets = [by_file[str(f)] for f in _schcorpus.project_files(placed[root]) if str(f) in by_file]
        if any("sch-old" in s.uses for s in sheets):
            left["sch-old"] += 1
            continue
        if any(_schcorpus.version_of(s.file) > newest for s in sheets):
            left["newer-than-the-running-major"] += 1
            continue
        board = folder / path
        shutil.copyfile(cached, board)
        board.with_suffix(".kicad_pro").write_text("{}\n", encoding="utf-8")
        found.append(DemoProject(row_id, Path(path).stem, board, placed[root]))
    return found, left


def newest_schematic(major: int) -> int:
    return FORMAT_VERSIONS[FileKind.SCHEMATIC][major]


def _others(folder: Path, without: str) -> dict[str, Path]:
    return {p.name: p for p in sorted(folder.iterdir()) if p.name != without}


def kicad_parity(cli: KicadCli, board: Path) -> DrcReport | None:
    """The DRC report of ``board`` with the parity test, run on copies of its folder."""
    return cli.drc(board, files=_others(board.parent, board.name), schematic_parity=True).report


def kicad_netlist(cli: KicadCli, schematic: Path) -> KicadNetlist | None:
    """``kicad-cli``'s netlist of ``schematic``, exported from copies of its folder."""
    run = cli.export_netlist(schematic, files=_others(schematic.parent, schematic.name))
    data = run.outputs.get(NETLIST)
    return None if data is None else read_netlist(data.decode("utf-8"), file=NETLIST)


def kicad_counts(report: DrcReport) -> dict[str, int]:
    """The number of parity entries of ``report`` per type of ``TYPES``; other types are left out."""
    counts = Counter(v.type for v in report.schematic_parity)
    return {kind: counts.get(kind, 0) for kind in TYPES}


def other_types(report: DrcReport) -> dict[str, int]:
    """The parity entries of ``report`` whose type Fenolite's comparison has no code for, per type."""
    counts = Counter(v.type for v in report.schematic_parity if v.type not in TYPES)
    return dict(sorted(counts.items()))


def own_report(board: Path, schematic: Path, netlist: KicadNetlist | None) -> parity.ParityReport:
    """Fenolite's comparison of ``board`` with ``schematic``; the nodes come from ``netlist``, or from the
    own netlist without one."""
    side = parity_inputs.schematic_side(schematic, netlist=netlist)
    design = read_board(board.read_text(encoding="utf-8"), file=board.name)
    return parity.compare(side, design)


def own_counts(report: parity.ParityReport) -> dict[str, int]:
    """The findings of ``report`` per KiCad type of ``TYPES``."""
    counts = Counter(entry[0] for f in report.findings if (entry := parity.oracle_entry(f)) is not None)
    return {kind: counts.get(kind, 0) for kind in TYPES}


__all__ = [
    "TAG_OF_MAJOR",
    "TYPES",
    "DemoProject",
    "board_rows",
    "demo_projects",
    "kicad_counts",
    "kicad_netlist",
    "kicad_parity",
    "newest_schematic",
    "other_types",
    "own_counts",
    "own_report",
]
