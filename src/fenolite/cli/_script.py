# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Running a design script in-process (``docs/dsl.md``, "Scripts").

``build`` executes ``design.py`` as the user's own code: there is no sandbox, and it must never be run
on an untrusted script. The run writes no bytecode, captures the script's output, and restores
``sys.path``, ``sys.argv``, ``sys.dont_write_bytecode`` and the module cache of the script folder.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import os
import runpy
import sys
import traceback
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.catalog.devices import edited_issue, is_edited
from fenolite.catalog.records import DeviceRecord, LibraryTree, load_tree
from fenolite.catalog.vendored import VendoredTree, load_vendored, overlay
from fenolite.cli._vendored import hint_namespaces
from fenolite.cli.blockvendored import check_used
from fenolite.core.errors import FormatError, Issue
from fenolite.dsl import Design, Panel
from fenolite.dsl._sites import Site, recording
from fenolite.dsl.devices import ProjectDevices, installed
from fenolite.dsl.record import BlockRecord
from fenolite.library.importer.native import Native, read_native_definitions
from fenolite.pick.rows import PROPOSED_DIR

SCRIPT_OUTPUT_LIMIT = 4000
TRUNCATED = "…[truncated]"
RUN_NAME = "__fenolite_build__"
DEVICES_DIR = "devices"
"""The folder beside a design script whose ``*.toml`` files are the project devices (change c0248)."""


class DesignScriptError(FormatError):
    """A design script raised, or binds no module-level ``design`` (FEN-3004)."""

    hint: str = ""


@dataclass(frozen=True)
class DeviceFile:
    """A project device file read for a run: its path relative to the script folder and its SHA-256."""

    path: str
    sha256: str


@dataclass(frozen=True)
class ScriptRun:
    design: Design
    output: str
    devices: ProjectDevices = ProjectDevices()
    """The project devices of ``devices/`` beside the script, installed while it ran."""
    device_files: tuple[DeviceFile, ...] = ()
    device_issues: tuple[Issue, ...] = ()
    library: LibraryTree = LibraryTree()
    """Every record of ``devices/`` beside the script, read recursively (change c0259): devices, parts,
    pins and packages; its pins and packages override catalog definitions of the same id."""
    unattached: tuple[Site, ...] = ()
    """The parts, nets and interfaces the script created that never reached the design (c0256)."""
    block_issues: tuple[Issue, ...] = ()
    source_files: tuple[Path, ...] = ()
    block_records: Mapping[int, BlockRecord] = field(default_factory=lambda: dict[int, BlockRecord]())
    imported: Native = Native()
    vendored: VendoredTree = VendoredTree()


