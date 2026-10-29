# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The naming convention of packages authored by Fenolite (change c0260, decision 14;
``docs/formats/library/naming.md``)::

    <FAMILY><pins>_B<L>x<W>[x<H>]_P<pitch>[_EP<x>x<y>][_<variant>]   generic, from a registered outline
    <FAMILY><pins>_<Maker>_<drawing id>                              a manufacturer's own drawing

A name is generic when it holds a ``_B<L>x<W>`` or a ``_P<pitch>`` field; each field it holds is checked
against the record's nominal numbers, in millimetres without trailing zeros. Other names are not checked.
"""

from __future__ import annotations

import re

from fenolite.catalog.footprints.codes import issue
from fenolite.catalog.footprints.record import Keys, Package
from fenolite.core.errors import Issue
from fenolite.core.quantities import LengthRange
from fenolite.core.units import format_length

_HEAD = re.compile(r"^(?P<family>[A-Z]+)(?P<pins>\d+)(?:x(?P<cols>\d+))?(?=_|$)")
_BODY = re.compile(r"_B(?P<l>\d+(?:\.\d+)?)x(?P<w>\d+(?:\.\d+)?)(?:x(?P<h>\d+(?:\.\d+)?))?(?=_|$)")
_PITCH = re.compile(r"_P(?P<p>\d+(?:\.\d+)?)(?=_|$)")
_EP = re.compile(r"_EP(?P<x>\d+(?:\.\d+)?)x(?P<y>\d+(?:\.\d+)?)(?=_|$)")
_TWO_TERMINAL = ("chip", "molded")


def mm(value: int) -> str:
    """``4900000`` → ``"4.9"``, ``3000000`` → ``"3"``: nominal millimetres without trailing zeros."""
    return format_length(value, "mm")[:-2]


def _nominal(value: LengthRange | None) -> int | None:
    return None if value is None else value.nominal


def _pins(package: Package) -> int | None:
    keys = package.keys
    if package.family in _TWO_TERMINAL:
        return None
    if package.family == "grid":
        return None
    if package.family == "header":
        return (keys.count("rows") or 0) * (keys.count("columns") or 0)
    if package.family == "to":
        return keys.count("leads")
    return keys.count("pins")


def check(package: Package) -> list[Issue]:
    """``package.name-mismatch`` for each field of a generic name that disagrees with the record."""
    name = package.name
    body_match, pitch_match = _BODY.search(name), _PITCH.search(name)
    if body_match is None and pitch_match is None:
        return []
    keys = package.keys
    found: list[Issue] = []

    def mismatch(field: str, expected: str) -> None:
        found.append(
            issue(
                "package.name-mismatch",
                f"the name field {field} disagrees with the record ({expected})",
                where=f"{package.file or name}:name",
            )
        )

    head = _HEAD.match(name)
    pins = _pins(package)
    if head is not None and pins is not None:
        count = int(head.group("pins")) * (int(head.group("cols")) if head.group("cols") else 1)
        if count != pins:
            mismatch(head.group(0), f"{pins} pins")
    body = keys.table("body")
    if body_match is not None and body is not None:
        length, width = _body_axes(package, body)
        for text, value in ((body_match.group("l"), length), (body_match.group("w"), width)):
            if value is not None and text != mm(value):
                mismatch(
                    f"B{body_match.group('l')}x{body_match.group('w')}",
                    f"body {_text(length)}x{_text(width)}",
                )
                break
        height = _nominal(body.length("height"))
        if body_match.group("h") and height is not None and body_match.group("h") != mm(height):
            mismatch(f"x{body_match.group('h')}", f"height {mm(height)}")
    pitch = _nominal(keys.length("pitch")) if keys.has("pitch") else _nominal(keys.length("pitch_x"))
    if pitch_match is not None and pitch is not None and pitch_match.group("p") != mm(pitch):
        mismatch(f"P{pitch_match.group('p')}", f"pitch {mm(pitch)}")
    ep_match = _EP.search(name)
    ep = keys.table("ep")
    if ep_match is not None and ep is not None:
        ex, ey = _nominal(ep.length("width")), _nominal(ep.length("length"))
        if (ex is not None and ep_match.group("x") != mm(ex)) or (
            ey is not None and ep_match.group("y") != mm(ey)
        ):
            mismatch(f"EP{ep_match.group('x')}x{ep_match.group('y')}", f"exposed pad {_text(ex)}x{_text(ey)}")
    return found


def _text(value: int | None) -> str:
    return "?" if value is None else mm(value)


def _body_axes(package: Package, body: Keys) -> tuple[int | None, int | None]:
    """``L`` along the pin rows and ``W`` across them; for two-terminals ``L`` is the terminal axis."""
    return _nominal(body.length("length")), _nominal(body.length("width"))


__all__ = ["check", "mm"]
