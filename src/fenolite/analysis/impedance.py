# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Estimates of the quasi-static impedance of single-ended lines (capability board-analyses, "Impedance
estimates"; user guide ``docs/impedance.md``; change c0105).

Two closed forms from public sources, re-derived and written in Fenolite's own code (``PROVENANCE.md``):

- the one-formula microstrip form of 1977 with its thickness correction, as S-0641 states it;
- the thick-strip form of a strip centred between two planes, as S-0642 states it, and the estimate of an
  offset strip from the two centred lines of the heights on each side, combined as S-0642 describes.

Every constant is a row of ``docs/analyses.md``, "Impedance formulas". The forms leave out solder mask,
etch angle, frequency, loss and copper roughness, so every result is ``INFERRED`` advice: it is returned,
never written into a design. Arithmetic is ``decimal`` at 40 digits; no ``float`` is used.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from functools import cache

from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.board import Stackup
from fenolite.model.rules import TraceGeometry

PRECISION = 40
Z_VACUUM_OHM = Decimal("376.730313412")
"""The characteristic impedance of vacuum in ohms, CODATA 2022 (S-0643)."""
MS_ER_A = Decimal(14)
"""Microstrip: the constant term of the factor ``(14 + 8/εr) / 11`` (S-0641)."""
MS_ER_B = Decimal(8)
"""Microstrip: the factor of ``1/εr`` in ``(14 + 8/εr) / 11`` (S-0641)."""
MS_ER_C = Decimal(11)
"""Microstrip: the divisor of ``(14 + 8/εr) / 11`` (S-0641)."""
MS_H_FACTOR = Decimal(4)
"""Microstrip: the factor of ``h / w_eff`` in the form, ``4h / w_eff`` (S-0641)."""
MS_E_FACTOR = Decimal(4)
"""Microstrip: the factor of ``e`` in the thickness correction, ``ln(4e / …)`` (S-0641)."""
MS_T_OFFSET = Decimal("1.1")
"""Microstrip: the term added to ``w/t`` in the thickness correction, ``w/t + 11/10`` (S-0641)."""
MS_ERROR_TYPICAL_PERCENT = Decimal(1)
"""Microstrip: the error S-0641 claims for the form outside its three exact limits, in most cases."""
MS_ERROR_MAX_PERCENT = Decimal(2)
"""Microstrip: the error S-0641 claims the form always stays below."""
SL_FACTOR = Decimal(30)
"""Stripline: the factor of the thick-strip form, ``30 / √εr`` (S-0642)."""
SL_C_FACTOR = Decimal(8)
"""Stripline: the factor of ``C = 8 (1 − T) / (π (W + ΔW))`` (S-0642)."""
SL_ROOT_TERM = Decimal("6.27")
"""Stripline: the term under the root, ``√(C² + 6.27)`` (S-0642)."""
SL_DW_A = Decimal("0.0796")
"""Stripline: the factor of ``T`` in the thickness correction ``ΔW`` (S-0642)."""
SL_DW_B = Decimal("1.1")
"""Stripline: the factor of ``T`` added to ``W`` in ``ΔW`` (S-0642)."""
SL_M_A = Decimal(3)
"""Stripline: the numerator of the exponent ``M = 3 / (1.5 + T / (1 − T))`` (S-0642)."""
SL_M_B = Decimal("1.5")
"""Stripline: the constant term of the denominator of ``M`` (S-0642)."""
SL_C_MIN = Decimal("0.25")
"""Stripline: S-0642 claims the form's accuracy for ``C`` above this value."""
SL_ERROR_PERCENT = Decimal("0.5")
"""Stripline: the accuracy S-0642 claims above ``SL_C_MIN``."""
CONSTANTS: tuple[str, ...] = (
    "Z_VACUUM_OHM",
    "MS_ER_A",
    "MS_ER_B",
    "MS_ER_C",
    "MS_H_FACTOR",
    "MS_E_FACTOR",
    "MS_T_OFFSET",
    "MS_ERROR_TYPICAL_PERCENT",
    "MS_ERROR_MAX_PERCENT",
    "SL_FACTOR",
    "SL_C_FACTOR",
    "SL_ROOT_TERM",
    "SL_DW_A",
    "SL_DW_B",
    "SL_M_A",
    "SL_M_B",
    "SL_C_MIN",
    "SL_ERROR_PERCENT",
)
"""The named constants of the forms, each a row of ``docs/analyses.md``, "Impedance formulas"."""
UM = 1_000
"""``solve_width`` returns a multiple of 1 µm."""
WIDTH_CAP = 1_000_000_000
"""The widest width ``solve_width`` tries, 1 m: a bound of the search, no value of a design."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-AN-ZMS", "H-G-AN-ZSL"))


def _check(value: int, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(f"{name} must be an int of nanometres above 0, not {value!r}")
    return Decimal(value)


def _epsilon(text: str) -> Decimal:
    if not isinstance(text, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(f"epsilon_r must be decimal text, not {text!r}")
    try:
        value = Decimal(text)
    except ArithmeticError:
        raise ValueError(f"epsilon_r {text!r} is not a decimal number") from None
    if not value.is_finite() or value < 1:
        raise ValueError(f"epsilon_r {text!r} must be a number of at least 1")
    return value


@cache
def _pi() -> Decimal:
    """π at ``PRECISION`` digits: the series of the ``decimal`` documentation (S-0012)."""
    with localcontext() as context:
        context.prec = PRECISION + 2
        three = Decimal(3)
        last, t, s, n, na, d, da = Decimal(0), three, three, 1, 0, 0, 24
        while s != last:
            last = s
            n, na = n + na, na + 8
            d, da = d + da, da + 32
            t = (t * n) / d
            s += t
        context.prec = PRECISION
        return +s


def _mohm(ohms: Decimal) -> int:
    return int((ohms * 1000).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _microstrip(w: Decimal, h: Decimal, t: Decimal, er: Decimal) -> Decimal:
    pi = _pi()
    one = Decimal(1)
    e = one.exp()
    root = ((t / h) ** 2 + (one / pi / (w / t + MS_T_OFFSET)) ** 2).sqrt()
    w_eff = w + t * (one + one / er) / (2 * pi) * (MS_E_FACTOR * e / root).ln()
    a = MS_H_FACTOR * h / w_eff
    b = (MS_ER_A + MS_ER_B / er) / MS_ER_C * a
    inner = one + a * (b + (b**2 + pi**2 * (one + one / er) / 2).sqrt())
    return Z_VACUUM_OHM / (2 * pi * (2 * (one + er)).sqrt()) * inner.ln()


def microstrip_mohm(width: Nm, height: Nm, thickness: Nm, epsilon_r: str) -> int:
    """The quasi-static impedance in milliohms of a strip of ``width`` and ``thickness`` at ``height``
    above its plane in a dielectric of ``epsilon_r``: the 1977 form of S-0641 (``H-G-AN-ZMS``)."""
    w, h, t = _check(width, "width"), _check(height, "height"), _check(thickness, "thickness")
    if thickness >= height:
        raise ValueError("thickness must be below height")
    er = _epsilon(epsilon_r)
    with localcontext() as context:
        context.prec = PRECISION
        return _mohm(_microstrip(w, h, t, er))


def _stripline_c(w: Decimal, b: Decimal, t: Decimal) -> Decimal:
    pi = _pi()
    one = Decimal(1)
    big_t, big_w = t / b, w / b
    m = SL_M_A / (SL_M_B + big_t / (one - big_t))
    log = ((big_t / (2 - big_t)) ** 2 + (SL_DW_A * big_t / (big_w + SL_DW_B * big_t)) ** m).ln()
    delta = big_t / (pi * (one - big_t)) * (one - log / 2)
    return SL_C_FACTOR * (one - big_t) / (pi * (big_w + delta))


def _stripline(w: Decimal, b: Decimal, t: Decimal, er: Decimal) -> Decimal:
    c = _stripline_c(w, b, t)
    return SL_FACTOR / er.sqrt() * (1 + c / 2 * (c + (c**2 + SL_ROOT_TERM).sqrt())).ln()


def _strip_args(width: Nm, spacing: Nm, thickness: Nm) -> tuple[Decimal, Decimal, Decimal]:
    w, b, t = _check(width, "width"), _check(spacing, "spacing"), _check(thickness, "thickness")
    if thickness >= spacing:
        raise ValueError("thickness must be below spacing")
    return w, b, t


def stripline_mohm(width: Nm, spacing: Nm, thickness: Nm, epsilon_r: str) -> int:
    """The impedance in milliohms of a strip centred between two planes ``spacing`` apart (the strip's
    thickness included): the thick-strip form of S-0642 (``H-G-AN-ZSL``)."""
    w, b, t = _strip_args(width, spacing, thickness)
    er = _epsilon(epsilon_r)
    with localcontext() as context:
        context.prec = PRECISION
        return _mohm(_stripline(w, b, t, er))


def stripline_in_range(width: Nm, spacing: Nm, thickness: Nm, epsilon_r: str) -> bool:
    """Whether a centred stripline lies where S-0642 claims the form's accuracy: ``C`` above
    ``SL_C_MIN``."""
    w, b, t = _strip_args(width, spacing, thickness)
    _epsilon(epsilon_r)
    with localcontext() as context:
        context.prec = PRECISION
        return _stripline_c(w, b, t) > SL_C_MIN


def _offset(w: Decimal, below: Decimal, above: Decimal, t: Decimal, er: Decimal) -> Decimal:
    z1 = _stripline(w, 2 * below + t, t, er)
    z2 = _stripline(w, 2 * above + t, t, er)
    return 2 * z1 * z2 / (z1 + z2)


def offset_stripline_mohm(width: Nm, below: Nm, above: Nm, thickness: Nm, epsilon_r: str) -> int:
    """An offset strip as the two centred lines of spacings ``2·below + thickness`` and
    ``2·above + thickness`` in parallel, ``2·Z₁·Z₂ / (Z₁ + Z₂)``: the estimate of S-0642, meant for small
    offsets (``H-G-AN-ZSL``)."""
    w, t = _check(width, "width"), _check(thickness, "thickness")
    low, high = _check(below, "below"), _check(above, "above")
    er = _epsilon(epsilon_r)
    with localcontext() as context:
        context.prec = PRECISION
        return _mohm(_offset(w, low, high, t, er))


@dataclass(frozen=True, slots=True)
class Dielectric:
    """What lies between a copper layer and a reference: the summed thickness of the dielectric entries,
    their permittivity combined in series as decimal text, whether their permittivities differ, and
    whether a copper entry lies between."""

    height: Nm
    epsilon_r: str
    mixed: bool
    copper_between: bool


def _series(entries: Sequence[tuple[int, str]]) -> tuple[str, bool]:
    """The permittivity of dielectrics in series, ``h / Σ(hᵢ / εᵢ)``, as decimal text (six places when
    they differ), and whether they differ."""
    values = {Decimal(eps) for _, eps in entries}
    if len(values) == 1:
        return entries[0][1], False
    with localcontext() as context:
        context.prec = PRECISION
        total = sum((Decimal(h) for h, _ in entries), Decimal(0))
        combined = total / sum((Decimal(h) / Decimal(eps) for h, eps in entries), Decimal(0))
        return format(combined.quantize(Decimal("0.000001")).normalize(), "f"), True


def dielectric_between(stackup: Stackup, layer: str, reference: str) -> Dielectric | None:
    """The dielectric between two copper layers of ``stackup``, in either order; ``None`` for a layer
    absent from the stack-up or a dielectric entry without ``epsilon_r``."""
    names = [entry.name for entry in stackup.layers]
    if layer not in names or reference not in names or layer == reference:
        return None
    upper, lower = (layer, reference) if names.index(layer) < names.index(reference) else (reference, layer)
    between = stackup.between(upper, lower)
    dielectrics = [entry for entry in between if entry.kind == "dielectric"]
    if not dielectrics or any(not entry.epsilon_r for entry in dielectrics):
        return None
    try:
        for entry in dielectrics:
            _epsilon(entry.epsilon_r)
    except ValueError:
        return None
    epsilon, mixed = _series([(entry.thickness, entry.epsilon_r) for entry in dielectrics])
    return Dielectric(
        sum(entry.thickness for entry in dielectrics),
        epsilon,
        mixed,
        any(entry.kind == "copper" for entry in between),
    )


@dataclass(frozen=True, slots=True)
class Estimate:
    """The estimate of one layer of a target. ``mohm`` is ``None`` when no form applies, and ``reason``
    then names why: ``differential``, ``structure`` or ``stackup``. ``form`` is ``microstrip``,
    ``stripline`` or ``offset-stripline``; ``in_range`` whether the row lies where its source claims the
    form's accuracy; ``heights`` one per reference; ``epsilon_r`` the permittivity used."""

    mohm: int | None
    form: str = ""
    in_range: bool | None = None
    heights: tuple[Nm, ...] = ()
    epsilon_r: str = ""
    mixed: bool = False
    reason: str = ""