def read_project_library(folder: Path) -> tuple[LibraryTree, tuple[DeviceFile, ...], tuple[Issue, ...]]:
    """The records of ``folder/devices/`` (recursively, in POSIX path order), its files with their SHA-256,
    and a ``device.edited`` info for each edited device record. A malformed file raises its
    ``FormatError`` (FEN-3004 or FEN-3002); two records of one kind and id raise FEN-3004 naming both."""
    devices_dir = folder / DEVICES_DIR
    # devices/proposed/ holds unreviewed rows that only a query naming them picks (change c0254)
    tree = load_tree(devices_dir, label=f"{DEVICES_DIR}/", exclude=(PROPOSED_DIR,))
    files = (
        tuple(
            DeviceFile(path.relative_to(folder).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(
                devices_dir.rglob("*.toml"), key=lambda found: found.relative_to(folder).as_posix()
            )
        )
        if devices_dir.is_dir()
        else ()
    )
    issues = tuple(
        edited_issue(record.device, tree.files[("device", record.header.id)])
        for record in tree.records
        if isinstance(record, DeviceRecord) and is_edited(record.device)
    )
    return tree, files, issues


def read_project_devices(folder: Path) -> tuple[ProjectDevices, tuple[DeviceFile, ...], tuple[Issue, ...]]:
    """The project devices of ``folder/devices/`` (``read_project_library``) as the DSL takes them."""
    tree, files, issues = read_project_library(folder)
    return _project(tree), files, issues


def _project(tree: LibraryTree, vendored: VendoredTree | None = None) -> ProjectDevices:
    vendored = vendored or VendoredTree()
    owners = {key[1]: name for key, name in tree.files.items() if key[0] == "device"}
    libraries = {
        key[1]: ref.as_json()
        for key, ref in vendored.items.items()
        if key[0] == "device" and tree.files.get(key, "").startswith("fenolite_library/")
    }
    symbols, _ = tree.device_symbols()
    return ProjectDevices(
        tree.devices(), owners, dict(tree.parts), libraries, hint_namespaces(), {key: key for key in symbols}
    )


def _inside(path: str | None, folder: Path) -> bool:
    if not path:
        return False
    try:
        return Path(path).resolve().is_relative_to(folder)
    except OSError:
        return False


def _locator(error: BaseException, script: Path) -> str:
    line = None
    for frame in traceback.extract_tb(error.__traceback__):
        if Path(frame.filename).resolve() == script:
            line = frame.lineno
    return f"line:{line}" if line is not None else ""


def _capped(text: str) -> str:
    if len(text) <= SCRIPT_OUTPUT_LIMIT:
        return text
    return text[: SCRIPT_OUTPUT_LIMIT - len(TRUNCATED)] + TRUNCATED


def _missing_block_hint(error: ModuleNotFoundError, script: Path) -> str:
    """Use the failed import's module path, including an absent namespace-package ancestor."""
    missing = error.name or ""
    if missing != "fenolite_library" and not missing.startswith("fenolite_library."):
        return ""
    candidates = [missing]
    for frame in reversed(traceback.extract_tb(error.__traceback__)):
        file = Path(frame.filename)
        if not file.is_file() or not file.resolve().is_relative_to(script.parent):
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)) or not (
                node.lineno <= (frame.lineno or 0) <= (node.end_lineno or node.lineno)
            ):
                continue
            if isinstance(node, ast.Import):
                candidates += [alias.name for alias in node.names]
            elif node.module:
                candidates.append(node.module)
                candidates += [node.module + "." + alias.name for alias in node.names]
    for module in candidates:
        parts = module.split(".")
        if (
            len(parts) >= 4
            and parts[:2] == ["fenolite_library", "blocks"]
            and (module == missing or module.startswith(missing + "."))
        ):
            namespace, name = parts[2:4]
            if namespace.isidentifier() and name.isidentifier():
                return f"fenolite get block {namespace}:{name} --dry-run"
    return ""


def _run_script(
    path: Path,
    what: str,
    devices: ProjectDevices | None = None,
    *,
    source_files: list[Path] | None = None,
    block_issues: list[Issue] | None = None,
    block_records: dict[int, BlockRecord] | None = None,
) -> tuple[dict[str, object], str]:
    """The namespace of the script at ``path`` and its captured stdout and stderr; ``what`` names the
    script in errors. ``devices`` are installed for the run (``fenolite.dsl.devices.installed``)."""
    script = Path(path).resolve()
    if not script.is_file():
        raise DesignScriptError(f"{what} script {path} does not exist", file=os.fspath(path))
    folder = script.parent
    saved_path, saved_argv, saved_bytecode = list(sys.path), list(sys.argv), sys.dont_write_bytecode
    # a module already loaded under the name of a file beside the script (``copper`` of an imported board,
    # change c0275) would shadow that file: it is set aside for the run and put back after it
    siblings = {p.stem for p in folder.glob("*.py")} | {
        p.name for p in folder.iterdir() if p.is_dir() and (p / "__init__.py").is_file()
    }
    shadowed = {
        name: module
        for name, module in list(sys.modules.items())
        if name == "fenolite_library"
        or name.startswith("fenolite_library.")
        or (name.partition(".")[0] in siblings and not _inside(getattr(module, "__file__", None), folder))
    }
    for name in shadowed:
        del sys.modules[name]
    before = set(sys.modules)
    output = io.StringIO()
    sys.dont_write_bytecode = True
    sys.argv = [os.fspath(script)]
    sys.path.insert(0, os.fspath(folder))
    try:
        with (
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
            installed(devices or ProjectDevices()),
        ):
            namespace = runpy.run_path(os.fspath(script), run_name=RUN_NAME)
            design = namespace.get("design")
            if block_issues is not None and isinstance(design, Design):
                block_issues.extend(check_used(design, folder, records=block_records))
    except KeyboardInterrupt:
        raise
    except BaseException as error:  # SystemExit and DslError included: the script failed
        failure = DesignScriptError(
            f"{what} script failed: {type(error).__name__}: {error}",
            file=os.fspath(path),
            locator=_locator(error, script),
        )
        if isinstance(error, ModuleNotFoundError):
            failure.hint = _missing_block_hint(error, script)
        raise failure from error
    finally:
        sys.path[:] = saved_path
        sys.argv = saved_argv
        sys.dont_write_bytecode = saved_bytecode
        for name in set(sys.modules) - before:
            module = sys.modules.get(name)
            file = getattr(module, "__file__", None)
            local = module is not None and _inside(file, folder)
            if local and source_files is not None and isinstance(file, str) and file.endswith(".py"):
                source_files.append(Path(file).resolve())
            if local or name == "fenolite_library" or name.startswith("fenolite_library."):
                del sys.modules[name]
        sys.modules.update(shadowed)
    return namespace, _capped(output.getvalue())


