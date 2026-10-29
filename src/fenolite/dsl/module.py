# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Modules: named groups of parts whose paths prefix their components' paths (``docs/dsl.md``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from fenolite.core.partquery import PartQuery
from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import Interface
from fenolite.dsl.part import Net, Part, check_name
from fenolite.dsl.quantity import Quantity, Range

if TYPE_CHECKING:
    from fenolite.dsl.design import Design


class Container:
    """What ``Design`` and ``Module`` share: ``add()`` and the objects it attached, in order."""

    def __init__(self) -> None:
        self.children: list[Part | Module] = []
        self.pending_nets: list[Net] = []
        self.pending_interfaces: list[Interface] = []

    @property
    def design(self) -> Design | None:
        raise NotImplementedError

    def describe(self) -> str:
        """The container as messages name it."""
        raise NotImplementedError

    def part(
        self,
        ref: str | None = None,
        lib_id: str | None = None,
        footprint: str | None = None,
        value: str | Quantity | Range | None = None,
        *,
        name: str | None = None,
        prefix: str | None = None,
        device: str | PartQuery | None = None,
        properties: Mapping[str, str] | None = None,
        pad_map: Mapping[str, str | Sequence[str]] | None = None,
        height: object = None,
    ) -> Part:
        """Create a part with the arguments of ``Part`` and attach it; the ref may be left out
        (``docs/dsl.md``, "Reference designators and the design lock"), and a device id resolves against
        the design's ``devices()`` records first (``docs/devices.md``)."""
        from fenolite.dsl.devices import design_records

        design = self.design
        with design_records(design.device_records if design is not None else {}):
            made = Part(
                ref,
                lib_id,
                footprint,
                value,
                name=name,
                prefix=prefix,
                device=device,
                properties=properties,
                pad_map=pad_map,
                height=height,
            )
        self.add(made)
        return made

    def _check_key(self, part: Part) -> None:
        """Refuse a part whose key is the key of a sibling when one of the two is unnamed: a path made from
        a prefix is taken by the first part that has it, and a counter would depend on statement order."""
        for sibling in self.children:
            if not isinstance(sibling, Part) or sibling.key != part.key:
                continue
            if (
                part.explicit_ref is None
                and part.name is None
                or sibling.explicit_ref is None
                and sibling.name is None
            ):
                where = part.key if not isinstance(self, Module) else f"{self.path}/{part.key}"
                raise DslError(
                    f"{self.describe()}: the path {where} is taken by an unnamed part; "
                    "give this part name=..."
                )

    def add(self, *objs: Part | Module | Net | Interface) -> None:
        """Attach parts, modules, nets and interfaces; objects join a design only through ``add()``."""
        for obj in objs:
            if isinstance(obj, (Part, Module)):
                if obj.parent is not None:
                    raise DslError(f"{obj!r} is already added")
                if obj is self:
                    raise DslError("a module cannot hold itself")
                if isinstance(obj, Part):
                    self._check_key(obj)
                obj.parent = self
                self.children.append(obj)
                design = self.design
                if design is not None:
                    design.register_tree(obj)
            elif isinstance(obj, Net):
                self.pending_nets.append(obj)
                if self.design is not None:
                    self.design.register_net(obj)
            elif isinstance(obj, Interface):  # pyright: ignore[reportUnnecessaryIsInstance]
                self.pending_interfaces.append(obj)
                if self.design is not None:
                    self.design.register_interface(obj)
            else:
                raise DslError(f"add() takes parts, modules, nets and interfaces, not {obj!r}")


class Module(Container):
    """A named group; its path is its name at the top and ``<parent path>/<name>`` below."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = check_name(name, "module name")
        self.parent: Container | None = None

    @property
    def path(self) -> str:
        if isinstance(self.parent, Module):
            return f"{self.parent.path}/{self.name}"
        return self.name

    @property
    def design(self) -> Design | None:
        return None if self.parent is None else self.parent.design

    def describe(self) -> str:
        return f"module {self.path}"

    def __repr__(self) -> str:
        return f"Module({self.name!r})"


__all__ = ["Container", "Module"]
