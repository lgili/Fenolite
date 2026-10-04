# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of the Specctra codec against Freerouting (capability kicad-oracle, "Freerouting routes pass the
oracle"; change c0023): ``H-G-DSN-ACCEPT``, ``H-G-DSN-UNITS`` and ``H-G-DSN-PROTECT``.

The tests run the jar named by ``FENOLITE_FREEROUTING_JAR`` as a subprocess, with ``java`` from
``FENOLITE_JAVA`` or ``PATH``, in a temporary folder that is also its ``HOME``. With
``FENOLITE_ROUTING_EVIDENCE=1`` each outcome is written to
``docs/evidence/routing/freerouting-<version>.json``; run that mode without ``-n``.

``test_route`` (``H-G-DSN-ROUTE``) also needs ``kicad-cli``: it builds the blink for targets 9 and 10, routes
it with ``fenolite route --router freerouting`` and compares KiCad's DRC before and after, under
``kicad-cli`` of the board's own major (the local one, or the pinned image when it is here already).
``test_repeat`` compares two runs and ``test_offline`` runs the pinned Freerouting image without a network.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _copper import built_blink
from _resources import FREEROUTING_ENV, kicad_cli
from _specctra import DEFAULTS, Bench, two_pads

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.cli import DockerCli, KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.specctra.dsn import DsnResult
from fenolite.backends.specctra.ses import Session, read_session, to_copper
from fenolite.model.board import Track
from fenolite.routing.plugins.specctra.freerouting import FreeroutingRouter
from fenolite.routing.protocol import JobNet, RoutingJob

pytestmark = pytest.mark.needs_freerouting

PINNED_VERSION = "2.4.1"
KICAD_IMAGES = {
    9: "kicad/kicad:9.0.9@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729",
    10: "kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec",
}
FREEROUTING_IMAGE = (
    "ghcr.io/freerouting/freerouting:2.4.1"
    "@sha256:67794b10c4565c259461343cf6db4158e6a5c5baa7c2f93030d045974f313074"
)
JAVA_MIN = 25
PASSES = 20
TIMEOUT = 900
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "blink_2layer" / "design.py"
EVIDENCE = ROOT / "docs" / "evidence" / "routing" / f"freerouting-{PINNED_VERSION}.json"
WRITE = "FENOLITE_ROUTING_EVIDENCE"


def _java() -> str:
    java = os.environ.get("FENOLITE_JAVA") or shutil.which("java")
    if not java:
        pytest.fail("no Java runtime: set FENOLITE_JAVA or put java on PATH", pytrace=False)
    return java


def _java_version(java: str) -> str:
    done = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=60, check=False)
    lines = (done.stderr or done.stdout).splitlines()
    return lines[0].strip() if lines else ""


