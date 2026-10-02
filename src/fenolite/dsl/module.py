# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Modules: named groups of parts whose paths prefix their components' paths (``docs/dsl.md``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import Interface
from fenolite.dsl.part import Net, Part, check_name

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

    def add(self, *objs: Part | Module | Net | Interface) -> None:
        """Attach parts, modules, nets and interfaces; objects join a design only through ``add()``."""
        for obj in objs:
            if isinstance(obj, (Part, Module)):
                if obj.parent is not None:
                    raise DslError(f"{obj!r} is already added")
                if obj is self:
                    raise DslError("a module cannot hold itself")
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

    def __repr__(self) -> str:
        return f"Module({self.name!r})"


__all__ = ["Container", "Module"]
