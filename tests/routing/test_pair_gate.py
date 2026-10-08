# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pair half of the feasibility gate of change c0110 (Decision 1; task 1.4): ``H-K-KRT-PAIR``,
``H-K-KRT-PAIRNAMES`` and ``H-G-DSN-PAIR``.

- ``test_krt_pair`` runs ``route_diff.py`` and then ``route.py`` on the pair bench built for the major of the
  local ``kicad-cli`` and judges the merged board with it: ``krt-pair-t<M>`` is ``equal`` when KiCad reports
  no unconnected item, no ``diff_pair_gap_out_of_range``, no ``diff_pair_uncoupled_length_too_long`` and no
  error type the unrouted bench lacks; ``skew_out_of_range`` is recorded and gates nothing.
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

from fenolite.backends.specctra.dsn import DsnDefaults, DsnResult, write_dsn
from fenolite.routing.plugins.kicad.routingtools import tool_pairs


@pytest.mark.needs_kicad
@pytest.mark.needs_router
def test_krt_pair(tmp_path: Path) -> None:
    target = 10 if gate.running_major() >= 10 else 9
    run = pg.pair_run(tmp_path, target)
    assert all(step.done for _name, step in run.steps), run.steps
    before, after = gate.drc(run.built), gate.drc(run.merged)
    pair_findings = gate.findings_of(after, gate.PAIR_TYPES)
    new_errors = sorted(gate.error_types(after) - gate.error_types(before) - gate.PAIR_TYPES)
    skew = gate.findings_of(after, {"skew_out_of_range"})
    equal = not after.unconnected_items and not pair_findings and not new_errors
    detail = (
        f"target {target}; unconnected {len(after.unconnected_items)}; "
        f"pair findings {pair_findings or 'none'}; "
        f"new error types {new_errors or 'none'}; skew {skew or 'none'}; "
        f"steps {[(name, step.code, step.seconds) for name, step in run.steps]}"
    )
    gate.record(f"krt-{gate.KRT_TAG}", f"krt-pair-t{target}", "equal" if equal else "different", detail)


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
