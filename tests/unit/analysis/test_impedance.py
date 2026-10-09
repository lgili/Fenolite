# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Impedance estimates (capability board-analyses, "Impedance estimates"; hypotheses H-G-AN-ZMS and
H-G-AN-ZSL; change c0105). Each form is computed again here with ``math``, independently of the module."""

from __future__ import annotations

import math

import pytest

from fenolite.analysis import EVIDENCE as PACKAGE_EVIDENCE
from fenolite.analysis import impedance as imp
from fenolite.core.evidence import Level
from fenolite.model.board import StackLayer, Stackup
from fenolite.model.rules import TraceGeometry

Z0 = 376.730313412
STK = "stk_00000000-0000-4000-8000-000000000001"
COPPER = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def _ms(w: float, h: float, t: float, er: float) -> float:
    """The 1977 microstrip form of S-0641 in floats."""
    root = math.hypot(t / h, 1 / math.pi / (w / t + 1.1))
    w_eff = w + t * (1 + 1 / er) / (2 * math.pi) * math.log(4 * math.e / root)
    a = 4 * h / w_eff
    b = (14 + 8 / er) / 11 * a
    return (
        Z0
        / (2 * math.pi * math.sqrt(2 * (1 + er)))
        * math.log(1 + a * (b + math.sqrt(b * b + math.pi**2 * (1 + 1 / er) / 2)))
    )


def _hammerstad(w: float, h: float, er: float) -> float:
    """The 1975 form that S-0641 also states (zero thickness), the cross-check of the 1977 one."""
    u = w / h
    q2 = 0.04 * (1 - u) ** 2 if u <= 1 else 0.0
    eff = (er + 1) / 2 + (er - 1) / 2 * (1 / math.sqrt(1 + 12 / u) + q2)
    if u <= 1:
        return Z0 / (2 * math.pi * math.sqrt(eff)) * math.log(8 / u + u / 4)
    return Z0 / (math.sqrt(eff) * (u + 1.393 + 0.667 * math.log(u + 1.444)))


def _sl(w: float, b: float, t: float, er: float) -> float:
    """The thick-strip form of S-0642 in floats."""
    big_t, big_w = t / b, w / b
    m = 3 / (1.5 + big_t / (1 - big_t))
    dw = (
        big_t
        / (math.pi * (1 - big_t))
        * (1 - 0.5 * math.log((big_t / (2 - big_t)) ** 2 + (0.0796 * big_t / (big_w + 1.1 * big_t)) ** m))
    )
    c = 8 * (1 - big_t) / (math.pi * (big_w + dw))
    return 30 / math.sqrt(er) * math.log(1 + c / 2 * (c + math.sqrt(c * c + 6.27)))


def _ellipk(k: float) -> float:
    """The complete elliptic integral of the first kind by the arithmetic-geometric mean."""
    a, g = 1.0, math.sqrt(1 - k * k)
    for _ in range(60):
        a, g = (a + g) / 2, math.sqrt(a * g)
    return math.pi / (2 * a)


def _exact_thin(w: float, b: float, er: float) -> float:
    k = 1 / math.cosh(math.pi * w / (2 * b))
    return 30 * math.pi / math.sqrt(er) * _ellipk(k) / _ellipk(math.sqrt(1 - k * k))


def test_microstrip_of_the_bench() -> None:
    found = imp.microstrip_mohm(350_000, 200_000, 35_000, "4.3")
    assert abs(found - _ms(350_000, 200_000, 35_000, 4.3) * 1000) <= 1
    assert 50_700 < found < 50_800


@pytest.mark.parametrize("er", ["2.2", "4.3", "10"])
@pytest.mark.parametrize("ratio", ["0.1", "0.5", "1", "3.3", "10"])
def test_microstrip_arithmetic_and_the_1975_form(er: str, ratio: str) -> None:
    h = 200_000
    w = int(h * float(ratio))
    found = imp.microstrip_mohm(w, h, 35_000, er)
    assert abs(found - _ms(w, h, 35_000, float(er)) * 1000) <= 1
    thin = imp.microstrip_mohm(w, h, 1, er) / 1000
    assert abs(thin - _hammerstad(w, h, float(er))) / _hammerstad(w, h, float(er)) < 0.02


@pytest.mark.parametrize("ratio", ["0.1", "0.25", "0.5", "1", "1.5", "2"])
def test_stripline_against_the_exact_thin_strip(ratio: str) -> None:
    b = 1_000_000
    w = int(b * float(ratio))
    found = imp.stripline_mohm(w, b, 1, "4.3")
    assert abs(found - _sl(w, b, 1, 4.3) * 1000) <= 1
    exact = _exact_thin(w, b, 4.3) * 1000
    assert abs(found - exact) / exact < 0.01


def test_stripline_arithmetic_thick() -> None:
    found = imp.stripline_mohm(150_000, 400_000, 35_000, "4.3")
    assert abs(found - _sl(150_000, 400_000, 35_000, 4.3) * 1000) <= 1
    assert imp.stripline_in_range(150_000, 400_000, 35_000, "4.3")
    assert not imp.stripline_in_range(40_000_000, 400_000, 35_000, "4.3")


def test_offset_stripline_form_at_equal_heights() -> None:
    assert imp.offset_stripline_mohm(150_000, 182_500, 182_500, 35_000, "4.3") == imp.stripline_mohm(
        150_000, 400_000, 35_000, "4.3"
    )
    z1, z2 = _sl(150_000, 2 * 150_000 + 35_000, 35_000, 4.3), _sl(150_000, 2 * 250_000 + 35_000, 35_000, 4.3)
    found = imp.offset_stripline_mohm(150_000, 150_000, 250_000, 35_000, "4.3")
    assert abs(found - 2 * z1 * z2 / (z1 + z2) * 1000) <= 1


@pytest.mark.parametrize(
    "args",
    [(0, 200_000, 35_000, "4.3"), (350_000, 200_000, 200_000, "4.3"), (350_000, 200_000, 35_000, "0.5"),
     (350_000, 200_000, 35_000, "x"), (True, 200_000, 35_000, "4.3")],
)  # fmt: skip
def test_microstrip_refuses(args: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        imp.microstrip_mohm(*args)  # type: ignore[arg-type]


def test_evidence() -> None:
    assert imp.EVIDENCE.level is Level.INFERRED and imp.EVIDENCE.hypotheses == ("H-G-AN-ZMS", "H-G-AN-ZSL")
    assert "H-G-AN-ZMS" not in PACKAGE_EVIDENCE.hypotheses


def _layer(n: int, name: str, kind: str, thickness: int, eps: str = "") -> StackLayer:
    return StackLayer(
        id=f"sly_00000000-0000-4000-8000-{n:012d}",
        name=name,
        kind=kind,
        thickness=thickness,
        epsilon_r=eps,  # type: ignore[arg-type]
    )


def bench_stackup(core_eps: str = "4.3") -> Stackup:
    return Stackup(
        id=STK,
        layers=(
            _layer(1, "F.Cu", "copper", 35_000),
            _layer(2, "pp1", "dielectric", 200_000, "4.3"),
            _layer(3, "In1.Cu", "copper", 35_000),
            _layer(4, "core", "dielectric", 1_065_000, core_eps),
            _layer(5, "In2.Cu", "copper", 35_000),
            _layer(6, "pp2", "dielectric", 200_000, "4.3"),
            _layer(7, "B.Cu", "copper", 35_000),
        ),
        impedance_controlled=True,
    )


def test_dielectric_between() -> None:
    found = imp.dielectric_between(bench_stackup(), "F.Cu", "In1.Cu")
    assert found == imp.Dielectric(200_000, "4.3", False, False)
    assert imp.dielectric_between(bench_stackup(), "In1.Cu", "F.Cu") == found
    through = imp.dielectric_between(bench_stackup("3.7"), "F.Cu", "In2.Cu")
    assert through is not None and through.height == 1_265_000 and through.mixed and through.copper_between
    assert imp.dielectric_between(bench_stackup(), "F.Cu", "In7.Cu") is None
    assert imp.dielectric_between(bench_stackup(""), "In1.Cu", "In2.Cu") is None


def test_estimate_microstrip() -> None:
    found = imp.estimate(bench_stackup(), COPPER, TraceGeometry("F.Cu", ("In1.Cu",), 350_000))
    assert found.mohm == imp.microstrip_mohm(350_000, 200_000, 35_000, "4.3")
    assert (found.form, found.heights, found.epsilon_r, found.mixed, found.reason) == (
        "microstrip",
        (200_000,),
        "4.3",
        False,
        "",
    )


def test_estimate_stripline_centred_and_offset() -> None:
    stack = bench_stackup()
    centred = Stackup(id=STK, layers=(*stack.layers[:4], _layer(8, "In1b", "copper", 35_000)))
    assert centred.layers  # the bench is offset; the centred case is the scenario of the forms
    offset = imp.estimate(stack, COPPER, TraceGeometry("In1.Cu", ("F.Cu", "In2.Cu"), 150_000))
    assert offset.form == "offset-stripline" and offset.heights == (200_000, 1_065_000)
    assert offset.mohm == imp.offset_stripline_mohm(150_000, 1_065_000, 200_000, 35_000, "4.3")


def test_no_estimate_for_a_pair() -> None:
    found = imp.estimate(bench_stackup(), COPPER, TraceGeometry("F.Cu", ("In1.Cu",), 200_000, 150_000))
    assert found.mohm is None and found.reason == "differential"


def test_no_estimate_for_other_structures() -> None:
    found = imp.estimate(bench_stackup(), COPPER, TraceGeometry("In1.Cu", ("F.Cu",), 200_000))
    assert (found.mohm, found.reason) == (None, "structure")
    assert imp.estimate(None, COPPER, TraceGeometry("F.Cu", ("In1.Cu",), 200_000)).reason == "stackup"


def test_estimate_solve_width() -> None:
    geometry = TraceGeometry("F.Cu", ("In1.Cu",), 350_000)
    width = imp.solve_width(50_000, bench_stackup(), COPPER, geometry)
    assert width is not None and width % 1000 == 0
    at = imp.estimate(bench_stackup(), COPPER, TraceGeometry("F.Cu", ("In1.Cu",), width)).mohm
    near = [
        imp.estimate(bench_stackup(), COPPER, TraceGeometry("F.Cu", ("In1.Cu",), width + d)).mohm
        for d in (-1000, 1000)
    ]
    assert at is not None and all(n is not None and abs(n - 50_000) >= abs(at - 50_000) for n in near)
    assert imp.solve_width(90_000, bench_stackup(), COPPER, TraceGeometry("F.Cu", ("In1.Cu",), 1, 1)) is None