def structure(layers: Sequence[str], geometry: TraceGeometry) -> str:
    """``microstrip`` for one reference on an outer copper layer, ``stripline`` for two references on an
    inner layer, else ``""``. ``layers`` are the copper layers of the board, top to bottom."""
    if not layers or geometry.layer not in layers:
        return ""
    outer = geometry.layer in (layers[0], layers[-1])
    if outer and len(geometry.references) == 1:
        return "microstrip"
    if not outer and len(geometry.references) == 2:
        return "stripline"
    return ""


def _value(
    stackup: Stackup | None, layers: Sequence[str], geometry: TraceGeometry
) -> tuple[Decimal | None, Estimate]:
    """The unrounded impedance in ohms and the estimate without its ``mohm``."""
    if geometry.gap is not None:
        return None, Estimate(None, reason="differential")
    shape = structure(layers, geometry)
    if not shape:
        return None, Estimate(None, reason="structure")
    if stackup is None:
        return None, Estimate(None, reason="stackup")
    copper = {entry.name: entry for entry in stackup.layers if entry.kind == "copper"}
    found = [dielectric_between(stackup, geometry.layer, ref) for ref in geometry.references]
    strip = copper.get(geometry.layer)
    if strip is None or any(d is None for d in found):
        return None, Estimate(None, reason="stackup")
    sides = [d for d in found if d is not None]
    if any(d.copper_between for d in sides):
        return None, Estimate(None, reason="structure")
    heights = tuple(d.height for d in sides)
    epsilon, mixed = _series([(d.height, d.epsilon_r) for d in sides])
    mixed = mixed or any(d.mixed for d in sides)
    t = Decimal(strip.thickness)
    w = Decimal(geometry.width)
    if t <= 0:
        return None, Estimate(None, reason="stackup")
    er = _epsilon(epsilon)
    with localcontext() as context:
        context.prec = PRECISION
        if shape == "microstrip":
            if strip.thickness >= heights[0]:
                return None, Estimate(None, reason="structure")
            ohms = _microstrip(w, Decimal(heights[0]), t, er)
            return ohms, Estimate(None, "microstrip", True, heights, epsilon, mixed)
        above, below = Decimal(heights[0]), Decimal(heights[1])
        if above == below:
            spacing = above + below + t
            ohms = _stripline(w, spacing, t, er)
            in_range = _stripline_c(w, spacing, t) > SL_C_MIN
            return ohms, Estimate(None, "stripline", in_range, heights, epsilon, mixed)
        ohms = _offset(w, below, above, t, er)
        in_range = all(_stripline_c(w, 2 * side + t, t) > SL_C_MIN for side in (below, above))
        return ohms, Estimate(None, "offset-stripline", in_range, heights, epsilon, mixed)