def _record(outcome: str, value: str, detail: str = "") -> None:
    """Add one outcome to the results file when ``FENOLITE_ROUTING_EVIDENCE=1``."""
    if os.environ.get(WRITE) != "1":
        return
    jar = Path(os.environ[FREEROUTING_ENV])
    java = _java()
    data: dict[str, object] = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.is_file() else {}
    outcomes = data.get("outcomes")
    merged: dict[str, object] = dict(outcomes) if isinstance(outcomes, dict) else {}
    merged[outcome] = {"value": value, "detail": detail}
    data.update(
        tool="freerouting",
        pinned_version=PINNED_VERSION,
        jar_sha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
        java=_java_version(java),
        outcomes=dict(sorted(merged.items())),
    )
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _route(written: DsnResult, folder: Path) -> tuple[Session | None, str]:
    """Run Freerouting on ``written`` in ``folder``; the session it wrote (``None`` without one) and the
    tail of its output."""
    java = _java()
    match = re.search(r'"?(\d+)[.\d]*', _java_version(java).split("version")[-1])
    if match is None or int(match.group(1)) < JAVA_MIN:
        pytest.fail(
            f"Freerouting {PINNED_VERSION} needs Java {JAVA_MIN}: {_java_version(java)!r}", pytrace=False
        )
    (folder / "board.dsn").write_text(written.text, encoding="utf-8")
    command = [
        java,
        "-jar",
        os.environ[FREEROUTING_ENV],
        "-de",
        "board.dsn",
        "-do",
        "board.ses",
        "-mp",
        str(PASSES),
        "-mt",
        "1",
        "-da",
        "--gui.enabled=false",
    ]
    env = {**os.environ, "HOME": str(folder), "LANG": "C"}
    done = subprocess.run(
        command, cwd=folder, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    tail = "\n".join((done.stdout + done.stderr).splitlines()[-20:])
    session = folder / "board.ses"
    if not session.is_file():
        return None, f"exit {done.returncode}, no session\n{tail}"
    return read_session(session.read_text(encoding="utf-8"), file="board.ses"), tail


def _blink() -> Bench:
    design = built_blink(10)
    pads = board_pads(design)
    nets = tuple(sorted({pad.net for pad in pads if pad.net}))
    return Bench(design, pads, board_outline(design).rings, nets)


def _centres(pads: tuple[BoardPad, ...], net: str) -> list[tuple[int, int]]:
    return [(pad.position.x, pad.position.y) for pad in pads if pad.net == net]


def test_accept(tmp_path: Path) -> None:
    """``H-G-DSN-ACCEPT``: Freerouting writes a readable session for the two-pad board and the blink."""
    details: list[str] = []
    for name, b in (("two-pads", two_pads()), ("blink", _blink())):
        folder = tmp_path / name
        folder.mkdir()
        session, tail = _route(b.write(), folder)
        if session is None:
            _record("dsn-accept", "absent", f"{name}: {tail}")
            pytest.fail(f"{name}: Freerouting wrote no session\n{tail}", pytrace=False)
        details.append(
            f"{name}: {len(session.wires)} wire(s), {len(session.vias)} via(s), resolution "
            f"{session.unit} {session.resolution}, {len(session.places)} place(s), "
            f"placement unit {session.place_unit} {session.place_resolution}, "
            f"unknown lists {list(session.unknown)}"
        )
        assert session.wires, f"{name}: the session holds no wire\n{tail}"
    _record("dsn-accept", "present", "; ".join(details))


def test_units(tmp_path: Path) -> None:
    """``H-G-DSN-UNITS``: both ends of the two-pad route lie within 100 nm of the pad centres."""
    b = two_pads()
    written = b.write()
    session, tail = _route(written, tmp_path)
    assert session is not None, tail
    tracks, _vias, issues = to_copper(session, written.names, selected=b.selected)
    assert not [issue for issue in issues if issue.severity == "error"], issues
    assert tracks, tail
    ends = {(p.x, p.y) for track in tracks for p in (track.start, track.end)}
    worst = 0
    for x, y in _centres(b.pads, "A"):
        nearest = min(max(abs(x - ex), abs(y - ey)) for ex, ey in ends)
        worst = max(worst, nearest)
    _record(
        "dsn-units", "equal" if worst <= 100 else "different", f"largest distance to a pad centre: {worst} nm"
    )
    assert worst <= 100, f"a route end lies {worst} nm from its pad centre"


def test_protect(tmp_path: Path) -> None:
    """``H-G-DSN-PROTECT``: with one blink net routed beforehand, the session leaves that net's wiring as it
    was: ``to_copper`` returns nothing on it."""
    b = _blink()
    assert b.design.board is not None
    net = "LED_A"
    (first, second) = [pad for pad in b.pads if pad.net == net]
    shared = {entry.layer for entry in first.copper} & {entry.layer for entry in second.copper}
    layer = min(shared)
    track = Track(
        id="trk_00000000-0000-4000-8000-0000000000aa",
        start=first.position,
        end=second.position,
        width=DEFAULTS.width,
        layer=layer,
        net_id=first.net_id,
    )
    board = dataclasses.replace(b.design.board, tracks=(track,))
    routed = dataclasses.replace(b, design=dataclasses.replace(b.design, board=board))
    written = routed.write()
    session, tail = _route(written, tmp_path)
    assert session is not None, tail
    tracks, vias, issues = to_copper(session, written.names, selected=(net,))
    assert not [issue for issue in issues if issue.severity == "error"], issues
    repeated = [wire for wire in session.wires if written.names.nets.get(wire.net) == net]
    changed = len(tracks) + len(vias)
    _record(
        "dsn-protect",
        "equal" if changed == 0 else "different",
        f"{len(repeated)} session wire(s) on the protected net, {changed} item(s) that differ from the input",
    )
    assert changed == 0, f"the session changes the protected net {net}: {tracks} {vias}"


def _errors(report: object) -> set[str]:
    violations = (*report.violations, *report.unconnected_items)  # type: ignore[attr-defined]
    return {item.type for item in violations if item.severity == "error"}


def _built(folder: Path, target: int) -> Path:
    """The blink built for ``target`` in ``folder``; the path of its board."""
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "fenolite",
            "build",
            str(EXAMPLE),
            "--out",
            str(folder),
            "--kicad-version",
            str(target),
            "--seed",
            "230023",
            "--timestamp",
            "2026-10-04T00:00:00Z",
            "--confirm",
            "--no-backup",
            "--json",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0 and json.loads(done.stdout)["ok"] is True, done.stderr or done.stdout
    return folder / "blink.kicad_pcb"


def _related(folder: Path, stem: str) -> dict[str, Path]:
    files = {
        f"{stem}.kicad_pro": folder / "blink.kicad_pro",
        f"{stem}.kicad_dru": folder / "blink.kicad_dru",
        "fp-lib-table": folder / "fp-lib-table",
        "lib": folder / "lib",
    }
    return {name: path for name, path in files.items() if path.exists()}


def _fenolite(folder: Path, *args: str) -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=folder,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    assert done.returncode == 0, done.stderr or done.stdout
    envelope: dict[str, object] = json.loads(done.stdout)
    assert envelope["ok"] is True, envelope
    return envelope


def _oracle(target: int) -> KicadCli:
    """``kicad-cli`` of the major ``target``: the local one, else the pinned image when it is here already
    (it is never pulled)."""
    binary = kicad_cli()
    assert binary is not None
    local = KicadCli(Path(binary), timeout=300)
    if local.major() == target:
        return local
    image = KICAD_IMAGES[target]
    if shutil.which("docker") is None:
        pytest.skip(f"target {target} needs kicad-cli {target}.x or Docker; running {local.major()}.x")
    found = subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False)
    if found.returncode:
        pytest.skip(f"target {target} needs kicad-cli {target}.x; the pinned image is not local")
    return DockerCli(image, timeout=600)


