# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where a backend tells the format-neutral checks the nets of board graphics it keeps outside ``net_id``.

A KiCad board graphic on a copper layer keeps its net in its KiCad slot and leaves ``net_id`` unset (change
c0412). The equivalence check, which imports no backend, asks the hooks registered here for the design with
those nets set (change c0439). The KiCad backend registers its hook when its package is imported, which
reading a KiCad board always does.
"""

from __future__ import annotations

from collections.abc import Callable

from fenolite.model.design import Design

GraphicNets = Callable[[Design], Design]
"""A hook: ``design`` with the nets of its board graphics set, or ``design`` itself."""

_HOOKS: list[GraphicNets] = []


def register(hook: GraphicNets) -> None:
    """Register ``hook`` once."""
    if hook not in _HOOKS:
        _HOOKS.append(hook)


def with_graphic_nets(design: Design) -> Design:
    """``design`` passed through every registered hook, in registration order."""
    for hook in _HOOKS:
        design = hook(design)
    return design


__all__ = ["GraphicNets", "register", "with_graphic_nets"]
