# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Routing of nets that already hold copper (change c0108; capability kicad-oracle, "Routing of open nets
passes the oracle"): ``H-G-DSN-PARTIAL`` (Freerouting) and ``H-K-KRT-PARTIAL`` (KiCadRoutingTools).

The bench holds one net per kind of copper that a second pass meets: a stub; three pads, two of them
joined; a fan-out of a track, a via and a ``B.Cu`` stub; a via beside the pad; a floating via of the net.
One ``fenolite route`` run must close every net from that copper, by the open connections of the board
and by ``kicad-cli pcb drc``, and leave every item that was there on the board with its uuid.

A sixth net, ``TEE``, records a limit found on 2026-10-07: its third pad is nearest to the *middle* of the
track that joins the two others. Freerouting 2.4.1 leaves that connection open (it would have to split a
protected wire); it closes it when the nearest copper is a pad or a wire end, as on ``THREE``. The outcome
``dsn-partial-tee`` is recorded either way, and the test only requires that Fenolite's verdict and KiCad's
agree on it.

With ``FENOLITE_ROUTING_EVIDENCE=1`` the outcome is written to the router's results file under
``docs/evidence/routing/``; ``docs/evidence/routing.md`` holds the record. The Freerouting test carries
the marker ``needs_freerouting`` (the jar named by ``FENOLITE_FREEROUTING_JAR`` and Java 25 or newer); the
KiCadRoutingTools test carries ``needs_router`` and passes on either outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _openconn import rb
from _resources import FREEROUTING_ENV, kicad_cli

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence" / "routing"
WRITE = "FENOLITE_ROUTING_EVIDENCE"
MM = rb.MM
TIMEOUT = 900
NETS = ("STUB", "THREE", "FANOUT", "NEAR", "FLOAT")
"""The five kinds of the requirement."""
TEE = "TEE"
"""The recorded limit: a pad to be joined to the middle of one protected track."""
HALF_TURN = 180_000_000


