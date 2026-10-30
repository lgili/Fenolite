# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog sources of ``fenolite blocks`` (``docs/blocks.md``, "Catalog"; change c0268).

``builtin`` is the package ``fenolite.blocks`` and its modules, imported, each listing its blocks in
``__all__``. ``file`` is each ``--from FILE.py``, imported by path under a private module name: importing
runs that module's code, so a block module is best kept apart from a design script. Every top-level block
that a file defines is listed. Records are described on demand (``fenolite.dsl.describe``), and once.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import pkgutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from fenolite.core.errors import FormatError, Issue
from fenolite.dsl.block import BlockDef
from fenolite.dsl.errors import DslError
from fenolite.dsl.record import BlockRecord, describe

SHIPPED = "fenolite.blocks"
SOURCES: tuple[str, ...] = ("builtin", "file")
"""The catalog sources, in the order a list gives them for one id (c0273 adds ``library``)."""
DUPLICATE = "blocks.duplicate-id"


@dataclass(eq=False)
class CatalogEntry:
    """One block of the catalog: its definition, its ``source`` and ``where`` (a module name, or the
    file as the command line gave it; never an absolute path)."""

    definition: BlockDef
    source: str
    where: str
    _record: BlockRecord | None = field(default=None, repr=False)

    @property
    def id(self) -> str:
        return self.definition.name

    @property
    def record(self) -> BlockRecord:
        """The block's record (``describe``), computed once."""
        if self._record is None:
            self._record = describe(self.definition)
        return self._record


def _listed(module: ModuleType) -> list[BlockDef]:
    names = getattr(module, "__all__", ())
    return [found for name in names if isinstance(found := getattr(module, name, None), BlockDef)]


def _builtin() -> list[CatalogEntry]:
    package = importlib.import_module(SHIPPED)
    entries = [CatalogEntry(found, "builtin", SHIPPED) for found in _listed(package)]
    for info in sorted(pkgutil.walk_packages(package.__path__, f"{SHIPPED}."), key=lambda m: m.name):
        module = importlib.import_module(info.name)
        entries += [CatalogEntry(found, "builtin", info.name) for found in _listed(module)]
    return entries


def _shown(path: Path, given: str) -> str:
    return given if not Path(given).is_absolute() else path.name


def import_file(path: Path) -> ModuleType:
    """The module of ``path``, imported under a private name (``_fenolite_blocks_<digest>``); ``FormatError``
    (``FEN-3004``) for a file that does not import."""
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    name = f"_fenolite_blocks_{digest}"
    known = sys.modules.get(name)
    if known is not None:
        return known
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FormatError(f"{path.name} is not a Python module", file=path.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    quiet = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # importing a --from file leaves no __pycache__ beside it
    try:
        spec.loader.exec_module(module)
    except DslError as error:
        del sys.modules[name]
        raise FormatError(f"{path.name}: {error}", file=path.name) from error
    except Exception as error:  # noqa: BLE001 - any failure of the imported code is the input's
        del sys.modules[name]
        raise FormatError(
            f"{path.name} does not import: {type(error).__name__}: {error}", file=path.name
        ) from error
    finally:
        sys.dont_write_bytecode = quiet
    return module


def _file(path: Path, given: str) -> list[CatalogEntry]:
    module = import_file(path)
    where = _shown(path, given)
    return [
        CatalogEntry(found, "file", where)
        for _, found in sorted(vars(module).items())
        if isinstance(found, BlockDef) and getattr(found.function, "__module__", "") == module.__name__
    ]


def find_blocks(*, files: Sequence[str] = (), cwd: Path | None = None) -> tuple[CatalogEntry, ...]:
    """Every block of the catalog: the shipped ones (``builtin``), then those of each ``files`` path
    (``file``), sorted by id and then by source."""
    root = cwd or Path.cwd()
    entries = _builtin()
    for given in files:
        path = Path(given) if Path(given).is_absolute() else root / given
        if not path.is_file():
            raise FormatError(f"--from {given}: no such file", file=given)
        entries += _file(path, given)
    return tuple(sorted(entries, key=lambda e: (e.id, SOURCES.index(e.source), e.where)))


def duplicate_issues(entries: Sequence[CatalogEntry]) -> list[Issue]:
    """One ``blocks.duplicate-id`` error per id that two entries hold, naming both sources."""
    by_id: dict[str, list[CatalogEntry]] = {}
    for entry in entries:
        by_id.setdefault(entry.id, []).append(entry)
    return [
        Issue(
            DUPLICATE,
            "error",
            f"the block id {block_id} is held by "
            + " and ".join(f"{entry.source} {entry.where}" for entry in found),
            where=block_id,
            hint="give one of the blocks another id, or leave one --from file out",
        )
        for block_id, found in sorted(by_id.items())
        if len(found) > 1
    ]


__all__ = [
    "DUPLICATE",
    "SHIPPED",
    "SOURCES",
    "CatalogEntry",
    "duplicate_issues",
    "find_blocks",
    "import_file",
]
