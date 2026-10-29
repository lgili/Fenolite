# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generators: exact, enclosed, recorded (change c0254; part-selection, "Generators", "Generator
results", "Locked generator picks", "Voltage divider search", "Filter and LED generators", "Pull-up and
shunt generators")."""

from __future__ import annotations

import itertools
import re
from decimal import Decimal, getcontext
from fractions import Fraction

from _picks import family, rows
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.core.partquery import Bounds, GeneratorRequest
from fenolite.dsl import (
    I2C,
    Design,
    Net,
    amp,
    between,
    capacitor,
    farad,
    hertz,
    i2c_pull_ups,
    led_resistor,
    pct,
    rc_lowpass,
    shunt,
    volt,
)
from fenolite.pick.generators import LN_7_3, PI, divider, led, pullup, rc
from fenolite.pick.generators import shunt as shunt_gen
from fenolite.pick.resolve import resolve
from fenolite.pick.rows import shipped_rows

E96 = tuple(row for row in shipped_rows() if row.row == "Fenolite:R_0603_E96_1pct")
E24 = tuple(row for row in shipped_rows() if row.row == "Fenolite:R_0603_E24_5pct")
F = Fraction


def _v(text: str) -> Fraction:
    return F(text)


def _divider(percent: int, ref: tuple[str, str, str] = ("0.594", "0.606", "0.6")) -> GeneratorRequest:
    nominal = F("3.3")
    target = Bounds("volt", nominal * (1 - F(percent, 100)), nominal * (1 + F(percent, 100)), nominal)
    inputs = (
        ("target", target),
        ("ref", Bounds("volt", _v(ref[0]), _v(ref[1]), _v(ref[2]))),
        ("current", Bounds("ampere", F(40, 10**6), F(100, 10**6))),
    )
    return GeneratorRequest("voltage_divider", "buck1/FB", "top", inputs, "voltage_divider()")


def _micro(achieved: str) -> tuple[Fraction, Fraction]:
    low, high = re.findall(r"(\d+)u", achieved)[:2]
    return F(int(low), 10**6), F(int(high), 10**6)


def _span(row) -> tuple[Fraction, Fraction]:  # noqa: ANN001
    tolerance = row.tolerance
    return row.value * (1 + tolerance.lo / 100), row.value * (1 + tolerance.hi / 100)


# ---------------------------------------------------------------------------------------- framework


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=3, max_value=8), st.integers(min_value=0, max_value=3))
def test_enclosure_divider_achieved_range_holds_the_exact_one(percent: int, ref_percent: int) -> None:
    ref = (str(F("0.6") * (1 - F(ref_percent, 100))), str(F("0.6") * (1 + F(ref_percent, 100))), "0.6")
    request = _divider(percent, ref)
    found = divider.solve(request, {"top": E96, "bot": E96})
    if not found.ok:
        return
    top, bot = found.rows["top"], found.rows["bot"]
    corners = [
        F(r) * (1 + t / b) for r, t, b in itertools.product((F(ref[0]), F(ref[1])), _span(top), _span(bot))
    ]
    low, high = _micro(found.achieved)
    assert low <= min(corners) and max(corners) <= high
    target = request.input("target")
    assert isinstance(target, Bounds) and target.contains(min(corners), max(corners))


def _pi() -> Fraction:
    getcontext().prec = 40
    return F(Decimal("3.141592653589793238462643383279502884197"))


@settings(max_examples=15, deadline=None)
@given(st.sampled_from(["100", "470", "1000", "2200", "10000"]), st.integers(min_value=5, max_value=20))
def test_enclosure_rc_achieved_range_holds_the_exact_one(corner: str, percent: int) -> None:
    caps = rows(family("Test:C", kind="capacitor", series="E12", low="1n", high="1u", tolerance="5%"))
    target = hertz(corner).pct(percent)
    request = GeneratorRequest(
        "rc_lowpass",
        "F",
        "r",
        (("corner", Bounds("hertz", target.low, target.high, target.nominal_value)),),
        "rc_lowpass()",
    )
    found = rc.solve(request, {"r": E96, "c": caps})
    if not found.ok:
        return
    pi = _pi()
    assert PI[0] < pi < PI[1] and LN_7_3[0] < F(Decimal("0.8472978603872036606")) < LN_7_3[1]
    r, c = found.rows["r"], found.rows["c"]
    corners = [1 / (2 * pi * rv * cv) for rv, cv in itertools.product(_span(r), _span(c))]
    low, high = _micro(found.achieved)
    assert low <= min(corners) and max(corners) <= high


