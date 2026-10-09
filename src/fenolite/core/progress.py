# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""How a long step says that it is alive and how far it is (capability cli-contract, "Progress on
stderr").

The checks, the routers and the backends report their units of work through :class:`Progress` and know
nothing of who listens: the CLI passes a reporter that writes records on stderr, everything else passes
:data:`NULL_PROGRESS`.
"""

from __future__ import annotations

from typing import Protocol


class Progress(Protocol):
    """A listener for units of work. ``name`` is a short stable word (a stage, a net, a kind), never a
    path of the machine."""

    def step(self, name: str, *, index: int | None = None, total: int | None = None) -> None:
        """The unit ``name`` starts; ``index`` of ``total`` counts from 1 when the caller knows them."""
        ...

    def done(self, name: str, *, detail: str = "") -> None:
        """The unit ``name`` ended; ``detail`` says how in a few words."""
        ...


class _Null:
    """The reporter that does nothing."""

    __slots__ = ()

    def step(self, name: str, *, index: int | None = None, total: int | None = None) -> None:
        return None

    def done(self, name: str, *, detail: str = "") -> None:
        return None

    def __repr__(self) -> str:
        return "NULL_PROGRESS"


NULL_PROGRESS: Progress = _Null()

__all__ = ["NULL_PROGRESS", "Progress"]