def run_design_script(path: Path, *, describe_blocks: bool = False) -> ScriptRun:
    """The module-level ``design`` of the script at ``path`` and its captured stdout and stderr. The project
    devices of ``devices/*.toml`` beside the script are read first and installed while it runs."""
    script = Path(path).resolve()
    tree, files, issues = read_project_library(script.parent) if script.is_file() else (LibraryTree(), (), ())
    vendored = load_vendored(script.parent) if script.is_file() else VendoredTree()
    tree, vendored_issues = overlay(tree, vendored)
    issues += vendored_issues
    files += tuple(
        DeviceFile(path.relative_to(script.parent).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in vendored.files
    )
    native = read_native_definitions(tree, script.parent)
    known_files = {file.path for file in files}
    files += tuple(
        DeviceFile(path.relative_to(script.parent).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in native.files
        if path.relative_to(script.parent).as_posix() not in known_files
    )
    files = tuple(sorted(files, key=lambda file: file.path))
    issues += native.issues
    devices = _project(tree, vendored)
    sources = [script]
    block_issues: list[Issue] = []
    records: dict[int, BlockRecord] | None = {} if describe_blocks else None
    with recording(script.parent) as recorder:
        namespace, output = _run_script(
            path, "design", devices, source_files=sources, block_issues=block_issues, block_records=records
        )
    design = namespace.get("design")
    if not isinstance(design, Design):
        found = "nothing" if design is None else type(design).__name__
        raise DesignScriptError(
            f"design script binds no module-level 'design' of type fenolite.dsl.Design (found {found})",
            file=os.fspath(path),
        )
    for record_id in sorted(design.device_records):
        if ("device", record_id) in vendored.items:
            issues += (
                Issue(
                    "library.overrides-item",
                    "info",
                    f"design-authored device {record_id} overrides its vendored item",
                    where=record_id,
                ),
            )
    return ScriptRun(
        design=design,
        output=output,
        devices=devices,
        device_files=files,
        device_issues=issues,
        library=tree,
        unattached=recorder.unattached(design),
        block_issues=tuple(block_issues),
        source_files=tuple(sorted(set(sources))),
        block_records=records or {},
        imported=native,
        vendored=vendored,
    )


@dataclass(frozen=True)
class PanelRun:
    panel: Panel
    output: str


def run_panel_script(path: Path) -> PanelRun:
    """The module-level ``panel`` of the panel script at ``path`` and its captured output (change c0173)."""
    namespace, output = _run_script(path, "panel")
    panel = namespace.get("panel")
    if not isinstance(panel, Panel):
        found = "nothing" if panel is None else type(panel).__name__
        raise DesignScriptError(
            f"panel script binds no module-level 'panel' of type fenolite.dsl.Panel (found {found})",
            file=os.fspath(path),
        )
    return PanelRun(panel, output)


__all__ = [
    "DEVICES_DIR",
    "SCRIPT_OUTPUT_LIMIT",
    "DesignScriptError",
    "DeviceFile",
    "PanelRun",
    "ScriptRun",
    "read_project_devices",
    "read_project_library",
    "run_design_script",
    "run_panel_script",
]
