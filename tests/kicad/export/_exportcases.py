# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0024 (capability kicad-oracle, "Exports are probed on both majors"): the ``export-*``
rows of ``_probes.PROBES``.

``export-files-<kind>`` compares the files a kind writes with the expected set, ``export-repeat-<kind>``
exports twice and compares the date-stripped hashes, and ``export-render-*`` asks for one view. The
subjects are ``two_layer.kicad_pcb`` and the authored project of the running major.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

from _boards import FIXTURE
from _projects import authored_project

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.plot import plot_view, png_size
from fenolite.backends.kicad.projectset import project_set
from fenolite.exports.manifest import content_sha256
from fenolite.exports.plan import (
    FAB_KINDS,
    JOB_SUFFIX,
    VOLATILE_PREFIXES,
    KindResult,
    gerber_layers,
    run_kind,
)

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
RENDER_SIZE = (400, 300)


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@cache
def subjects() -> tuple[tuple[Path, dict[str, Path]], ...]:
    """``(board, the rest of its copy set)`` for the fixture board and the authored project."""
    root = authored_project(Path(tempfile.mkdtemp(prefix="fenolite-export-")), major=runner().major())
    project = project_set(root)
    others = {name: path for name, path in project.files.items() if name != project.board}
    return ((FIXTURE, {}), (root / project.board, others))


@cache
def exported(kind: str, subject: int, attempt: int = 0) -> KindResult:
    """One export of ``kind`` for a subject; ``attempt`` asks for another run."""
    board, files = subjects()[subject]
    cli = runner()
    return run_kind(cli, kind, board, files, major=cli.major(), design=read_board(board))


def expected_names(kind: str, board: Path) -> set[str]:
    stem = board.stem
    if kind == "drill":
        return {f"drill/{stem}-PTH.drl", f"drill/{stem}-NPTH.drl"}
    if kind == "pos":
        return {f"pos/{stem}-pos.csv"}
    if kind == "ipcd356":
        return {f"netlist/{stem}.d356"}
    raise ValueError(kind)


def files_outcome(kind: str) -> str:
    """``equal`` when every subject gives exactly the expected files, ``reject`` when a run fails."""
    for index, (board, _) in enumerate(subjects()):
        result = exported(kind, index)
        if result.issues:
            return "reject"
        paths = {a.path for a in result.artifacts}
        if kind == "gerbers":
            layers = gerber_layers(read_board(board))
            plots = [a for a in result.artifacts if not a.path.endswith(JOB_SUFFIX)]
            named = all(Path(a.path).name.startswith(f"{board.stem}-") for a in result.artifacts)
            job = f"gerbers/{board.stem}{JOB_SUFFIX}" in paths
            if not (named and job and sorted(a.layer or "" for a in plots) == sorted(layers)):
                return "different"
        elif paths != expected_names(kind, board):
            return "different"
    return "equal"


def unknown_lines(kind: str) -> list[bytes]:
    """The first 40 bytes of every line that differs between two exports and is not a known date line."""
    found: list[bytes] = []
    prefixes = VOLATILE_PREFIXES[kind]
    for index in range(len(subjects())):
        first = {a.path: a.data for a in exported(kind, index).artifacts}
        second = {a.path: a.data for a in exported(kind, index, 1).artifacts}
        for path in sorted(first):
            a, b = first[path].splitlines(), second.get(path, b"").splitlines()
            if len(a) != len(b):
                found.append(f"{path}: line count".encode())
                continue
            found += [
                x[:40] for x, y in zip(a, b, strict=True) if x != y and not x.lstrip().startswith(prefixes)
            ]
    return found


def byte_equal(kind: str) -> bool:
    """Whether two exports of every subject are byte-equal for ``kind``."""
    return all(
        [a.data for a in exported(kind, index).artifacts]
        == [a.data for a in exported(kind, index, 1).artifacts]
        for index in range(len(subjects()))
    )


def repeat_outcome(kind: str) -> str:
    """``equal`` when every file of two exports has the same ``content_sha256``."""
    for index in range(len(subjects())):
        first, second = exported(kind, index), exported(kind, index, 1)
        if first.issues or second.issues:
            return "reject"
        one = {a.path: content_sha256(a.data, kind) for a in first.artifacts}
        two = {a.path: content_sha256(a.data, kind) for a in second.artifacts}
        if one != two:
            return "different"
    return "equal"


@cache
def view(name: str) -> tuple[bytes | None, str]:
    board, files = subjects()[1]
    width, height = RENDER_SIZE
    return plot_view(runner(), name, board, files, width=width, height=height)


def render_outcome(kind: str) -> str:
    """``present`` when both views of ``kind`` are written (a PNG no larger than asked), else ``absent``."""
    for name in ("front.svg", "back.svg") if kind == "svg" else ("top.png", "bottom.png"):
        data, _ = view(name)
        if data is None:
            return "absent"
        if kind == "svg" and b"<svg" not in data:
            return "absent"
        if kind == "png":
            size = png_size(data)
            if size is None or not (0 < size[0] <= RENDER_SIZE[0] and 0 < size[1] <= RENDER_SIZE[1]):
                return "absent"
    return "present"


def export_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {}
    for kind in FAB_KINDS:  # the six document kinds are probed by _doccases (c0116)
        probes[f"export-files-{kind}"] = (lambda kind=kind: files_outcome(kind), both)
        probes[f"export-repeat-{kind}"] = (lambda kind=kind: repeat_outcome(kind), both)
    probes["export-render-png"] = (lambda: render_outcome("png"), both)
    probes["export-render-svg"] = (lambda: render_outcome("svg"), both)
    return probes


__all__ = ["byte_equal", "export_probes", "exported", "render_outcome", "subjects", "unknown_lines", "view"]
