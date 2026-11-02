# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tool-free block convention and deterministic tests (change c0270)."""

from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import json
import random
import re
import shlex
import shutil
import sys
import tempfile
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fenolite.core.errors import Issue
from fenolite.dsl.block import BlockDef
from fenolite.testing._devices import copy_device_context, vendored_project
from fenolite.testing.design import DEFAULT_TIMESTAMP, TestingError, load

if TYPE_CHECKING:
    from fenolite.cli.blocksrc import CatalogEntry

KINDS = ("usage", "golden", "tests")
ISSUE_CODES = {
    "blocks.convention-missing": ("error", "warning"),
    "blocks.usage-failed": ("error",),
    "blocks.golden-differs": ("error",),
    "blocks.golden-missing": ("error",),
    "blocks.test-failed": ("error",),
    "blocks.test-unsupported": ("warning",),
}


@dataclass(frozen=True, slots=True)
class Convention:
    root: Path | None
    name: str
    project: Path | None = None
    """Owning project of a vendored namespace package; paths remain relative to its item root."""

    def path(self, kind: str) -> Path | None:
        if self.root is None:
            return None
        folder, filename = {
            "tests": ("tests", f"test_{self.name}.py"),
            "usage": ("usage", f"{self.name}.py"),
            "golden": ("golden", f"{self.name}.json"),
        }[kind]
        return self.root / folder / filename

    def paths(self) -> dict[str, str | None]:
        return {
            kind: path.relative_to(self.root).as_posix()
            if (path := self.path(kind)) is not None and path.is_file() and self.root is not None
            else None
            for kind in ("tests", "usage", "golden")
        }


def convention(block: BlockDef) -> Convention:
    """Paths beside the defining module, using the name part of the block's id."""
    source = inspect.getsourcefile(block.function)
    return Convention(Path(source).resolve().parent if source else None, block.name.rpartition(":")[2])


def convention_of_entry(entry: CatalogEntry) -> Convention:
    """Static vendored records can report paths without importing their code (c0273)."""
    root = getattr(entry, "item_root", None)
    if entry.source == "library" and isinstance(root, Path):
        root = root.resolve()
        return Convention(root, entry.id.rpartition(":")[2], vendored_project(root))
    return convention(entry.definition)


@dataclass(frozen=True, slots=True)
class GoldenWrite:
    path: Path
    data: bytes


@dataclass(frozen=True, slots=True)
class RunResult:
    blocks: tuple[dict[str, Any], ...]
    issues: tuple[Issue, ...] = ()
    writes: tuple[GoldenWrite, ...] = ()
    depends: tuple[Path, ...] = ()

    @property
    def exit_code(self) -> int:
        return 5 if any(issue.severity != "info" for issue in self.issues) else 0


def _message(error: BaseException) -> str:
    text = str(error) if isinstance(error, AssertionError) else f"{type(error).__name__}: {error}"
    # Private build folder names carry no diagnostic meaning and differ between runs and platforms.
    return re.sub(r"(?:[A-Za-z]:)?[^\s:]*fenolite-(?:test|block)-[^\s/:\\]+", "<temporary>", text)[:500]


@contextlib.contextmanager
def _isolated(root: Path) -> Generator[Path]:
    """Restore the runner's import, working-folder and random state after authored Python runs."""
    saved_path, saved_argv = list(sys.path), list(sys.argv)
    bytecode, rng = sys.dont_write_bytecode, random.getstate()
    siblings = {p.stem for p in root.iterdir() if p.suffix == ".py" or p.is_dir()}
    saved_modules = {
        name: module
        for name, module in list(sys.modules.items())
        if name.partition(".")[0] in siblings
        or name == "_fenolite_block_tests"
        or (
            isinstance(filename := getattr(module, "__file__", None), str)
            and Path(filename).resolve().is_relative_to(root)
        )
    }
    for name in saved_modules:
        if name.partition(".")[0] in siblings or name == "_fenolite_block_tests":
            del sys.modules[name]
    sys.path.insert(0, str(root))
    sys.argv[:] = ["blocks test"]
    sys.dont_write_bytecode = True
    random.seed(0)
    try:
        with tempfile.TemporaryDirectory(prefix="fenolite-block-") as folder, contextlib.chdir(folder):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                yield Path(folder)
    finally:
        sys.path[:], sys.argv[:] = saved_path, saved_argv
        sys.dont_write_bytecode = bytecode
        random.setstate(rng)
        for name, module in list(sys.modules.items()):
            filename = getattr(module, "__file__", None)
            local = isinstance(filename, str) and Path(filename).resolve().is_relative_to(root)
            if local or name == "_fenolite_block_tests" or name.partition(".")[0] in siblings:
                sys.modules.pop(name, None)
        sys.modules.update(saved_modules)


