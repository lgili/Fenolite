# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

from fenolite.model.circuit import PinRef
from fenolite.placement.decoupling import Capacitor
from fenolite.placement.signal_intent import (
    OscillatorPort,
    Protection,
    Resonator,
    SeriesElement,
    SignalPath,
    SignalPort,
    suggest_oscillators,
    suggest_signal_path,
)
from fenolite.placement.topology import Incidence, PadIdentity


def row(part, pin, net):
    return Incidence(PinRef(part, pin), net, (PadIdentity(part, pin),))


def test_repeated_oscillators_match_their_own_branch_and_return():
    rows = []
    ports = []
    crystals = []
    caps = []
    for side in ("a", "b"):
        ic, x, c_in, c_out = (f"/{side}/{ref}" for ref in ("U1", "X1", "C1", "C2"))
        net_in, net_out, ret = (f"{side}/{net}" for net in ("IN", "OUT", "GND"))
        rows.extend(
            (
                row(ic, "i", net_in),
                row(ic, "o", net_out),
                row(ic, "g", ret),
                row(x, "1", net_out),
                row(x, "2", net_in),
                row(c_in, "1", ret),
                row(c_in, "2", net_in),
                row(c_out, "1", net_out),
                row(c_out, "2", ret),
            )
        )
        ports.append(OscillatorPort(side, PinRef(ic, "i"), PinRef(ic, "o"), PinRef(ic, "g"), "authored"))
        crystals.append(Resonator(x, "1", "2", "crystal"))
        caps.extend((Capacitor(c_in, "1", "2"), Capacitor(c_out, "1", "2")))
    ignored = replace(crystals[0], component_id="module", kind="clock_module")
    rc = replace(crystals[0], component_id="rc", kind="rc")
    result = suggest_oscillators(tuple(rows), tuple(ports), (*crystals, ignored, rc), tuple(caps))
    assert [s.state for s in result] == ["suggested", "suggested", "excluded", "excluded"]
    for side, suggestion in zip(("a", "b"), result[:2], strict=True):
        (match,) = suggestion.matches
        assert match.port.key == side
        assert match.resonator_input.terminal == PinRef(f"/{side}/X1", "2")
        assert match.input_loads[0][0].terminal == PinRef(f"/{side}/C1", "2")
        assert match.output_loads[0][1].net_id == f"{side}/GND"
    assert (
        suggest_oscillators(
            tuple(reversed(rows)), tuple(reversed(ports)), (*crystals, ignored, rc), tuple(reversed(caps))
        )
        == result
    )


def test_ambiguous_loads_stay_as_separate_options():
    inp, out, gnd = (PinRef("ic", p) for p in ("i", "o", "g"))
    rows = (
        row("ic", "i", "in"),
        row("ic", "o", "out"),
        row("ic", "g", "gnd"),
        row("x", "1", "in"),
        row("x", "2", "out"),
        row("a", "1", "in"),
        row("a", "2", "gnd"),
        row("b", "1", "in"),
        row("b", "2", "gnd"),
    )
    (result,) = suggest_oscillators(
        rows,
        (OscillatorPort("osc", inp, out, gnd, "authored"),),
        (Resonator("x", "1", "2", "crystal"),),
        (Capacitor("a", "1", "2"), Capacitor("b", "1", "2")),
    )
    assert result.state == "ambiguous"
    assert len(result.matches[0].input_loads) == 2


def test_explicit_series_direction_and_connector_protection():
    source, sink = PinRef("J1", "data"), PinRef("IC", "in")
    term = SeriesElement(PinRef("R", "2"), PinRef("R", "1"), "source_termination")
    esd = Protection(PinRef("D", "1"), PinRef("D", "2"), PinRef("J1", "gnd"))
    path = SignalPath(
        "signal", SignalPort(source, "source"), SignalPort(sink, "sink"), "authored", (term,), (esd,), source
    )
    rows = (
        row("J1", "data", "raw"),
        row("R", "1", "raw"),
        row("R", "2", "protected"),
        row("IC", "in", "protected"),
        row("D", "1", "raw"),
        row("D", "2", "ground"),
        row("J1", "gnd", "ground"),
    )
    result = suggest_signal_path(rows, path)
    assert result.state == "suggested"
    assert [(a.terminal, b.terminal) for a, b in result.links] == [(source, term.second), (term.first, sink)]
    assert result.protection_links[1][1].terminal == PinRef("J1", "gnd")
    assert (
        suggest_signal_path(rows, replace(path, source=SignalPort(source, "bidirectional"))).state
        == "ambiguous_direction"
    )
    wrong_return = (*rows[:-1], replace(rows[-1], net_id="other-return"))
    assert suggest_signal_path(wrong_return, path).state == "disconnected"
