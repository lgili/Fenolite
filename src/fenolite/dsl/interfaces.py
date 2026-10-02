# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Groups of nets (``docs/dsl.md``, "Interfaces"): kept in the model, never lowered to KiCad."""

from __future__ import annotations

from collections.abc import Mapping

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net


class Interface:
    """A typed bundle of nets: role → net."""

    def __init__(self, name: str, kind: str, members: Mapping[str, Net]) -> None:
        if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"an interface name must be a non-empty string, not {name!r}")
        if not isinstance(kind, str) or not kind:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"interface {name}: kind must be a non-empty string")
        for role, net in members.items():
            if not isinstance(net, Net):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"interface {name}: member {role!r} is not a Net")
        self.name = name
        self.kind = kind
        self.members = dict(members)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class Power(Interface):
    """A supply: ``hv`` and ``lv`` nets; the default name is ``<hv>/<lv>``."""

    def __init__(self, hv: Net, lv: Net, *, name: str | None = None) -> None:
        super().__init__(name or f"{hv.name}/{lv.name}", "power", {"hv": hv, "lv": lv})


class DiffPair(Interface):
    """A differential pair: ``p`` and ``n`` nets; the default name is ``<p>/<n>``."""

    def __init__(self, p: Net, n: Net, *, name: str | None = None) -> None:
        super().__init__(name or f"{p.name}/{n.name}", "diff_pair", {"p": p, "n": n})


__all__ = ["DiffPair", "Interface", "Power"]
