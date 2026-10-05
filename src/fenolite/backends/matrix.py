# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix and the rule that every backend module declares its evidence (capability
backend-protocol, "Evidence matrix rows" and "Backend modules declare their evidence"; change c0067).

A module under ``fenolite/backends/<name>/`` declares its evidence in exactly one of three forms:

1. **constants**: it owns a claim, so it assigns one or more module-level ``Evidence`` values, as in
   ``EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))``. Every id is a row of
   ``docs/hypotheses.md``, and the level is never above a row it names (lowest wins);
2. **``# evidence: see <module>[, <module>…]``**: it makes no claim of its own, because its code runs only
   inside the operations of the named modules of the same package, each of which holds constants;
3. **``# evidence: none, <reason>``**: it states nothing about a file format or a tool.

A marker is a comment that starts in column 0. Each package places its constants in the cells of the
matrix in its ``claims`` module, which states no level of its own. ``problems()`` lists what breaks these
rules; ``tests/unit/backends/test_evidence_declared.py`` fails while it lists anything.

Importing this module imports no backend package: ``rows``, ``module_claims`` and ``problems`` do.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import io
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fenolite.backends.base import MatrixRow
from fenolite.core.evidence import Evidence, Level

ROOT_PACKAGE = "fenolite.backends"
CLAIMS = "claims"
MARKER = "# evidence:"
PAGE = "docs/evidence/matrix.md"
REGENERATE = "uv run python tools/gen_evidence_matrix.py"
HELP = f"""\
How to fix it. Every module of a backend package declares its evidence in exactly one of three forms:

  1. The module owns a claim about a file format or a tool (it reads, writes or runs something and its
     result carries an evidence). Assign a module-level constant:
         EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-…",))
     Every id must be a row of docs/hypotheses.md that is not refuted, and the level must not be above
     any row it names (lowest wins). INFERRED needs at least one id. A new reader or writer of a file
     kind also gets a cell in the package's claims.py; a level of UNVERIFIED is allowed there only when
     the operation is listed in the row's `experimental`.
  2. The module is a helper whose code runs only inside other modules of the same package. Add one
     comment line in column 0, with names relative to the package:
         # evidence: see pcb, mod
  3. The module states nothing about a file format or a tool (error classes, issue-code tables, a
     facade). Add one comment line in column 0, with the reason:
         # evidence: none, error classes only

Use one form only. Then regenerate the page that lists every declaration and commit it:
    {REGENERATE}
The rules: openspec/specs/backend-protocol/spec.md, "Backend modules declare their evidence" and
"Evidence matrix rows"; the levels: docs/evidence/README.md."""
"""What a failing guard prints after its problems: the three forms, for a reader who never saw the rule."""


@dataclass(frozen=True, slots=True)
class ModuleClaim:
    """The declaration of one module: ``constants`` as ``(name, Evidence)`` sorted by name, or the modules
    its ``see`` marker names, or the reason of its ``none`` marker (``""`` when there is none).

    ``module`` is the dotted name below the package (``pcb``, ``read.pcb``); the ``__init__`` of a
    sub-package that assigns constants is listed under the sub-package's name (``read.sch``)."""

    package: str
    module: str
    constants: tuple[tuple[str, Evidence], ...] = ()
    see: tuple[str, ...] = ()
    none: str = ""


@dataclass(frozen=True, slots=True)
class _Scan:
    claim: ModuleClaim
    markers: tuple[str, ...]
    """The text of each marker comment, after ``# evidence:``."""
    required: bool
    """False for an ``__init__``, which may hold constants but need not declare."""


def packages() -> tuple[str, ...]:
    """The dotted names of the sub-packages of ``fenolite.backends``, sorted. No backend is imported."""
    spec = importlib.util.find_spec(ROOT_PACKAGE)
    found: set[str] = set()
    for location in (spec.submodule_search_locations or ()) if spec else ():
        for child in Path(location).iterdir():
            if child.is_dir() and (child / "__init__.py").is_file():
                found.add(f"{ROOT_PACKAGE}.{child.name}")
    return tuple(sorted(found))


_all_packages = packages
"""``packages`` under a name that the parameter of ``problems`` does not shadow."""


