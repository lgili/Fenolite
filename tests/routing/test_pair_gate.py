# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pair half of the feasibility gate of change c0110 (Decision 1; task 1.4): ``H-K-KRT-PAIR``,
``H-K-KRT-PAIRNAMES`` and ``H-G-DSN-PAIR``.

- ``test_krt_pair`` routes the pair bench built for the major of the local ``kicad-cli`` with
  ``fenolite route --router kicadroutingtools --confirm`` (task 6.1: the command runs ``route_diff.py`` per
  pair and ``route.py`` on the single nets, since the plugin declares ``pairs``) and judges the written board
  with it: ``krt-pair-t<M>`` is ``equal`` when both pairs are routed and KiCad reports no unconnected item, no
  ``diff_pair_gap_out_of_range``, no ``diff_pair_uncoupled_length_too_long`` and no error type the unrouted
  bench lacks; ``skew_out_of_range`` is recorded and gates nothing. Before task 6.1 it ran the two scripts
  itself (``_pairgate.pair_run``, kept for the record of task 1.4).
- ``test_loop`` is the loop on the pair bench (task 6.1): build, route with KiCadRoutingTools, fill, build
  twice; the second build keeps every routed track and via and both pairs, and the third build writes the
  same bytes as the second.
- ``test_krt_names`` runs ``route_diff.py`` on the name bench; ``krt-pair-names`` is ``equal`` when the pairs
  given copper are those whose names ``routingtools.tool_pairs`` accepts (``PAIR_NAME_FORMS``). It needs the
  checkout only.
- ``test_dsn_pair_ignored`` runs the pinned Freerouting jar on the pair bench's design file without a
  ``pair`` list, with one per pair and with one holding a rule; ``dsn-pair-ignored`` is ``equal`` when the
  three sessions' ``routes`` sections are the same text.

Each test prints its outcome (the ``-rA`` log of the ``routing`` job shows it) and passes on any outcome: the
gate's verdict is written by task 1.6 from these outcomes, not by the result of the test.
"""

from __future__ import annotations

from pathlib import Path

import _gate as gate
import _pairgate as pg
import _planebench as pb
import _routepairbench as pairb
import pytest

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.specctra.dsn import DsnDefaults, DsnResult, write_dsn
from fenolite.routing.plugins.kicad.routingtools import tool_pairs

STAMP = ("--seed", "1100061", "--timestamp", "2026-10-09T00:00:00Z")
"""Fixed seed and time, so that two builds of the loop can be compared byte for byte."""


def _build(folder: Path, target: int) -> Path:
    """The pair bench built by ``fenolite build`` into ``folder / "out"`` for ``target`` with ``STAMP``;
    returns its board. A second call builds over the first, keeping the router's copper."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "design.py"
    script.write_text(
        "from _routepairbench import bench_design\n\ndesign = bench_design()\n", encoding="utf-8"
    )
    out = folder / "out"
    code, envelope, error = pb.run_cli(
        "--kicad-version", str(target), "build", str(script), "--out", str(out), *STAMP,
        "--confirm", "--no-backup",
    )  # fmt: skip
    assert code == 0, (error, envelope.get("issues"))
    return out / f"{pairb.NAME}.kicad_pcb"


def _route(board: Path) -> dict[str, object]:
    """``fenolite route --router kicadroutingtools --confirm`` on ``board``; returns ``result``."""
    code, envelope, error = pb.run_cli(
        "route", str(board), "--router", "kicadroutingtools", "--timeout", str(gate.GATE_SECONDS),
        "--confirm", "--no-backup",
    )  # fmt: skip
    assert code == 0, error or envelope
    result = envelope["result"]
    assert isinstance(result, dict), envelope
    return result


def _pairs(result: dict[str, object]) -> list[tuple[str, bool]]:
    found = result.get("pairs") or []
    assert isinstance(found, list)
    return sorted((str(pair["name"]), bool(pair["routed"])) for pair in found)


@pytest.mark.needs_kicad
@pytest.mark.needs_router
def test_krt_pair(tmp_path: Path) -> None:
    target = 10 if gate.running_major() >= 10 else 9
    built = _build(tmp_path / "build", target)
    work = gate.copy_project(built, tmp_path / "work")
    result = _route(work)
    pairs = _pairs(result)
    before, after = gate.drc(built), gate.drc(work)
    pair_findings = gate.findings_of(after, gate.PAIR_TYPES)
    new_errors = sorted(gate.error_types(after) - gate.error_types(before) - gate.PAIR_TYPES)
    skew = gate.findings_of(after, {"skew_out_of_range"})
    routed_pairs = len(pairs) == len(pairb.PAIRS) and all(routed for _name, routed in pairs)
    equal = routed_pairs and not after.unconnected_items and not pair_findings and not new_errors
    detail = (
        f"target {target}, through fenolite route; pairs {pairs}; unrouted {result.get('unrouted')}; "
        f"unconnected {len(after.unconnected_items)}; pair findings {pair_findings or 'none'}; "
        f"new error types {new_errors or 'none'}; skew {skew or 'none'}"
    )
    gate.record(f"krt-{gate.KRT_TAG}", f"krt-pair-t{target}", "equal" if equal else "different", detail)


