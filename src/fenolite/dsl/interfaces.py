# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Groups of nets (``docs/dsl.md``, "Interfaces"): kept in the model, never lowered to KiCad.

``Harness`` (change c0037) is lowered by the Altium build only."""

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


class Harness(Interface):
    """A named group of nets with different names, such as SPI with MOSI, MISO and SCK (change c0037).

    ``name`` is the harness type name and has no default; ``members`` maps an entry name to its net. The
    order of the entries carries no meaning: a backend that needs one sorts the entry names. The KiCad
    build keeps a harness in the model only; the Altium build draws it as a signal harness."""

    def __init__(self, name: str, members: Mapping[str, Net]) -> None:
        if isinstance(name, str) and name and not members:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"harness {name}: a harness needs at least one entry")
        for entry in members:
            if not isinstance(entry, str) or not entry:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"harness {name}: an entry name must be a non-empty string, not {entry!r}")
        super().__init__(name, "harness", members)


__all__ = ["DiffPair", "Harness", "Interface", "Power"]