def test_results_are_reported_in_one_text() -> None:
    found = divider.solve(_divider(5), {"top": E96, "bot": E96})
    assert "VOUT 3.224694–3.399373 V within 3.135–3.465 V" in found.message
    assert "divider current 42.92–44.69 µA" in found.message and found.achieved == "VOUT 3224694uV..3399373uV"


def test_a_wider_target_keeps_the_pair_relock() -> None:
    first = divider.solve(_divider(5), {"top": E96, "bot": E96})
    wider = divider.evaluate(_divider(6), first.rows)
    assert wider.ok and wider.rows == first.rows
    tighter = divider.evaluate(_divider(3), first.rows)
    assert not tighter.ok


def test_relock_through_resolve() -> None:
    design = Design("g")
    from fenolite.dsl import voltage_divider

    out, fb, gnd = Net("OUT"), Net("FB"), Net("GND")
    design.defaults(resistor={"case": "0603", "tolerance": pct(1), "series": "E96"})
    top, bot = voltage_divider(design, out, fb, gnd, target=volt("3.3").pct(5), ref=volt("0.6").pct(1),
                               current=between(amp("40u"), amp("100u")))  # fmt: skip
    queries = {part.path: part.query for part in (top, bot)}
    first = resolve(queries, {}, E96)  # pyright: ignore[reportArgumentType]
    assert {e.device for e in first.entries.values()} == {
        "Fenolite:R_0603_E96_1pct@61k9",
        "Fenolite:R_0603_E96_1pct@13k7",
    }
    again = resolve(queries, first.entries, E96)  # pyright: ignore[reportArgumentType]
    assert again.changes == () and [i.code for i in again.issues] == ["gen.achieved"]


# ---------------------------------------------------------------------------------------- divider


def test_divider_modes() -> None:
    found = divider.solve(_divider(5), {"top": E96, "bot": E96})
    assert (found.rows["top"].device, found.rows["bot"].device) == (
        "Fenolite:R_0603_E96_1pct@61k9",
        "Fenolite:R_0603_E96_1pct@13k7",
    )
    failed = divider.solve(_divider(3), {"top": E96, "bot": E96})
    assert not failed.ok and "373 µV above" in failed.message
    mid = Bounds("volt", F("1.6"), F("1.7"), F("1.65"))
    request = GeneratorRequest(
        "voltage_divider",
        "D",
        "top",
        (
            ("target", mid),
            ("vin", Bounds("volt", F("3.25"), F("3.35"), F("3.3"))),
            ("current", Bounds("ampere", F(1, 10**4), F(1, 10**3))),
        ),
        "voltage_divider()",
    )
    plain = divider.solve(request, {"top": E96, "bot": E96})
    assert plain.ok and "VMID" in plain.message
    top, bot = plain.rows["top"], plain.rows["bot"]
    assert mid.contains(
        F("3.25") * _span(bot)[0] / (_span(top)[1] + _span(bot)[0]),
        F("3.35") * _span(bot)[1] / (_span(top)[0] + _span(bot)[1]),
    )


# ---------------------------------------------------------------------------------------- rc and led


def test_an_rc_corner() -> None:
    design = Design("g")
    design.defaults(resistor={"series": "E24", "tolerance": pct(5)})
    r, c = rc_lowpass(
        design, Net("IN"), Net("OUT"), Net("GND"), corner=hertz(1000).pct(10), c=capacitor(farad("100n"))
    )
    # a 5 % capacitor with an E24 5 % resistor cannot hold ±10 % (1.6 kΩ: 902–1102 Hz): a 1 % C0G family
    c0g = rows(
        family(
            "Test:C_C0G",
            kind="capacitor",
            series="E12",
            low="1n",
            high="1u",
            tolerance="1%",
            extra='dielectric = "C0G"\n',
        )
    )
    found = resolve({r.path: r.query, c.path: c.query}, {}, (*E24, *c0g))  # pyright: ignore[reportArgumentType]
    assert not found.refused
    resistor_value = found.rows()[r.path].value
    assert found.rows()[c.path].value == F(1, 10**7)
    assert (
        resistor_value == 1600
    )  # 1 / (2π · 100 nF · 1 kHz) = 1591.5 Ω: E24 1.6 kΩ, corner within 900–1100 Hz
    achieved = next(i.message for i in found.issues if i.code == "gen.achieved")
    assert "corner" in achieved and "within 900–1100 Hz" in achieved