@pytest.mark.needs_kicad
@pytest.mark.needs_router
def test_loop(tmp_path: Path) -> None:
    """The loop on the pair bench: build, route, fill, build twice. The routes are kept, both pairs stay
    routed (each of their nets holds copper), and the last build is byte-equal to the one before it."""
    target = 10 if gate.running_major() >= 10 else 9
    board = _build(tmp_path, target)
    result = _route(board)
    assert all(routed for _name, routed in _pairs(result)), result.get("pairs")
    routed = read_board(board.read_text(encoding="utf-8"))
    assert routed.board is not None
    copper = {item.id for item in (*routed.board.tracks, *routed.board.arcs, *routed.board.vias)}
    assert copper
    if target >= 10:
        code, envelope, error = pb.run_cli("fill", str(board), "--confirm", "--no-backup")
        assert code == 0, error or envelope
    _build(tmp_path, target)
    second = board.read_bytes()
    rebuilt = read_board(second.decode("utf-8"))
    assert rebuilt.board is not None
    assert copper <= {item.id for item in (*rebuilt.board.tracks, *rebuilt.board.arcs, *rebuilt.board.vias)}
    for positive, negative in pairb.PAIRS:
        assert pg.coupled(rebuilt, positive, negative), (positive, negative)
    _build(tmp_path, target)
    assert board.read_bytes() == second
    assert not gate.drc(board).unconnected_items


@pytest.mark.needs_router
def test_krt_names(tmp_path: Path) -> None:
    import _namebench as nb

    run = pg.names_run(tmp_path, 10)
    assert all(step.done for _name, step in run.steps), run.steps
    routed = {f"{p}/{n}" for p, n in nb.PAIRS if pg.coupled(run.design, p, n)}
    expected = {f"{p}/{n}" for p, n in nb.PAIRS if tool_pairs(p, n)}
    value = "equal" if routed == expected else "different"
    detail = f"routed as pairs: {sorted(routed)}; PAIR_NAME_FORMS gives: {sorted(expected)}"
    gate.record(f"krt-{gate.KRT_TAG}", "krt-pair-names", value, detail)


def _with_pairs(written: DsnResult, rule: bool) -> DsnResult:
    """``written`` with one ``pair`` list per pair of the bench in its network section, before the classes;
    with ``rule``, each list holds the pair's width and clearance."""
    written_names = {model: dsn for dsn, model in written.names.nets.items()}
    inner = "\n        (rule (width 200) (clearance 150))" if rule else ""
    lists = "".join(
        f"    (pair (nets {written_names[p]} {written_names[n]}){inner}\n    )\n" for p, n in pairb.PAIRS
    )
    head, network, tail = written.text.partition("  (network\n")
    assert network, "the design file has no network section"
    first_class = tail.index("    (class ")
    text = head + network + tail[:first_class] + lists + tail[first_class:]
    return DsnResult(text, written.names, written.issues)


def _routes(session: str | None) -> str | None:
    return None if session is None else session[session.index("(routes") :]


@pytest.mark.needs_freerouting
def test_dsn_pair_ignored(tmp_path: Path) -> None:
    board = gate.build("_routepairbench", "bench_design", tmp_path / "build", 10)
    found = pb.load(board)
    defaults = DsnDefaults(
        width=pairb.WIDTH, clearance=pairb.CLEARANCE, via_diameter=pairb.VIA[0], via_drill=pairb.VIA[1]
    )
    written = write_dsn(
        found.design, pads=found.pads, outline=found.outline, selected=pairb.NETS, defaults=defaults
    )
    runs = {
        "p00": gate.freerouting(written, tmp_path / "p00"),
        "p01": gate.freerouting(_with_pairs(written, False), tmp_path / "p01"),
        "p02": gate.freerouting(_with_pairs(written, True), tmp_path / "p02"),
    }
    routes = {label: _routes(session) for label, (_run, session) in runs.items()}
    assert routes["p00"] is not None, runs["p00"][0].tail
    value = "equal" if routes["p00"] == routes["p01"] == routes["p02"] else "different"
    detail = "; ".join(
        f"{label}: exit {run.code}, {run.seconds} s, {'no session' if routes[label] is None else 'session'}"
        for label, (run, _session) in runs.items()
    )
    gate.record("freerouting-2.4.1", "dsn-pair-ignored", value, detail)