def _folder(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    locations = list(spec.submodule_search_locations or ()) if spec else []
    if not locations:
        raise ValueError(f"{package!r} is not a package")
    return Path(locations[0])


def _assigned(tree: ast.Module) -> set[str]:
    """The names a module assigns at its top level (an imported name is not assigned there)."""
    names: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        names.update(t.id for t in targets if isinstance(t, ast.Name))
    return names


def _markers(source: str) -> tuple[str, ...]:
    """The marker comments of a source text: comments in column 0, so text in a string is none."""
    found: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and token.start[1] == 0 and token.string.startswith(MARKER):
            found.append(token.string[len(MARKER) :].strip())
    return tuple(found)


def _parse_marker(text: str) -> tuple[tuple[str, ...], str] | None:
    """``(see, none)`` of a marker's text, or ``None`` when it is neither form."""
    word, _, rest = text.partition(" ")
    if word == "see":
        names = tuple(name.strip() for name in rest.split(","))
        return (names, "") if all(names) else None
    if word in ("none,", "none"):
        return ((), rest.strip() if word == "none," else "")
    return None


def _scan(package: str) -> tuple[_Scan, ...]:
    folder = _folder(package)
    scans: list[_Scan] = []
    for path in sorted(folder.rglob("*.py")):
        parts = path.relative_to(folder).with_suffix("").parts
        if parts == (CLAIMS,):
            continue
        is_init = parts[-1] == "__init__"
        if is_init:
            parts = parts[:-1]
        module = ".".join(parts)
        source = path.read_text(encoding="utf-8")
        assigned = _assigned(ast.parse(source))
        loaded = importlib.import_module(f"{package}.{module}" if module else package)
        constants = tuple(
            sorted(
                (
                    (name, value)
                    for name in assigned
                    if isinstance(value := getattr(loaded, name, None), Evidence)
                ),
                key=lambda item: item[0],
            )
        )
        markers = _markers(source)
        if is_init and not constants and not markers:
            continue
        parsed = _parse_marker(markers[0]) if len(markers) == 1 else None
        see, none = parsed if parsed else ((), "")
        claim = ModuleClaim(package, module or "__init__", constants, see, none)
        scans.append(_Scan(claim, markers, required=not is_init))
    return tuple(sorted(scans, key=lambda scan: scan.claim.module))


def module_claims(package: str) -> tuple[ModuleClaim, ...]:
    """One ``ModuleClaim`` per module of the package with that dotted name, sorted by module: every ``.py``
    file at any depth but ``claims.py`` and the ``__init__`` files that declare nothing. Constants are read
    by importing the module, markers by tokenising its source."""
    return tuple(scan.claim for scan in _scan(package))


def _load_rows(package: str) -> tuple[MatrixRow, ...] | None:
    """``MATRIX`` of the package's ``claims`` module, or ``None`` when it has none."""
    if importlib.util.find_spec(f"{package}.{CLAIMS}") is None:
        return None
    found: object = getattr(importlib.import_module(f"{package}.{CLAIMS}"), "MATRIX", None)
    if not isinstance(found, tuple):
        return None
    listed = tuple(row for row in cast("tuple[object, ...]", found) if isinstance(row, MatrixRow))
    return listed if len(listed) == len(cast("tuple[object, ...]", found)) else None


def rows() -> tuple[MatrixRow, ...]:
    """The rows of every backend package, sorted by ``(backend, kind)``. Runs no tool and reads no file
    but the modules it imports."""
    found = [row for package in packages() for row in _load_rows(package) or ()]
    return tuple(sorted(found, key=lambda row: (row.backend, row.kind)))


def _declaration_problems(package: str) -> list[str]:
    problems: list[str] = []
    scans = _scan(package)
    with_constants = {scan.claim.module for scan in scans if scan.claim.constants}
    known = {scan.claim.module for scan in scans}
    for scan in scans:
        claim = scan.claim
        name = f"{package}.{claim.module}"
        for constant, evidence in claim.constants:
            if evidence.level is Level.INFERRED and not evidence.hypotheses:
                problems.append(
                    f"{name}: {constant} is INFERRED and names no hypothesis; name the rows of "
                    "docs/hypotheses.md it is inferred from"
                )
        if len(scan.markers) > 1:
            problems.append(f"{name}: carries {len(scan.markers)} '{MARKER}' markers; keep one")
            continue
        if claim.constants and scan.markers:
            listed = ", ".join(constant for constant, _ in claim.constants)
            problems.append(
                f"{name}: declares the constant {listed} and the marker '{MARKER} {scan.markers[0]}'; "
                "a module with constants carries no marker, so remove one of the two"
            )
            continue
        if claim.constants:
            continue
        if not scan.markers:
            if scan.required:
                problems.append(
                    f"{name}: declares no evidence; add exactly one of: a constant "
                    "'EVIDENCE = Evidence(Level.…, hypotheses=(\"H-…\",))' when the module owns a claim, the "
                    f"comment '{MARKER} see <module>' when its code runs only inside other modules of "
                    f"{package}, or the comment '{MARKER} none, <reason>' when it states nothing about a "
                    "file format or a tool"
                )
            continue
        text = scan.markers[0]
        if _parse_marker(text) is None:
            problems.append(
                f"{name}: the marker '{MARKER} {text}' is neither '{MARKER} see <module>[, <module>]' "
                f"nor '{MARKER} none, <reason>'"
            )
            continue
        if not claim.see and not claim.none:
            problems.append(
                f"{name}: the marker '{MARKER} {text}' gives no reason; write '{MARKER} none, <reason>'"
            )
        for target in claim.see:
            if target not in known:
                problems.append(
                    f"{name}: the marker names '{target}', which is not a module of {package} "
                    "(write the name below the package, as in 'pcb' or 'read.pcb')"
                )
            elif target not in with_constants:
                problems.append(
                    f"{name}: the marker names '{target}', which declares no constant; name the module "
                    "that owns the claim"
                )
    return problems


def _literal_problems(package: str) -> list[str]:
    """``claims.py`` states no level: it never names ``Level`` and calls ``Evidence`` only as
    ``Evidence.combine``."""
    path = _folder(package) / f"{CLAIMS}.py"
    where = f"{package.rsplit('.', 1)[-1]}.{CLAIMS}"
    problems: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        named = (
            node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""
        )
        if isinstance(node, ast.alias):
            named = node.name.rsplit(".", 1)[-1]
        if named in ("Level", "min_level"):
            problems.add(
                f"{where}: names {named}; a cell is an evidence constant of a module of the package, or "
                "Evidence.combine of such constants, so the level changes in the module that owns the claim"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Evidence":
            problems.add(
                f"{where}: calls Evidence(...); a cell is an evidence constant of a module of the package, "
                "or Evidence.combine of such constants"
            )
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Evidence"
            and node.attr != "combine"
        ):
            problems.add(f"{where}: uses Evidence.{node.attr}; only Evidence.combine is allowed")
    return sorted(problems)


def _row_problems(package: str) -> list[str]:
    short = package.rsplit(".", 1)[-1]
    if importlib.util.find_spec(f"{package}.{CLAIMS}") is None:
        return [
            f"{package}: has no '{CLAIMS}' module; add {CLAIMS}.py with 'MATRIX: tuple[MatrixRow, ...]', one "
            "row per file kind the package reads or writes"
        ]
    problems = _literal_problems(package)
    matrix = _load_rows(package)
    if matrix is None:
        return [*problems, f"{short}.{CLAIMS}: MATRIX is not a tuple of MatrixRow"]
    kinds: set[str] = set()
    for row in matrix:
        where = f"{short}.{CLAIMS}: row {row.kind}"
        if row.backend != short:
            problems.append(f"{where}: its backend is {row.backend!r}, not the package name {short!r}")
        if row.kind in kinds:
            problems.append(f"{where}: the kind is listed twice")
        kinds.add(row.kind)
        for operation, cell in row.cells():
            if cell.level is Level.INFERRED and not cell.hypotheses:
                problems.append(f"{where}: {operation} is INFERRED and names no hypothesis")
            if cell.level is Level.UNVERIFIED and operation not in row.experimental:
                problems.append(
                    f"{where}: {operation} is UNVERIFIED, which is allowed only for an experimental "
                    f"operation; list '{operation}' in the row's experimental, or give the constant a row "
                    "of docs/hypotheses.md and a level it supports"
                )
    return problems


def _report_problems(checked: Iterable[str]) -> list[str]:
    """The agreement between each registered backend's report and the rows of its package."""
    from fenolite.backends import registry

    problems: list[str] = []
    wanted = set(checked)
    for backend in registry.all_backends():
        package = f"{ROOT_PACKAGE}.{backend.name}"
        if package not in wanted:
            continue
        by_kind = {row.kind: row for row in _load_rows(package) or ()}
        report = backend.capabilities()
        for kind in report.read_kinds:
            row = by_kind.get(kind)
            if row is None or row.detect is None or row.read is None:
                problems.append(
                    f"{backend.name}.{CLAIMS}: the backend reads {kind}, so its row needs detect and read"
                )
        stable = sorted(k for k, row in by_kind.items() if row.write and "write" not in row.experimental)
        if stable != sorted(report.write_kinds):
            problems.append(
                f"{backend.name}.{CLAIMS}: the kinds with a write that is not experimental are "
                f"{', '.join(stable) or 'none'}, but the backend's write_kinds are "
                f"{', '.join(sorted(report.write_kinds)) or 'none'}; both must agree"
            )
    return problems


def problems(packages: Iterable[str] | None = None) -> tuple[str, ...]:
    """One message per broken rule of the declarations and of the matrix rows of ``packages`` (dotted
    names; every package of ``packages()`` when ``None``), sorted. Empty when every rule holds."""
    checked = _all_packages() if packages is None else tuple(packages)
    found: list[str] = []
    for package in checked:
        found += _declaration_problems(package)
        found += _row_problems(package)
    found += _report_problems(checked)
    return tuple(sorted(set(found)))


def failure_text(found: Iterable[str]) -> str:
    """The problems, one per line, then ``HELP``: what a failing guard shows."""
    listed = list(found)
    head = f"{len(listed)} problem(s) in the evidence declarations of the backends:"
    return "\n".join([head, *(f"  - {problem}" for problem in listed), "", HELP])


__all__ = [
    "HELP",
    "PAGE",
    "REGENERATE",
    "ModuleClaim",
    "failure_text",
    "module_claims",
    "packages",
    "problems",
    "rows",
]