def estimate(stackup: Stackup | None, layers: Sequence[str], geometry: TraceGeometry) -> Estimate:
    """The estimate of one layer of a target: the microstrip form for one reference on an outer layer, the
    stripline form for two references on an inner layer (centred when the two heights are equal), with
    the heights and the permittivity from ``stackup`` (c0101's ``Stackup.between``)."""
    ohms, found = _value(stackup, layers, geometry)
    if ohms is None:
        return found
    return Estimate(
        _mohm(ohms), found.form, found.in_range, found.heights, found.epsilon_r, found.mixed, found.reason
    )


def solve_width(
    target_mohm: int, stackup: Stackup | None, layers: Sequence[str], geometry: TraceGeometry
) -> Nm | None:
    """The multiple of 1 µm whose estimate is nearest ``target_mohm`` (the lower width on a tie), by
    bisection: the forms decrease with width. ``None`` when no form applies."""
    if isinstance(target_mohm, bool) or target_mohm <= 0:
        raise ValueError(f"target_mohm must be a positive int, not {target_mohm!r}")
    if geometry.gap is not None:
        return None

    def at(units: int) -> int | None:
        found = estimate(stackup, layers, TraceGeometry(geometry.layer, geometry.references, units * UM))
        return found.mohm

    low, high = 1, 2
    first = at(low)
    if first is None:
        return None
    if first <= target_mohm:
        return low * UM
    while (value := at(high)) is not None and value > target_mohm and high * UM < WIDTH_CAP:
        low, high = high, high * 2
    while high - low > 1:
        middle = (low + high) // 2
        value = at(middle)
        if value is None:
            return None
        if value > target_mohm:
            low = middle
        else:
            high = middle
    above, below = at(low), at(high)
    if above is None or below is None:
        return None
    return (low if abs(above - target_mohm) <= abs(below - target_mohm) else high) * UM


__all__ = [
    "CONSTANTS",
    "EVIDENCE",
    "MS_ERROR_MAX_PERCENT",
    "MS_ERROR_TYPICAL_PERCENT",
    "SL_C_MIN",
    "Z_VACUUM_OHM",
    "Dielectric",
    "Estimate",
    "dielectric_between",
    "estimate",
    "microstrip_mohm",
    "offset_stripline_mohm",
    "solve_width",
    "stripline_in_range",
    "stripline_mohm",
    "structure",
]
