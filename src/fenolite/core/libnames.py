# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The name a library entry gets in a KiCad library a conversion writes (change c0435): the Altium to KiCad
conversion names each footprint of its derived library with ``library_name``, and ``equivalent`` compares
footprint names after the same rewrite, so a name that only the rewrite changed (a ``/`` that became ``_``)
is no difference."""

from __future__ import annotations

import re

_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
"""Device names Windows reserves for a file stem."""
FREE_PAD_PREFIX = "FREE_"
"""The start of the item name of the footprint that the Altium to KiCad conversion makes for a free pad,
``FREE_<footprint id>`` (change c0447): a KiCad footprint always has a link, so the Altium writer knows the
footprint as a free pad by this name, with no reference and one pad (``lower.converted_free_pad``)."""


def library_name(value: str, *, allow_space: bool = False) -> str:
    """``value`` with every character other than a word character, ``.``, ``-`` (and a space when
    ``allow_space``) replaced by ``_``, without leading or trailing dots and spaces, ``unnamed`` when nothing
    is left, and with ``_`` before a reserved device name."""
    text = re.sub(r"[^\w. -]" if allow_space else r"[^\w.-]", "_", value).strip(". ") or "unnamed"
    return "_" + text if text.upper() in _RESERVED else text


__all__ = ["FREE_PAD_PREFIX", "library_name"]
