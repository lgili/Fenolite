# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The blink variant of 4, 6 and 8 copper layers that the build oracle runs through fill, DRC and export
(capability kicad-oracle, "Builds of four, six and eight copper layers pass the oracle"; hypothesis
H-K-BUILD-LAYERS; change c0100, design Decision 10).

The variant holds a zone on every inner layer (``GND`` on ``In1.Cu``, ``In3.Cu`` and ``In5.Cu``, ``VIN``
on the others), the ``LED_A`` track stepping through a via to the deepest inner layer and back to
``B.Cu``, and one via drop each for ``GND`` and ``VIN``. Every value is authored for Fenolite.
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from _buildhelp import blink_variant

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design as Model

COUNTS: tuple[int, ...] = (4, 6, 8)
TARGETS: tuple[int, ...] = (9, 10)
FIXTURE_COUNTS: tuple[int, ...] = (6, 8)
"""The counts whose filled target-9 board is committed for the 9.0.9 half."""
FIXTURES = Path(__file__).resolve().parents[2] / "data" / "kicad" / "layers"
SEED = ("--seed", "1", "--timestamp", "2026-10-05T00:00:00Z")
IMPORT = "from fenolite.dsl import Design, Net, Part, Power, connect, mm, no_connect"
BOARD_LINE = "design.board(mm(50), mm(30))"
VIA = "diameter=mm(0.6), drill=mm(0.3)"
X2_FUNCTION = re.compile(r"^%TF\.FileFunction,(.+)\*%$", re.MULTILINE)


def copper_names(copper: int) -> tuple[str, ...]:
    return tuple(layer.name for layer in created_layers(copper) if layer.kind == "copper")


def zone_net(layer: str) -> str:
    """``GND`` for the odd inner layers, ``VIN`` for the even ones."""
    return "gnd" if int(layer[2:-3]) % 2 else "vin"


def zone_name(layer: str) -> str:
    return f"{zone_net(layer).upper()}_{layer[:-3]}"


def copper_lines(copper: int) -> str:
    """The lines appended to the blink script: zones, the stepped ``LED_A`` track and the via drops."""
    inner = copper_names(copper)[1:-1]
    zones = "".join(
        f'design.zone({zone_net(layer)}, layers=("{layer}",), name="{zone_name(layer)}")\n' for layer in inner
    )
    return (
        "\n"
        f"{zones}"
        "design.track(\n"
        '    "led_drv",\n'
        "    u1.pad(1), (mm(8), mm(12.2)), (mm(8), mm(7)), (mm(31.2), mm(7)), r1.pad(1),\n"
        "    width=mm(0.3),\n"
        ")\n"
        "design.track(\n"
        '    "led_a",\n'
        "    r1.pad(2), (mm(36), mm(9)),\n"
        f'    via_step(mm(36), mm(14), to="{inner[-1]}", {VIA}),\n'
        "    (mm(41.5), mm(14)),\n"
        f'    via_step(mm(41.5), mm(17), to="B.Cu", {VIA}),\n'
        "    (mm(41.5), mm(20)), d1.pad(2),\n"
        "    width=mm(0.3),\n"
        ")\n"
        'design.track("gnd_drop", u1.pad(10), (mm(12), mm(24)))\n'
        f'design.via("gnd_via", mm(12), mm(24), net=gnd, {VIA})\n'
        'design.track("vin_drop", u1.pad(9), (mm(10), mm(26)))\n'
        f'design.via("vin_via", mm(10), mm(26), net=vin, {VIA})\n'
    )


def write_script(folder: Path, copper: int) -> Path:
    """The variant of ``copper`` layers as ``<folder>/design.py``, beside its library tables."""
    script = blink_variant(folder, append=copper_lines(copper))
    text = script.read_text(encoding="utf-8")
    assert IMPORT in text and BOARD_LINE in text
    text = text.replace(IMPORT, f"{IMPORT}, via_step")
    text = text.replace(BOARD_LINE, f"design.board(mm(50), mm(30), copper={copper})")
    script.write_text(text, encoding="utf-8")
    return script


def fixture(copper: int) -> Path:
    return FIXTURES / f"l{copper}_t9_filled.kicad_pcb"


def without_fills(design: Model) -> Model:
    """``design`` with every zone unfilled: what a fixture and its build are compared on."""
    assert design.board is not None
    zones = tuple(dataclasses.replace(zone, fills=(), filled=False) for zone in design.board.zones)
    return dataclasses.replace(design, board=dataclasses.replace(design.board, zones=zones))


# -- the runs (``kicad-cli`` needed)


