# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net names as KiCad stores and derives them (``docs/formats/kicad/schematic.md``, "Net names"; change
c0061).

Two facts, both measured with ``kicad-cli`` on 9.0.9 and 10.0.6 (``H-K-SCH-SLASH``,
``H-K-SCH-UNCONNECTED``): a ``/`` in a label text names the net with ``{slash}``, because KiCad keeps the
slash for sheet paths; and a pin on no net gets a net of its own, named after the reference, the pin name
and the pad number. Nothing here reads a file.
"""

# evidence: see pcb, schgen

from __future__ import annotations

import string
from collections.abc import Sequence

SLASH = "{slash}"
UNCONNECTED_PREFIX = "unconnected-("
PROVED_PIN_CHARS: frozenset[str] = frozenset(string.ascii_letters + string.digits + " /+-_.~{}")
"""The characters of a pin name for which ``unconnected_name`` equals KiCad's name on 9.0.9 and 10.0.6
(probes ``sch-unconnected-*``). A pin whose name holds another character keeps its pad on no net."""


def stored_name(name: str) -> str:
    """The spelling KiCad stores for the net that a label with the text ``name`` makes."""
    return name.replace("/", SLASH)


def model_name(stored: str) -> str:
    """The inverse of ``stored_name``: the label text of a stored net name."""
    return stored.replace(SLASH, "/")


def unit_letter(unit: int, unit_count: int) -> str:
    """``""`` for a symbol of one unit, else ``A`` to ``Z`` for the units 1 to 26."""
    if unit_count <= 1:
        return ""
    if not 1 <= unit <= 26:
        raise ValueError(f"unit {unit} has no letter: only the units 1 to 26 are named A to Z")
    return chr(ord("A") + unit - 1)


def pin_text(name: str) -> str:
    """A pin name as it stands inside a net name: a blank is ``_`` and a slash is ``{slash}``."""
    return name.replace(" ", "_").replace("/", SLASH)


def proved(pin_name: str) -> bool:
    """Whether every character of ``pin_name`` is one whose spelling in a net name was measured."""
    return all(ch in PROVED_PIN_CHARS for ch in pin_name)


def unconnected_name(ref: str, *, unit: int, unit_count: int, pin_name: str, pad_number: str) -> str:
    """The net name KiCad derives for a pin on no net.

    ``unconnected-(<ref><unit letter>-<pin name>-Pad<number>)`` for a pin with a name, the unit letter
    only for a symbol of several units; ``unconnected-(<ref>-Pad<number>)`` for a pin without a name.
    """
    if not pin_name:
        return f"{UNCONNECTED_PREFIX}{ref}-Pad{pad_number})"
    return f"{UNCONNECTED_PREFIX}{ref}{unit_letter(unit, unit_count)}-{pin_text(pin_name)}-Pad{pad_number})"


JOINED_PREFIX = "Net-("
"""The start of the name KiCad gives a net of several pins without a label."""


def stack_pad(pads: Sequence[str]) -> str:
    """The pad after which KiCad names the net of stacked pins without a label: the number that is the
    lowest in code-point order (``H-K-SCH-STACKED-OPEN``; ``docs/formats/kicad/schematic.md``). The pad
    itself for a pin of one pad."""
    return min(pads)


def open_name(
    ref: str, *, unit: int, unit_count: int, pin_name: str, pads: Sequence[str], marked: bool
) -> str:
    """The net name KiCad derives for a pin on no net that stands for ``pads`` (one pad, or the pads of
    stacked pins): ``unconnected_name`` with ``stack_pad(pads)``. Stacked pins without a no-connect flag
    are a net of several pins to KiCad, so their name starts with ``Net-(`` instead of ``unconnected-(``
    (``H-K-SCH-STACKED-OPEN``)."""
    name = unconnected_name(
        ref, unit=unit, unit_count=unit_count, pin_name=pin_name, pad_number=stack_pad(pads)
    )
    if len(pads) > 1 and not marked:
        return JOINED_PREFIX + name.removeprefix(UNCONNECTED_PREFIX)
    return name


__all__ = [
    "JOINED_PREFIX",
    "PROVED_PIN_CHARS",
    "SLASH",
    "UNCONNECTED_PREFIX",
    "model_name",
    "open_name",
    "pin_text",
    "proved",
    "stack_pad",
    "stored_name",
    "unconnected_name",
    "unit_letter",
]