def test_an_led_resistor() -> None:
    request = GeneratorRequest(
        "led_resistor",
        "LED_R",
        "r",
        (
            ("current", Bounds("ampere", F(2, 1000), F(5, 1000))),
            ("vf", Bounds("volt", F("1.8"), F("2.2"))),
            ("vs", Bounds("volt", F("3.201"), F("3.399"), F("3.3"))),
        ),
        "led_resistor()",
    )
    powered = rows(family("Test:R", low="10", high="10k", extra='power = "0.1W"\n'))
    found = led.solve(request, {"r": powered})
    assert found.ok
    r = found.rows["r"]
    low, high = (F("3.201") - F("2.2")) / _span(r)[1], (F("3.399") - F("1.8")) / _span(r)[0]
    assert F(2, 1000) <= low and high <= F(5, 1000)
    unpowered = led.solve(request, {"r": rows(family("Test:R0", low="10", high="10k"))})
    assert not unpowered.ok
    design = Design("g")
    part = led_resistor(
        design, Net("V"), Net("A"), current=between(amp("2m"), amp("5m")), vf=volt(2), vs=volt("3.3")
    )
    assert part.path == "A_R" and part.query is not None and part.query.text().startswith("led_resistor(")


# ---------------------------------------------------------------------------------------- pull-ups and shunt


def test_pull_ups_inside_the_window() -> None:
    design = Design("g")
    design.defaults(resistor={"series": "E24", "tolerance": pct(5)})
    bus = I2C(Net("SDA"), Net("SCL"))
    sda, scl = i2c_pull_ups(design, bus, Net("V3V3"), bus_capacitance=between(farad("50p"), farad("100p")),
                            vdd=volt("3.3").pct(3))  # fmt: skip
    found = resolve({sda.path: sda.query, scl.path: scl.query}, {}, E24)  # pyright: ignore[reportArgumentType]
    picked = found.rows()
    assert picked[sda.path].device == picked[scl.path].device == "Fenolite:R_0603_E24_5pct@3k3"
    low, high = (
        (F("3.399") - F("0.4")) / F(3, 1000),
        F(300, 10**9) / (F(Decimal("0.84729786038720367")) * F(100, 10**12)),
    )
    larger = [row for row in E24 if row.value > 3300 and low <= _span(row)[0] and _span(row)[1] <= high]
    assert larger == [] and low <= _span(picked[sda.path])[0] and _span(picked[sda.path])[1] <= high
    window = pullup.window(sda.query.generator)  # pyright: ignore[reportOptionalMemberAccess, reportArgumentType]
    assert window[0] == low and window[1] <= high
    achieved = next(i.message for i in found.issues if i.code == "gen.achieved")
    assert "window" in achieved and "3.3kΩ" in achieved


def test_a_shunt_with_its_dissipation() -> None:
    design = Design("g")
    part = shunt(design, Net("HI"), Net("LO"), current=between(amp(0), amp(5)), full_scale=volt("0.1").pct(2))
    shunts = rows(
        family("Test:Shunt_2512", case="2512", series="E24", low="1m", high="100m", extra='power = "2W"\n')
    )
    found = resolve({part.path: part.query}, {}, shunts)  # pyright: ignore[reportArgumentType]
    row = found.rows()[part.path]
    _, r_max = _span(row)
    assert 5 * r_max <= F("0.098") and 25 * r_max <= 2
    bigger = [
        r for r in shunts if r.value > row.value and 5 * _span(r)[1] <= F("0.098") and 25 * _span(r)[1] <= 2
    ]
    assert bigger == [] and row.value == F(18, 1000)
    from fenolite.dsl.roles import records

    assert records(design).classes[part.path][1] == "shunt"
    request = part.query.generator  # pyright: ignore[reportOptionalMemberAccess]
    assert (
        request is not None
        and not shunt_gen.solve(request, {"r": rows(family("Test:Big", low="1", high="10"))}).ok
    )