def fenolite(cwd: Path, *args: str) -> tuple[int, dict[str, Any], str]:
    """``(exit code, envelope, stderr)`` of ``fenolite <args> --json`` run in ``cwd``."""
    run = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    return run.returncode, json.loads(run.stdout) if run.stdout.strip() else {}, run.stderr


def build(folder: Path, out: Path, target: int) -> tuple[int, dict[str, Any], str]:
    return fenolite(
        folder, "build", str(folder / "design.py"), "--out", str(out), "--kicad-version", str(target),
        *SEED, "--no-backup", "--confirm",
    )  # fmt: skip


def files(folder: Path) -> dict[str, bytes]:
    """The project files a rebuild must leave as they are: everything but KiCad's local settings and the
    views under ``.fenolite/``, which describe the board as it is (its fills included)."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.suffix != ".kicad_prl" and ".fenolite" not in path.parts
    }


def stage(envelope: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in envelope["result"]["stages"] if s["name"] == name)


def gerber_functions(folder: Path) -> dict[str, str]:
    """Copper layer name → X2 file function, for every Gerber under ``folder`` that states a copper one."""
    found: dict[str, str] = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() in (".json", ".gbrjob", ".drl", ".csv", ".zip"):
            continue
        match = X2_FUNCTION.search(path.read_text(encoding="utf-8", errors="replace"))
        if match and match.group(1).startswith("Copper,"):
            found[path.stem.rsplit("-", 1)[-1].replace("_", ".")] = match.group(1)
    return found


def expected_functions(copper: int) -> dict[str, str]:
    names = copper_names(copper)
    places = ["Top", *["Inr"] * (copper - 2), "Bot"]
    return {
        name: f"Copper,L{i},{place}" for i, (name, place) in enumerate(zip(names, places, strict=True), 1)
    }


@dataclass(frozen=True)
class LayerRun:
    """What one variant gave on the running 10.0 ``kicad-cli``; empty ``problems`` means the oracle passed."""

    problems: tuple[str, ...]
    drc_problems: tuple[str, ...]
    gerber_problems: tuple[str, ...]
    filled_board: str
    functions: tuple[tuple[str, str], ...]


@cache
def layer_run(copper: int, target: int) -> LayerRun:
    """build, fill, check, export and build again of the variant, on the running ``kicad-cli`` (10.0)."""
    from _probes import runner

    cli = str(runner().path)
    problems: list[str] = []
    drc_problems: list[str] = []
    gerber_problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_script(root / "src", copper)
        out = root / "out"
        code, env, err = build(root / "src", out, target)
        if code != 0:
            return LayerRun(
                (f"build exit {code}: {err.strip()[:300]}",), ("no build",), ("no build",), "", ()
            )
        issue_codes = sorted({issue["code"] for issue in env["issues"]})
        if issue_codes != ["model.single-pin-net"]:
            problems.append(f"build issues {issue_codes}")
        first = files(out)
        board = out / "blink.kicad_pcb"

        code, env, err = fenolite(out, "fill", str(out), "--kicad-cli", cli, "--no-backup", "--confirm")
        if code != 0:
            problems.append(f"fill exit {code}: {err.strip()[:300]}")
        filled = read_board(board)
        assert filled.board is not None
        unfilled = [zone.name for zone in filled.board.zones if not zone.filled or len(zone.fills) != 1]
        if unfilled or len(filled.board.zones) != copper - 2:
            problems.append(f"zones not filled once: {unfilled} of {len(filled.board.zones)}")
        filled_text = board.read_text(encoding="utf-8")

        code, env, err = fenolite(out, "check", str(out), "--kicad-cli", cli)
        if code != 0 or not env:
            drc_problems.append(f"check exit {code}: {err.strip()[:300]}")
        else:
            drc = stage(env, "drc.kicad")
            summary = drc["summary"]
            if drc["status"] != "ok" or summary.get("violations") != 0 or summary.get("unconnected") != 0:
                drc_problems.append(f"drc.kicad {drc['status']} {summary}")
            if summary.get("canary") != "fired":
                drc_problems.append(f"canary {summary.get('canary')!r}")
            fill = stage(env, "zone.fill")
            if fill["status"] != "ok" or fill["summary"].get("current") != copper - 2:
                problems.append(f"zone.fill {fill['status']} {fill['summary']}")
            clearance = stage(env, "copper.clearance")
            found = clearance["summary"]
            if clearance["status"] != "ok" or found.get("shorts") != 0 or found.get("clearance") != 0:
                problems.append(f"copper.clearance {clearance['status']} {found}")

        exported = root / "fab"
        code, env, err = fenolite(
            out, "export", str(out), "--all", "--out", str(exported), "--kicad-cli", cli, *SEED, "--confirm"
        )
        functions = gerber_functions(exported) if exported.is_dir() else {}
        if code != 0:
            gerber_problems.append(f"export exit {code}: {err.strip()[:300]}")
        if functions != expected_functions(copper):
            gerber_problems.append(f"copper Gerbers {functions}")
        jobs = sorted(exported.rglob("*.gbrjob")) if exported.is_dir() else []
        number = None
        if jobs:
            number = json.loads(jobs[0].read_text(encoding="utf-8"))["GeneralSpecs"].get("LayerNumber")
        if number != copper:
            gerber_problems.append(f"job file LayerNumber {number!r}")

        before = files(out)
        code, env, err = build(root / "src", out, target)
        if code != 0:
            problems.append(f"second build exit {code}: {err.strip()[:300]}")
        elif files(out) != before:
            changed = sorted(k for k, v in files(out).items() if before.get(k) != v)
            problems.append(f"second build changed {changed}")
        if set(first) != set(before):
            problems.append(f"fill, check or export changed the file set: {sorted(set(first) ^ set(before))}")
    return LayerRun(
        tuple(problems), tuple(drc_problems), tuple(gerber_problems), filled_text, tuple(functions.items())
    )


def build_outcome(copper: int, target: int) -> str:
    """``absent``: no violation, no unconnected item, the canary fired, and every other step as designed."""
    result = layer_run(copper, target)
    if result.drc_problems and result.drc_problems[0] == "no build":
        return "reject"
    return "absent" if not result.problems and not result.drc_problems else "present"


def gerber_outcome(copper: int, target: int) -> str:
    result = layer_run(copper, target)
    return "equal" if not result.gerber_problems else "different"


# -- the 9.0.9 half: the committed filled target-9 boards


@dataclass(frozen=True)
class FixtureRun:
    violations: int
    unconnected: int
    gerbers: tuple[str, ...]
    loaded: bool


@cache
def fixture_run(copper: int) -> FixtureRun:
    """DRC and Gerbers of the fixture of ``copper`` layers in a target-9 build of the same variant."""
    from _probes import runner

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_script(root / "src", copper)
        out = root / "out"
        code, _, err = build(root / "src", out, 9)
        assert code == 0, err
        board = out / "blink.kicad_pcb"
        board.write_bytes(fixture(copper).read_bytes())
        extra = {path.name: path for path in out.iterdir() if path.name != board.name}
        result = runner().drc(board, files=extra)
        if result.report is None:
            return FixtureRun(-1, -1, (), False)
        run = runner().run(
            ["pcb", "export", "gerbers", "-o", "g/", board.name], files={board.name: board, **extra}
        )
        gerbers = tuple(
            sorted(
                name.rsplit("/", 1)[-1].rsplit(".", 1)[0].rsplit("-", 1)[-1].replace("_", ".")
                for name in run.outputs
                if name.rsplit(".", 1)[0].endswith("_Cu")
            )
        )
    return FixtureRun(len(result.report.violations), len(result.report.unconnected_items), gerbers, True)


def fixture_outcome(copper: int) -> str:
    result = fixture_run(copper)
    if not result.loaded:
        return "reject"
    return "absent" if result.violations == 0 and result.unconnected == 0 else "present"


def fixture_gerber_outcome(copper: int) -> str:
    return "equal" if fixture_run(copper).gerbers == tuple(sorted(copper_names(copper))) else "different"


def layer_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """The ``build-layers-*`` probes. On 10.0 every count and target runs the whole loop; on 9.0 the two
    target-9 fixtures run DRC and Gerbers, under the same ids as their 10.0 rows."""
    from _probes import major

    def drc(copper: int, target: int) -> str:
        return build_outcome(copper, target) if major() >= 10 else fixture_outcome(copper)

    def gerbers(copper: int, target: int) -> str:
        return gerber_outcome(copper, target) if major() >= 10 else fixture_gerber_outcome(copper)

    probes: dict[str, tuple[object, tuple[int, ...]]] = {}
    for copper in COUNTS:
        for target in TARGETS:
            majors = (9, 10) if target == 9 and copper in FIXTURE_COUNTS else (10,)
            probes[f"build-layers-{copper}-t{target}"] = (
                lambda copper=copper, target=target: drc(copper, target),
                majors,
            )
            probes[f"build-layers-gerbers-{copper}-t{target}"] = (
                lambda copper=copper, target=target: gerbers(copper, target),
                majors,
            )
    return probes
