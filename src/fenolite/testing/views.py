# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable views use identities of the built circuit, never replacement ids."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from fenolite.testing.design import TestingError


def unknown(kind: str, name: str, known: tuple[str, ...]) -> TestingError:
    close = difflib.get_close_matches(name, sorted(known), n=3, cutoff=0)
    return TestingError(f"unknown {kind} {name!r}; closest: {', '.join(close) or '(none)'}")


@dataclass(frozen=True, slots=True)
class PinView:
    where: str
    id: str
    net: str | None


@dataclass(frozen=True, slots=True)
class NetView:
    name: str
    id: str
    netclass: str | None
    role: str | None
    voltage: None
    pins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PartView:
    ref: str
    id: str
    value: str
    footprint: str
    device: None
    pins: tuple[PinView, ...]
    _aliases: tuple[tuple[str, PinView], ...] = field(repr=False)

    def __getitem__(self, name: str | int) -> PinView:
        text = str(name)
        # Numbers take precedence, as the design DSL does.
        numbered = [pin for pin in self.pins if pin.where.rsplit("-", 1)[-1] == text]
        found = numbered or [pin for alias, pin in self._aliases if alias == text]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise TestingError(f"ambiguous pin {text!r} of {self.ref}; use its number")
        raise unknown(f"pin of {self.ref}", text, tuple(name for name, _ in self._aliases))

    def __getattr__(self, name: str) -> PinView:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]