@pytest.mark.needs_kicad
@pytest.mark.parametrize("target", [pytest.param(9, id="t9"), pytest.param(10, id="t10")])
def test_route(tmp_path: Path, target: int) -> None:
    """``H-G-DSN-ROUTE``: after ``fenolite route --router freerouting`` (and ``fenolite fill`` on KiCad 10),
    the blink has no unconnected item and no error type the unrouted blink lacks, under ``kicad-cli`` of
    the board's own major."""
    cli = _oracle(target)
    project = tmp_path / "project"
    board_path = _built(project, target)
    before = cli.drc(board_path, files=_related(project, "blink"))
    assert before.report is not None, before.run.stderr or before.run.stdout
    routed_path = project / "blink_routed.kicad_pcb"
    routed = _fenolite(
        project,
        "route",
        board_path.name,
        "--router",
        "freerouting",
        "--allow-offsite",
        "--out",
        routed_path.name,
        "--confirm",
        "--no-backup",
    )
    result = routed["result"]
    assert isinstance(result, dict) and routed_path.is_file(), routed
    if target >= 10 and cli.major() >= 10 and not isinstance(cli, DockerCli):
        _fenolite(project, "fill", routed_path.name, "--confirm", "--no-backup")
    after = cli.drc(routed_path, files=_related(project, "blink_routed"))
    assert after.report is not None, after.run.stderr or after.run.stdout
    new_errors = _errors(after.report) - _errors(before.report)
    equal = not after.report.unconnected_items and not new_errors
    _record(
        f"dsn-route-t{target}",
        "equal" if equal else "different",
        f"kicad-cli {cli.version()}: fenolite route --router freerouting, {len(result['selected'])} net(s) "
        f"selected, {result['tracks']} track(s), {result['vias']} via(s), "
        f"{len(before.report.unconnected_items)} unconnected item(s) before and "
        f"{len(after.report.unconnected_items)} after, new error types {sorted(new_errors)}",
    )
    assert equal, f"unconnected={len(after.report.unconnected_items)}, new_errors={sorted(new_errors)}"


def _geometry(session: Session) -> tuple[frozenset[object], frozenset[object]]:
    return frozenset(session.wires), frozenset(session.vias)


def test_repeat(tmp_path: Path) -> None:
    """``H-G-DSN-REPEAT``: two runs on the same design file, compared; recorded either way."""
    written = _blink().write()
    sessions: list[Session] = []
    for name in ("first", "second"):
        folder = tmp_path / name
        folder.mkdir()
        session, tail = _route(written, folder)
        assert session is not None, tail
        sessions.append(session)
    equal = _geometry(sessions[0]) == _geometry(sessions[1])
    _record(
        "dsn-repeat",
        "equal" if equal else "different",
        f"blink, -mt 1: {len(sessions[0].wires)} and {len(sessions[1].wires)} wire(s), "
        f"{len(sessions[0].vias)} and {len(sessions[1].vias)} via(s)",
    )


def test_offline() -> None:
    """``H-G-DSN-OFFLINE``: the pinned image routes the two-pad board with ``--network none``. The image is
    used only when it is here already; Fenolite and its tests never pull it."""
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    found = subprocess.run(
        ["docker", "image", "inspect", FREEROUTING_IMAGE], capture_output=True, check=False
    )
    if found.returncode:
        pytest.skip(f"the image {FREEROUTING_IMAGE} is not local; pull it yourself to run the offline probe")
    b = two_pads()
    net = b.design.nets_by_name["A"]
    job = RoutingJob(
        b.design,
        (
            JobNet(
                "A", net.id, (), DEFAULTS.width, DEFAULTS.clearance, DEFAULTS.via_diameter, DEFAULTS.via_drill
            ),
        ),
        ("F.Cu", "B.Cu"),
        {},
        {"board_pads": b.pads, "outline": b.outline},
    )
    result = FreeroutingRouter(f"docker:{FREEROUTING_IMAGE}").route(job)
    failed = [issue.message for issue in result.issues if issue.severity == "error"]
    present = not failed and bool(result.tracks)
    _record(
        "dsn-offline",
        "present" if present else "absent",
        "; ".join(failed) or f"{len(result.tracks)} track(s)",
    )
    assert present, failed or result.log