def _usage(path: Path, *, project: Path | None = None) -> tuple[dict[str, Any] | None, str]:
    from fenolite.model import canonical

    try:
        root = project or path.parent.parent
        with _isolated(root) as private:
            # A build can allocate a source-side lock; all such writes belong to this private copy.
            copied = private / "library"
            ignore = shutil.ignore_patterns(
                "__pycache__", ".git", ".venv", ".fenolite", "node_modules", "*.bak"
            )
            shutil.copytree(
                root / "fenolite_library" if project is not None else root,
                copied / "fenolite_library" if project is not None else copied,
                ignore=ignore,
                symlinks=True,
            )
            usage = copied / path.relative_to(root)
            if project is not None:
                authored = root / "devices"
                if authored.is_dir():
                    shutil.copytree(authored, copied / "devices", ignore=ignore, symlinks=True)
                copy_device_context(copied, usage.parent)
            sys.path.insert(0, str(copied))
            with load(usage, seed=0, timestamp=DEFAULT_TIMESTAMP) as design:
                # The runner judges build warnings as well as the check findings.
                build = design._build_issues  # pyright: ignore[reportPrivateUsage]
                first = next((i for i in build if i["severity"] != "info"), None)
                if first is not None:
                    return None, f"{first['code']}: {first['message']}"
                first_check = next((i for i in design.findings() if i.severity != "info"), None)
                if first_check is not None:
                    return None, f"{first_check.code}: {first_check.message}"
                return {
                    "circuit": canonical.to_data(design.model.circuit),
                    "rules": canonical.to_data(design.model.rules),
                }, ""
    except Exception as error:  # noqa: BLE001 - input code failures are runner findings
        return None, _message(error)


def golden_bytes(entry: CatalogEntry, data: dict[str, Any]) -> bytes:
    from fenolite.model import canonical

    header = entry.definition.header
    paths = convention(entry.definition)
    return canonical.dumps(
        {
            "schema": "fenolite.block-golden.v0",
            "block": entry.id,
            "version": header.version if header else None,
            "usage": f"usage/{paths.name}.py",
            "seed": 0,
            "timestamp": DEFAULT_TIMESTAMP,
            **data,
        }
    ).encode("utf-8")


def differing_paths(before: bytes, after: bytes) -> tuple[str, ...]:
    """The first twenty changed JSON leaves, sorted; malformed input differs at its root."""
    try:
        old, new = json.loads(before), json.loads(after)
    except (ValueError, UnicodeDecodeError):
        return ("$",)
    paths: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if type(a) is not type(b):
            paths.append(path or "$")
        elif isinstance(a, dict):
            for key in sorted(a.keys() | b.keys()):
                at = f"{path}.{key}" if path else key
                if key not in a or key not in b:
                    paths.append(at)
                else:
                    walk(a[key], b[key], at)
        elif isinstance(a, list):
            old_items, new_items = cast(list[Any], a), cast(list[Any], b)
            for index in range(max(len(old_items), len(new_items))):
                at = f"{path}[{index}]"
                if index >= len(old_items) or index >= len(new_items):
                    paths.append(at)
                else:
                    walk(old_items[index], new_items[index], at)
        elif a != b:
            paths.append(path or "$")

    walk(old, new, "")
    return tuple(sorted(paths)[:20]) or ("$",)  # noncanonical bytes can hold equal objects


def _golden(
    entry: CatalogEntry,
    data: dict[str, Any],
    row: dict[str, Any],
    issues: list[Issue],
    *,
    plan: bool,
) -> GoldenWrite | None:
    path = convention_of_entry(entry).path("golden")
    if path is None:
        return None
    built = golden_bytes(entry, data)
    if plan:
        row["golden"] = "written"
        return GoldenWrite(path, built)
    if not path.is_file():
        return None
    old = path.read_bytes()
    row["golden"] = "equal" if old == built else "differs"
    if old != built:
        changed = differing_paths(old, built)
        row["golden_paths"] = list(changed)
        issues.append(
            Issue(
                "blocks.golden-differs",
                "error",
                f"{entry.id}: golden differs at {', '.join(changed)}",
                where=entry.id,
                hint=_regenerate(entry),
            )
        )
    return None


def _regenerate(entry: CatalogEntry) -> str:
    args = ["fenolite", "blocks", "test", entry.id]
    if entry.source == "file":
        args += ["--from", entry.where]
    return shlex.join([*args, "--golden", "--dry-run"])