def bench(target: int = 10) -> Design:
    """The bench: per net two ``Mini_R_0603`` copies 10 mm apart whose pads ``1`` are on the net, inside
    the board outline, and the copper of the net's kind."""
    builder = rb.Builder()
    for index, net in enumerate((*NETS, TEE)):
        y = builder.row()
        refs = (f"RA{index}", f"RB{index}")
        builder.part(f"{net}:a", refs[0], Point(rb.LEFT, y), target=target, nets={"1": net},
                     rotation=HALF_TURN)  # fmt: skip
        builder.part(f"{net}:b", refs[1], Point(rb.RIGHT, y), target=target, nets={"1": net})
        if net in ("THREE", TEE):
            # THREE: the third pad left of the pair, nearest to a pad; TEE: below the middle of the track
            x = rb.LEFT - 3 * MM if net == "THREE" else (rb.LEFT + rb.RIGHT) // 2
            builder.part(f"{net}:c", f"RC{index}", Point(x, y + 4 * MM), target=target, nets={"1": net})
        centres = {
            pad.ref: pad.position
            for pad in board_pads(builder.build().design)
            if pad.ref in refs and pad.number == "1"
        }
        a, b = centres[refs[0]], centres[refs[1]]
        if net == "STUB":
            builder.track(f"{net}:t", net, y, x0=a.x, x1=a.x + 3 * MM)
        elif net in ("THREE", TEE):
            builder.track(f"{net}:t", net, y, x0=a.x, x1=b.x)
        elif net == "FANOUT":
            at = Point(a.x + 1_500_000, y)
            builder.track(f"{net}:t", net, y, x0=a.x, x1=at.x)
            builder.via(f"{net}:v", net, at)
            builder.track(f"{net}:s", net, y, layer="B.Cu", x0=at.x, x1=at.x + 2 * MM)
        elif net == "NEAR":
            at = Point(a.x + MM, y)
            builder.track(f"{net}:t", net, y, x0=a.x, x1=at.x)
            builder.via(f"{net}:v", net, at)
        else:
            builder.via(f"{net}:v", net, Point((a.x + b.x) // 2, y + 3 * MM))
    return builder.build().design


def copper_uuids(design: Design) -> set[str]:
    board = design.board
    assert board is not None
    return {kicad_uuid(item) for item in (*board.tracks, *board.arcs, *board.vias)}


def open_total(design: Design, nets: tuple[str, ...] = NETS) -> int:
    return connectivity(design, pads=board_pads(design), nets=nets).total


def _record(tool: str, version: str, outcome: str, value: str, detail: str) -> None:
    """Add one outcome to the router's results file when ``FENOLITE_ROUTING_EVIDENCE=1``."""
    if os.environ.get(WRITE) != "1":
        return
    path = EVIDENCE / f"{tool}-{version}.json"
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    outcomes = data.get("outcomes")
    merged: dict[str, object] = dict(outcomes) if isinstance(outcomes, dict) else {}
    merged[outcome] = {"value": value, "detail": detail}
    data["outcomes"] = dict(sorted(merged.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _route(folder: Path, router: str, *extra: str) -> tuple[int, dict[str, object], str]:
    """``fenolite route bench.kicad_pcb --router <router> --confirm`` in ``folder``."""
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "fenolite",
            "route",
            "bench.kicad_pcb",
            "--router",
            router,
            *extra,
            "--out",
            "routed.kicad_pcb",
            "--confirm",
            "--no-backup",
            "--json",
        ],  # fmt: skip
        cwd=folder,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    envelope: dict[str, object] = json.loads(done.stdout) if done.stdout.strip() else {}
    return done.returncode, envelope, done.stderr


def _judge(folder: Path, before: Design) -> tuple[bool, str, dict[str, object]]:
    """Whether the routed bench is closed by the query and by ``kicad-cli``, with every earlier copper
    item still on it; a text for the record; the facts."""
    routed_path = folder / "routed.kicad_pcb"
    routed = read_board(routed_path.read_text(encoding="utf-8"))
    cli = kicad_cli()
    assert cli is not None
    runner = KicadCli(Path(cli), timeout=TIMEOUT)
    (folder / "routed.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
    report = runner.drc(routed_path, files={"routed.kicad_pro": folder / "routed.kicad_pro"}).report
    assert report is not None, "kicad-cli wrote no DRC report for the routed bench"
    kept = copper_uuids(before) <= copper_uuids(routed)
    tee = open_total(routed, (TEE,))
    facts: dict[str, object] = {
        "open_before": open_total(before),
        "open_after": open_total(routed),
        "tee_open": tee,
        "unconnected": len(report.unconnected_items),
        "kept": kept,
        "kicad": runner.version(),
    }
    # KiCad's count is that of the whole board: the five kinds and the limit case
    equal = facts["open_after"] == 0 and facts["unconnected"] == tee and kept
    detail = (
        f"kicad-cli {facts['kicad']}: {len(NETS)} nets that hold copper, {facts['open_before']} open "
        f"connection(s) before and {facts['open_after']} after by the query, {facts['unconnected']} "
        f"unconnected item(s) by KiCad on the whole bench ({tee} on the net {TEE}), earlier copper kept: "
        f"{kept}"
    )
    return equal, detail, facts


def _bench_folder(tmp_path: Path) -> tuple[Path, Design]:
    """The bench written for the major of the local ``kicad-cli``, which judges the routed board: a 10.0
    file is one that KiCad 9 cannot read, and the route keeps the version of the board it reads."""
    cli = kicad_cli()
    assert cli is not None
    target = min(KicadCli(Path(cli), timeout=TIMEOUT).major(), 10)
    design = bench(target)
    folder = tmp_path / "bench"
    folder.mkdir()
    (folder / "bench.kicad_pcb").write_text(write_board(design, target=target).text, encoding="utf-8")
    return folder, read_board((folder / "bench.kicad_pcb").read_text(encoding="utf-8"))


def test_bench_holds_one_open_connection_per_net_kind() -> None:
    """Hermetic: every net of the bench holds copper and is open; ``THREE`` and the others by one
    connection, ``FLOAT`` by two (the two pads and the via)."""
    design = bench(10)
    report = connectivity(design, pads=board_pads(design), nets=(*NETS, TEE))
    assert {net.name: len(net.open) for net in report.nets} == {
        "FANOUT": 1, "FLOAT": 2, "NEAR": 1, "STUB": 1, "TEE": 1, "THREE": 1,
    }  # fmt: skip
    assert len(copper_uuids(design)) == 9


@pytest.mark.needs_freerouting
def test_freerouting_completes_nets_that_hold_copper(tmp_path: Path) -> None:
    """``H-G-DSN-PARTIAL``, scenario "Freerouting completes nets that hold copper"."""
    if shutil.which("java") is None and not os.environ.get("FENOLITE_JAVA"):
        pytest.fail("no Java runtime: set FENOLITE_JAVA or put java on PATH", pytrace=False)
    folder, before = _bench_folder(tmp_path)
    code, envelope, stderr = _route(folder, "freerouting", "--allow-offsite")
    assert code == 0 and envelope.get("ok") is True, stderr or envelope
    result = envelope["result"]
    assert isinstance(result, dict)
    equal, detail, facts = _judge(folder, before)
    version = str(result.get("tool_version") or "unknown")
    jar = hashlib.sha256(Path(os.environ[FREEROUTING_ENV]).read_bytes()).hexdigest()[:12]
    _record(
        "freerouting", version, "dsn-partial", "equal" if equal else "different",
        f"{detail}; fenolite route selected {len(result['selected'])} net(s), {result['tracks']} track(s), "
        f"{result['vias']} via(s); jar {jar}",
    )  # fmt: skip
    tee_open = facts["tee_open"]
    _record(
        "freerouting", version, "dsn-partial-tee", "equal" if tee_open == 0 else "different",
        f"a pad nearest to the middle of one protected track: {tee_open} open connection(s) after the run "
        f"by the query, listed in result.unrouted: {TEE in result['unrouted']}",
    )  # fmt: skip
    assert result["selected"] == sorted((*NETS, TEE))
    # the five kinds are closed; the limit case is closed or reported open, and KiCad agrees either way
    assert set(result["unrouted"]) <= {TEE}, result
    assert result["connections"] == {"before": 7, "after": tee_open}, result
    assert (TEE in result["unrouted"]) == bool(tee_open)
    assert equal, facts


@pytest.mark.needs_router
def test_krt_outcome_is_recorded_either_way(tmp_path: Path) -> None:
    """``H-K-KRT-PARTIAL``, scenario "KiCadRoutingTools is recorded either way": the test passes on
    ``equal`` and on ``different``; nothing depends on the outcome."""
    folder, before = _bench_folder(tmp_path)
    code, envelope, stderr = _route(folder, "kicadroutingtools")
    result = envelope.get("result")
    if code != 0 or not isinstance(result, dict) or not (folder / "routed.kicad_pcb").is_file():
        open_before = open_total(before)
        note = (stderr or json.dumps(envelope.get("issues", [])))[-300:]
        _record("kicadroutingtools", "0.22.1", "krt-partial", "different",
                f"no routed board (exit {code}); {open_before} open connection(s) stay; {note}")  # fmt: skip
        return
    equal, detail, _facts = _judge(folder, before)
    version = str(result.get("tool_version") or "0.22.1")
    _record("kicadroutingtools", version, "krt-partial", "equal" if equal else "different", detail)
