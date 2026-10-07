# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Feasibility gate for the pinned KiCadRoutingTools subprocess (c0016)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import fields, is_dataclass, replace
from pathlib import Path

import pytest
from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.model.board import Board

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "blink_2layer" / "design.py"
KRT_TAG = "v0.22.1"
TARGETS = [pytest.param(9, id="t9"), pytest.param(10, id="t10")]
pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_router]


def _without_copper_and_provenance(value: object) -> object:
    if isinstance(value, Board):
        ext = {
            name: replace(
                bag,
                payload=tuple(
                    pair
                    for pair in bag.payload
                    if not (pair[0] == "slot:.:modeled" and pair[1] in {"tracks", "arcs", "vias"})
                ),
            )
            for name, bag in value.ext.items()
        }
        value = replace(value, tracks=(), arcs=(), vias=(), ext=ext)
    if isinstance(value, tuple):
        return tuple(_without_copper_and_provenance(item) for item in value)
    if isinstance(value, list):
        return [_without_copper_and_provenance(item) for item in value]
    if isinstance(value, dict):
        return {key: _without_copper_and_provenance(item) for key, item in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        changes = {
            item.name: None
            if item.name == "provenance"
            else _without_copper_and_provenance(getattr(value, item.name))
            for item in fields(value)
        }
        return replace(value, **changes)
    return value


def _runner() -> KicadCli:
    binary = kicad_cli()
    assert binary is not None
    return KicadCli(Path(binary), timeout=300)


@pytest.fixture(scope="module", params=TARGETS)
def target(request: pytest.FixtureRequest) -> int:
    requested = int(request.param)
    running = _runner().major()
    if requested != running:
        pytest.skip(f"gate target {requested} runs under KiCad {requested}.x; running {running}.x")
    return requested


@pytest.fixture(scope="module")
def blink(tmp_path_factory: pytest.TempPathFactory, target: int) -> tuple[int, Path]:
    out = tmp_path_factory.mktemp(f"krt-blink-t{target}") / "project"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fenolite",
            "build",
            str(EXAMPLE),
            "--out",
            str(out),
            "--kicad-version",
            str(target),
            "--seed",
            "160016",
            "--timestamp",
            "2026-10-04T00:00:00Z",
            "--confirm",
            "--no-backup",
            "--json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True, result.stdout
    board = out / "blink.kicad_pcb"
    design = read_board(board.read_text(encoding="utf-8"))
    board.write_text(write_board(design, target=target).text, encoding="utf-8")
    return target, out


def _related_files(folder: Path, stem: str) -> dict[str, Path]:
    files = {
        f"{stem}.kicad_pro": folder / "blink.kicad_pro",
        f"{stem}.kicad_dru": folder / "blink.kicad_dru",
        "fp-lib-table": folder / "fp-lib-table",
        "lib": folder / "lib",
    }
    return {name: path for name, path in files.items() if path.exists()}


def _router() -> tuple[Path, Path]:
    checkout = Path(os.environ["FENOLITE_KRT"])
    interpreter = Path(os.environ.get("FENOLITE_KRT_PYTHON", sys.executable))
    assert (checkout / "py_router" / "route.py").is_file()
    assert interpreter.is_file()
    return checkout, interpreter


def _route(
    folder: Path,
    target: int,
    run_dir: Path,
    *,
    nets: tuple[str, ...] = ("*",),
    track_width: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    source = folder / "blink.kicad_pcb"
    design = read_board(source.read_text(encoding="utf-8"))
    board = run_dir / "blink.kicad_pcb"
    board.write_text(write_board(design, target=target).text, encoding="utf-8")
    for name in ("blink.kicad_pro", "blink.kicad_dru", "fp-lib-table"):
        original = folder / name
        if original.is_file():
            shutil.copy2(original, run_dir / name)
    libraries = folder / "lib"
    if libraries.is_dir():
        shutil.copytree(libraries, run_dir / "lib")
    output = run_dir / "blink_routed.kicad_pcb"
    checkout, interpreter = _router()
    args = [
        str(interpreter),
        str(checkout / "py_router" / "route.py"),
        str(board),
        str(output),
        "--nets",
        *nets,
    ]
    if track_width is not None:
        args.extend(("--track-width", track_width))
    result = subprocess.run(
        args,
        cwd=run_dir,
        env={**os.environ, "LANG": "C", "LC_ALL": "C"},
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return result, output


def _record(probe: str, target: int, outcome: str) -> None:
    if os.environ.get("FENOLITE_ROUTING_EVIDENCE") != "1":
        return
    path = ROOT / "docs" / "evidence" / "routing.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"- `{probe}-t{target}`: `{outcome}` (`{KRT_TAG}`).\n")


def _errors(report: object) -> set[str]:
    violations = (*report.violations, *report.unconnected_items)  # type: ignore[attr-defined]
    return {item.type for item in violations if item.severity == "error"}


def test_cli(blink: tuple[int, Path], tmp_path: Path) -> None:
    actual, folder = blink
    result, output = _route(folder, actual, tmp_path / "cli", nets=("LED*",), track_width="0.3")
    present = result.returncode == 0 and output.is_file()
    _record("krt-cli", actual, "present" if present else "missing")
    assert present, result.stderr or result.stdout
    routed = read_board(output.read_text(encoding="utf-8"))
    assert routed.board is not None and routed.board.tracks
    assert any(track.width == 300_000 for track in routed.board.tracks)


def test_route(blink: tuple[int, Path], tmp_path: Path) -> None:
    actual, folder = blink
    baseline_path = folder / "blink.kicad_pcb"
    before = _runner().drc(baseline_path, files=_related_files(folder, "blink"))
    assert before.report is not None, before.run.stderr or before.run.stdout
    output = folder / "blink_routed.kicad_pcb"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "FENOLITE_KRT": str(_router()[0]),
        "FENOLITE_KRT_PYTHON": str(_router()[1]),
    }
    routed = subprocess.run(
        [
            sys.executable,
            "-m",
            "fenolite",
            "route",
            str(baseline_path),
            "--router",
            "kicadroutingtools",
            "--out",
            output.name,
            "--confirm",
            "--no-backup",
            "--json",
        ],
        cwd=folder,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert routed.returncode == 0 and output.is_file(), routed.stderr or routed.stdout
    after = _runner().drc(output, files=_related_files(folder, "blink_routed"))
    assert after.report is not None, after.run.stderr or after.run.stdout
    equal = not after.report.unconnected_items and _errors(after.report) <= _errors(before.report)
    _record("krt-route", actual, "equal" if equal else "different")
    new_errors = _errors(after.report) - _errors(before.report)
    assert equal, f"unconnected={len(after.report.unconnected_items)}, new_errors={new_errors}"


def test_keep(blink: tuple[int, Path], tmp_path: Path) -> None:
    actual, folder = blink
    before = read_board((folder / "blink.kicad_pcb").read_text(encoding="utf-8"))
    run, output = _route(folder, actual, tmp_path / "keep")
    assert run.returncode == 0 and output.is_file(), run.stderr or run.stdout
    after = read_board(output.read_text(encoding="utf-8"))
    assert before.board is not None and after.board is not None
    before_without_copper = _without_copper_and_provenance(before)
    after_without_copper = _without_copper_and_provenance(after)
    equal = before_without_copper == after_without_copper
    _record("krt-keep", actual, "equal" if equal else "different")
    assert equal


def test_repeat(blink: tuple[int, Path], tmp_path: Path) -> None:
    actual, folder = blink
    first, first_path = _route(folder, actual, tmp_path / "first")
    second, second_path = _route(folder, actual, tmp_path / "second")
    assert first.returncode == second.returncode == 0
    assert first_path.is_file() and second_path.is_file()
    left, right = read_board(first_path.read_text()), read_board(second_path.read_text())
    assert left.board is not None and right.board is not None
    left_tracks = sorted(
        (t.start.x, t.start.y, t.end.x, t.end.y, t.width, t.layer, t.net_id) for t in left.board.tracks
    )
    right_tracks = sorted(
        (t.start.x, t.start.y, t.end.x, t.end.y, t.width, t.layer, t.net_id) for t in right.board.tracks
    )
    left_vias = sorted(
        (v.position.x, v.position.y, v.diameter, v.drill, v.layers, v.net_id) for v in left.board.vias
    )
    right_vias = sorted(
        (v.position.x, v.position.y, v.diameter, v.drill, v.layers, v.net_id) for v in right.board.vias
    )
    equal = (left_tracks, left_vias) == (right_tracks, right_vias)
    _record("krt-repeat", actual, "equal" if equal else "different")


def _two_classes_of_equal_sizes(project: Path) -> tuple[int, set[float]]:
    """Rewrite the net classes of the project file ``project`` so that every class has the track width
    and the via sizes of the first one and a clearance of its own, 0.1 mm more per class. Returns the
    count of classes and their clearances."""
    data = json.loads(project.read_text(encoding="utf-8"))
    classes = data["net_settings"]["classes"]
    first = classes[0]
    clearances: set[float] = set()
    for index, entry in enumerate(classes):
        for key in ("track_width", "via_diameter", "via_drill"):
            entry[key] = first[key]
        entry["clearance"] = round(float(first["clearance"]) + 0.1 * index, 3)
        clearances.add(entry["clearance"])
    project.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return len(classes), clearances


def test_group(blink: tuple[int, Path], tmp_path: Path) -> None:
    """``H-K-KRT-GROUP`` (change c0109): the blink with two net classes that share sizes and differ in
    clearance is one group, routed by one process without ``--clearance``, with ``--escalation off`` and
    ``--no-fix-drc-settings``; KiCad of the board's major then reports no unconnected item and no error
    type that the unrouted board lacks."""
    actual, folder = blink
    project = tmp_path / "group"
    shutil.copytree(folder, project)
    for stale in project.glob("blink_routed*"):
        stale.unlink()
    count, clearances = _two_classes_of_equal_sizes(project / "blink.kicad_pro")
    assert count >= 2 and len(clearances) == count, "the bench needs two classes with different clearances"
    baseline_path = project / "blink.kicad_pcb"
    before = _runner().drc(baseline_path, files=_related_files(project, "blink"))
    assert before.report is not None, before.run.stderr or before.run.stdout
    output = project / "blink_routed.kicad_pcb"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "FENOLITE_KRT": str(_router()[0]),
        "FENOLITE_KRT_PYTHON": str(_router()[1]),
    }
    routed = subprocess.run(
        [
            sys.executable,
            "-m",
            "fenolite",
            "route",
            baseline_path.name,
            "--router",
            "kicadroutingtools",
            "--out",
            output.name,
            "--confirm",
            "--no-backup",
            "--json",
        ],  # fmt: skip
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
        check=False,
    )
    assert routed.returncode == 0 and output.is_file(), routed.stderr or routed.stdout
    result = json.loads(routed.stdout)["result"]
    runs = result["runs"]
    assert [run["outcome"] for run in runs] == ["done"], runs
    assert runs[0]["nets"] == len(result["selected"]) >= 2, "one process routed the whole group"
    after = _runner().drc(output, files=_related_files(project, "blink_routed"))
    assert after.report is not None, after.run.stderr or after.run.stdout
    new_errors = _errors(after.report) - _errors(before.report)
    equal = not after.report.unconnected_items and not new_errors
    _record("krt-group", actual, "equal" if equal else "different")
    assert equal, f"unconnected={len(after.report.unconnected_items)}, new_errors={new_errors}"