def _functions(
    path: Path, block_id: str, *, project: Path | None = None
) -> tuple[list[dict[str, str]], list[Issue]]:
    tests: list[dict[str, str]] = []
    issues: list[Issue] = []
    try:
        with _isolated(project or path.parent.parent):
            spec = importlib.util.spec_from_file_location("_fenolite_block_tests", path)
            if spec is None or spec.loader is None:
                raise TestingError(f"cannot import {path.name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            for name, function in sorted(vars(module).items()):
                if (
                    not name.startswith("test_")
                    or not inspect.isfunction(function)
                    or function.__module__ != spec.name
                ):
                    continue
                required = [
                    p.name
                    for p in inspect.signature(function).parameters.values()
                    if p.default is p.empty and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                ]
                if required or inspect.iscoroutinefunction(function):
                    message = (
                        "requires parameters: " + ", ".join(required)
                        if required
                        else "async test functions are unsupported"
                    )
                    tests.append({"name": name, "status": "skipped", "message": message})
                    issues.append(
                        Issue(
                            "blocks.test-unsupported",
                            "warning",
                            f"{block_id} {name}: {message}",
                            where=f"{block_id}/{name}",
                            hint="write a plain zero-argument test function",
                        )
                    )
                    continue
                try:
                    function()
                except (Exception, SystemExit) as error:  # noqa: BLE001 - failures are the runner's result
                    message = _message(error)
                    tests.append({"name": name, "status": "failed", "message": message})
                    issues.append(
                        Issue(
                            "blocks.test-failed",
                            "error",
                            f"{block_id} {name}: {message}",
                            where=f"{block_id}/{name}",
                        )
                    )
                else:
                    tests.append({"name": name, "status": "passed", "message": ""})
    except (Exception, SystemExit) as error:  # noqa: BLE001 - a module import is authored test code too
        message = _message(error)
        tests.append({"name": path.name, "status": "failed", "message": message})
        issues.append(
            Issue(
                "blocks.test-failed",
                "error",
                f"{block_id} {path.name}: {message}",
                where=block_id,
            )
        )
    return tests, issues


def run_block_tests(
    records: Sequence[CatalogEntry], *, kinds: Sequence[str] = KINDS, golden_plan: bool = False
) -> RunResult:
    """Run the given records in id order, in private build folders, with no timing or tool calls."""
    if not kinds or any(kind not in KINDS for kind in kinds):
        raise TestingError(f"block test kinds are {', '.join(KINDS)}")
    blocks: list[dict[str, Any]] = []
    issues: list[Issue] = []
    inputs: set[Path] = set()
    writes: list[GoldenWrite] = []
    for entry in sorted(records, key=lambda entry: (entry.id, entry.source, entry.where)):
        paths = convention_of_entry(entry)
        header = entry.definition.header
        row: dict[str, Any] = {
            "id": entry.id,
            "version": header.version if header else None,
            "usage": "missing",
            "golden": "missing",
            "tests": [],
        }
        blocks.append(row)
        missing = [kind for kind, path in paths.paths().items() if path is None]
        if golden_plan and "golden" in missing:
            missing.remove("golden")
        if missing:
            issues.append(
                Issue(
                    "blocks.convention-missing",
                    "error" if entry.id.startswith("Fenolite:") else "warning",
                    f"{entry.id}: missing {', '.join(missing)}",
                    where=entry.id,
                    hint="ship usage/<name>.py, tests/test_<name>.py and golden/<name>.json beside the block",
                )
            )
        golden = paths.path("golden")
        if (
            "golden" in kinds
            and not golden_plan
            and (golden is None or not golden.is_file())
            and (tuple(kinds) == ("golden",) or entry.id.startswith("Fenolite:"))
        ):
            issues.append(
                Issue(
                    "blocks.golden-missing",
                    "error",
                    f"{entry.id}: no golden/{paths.name}.json",
                    where=entry.id,
                    hint=_regenerate(entry),
                )
            )
        source = inspect.getsourcefile(entry.definition.function)
        if source:
            inputs.add(Path(source).resolve())
        for kind in KINDS:
            path = paths.path(kind)
            if path is not None and path.is_file():
                inputs.add(path)
        usage = paths.path("usage")
        if ("usage" in kinds or "golden" in kinds or golden_plan) and usage is not None and usage.is_file():
            data, message = _usage(usage, project=paths.project)
            row["usage"] = "passed" if data is not None else "failed"
            if data is None:
                issues.append(
                    Issue(
                        "blocks.usage-failed",
                        "error",
                        f"{entry.id}: {message}",
                        where=entry.id,
                        hint="fix the usage build and its tool-free findings before regenerating goldens",
                    )
                )
            elif "golden" in kinds or golden_plan:
                write = _golden(entry, data, row, issues, plan=golden_plan)
                if write is not None:
                    writes.append(write)
        elif golden_plan:
            issues.append(
                Issue(
                    "blocks.usage-failed",
                    "error",
                    f"{entry.id}: usage example is missing",
                    where=entry.id,
                )
            )
        test_path = paths.path("tests")
        if "tests" in kinds and test_path is not None and test_path.is_file():
            row["tests"], found = _functions(test_path, entry.id, project=paths.project)
            issues.extend(found)
    return RunResult(
        tuple(blocks),
        tuple(issues),
        tuple(writes) if not any(i.severity == "error" for i in issues) else (),
        tuple(sorted(inputs)),
    )


__all__ = ["Convention", "KINDS", "RunResult", "convention", "run_block_tests"]
