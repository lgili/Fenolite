# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracle cases of plane layers and of the plane fan-out (capability kicad-oracle, "Plane routing
passes the oracle"; hypotheses H-K-LAYER-POWER and H-K-FANOUT; change c0107).

**Row type.** The plane bench of ``tests/routing/_planebench.py`` is built without ``planes=``, so its inner
rows are ``signal``; it gets the hand-made dog-bones and one track of a signal net on each inner layer, the
copper a router may leave there. The same board with ``In1.Cu`` and ``In2.Cu`` of type ``power`` is the
board under test. ``pcb-layer-power-t<M>`` is ``equal`` when both boards load, the report of the ``power``
board holds no violation type that the ``signal`` board's lacks, and its inner Gerbers carry the file
functions ``Copper,L2,Inr`` and ``Copper,L3,Inr``, as a signal row's do. ``pcb-layer-power-resave`` is
``equal`` when ``pcb upgrade --force`` (10.0 only) keeps the two types.

**Fan-out.** The bench built with ``planes=`` for target M gets its fan-out from
``fenolite route --router direct`` with the two plane nets selected (the direct router avoids nothing, so the
signals are left to a real router). ``route-fanout-t<M>`` is ``equal`` when the copper check of the routed
board has no finding and, after ``fenolite fill`` with ``kicad-cli`` 10, ``pcb drc`` of the board's major
reports no unconnected item of a plane net and no violation type of severity error that the filled bench
without the fan-out lacks. The target-9 board is filled by ``kicad-cli`` 10 and judged by 9.0.
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

# the plane bench lives beside the routing gates; a run that loads this module without the conftest of
# ``tests/`` (the probe-file tests of ``tests/unit/test_kicad_probes.py``) still finds it
_ROUTING = str(Path(__file__).resolve().parents[2] / "routing")
if _ROUTING not in sys.path:
    sys.path.append(_ROUTING)

import _planebench as pb  # noqa: E402

from fenolite.backends.base import DrcReport  # noqa: E402
from fenolite.backends.kicad.cli import DOCKER_PREFIX, find_kicad_cli  # noqa: E402
from fenolite.backends.kicad.layers import plane_layers, with_plane_types  # noqa: E402
from fenolite.backends.kicad.pcb import read_board, write_board  # noqa: E402
from fenolite.checks.copper import check_copper  # noqa: E402
from fenolite.core.ids import derived_id  # noqa: E402
from fenolite.model.board import Track  # noqa: E402
from fenolite.model.design import Design  # noqa: E402

INNER_TRACKS = (("SIG3", "In1.Cu", 12.0), ("SIG4", "In2.Cu", 18.0))
"""One track per inner layer: net, layer and its row in millimetres from the top edge, from x = 10 mm to
x = 30 mm, clear of every hole of the bench."""
FILE_FUNCTION = re.compile(r"%TF\.FileFunction,Copper,L(\d+),(\w+)\*%")
PLANE_NETS = ("GND", "VCC")


def _related(board: Path) -> dict[str, Path]:
    """The project and rules files beside ``board``."""
    return {
        beside.name: beside
        for beside in (board.with_suffix(".kicad_pro"), board.with_suffix(".kicad_dru"))
        if beside.is_file()
    }


def _error_types(report: DrcReport) -> set[str]:
    return {v.type for v in report.violations if v.severity == "error" and not v.excluded}


# -- the row type


def routed_design(target: int, folder: Path) -> Design:
    """The bench with ``signal`` inner rows, the hand-made dog-bones and one signal track per inner layer."""
    found = pb.with_dogbones(pb.load(pb.build_project(folder, target=target, planes=False)))
    board = found.design.board
    assert board is not None
    tracks = tuple(
        Track(
            id=derived_id("trk", "planecases", f"{net}:{layer}"),
            start=pb.at(10, row, found.design),
            end=pb.at(30, row, found.design),
            width=200_000,
            layer=layer,
            net_id=found.net_id(net),
        )
        for net, layer, row in INNER_TRACKS
    )
    return dataclasses.replace(
        found.design, board=dataclasses.replace(board, tracks=(*board.tracks, *tracks))
    )


def powered(design: Design) -> Design:
    assert design.board is not None
    layers = with_plane_types(design.board.layers, pb.PLANE_LAYERS)
    return dataclasses.replace(design, board=dataclasses.replace(design.board, layers=layers))


@dataclass(frozen=True)
class PowerRun:
    """What one major says about the routed bench with ``signal`` and with ``power`` inner rows."""

    signal: DrcReport | None
    power: DrcReport | None
    functions: tuple[tuple[int, str], ...]
    resaved: tuple[str, ...] | None

    @property
    def new_types(self) -> set[str]:
        assert self.signal is not None and self.power is not None
        every = lambda report: {v.type for v in (*report.violations, *report.unconnected_items)}  # noqa: E731
        return every(self.power) - every(self.signal)


