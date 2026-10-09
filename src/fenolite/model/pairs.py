# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Differential pairs: which interfaces are pairs, and the name rule by which two nets form one.

A pair is an ``Interface`` whose kind is a key of ``PAIR_ROLES``; the model holds no other pair entity.
KiCad stores no pair object either: two nets pair by their names, and a rule selects them with
``inDiffPair('<base>')``. The name rule here is the measured one (``H-K-DIFFPAIR-NAMES-2``,
``docs/formats/kicad/rules.md``): a polarity character, ``P`` or ``N``, ``+`` or ``-``, followed in both
names by the same run of digits and underscores, possibly empty. Letter case counts throughout.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.model.circuit import Interface

PAIR_ROLES: Mapping[str, tuple[str, str]] = MappingProxyType({"diff_pair": ("p", "n"), "usb2": ("dp", "dn")})
"""Interface kind → the roles of its positive and its negative net."""
POLARITIES: Mapping[str, str] = MappingProxyType({"P": "N", "N": "P", "+": "-", "-": "+"})
"""Each polarity character → the one of the coupled net."""
POSITIVE = frozenset({"P", "+"})
_TAIL = frozenset("0123456789_")


@dataclass(frozen=True, slots=True)
class PairName:
    """A net name split by the name rule: ``base + polarity + tail`` is the name."""

    base: str
    polarity: str
    tail: str


def split_pair_name(name: str) -> PairName | None:
    """``name`` without its longest trailing run of digits and ``_`` (the tail) must end with a polarity
    character; the base is the text before it. ``None`` when it does not."""
    end = len(name)
    while end > 0 and name[end - 1] in _TAIL:
        end -= 1
    if end == 0 or name[end - 1] not in POLARITIES:
        return None
    return PairName(name[: end - 1], name[end - 1], name[end:])


def coupled_name(name: str) -> str | None:
    """The name of the other net of the pair: the base, the other polarity and the tail."""
    split = split_pair_name(name)
    if split is None:
        return None
    return split.base + POLARITIES[split.polarity] + split.tail


def pair_base(positive: str, negative: str) -> str | None:
    """The base of the pair that the two names form, the positive one first, or ``None``."""
    split = split_pair_name(positive)
    if split is None or split.polarity not in POSITIVE:
        return None
    if negative != split.base + POLARITIES[split.polarity] + split.tail:
        return None
    return split.base


def pair_nets(interface: Interface) -> tuple[str, str] | None:
    """The ids of the positive and the negative net of a pair interface; ``None`` for another kind or a
    missing role."""
    roles = PAIR_ROLES.get(interface.kind)
    if roles is None:
        return None
    positive, negative = (interface.members.get(role) for role in roles)
    if positive is None or negative is None:
        return None
    return positive, negative


def net_bases(names: Iterable[str]) -> dict[str, str]:
    """Net name → base, for each name whose coupled name is also among ``names``."""
    known = set(names)
    found: dict[str, str] = {}
    for name in known:
        split = split_pair_name(name)
        if split is not None and split.base + POLARITIES[split.polarity] + split.tail in known:
            found[name] = split.base
    return found


def base_matches(base: str | None, value: str) -> bool:
    """Whether a ``diff_pair`` leaf of ``value`` selects a net of the pair base ``base``: ``value`` is a
    glob compared with its letter case, and a base that ends with ``_`` also matches without that ``_``
    (``H-K-DRU-PAIRSEL``)."""
    if base is None:
        return False
    if fnmatch.fnmatchcase(base, value):
        return True
    return base.endswith("_") and fnmatch.fnmatchcase(base[:-1], value)


__all__ = [
    "PAIR_ROLES",
    "POLARITIES",
    "POSITIVE",
    "PairName",
    "base_matches",
    "coupled_name",
    "net_bases",
    "pair_base",
    "pair_nets",
    "split_pair_name",
]
