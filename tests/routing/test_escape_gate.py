# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The escape half of the feasibility gate of change c0110 (Decision 1; task 1.5): ``H-K-KRT-ESCAPE``,
``H-G-DSN-FANOUT`` and ``H-G-DSN-NARROW``, on the QFN and BGA benches of ``_escapebench``.

- ``test_krt[<bench>]``: KiCadRoutingTools with the part's escape step and without it, on the bench built
  for the major of the local ``kicad-cli``, which judges both merged boards. ``krt-escape-<bench>-t<M>`` is
  ``equal`` when no signal connection stays open, ``improved`` when fewer stay open than without the escape,
  each with no error type the unrouted bench lacks and no via inside a pad; else ``different``.
- ``test_dsn[<bench>]``: Freerouting with its fanout stage on (the escape) and off, judged the same way;
  ``dsn-escape-<bench>-t<M>``. A run with no session within the limit is recorded as such.
- ``test_narrow``: Freerouting on the QFN bench with four signal layers, its fanout stage on and off, both
  with automatic neck-down off; ``dsn-narrow-fanout`` is ``present`` when a signal wire is narrower than
  its class, and ``dsn-narrow-off`` likewise for the run without the stage. Run where the local
  ``kicad-cli`` is 10 (the table of the design has no 9.0.9 column for it).

Every tool run is bounded by ``FENOLITE_GATE_SECONDS`` (900 by default). Each test prints its outcome and
passes on any outcome: the verdict of the gate is written by task 1.6 from these outcomes.
"""

from __future__ import annotations

from pathlib import Path

import _escapebench as eb
import _escapegate as eg
import _gate as gate
import pytest

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design

BENCHES = ["qfn", "bga"]


def _target() -> int:
    return 10 if gate.running_major() >= 10 else 9


def _added_vias(before: Design, after: Design) -> list[object]:
    assert before.board is not None and after.board is not None
    known = {via.id for via in before.board.vias}
    return [via for via in after.board.vias if via.id not in known]


def _judge(kind: str, before: DrcReport, board: Design, run: eg.EscapeRun) -> tuple[int, list[str], int]:
    """Open signal connections, new error types and vias inside a pad of ``run``."""
    after = gate.drc(run.merged)
    signals = eb.signals(kind)
    new_errors = sorted(gate.error_types(after) - gate.error_types(before) - {"unconnected_items"})
    in_pads = gate.vias_in_pads(run.design, _added_vias(board, run.design))  # type: ignore[arg-type]
    return gate.open_on(after, signals), new_errors, in_pads


def _outcome(with_escape: tuple[int, list[str], int], without: tuple[int, list[str], int]) -> str:
    opened, errors, in_pads = with_escape
    if errors or in_pads:
        return "different"
    if opened == 0:
        return "equal"
    return "improved" if opened < without[0] else "different"


def _detail(label: str, run: eg.EscapeRun, judged: tuple[int, list[str], int]) -> str:
    steps = ", ".join(f"{name} exit {step.code} in {step.seconds} s" for name, step in run.steps)
    errors = judged[1] or "none"
    return f"{label}: {judged[0]} open, new error types {errors}, {judged[2]} via(s) in a pad ({steps})"


@pytest.mark.needs_kicad
@pytest.mark.needs_router
@pytest.mark.parametrize("kind", BENCHES)
def test_krt(kind: str, tmp_path: Path) -> None:
    target = _target()
    board = eg.built(tmp_path / "build", kind, target)
    before = gate.drc(board)
    base = read_board(board.read_text(encoding="utf-8"))
    escaped = eg.krt_run(board, tmp_path / "escape", kind, target, escape=True)
    plain = eg.krt_run(board, tmp_path / "plain", kind, target, escape=False)
    judged = {run.label: (_judge(kind, before, base, run), run) for run in (escaped, plain)}
    value = _outcome(judged["escape"][0], judged["plain"][0])
    detail = "; ".join(_detail(label, run, found) for label, (found, run) in judged.items())
    gate.record(f"krt-{gate.KRT_TAG}", f"krt-escape-{kind}-t{target}", value, detail)


@pytest.mark.needs_kicad
@pytest.mark.needs_freerouting
@pytest.mark.parametrize("kind", BENCHES)
def test_dsn(kind: str, tmp_path: Path) -> None:
    target = _target()
    board = eg.built(tmp_path / "build", kind, target)
    before = gate.drc(board)
    base = read_board(board.read_text(encoding="utf-8"))
    runs = [
        eg.dsn_run(board, tmp_path / label, kind, target, fanout=label == "fanout")
        for label in ("fanout", "off")
    ]
    judged = {run.label: (_judge(kind, before, base, run), run) for run in runs}
    sessions = {run.label: run.merged != board for run in runs}
    value = _outcome(judged["fanout"][0], judged["off"][0]) if sessions["fanout"] else "different"
    detail = "; ".join(
        _detail(label, run, found) + ("" if sessions[label] else ", no session")
        for label, (found, run) in judged.items()
    )
    gate.record("freerouting-2.4.1", f"dsn-escape-{kind}-t{target}", value, detail)


@pytest.mark.needs_kicad
@pytest.mark.needs_freerouting
def test_narrow(tmp_path: Path) -> None:
    if gate.running_major() < 10:
        pytest.skip(
            "the narrow-wire probe runs where the local kicad-cli is 10 (no 9.0.9 column in the design)"
        )
    board = eg.built(tmp_path / "build", "qfn", 10, planes=False)
    width = eb.SIZES["qfn"]["width"]
    assert isinstance(width, int)
    for label in ("fanout", "off"):
        run = eg.dsn_run(board, tmp_path / label, "qfn", 10, fanout=label == "fanout", planes=False)
        narrow = gate.narrow(run.design, eb.QFN_SIGNALS, width)
        steps = ", ".join(f"{name} exit {step.code} in {step.seconds} s" for name, step in run.steps)
        session = "session" if run.merged != board else "no session"
        detail = f"{len(narrow)} signal wire(s) narrower than {width} nm, the narrowest {narrow[:3]}; "
        detail += f"{session} ({steps})"
        gate.record("freerouting-2.4.1", f"dsn-narrow-{label}", "present" if narrow else "absent", detail)
