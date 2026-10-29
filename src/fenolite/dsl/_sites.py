# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build-scoped, weak creation records; no stack walk outside a script run (c0256)."""

from __future__ import annotations

import inspect
import weakref
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fenolite.dsl.design import Design


@dataclass(frozen=True, slots=True)
class Site:
    kind: str
    name: str
    where: str


class Recorder:
    def __init__(self, folder: Path) -> None:
        self.folder = folder.resolve()
        self.records: list[tuple[weakref.ReferenceType[object], Site]] = []

    def unattached(self, design: Design) -> tuple[Site, ...]:
        attached = {
            id(obj) for group in (design.parts, design.nets, design.interfaces) for obj in group.values()
        }
        return tuple(
            sorted(
                (
                    site
                    for ref, site in self.records
                    if (obj := ref()) is not None and id(obj) not in attached
                ),
                key=lambda s: (s.where, s.name, s.kind),
            )
        )


_CURRENT: ContextVar[Recorder | None] = ContextVar("fenolite_creation_sites", default=None)


@contextmanager
def recording(folder: Path) -> Generator[Recorder, None, None]:
    recorder = Recorder(folder)
    token = _CURRENT.set(recorder)
    try:
        yield recorder
    finally:
        _CURRENT.reset(token)


def record(obj: object, kind: str, name: str) -> None:
    recorder = _CURRENT.get()
    if recorder is None:
        return
    frame = inspect.currentframe()
    try:
        while frame is not None:
            if not str(frame.f_globals.get("__name__", "")).startswith("fenolite."):
                file = Path(frame.f_code.co_filename)
                if file.is_absolute() and file.is_relative_to(recorder.folder):
                    where = f"{file.relative_to(recorder.folder).as_posix()}:line:{frame.f_lineno}"
                    recorder.records.append((weakref.ref(obj), Site(kind, name, where)))
                    return
            frame = frame.f_back
    finally:
        del frame