@cache
def power_run(target: int) -> PowerRun:
    from _probes import runner

    cli = runner()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        os.environ.setdefault("KICAD_CONFIG_HOME", str(folder / "kicad-config"))
        design = routed_design(target, folder)
        built = folder / "out" / f"{pb.NAME}.kicad_pcb"
        related = _related(built)
        reports: dict[str, DrcReport | None] = {}
        paths: dict[str, Path] = {}
        for label, made in (("signal", design), ("power", powered(design))):
            # each board under the built name, so that it finds the project and the rules of the bench
            home = folder / label
            home.mkdir()
            path = home / built.name
            path.write_text(write_board(made, target=target).text, encoding="utf-8")
            for name, source in related.items():
                shutil.copyfile(source, home / name)
            paths[label] = path
            reports[label] = cli.drc(path, files=_related(path)).report
        power = paths["power"]
        run = cli.run(
            ["pcb", "export", "gerbers", "-o", "g/", power.name],
            files={power.name: power, **_related(power)},
        )
        functions: list[tuple[int, str]] = []
        for name, data in sorted(run.outputs.items()) if run.ok else ():
            if name.startswith("g/"):
                functions += [
                    (int(n), kind) for n, kind in FILE_FUNCTION.findall(data.decode("utf-8", "replace"))
                ]
        resaved = None
        if reports["power"] is not None and cli.major() >= 10:
            saved = cli.upgrade_board(power, files=_related(power)).decode("utf-8")
            resaved = plane_layers(read_board(saved))
    return PowerRun(reports["signal"], reports["power"], tuple(sorted(functions)), resaved)


def power_outcome(target: int) -> str:
    run = power_run(target)
    if run.signal is None or run.power is None:
        return "reject"
    inner = {(2, "Inr"), (3, "Inr")} <= set(run.functions)
    return "equal" if not run.new_types and inner else "different"


def resave_outcome() -> str:
    run = power_run(10)
    if run.power is None:
        return "reject"
    return "equal" if run.resaved == pb.PLANE_LAYERS else "different"


# -- the fan-out


def local_ten() -> str | None:
    """A ``kicad-cli`` 10 for ``fenolite fill``: the runner when it is one, else a local binary found
    without ``FENOLITE_KICAD_CLI`` (the variable may name the image of another major)."""
    from _probes import major, runner

    if major() >= 10:
        return str(runner().path)
    named = os.environ.pop("FENOLITE_KICAD_CLI", None)
    try:
        found = find_kicad_cli()
    finally:
        if named is not None:
            os.environ["FENOLITE_KICAD_CLI"] = named
    if found is None or str(found).startswith(DOCKER_PREFIX):
        return None
    from _resources import _version_of  # pyright: ignore[reportPrivateUsage]

    version = _version_of(str(found))
    return str(found) if version is not None and version[0] >= 10 else None


@dataclass(frozen=True)
class FanoutRun:
    """The bench after ``route``: the command's result, the findings of the copper check, and KiCad's
    reports of the filled bench without and with the fan-out (``None``: no report, or no ``kicad-cli`` 10
    to fill with)."""

    result: dict[str, object]
    findings: tuple[str, ...]
    before: DrcReport | None
    after: DrcReport | None
    filled: bool

    def open_plane_items(self, report: DrcReport | None = None) -> list[str]:
        report = report or self.after
        assert report is not None
        return [
            item.description
            for found in report.unconnected_items
            for item in found.items
            if any(f"[{net}]" in item.description for net in PLANE_NETS)
        ]

    @property
    def new_errors(self) -> set[str]:
        assert self.before is not None and self.after is not None
        return _error_types(self.after) - _error_types(self.before)


@cache
def fanout_run(target: int) -> FanoutRun:
    from _probes import runner

    cli = runner()
    ten = local_ten()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        os.environ.setdefault("KICAD_CONFIG_HOME", str(folder / "kicad-config"))
        reports: dict[str, DrcReport | None] = {}
        result: dict[str, object] = {}
        findings: tuple[str, ...] = ()
        for label in ("before", "after"):
            board = pb.build_project(folder / label, target=target)
            if label == "after":
                code, env, err = pb.run_cli(
                    "route", str(board), "--router", "direct", "--nets", "GND", "--nets", "VCC", "--confirm",
                    "--no-backup",
                )  # fmt: skip
                assert code == 0, err
                result = env["result"]  # type: ignore[assignment]
                found = pb.load(board)
                report = check_copper(
                    found.design,
                    pads=found.pads,
                    min_clearance=found.rules.min_clearance,
                    rules_over_classes=found.rules.rules_over_classes,
                    floor_over_rules=found.rules.floor_over_rules,
                )
                findings = tuple(f"{f.code}: {f.message}" for f in report.findings)
            if ten is not None:
                code, _env, err = pb.run_cli(
                    "fill", str(board), "--confirm", "--no-backup", "--kicad-cli", ten
                )
                assert code == 0, err
            reports[label] = cli.drc(board, files=_related(board)).report
    return FanoutRun(result, findings, reports["before"], reports["after"], ten is not None)


def fanout_outcome(target: int) -> str:
    run = fanout_run(target)
    if not run.filled:
        return "inconclusive"
    if run.before is None or run.after is None:
        return "reject"
    made = run.result.get("plane_fanout", {})
    complete = isinstance(made, dict) and made.get("vias") == len(pb.PLANE_PADS) and not made.get("failed")
    clean = not run.findings and not run.open_plane_items() and not run.new_errors
    return "equal" if complete and clean else "different"


def plane_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``. A major loads the texts up to its own
    format, so the target-10 boards run on 10.0 only; a fan-out board is judged by its own major."""
    return {
        "pcb-layer-power-t9": (lambda: power_outcome(9), (9, 10)),
        "pcb-layer-power-t10": (lambda: power_outcome(10), (10,)),
        "pcb-layer-power-resave": (resave_outcome, (10,)),
        "route-fanout-t9": (lambda: fanout_outcome(9), (9,)),
        "route-fanout-t10": (lambda: fanout_outcome(10), (10,)),
    }


__all__ = [
    "INNER_TRACKS",
    "PLANE_NETS",
    "FanoutRun",
    "PowerRun",
    "fanout_outcome",
    "fanout_run",
    "local_ten",
    "plane_probes",
    "power_outcome",
    "power_run",
    "powered",
    "resave_outcome",
    "routed_design",
]
