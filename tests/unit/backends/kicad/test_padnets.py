# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads paired with IPC-D-356 records (capability kicad-oracle, "Netlist oracle from IPC-D-356"), on
authored exports of the ``two_layer`` fixture: no ``kicad-cli`` runs here."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _ipc

from fenolite.backends.kicad import padnets
from fenolite.backends.kicad.ipcd356 import Ipcd356
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ELEMENTS = ("D1-1", "D1-2", "R1-1", "R1-2")


def _design() -> Design:
    return read_board(FIXTURE.read_text(encoding="utf-8"), file=FIXTURE.name)


def _renamed(design: Design, **names: str) -> Design:
    nets = tuple(dataclasses.replace(n, name=names.get(n.name, n.name)) for n in design.circuit.nets)
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=nets))


def _ref(design: Design, old: str, new: str) -> Design:
    components = tuple(
        dataclasses.replace(c, ref=new) if c.ref == old else c for c in design.circuit.components
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))


def test_every_pad_paired_whatever_the_origin() -> None:
    design = _design()
    for origin in ((0, 0), _ipc.ORIGIN, (-99_999, 42)):
        export = Ipcd356(_ipc.UNIT_NM, tuple(_ipc.records(design, origin=origin)))
        match = padnets.match_pads(design, export)
        assert sorted(p.element for p in match.pairs) == list(ELEMENTS)
        assert (match.unmatched, match.unpaired, match.problems) == ((), (), ())
    listed = padnets.export_netlist(design, _ipc.export(design))
    assert listed.source == "export" and listed.uncovered == ()
    assert {a.element: a.net for a in listed.assignments} == {
        "R1-1": "VCC",
        "R1-2": "LED_A",
        "D1-1": "GND",
        "D1-2": "LED_A",
    }


def test_vias_are_skipped_and_counted() -> None:
    design = _design()
    match = padnets.match_pads(design, _ipc.export(design, _ipc.via(1, 2), _ipc.via(3, 4)))
    assert match.vias == 2 and len(match.pairs) == 4 and match.unmatched == ()


def test_truncated_keys_keep_full_elements() -> None:
    design = _ref(_design(), "R1", "RESISTOR1")
    match = padnets.match_pads(design, _ipc.export(design))
    assert match.truncated_keys == 2 and match.problems == ()
    assert {p.element for p in match.pairs} >= {"RESISTOR1-1", "RESISTOR1-2"}
    assert {p.record.ref for p in match.pairs if p.ref == "RESISTOR1"} == {"RESIST"}


def test_ambiguous_keys_are_resolved_by_position() -> None:
    # Both references cut to "RESIST": two records and two pads per key, told apart by position.
    design = _ref(_ref(_design(), "R1", "RESISTOR1"), "D1", "RESISTOR2")
    match = padnets.match_pads(design, _ipc.export(design))
    assert match.ambiguous_keys == 2 and match.problems == ()
    nets = {n.id: n.name for n in design.circuit.nets}
    assert {(p.element, p.record.net) for p in match.pairs} == {
        (p.element, nets[p.pad.net_id or ""]) for p in match.pairs
    }
    assert len({p.element for p in match.pairs}) == 4


def test_colliding_labels_become_coverage() -> None:
    design = _renamed(_design(), VCC="/A/LONG_SIGNAL_NAME", LED_A="/B/LONG_SIGNAL_NAME")
    assert len(padnets.ambiguous_labels(design)) == 2
    listed = padnets.export_netlist(design, _ipc.export(design))
    assert {a.element for a in listed.assignments} == {"D1-1"}
    assert {(u.element, u.reason) for u in listed.uncovered} == {
        ("R1-1", "net-label-ambiguous"),
        ("R1-2", "net-label-ambiguous"),
        ("D1-2", "net-label-ambiguous"),
    }
    assert padnets.ambiguous_labels(_design()) == frozenset()


def test_missing_and_extra_records_are_coverage() -> None:
    design = _design()
    kept = [r for r in _ipc.records(design) if (r.ref, r.pin) != ("D1", "1")]
    stray = dataclasses.replace(kept[0], ref="X9", pin="7")
    listed = padnets.export_netlist(design, Ipcd356(_ipc.UNIT_NM, (*kept, stray)))
    assert {(u.element, u.reason) for u in listed.uncovered} == {
        ("D1-1", "not-exported"),
        ("X9-7", "unmatched-record"),
    }
    assert {a.element for a in listed.assignments} == {"R1-1", "R1-2", "D1-2"}


def test_record_out_of_bound_is_not_paired() -> None:
    design = _design()
    moved = [
        dataclasses.replace(r, x=r.x + 3 * padnets.BOUND_UNITS) if (r.ref, r.pin) == ("D1", "2") else r
        for r in _ipc.records(design)
    ]
    match = padnets.match_pads(design, Ipcd356(_ipc.UNIT_NM, tuple(moved)))
    assert [r.pin for r in match.unmatched] == ["2"] and match.unpaired == ("D1-2",)
    assert match.problems == ("D1 pin 2: no model pad within the bound",)


def test_no_records_and_no_board() -> None:
    design = _design()
    empty = padnets.match_pads(design, Ipcd356(_ipc.UNIT_NM, ()))
    assert empty.pairs == () and empty.unpaired == ELEMENTS and empty.problems == ()
    assert padnets.match_pads(Design.new("empty", seed=0), _ipc.export(design)).pairs == ()


def test_evidence_starts_inferred() -> None:
    assert padnets.EVIDENCE.hypotheses == ("H-K-NET-IPC",)
