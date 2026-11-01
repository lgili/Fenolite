# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit package execution for blocks index and lazy catalog execution (c0273)."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import sys
from collections.abc import Generator, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl.block import BlockDef
from fenolite.dsl.blockitem import FILE, from_record
from fenolite.dsl.record import describe
from fenolite.library.items import ItemError, folder_files
from fenolite.library.items import read_item as read_manifest

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BLOCK-PACKAGES",))


@contextlib.contextmanager
def item_module(root: Path, *, fresh: bool = True, keep: bool = False) -> Generator[ModuleType]:
    """Import a package by path without bytecode; fresh runs restore their private module cache."""
    path = root / "__init__.py"
    if not path.is_file():
        raise FormatError("a block item is a package with __init__.py", file=root.name)
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]
    name = f"_fenolite_block_item_{digest}"
    saved = {k: v for k, v in sys.modules.items() if k == name or k.startswith(name + ".")}
    if fresh:
        for key in saved:
            del sys.modules[key]
    quiet, paths = sys.dont_write_bytecode, list(sys.path)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root.parent))
    try:
        module = sys.modules.get(name)
        if module is None:
            spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(root)])
            if spec is None or spec.loader is None:
                raise FormatError("the block package cannot be imported", file=root.name)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        yield module
    except FormatError:
        raise
    except Exception as error:
        raise FormatError(f"block package failed: {type(error).__name__}: {error}", file=root.name) from error
    finally:
        sys.path[:] = paths
        sys.dont_write_bytecode = quiet
        if fresh and not keep:
            for key in list(sys.modules):
                if key == name or key.startswith(name + "."):
                    del sys.modules[key]
            sys.modules.update(saved)


def exported_block(module: ModuleType) -> BlockDef:
    names: object = getattr(module, "__all__", ())
    if not isinstance(names, (tuple, list)) or not all(
        isinstance(n, str) for n in cast(Sequence[object], names)
    ):
        raise FormatError("a block package __all__ is a list of export names")
    blocks = [
        found
        for name in cast(Sequence[str], names)
        if isinstance(found := getattr(module, name, None), BlockDef)
    ]
    if len(blocks) != 1:
        raise FormatError(f"a block item exports exactly one BlockDef in __all__; found {len(blocks)}")
    return blocks[0]


def load_definition(root: Path) -> BlockDef:
    with item_module(root, keep=True) as module:
        return exported_block(module)


def register_index(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--check", dest="index_check", action="store_true", help="index: check block.json without writing"
    )


def run_index(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.target) != 1:
        raise CliError("FEN-2001", "blocks index takes one package folder", where="ITEM_DIR")
    given = Path(args.target[0])
    root = given if given.is_absolute() else ctx.cwd / given
    if not root.is_dir():
        raise CliError("FEN-3001", "the block item folder does not exist", where=str(given))
    try:
        manifest = read_manifest((root / "item.json").read_bytes())
        files = folder_files(root, exclude=("__pycache__/",))
    except (ItemError, OSError) as error:
        raise CliError("FEN-3004", str(error), where=str(given)) from error
    if manifest.kind != "block" or not manifest.executes:
        raise CliError("FEN-3004", "a block item has kind block and executes true", where=str(given))
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), item_module(root) as module:
        definition = exported_block(module)
        record = describe(definition)
    item = from_record(record)
    if (item.id, item.version) != (manifest.id, manifest.version):
        raise CliError("FEN-3004", "block id and version must equal item.json", where=str(given))
    if record.elaboration is not None and "error" in record.elaboration:
        raise CliError(
            "FEN-3004", "the block cannot be described: " + record.elaboration["error"], where=str(given)
        )
    target = Path(args.out) if args.out is not None else root / FILE
    target_path = target if target.is_absolute() else ctx.cwd / target
    try:
        shown = target_path.resolve().relative_to(ctx.cwd.resolve()).as_posix()
    except ValueError:
        raise CliError("FEN-2001", "--out is inside the working directory", where="--out") from None
    text = item.text().encode("utf-8")
    same = target_path.is_file() and target_path.read_bytes() == text
    issues = (
        (Issue("blocks.index-stale", "error", "the stored block index differs from its code", where=shown),)
        if args.index_check and not same
        else ()
    )
    writes = () if args.index_check or same else (PlannedWrite(shown, text, "block-index"),)
    return Result(
        result={
            "id": item.id,
            "version": item.version,
            "file": shown,
            "current": same,
            "record": item.data(),
            "output": output.getvalue()[:4000],
        },
        issues=issues,
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(
            ctx.cwd, *(root / path for path in files if (root / path).resolve() != target_path.resolve())
        ),
    )
