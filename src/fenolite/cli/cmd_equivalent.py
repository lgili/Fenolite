# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite equivalent A [B]``: whether two designs are equivalent, level by level, with every
difference located at ``REF`` or ``REF-PIN``, and at the net for routing (capability design-equivalence,
"Equivalent command", "Level 5 in the equivalent command" and "Triangle oracle";
``docs/cli-contract.md``, "equivalent"; ``docs/equivalence.md``).

With two paths it reads both through the backend registry and runs no tool. With ``--against
kicad-import`` side ``b`` is the board that ``kicad-cli pcb import`` converts ``A`` to, compared under
the importer's exclusion profile of the running version line. It writes no file.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, KicadCliVersionError, cli_for, find_kicad_cli
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.equivalence import (
    LEVEL_NAMES,
    LEVELS,
    EquivalenceReport,
    Profile,
    Tolerances,
    compare_designs,
    difference_issues,
    load_profiles,
    max_level,
    select_profile,
)
from fenolite.checks.equivalence import codes as equivalence_codes
from fenolite.checks.equivalence.model import FRAMES, Difference
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, NO_TOOL_HINT
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

HELP = "say whether two designs are equivalent, level by level, and locate each difference"
BUILT_FILES = ("meta.json", "build.json")
"""A folder that holds one of these directly is a built design (a ``.fenolite/`` folder)."""
BUILT_BACKEND = "fenolite"
BUILT_EVIDENCE = Evidence(Level.INFERRED)
AGAINST = ("kicad-import",)
PCB_DOCUMENT = ".pcbdoc"
IMPORT_MAJOR = 10
READS = (
    "a KiCad board, project file or folder, an Altium document or project, or a .fenolite/ folder of a "
    "built design"
)


@dataclass(frozen=True, slots=True)
class _Side:
    name: str
    sha256: str | None
    backend: str
    design: Design
    issues: tuple[Issue, ...]
    evidence: Evidence
    kind: str
    tool_version: str | None = None
    messages: tuple[str, ...] = ()


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'equivalent'."
    parser.add_argument("a", metavar="A", help=READS)
    parser.add_argument("b", metavar="B", nargs="?", help="the design to compare with A")
    parser.add_argument(
        "--level", type=int, metavar="N", help="run the levels 1 to N (default: the highest available)"
    )
    parser.add_argument("--tolerance-nm", type=int, metavar="N", help="length tolerance per coordinate")
    parser.add_argument("--tolerance-udeg", type=int, metavar="N", help="angle tolerance in microdegrees")
    parser.add_argument(
        "--tolerance-ppm",
        type=int,
        metavar="N",
        help="tolerance of a routed length of level 5, in parts per million of the length",
    )
    parser.add_argument("--frame", choices=FRAMES, help="relative removes one translation (default absolute)")
    parser.add_argument(
        "--ignore-ref", action="append", default=[], metavar="GLOB", help="leave out matching references"
    )
    parser.add_argument("--exclusions", metavar="FILE", help="an exclusion file (TOML); needs --profile")
    parser.add_argument("--profile", metavar="NAME", help="the profile of --exclusions to apply")
    parser.add_argument(
        "--against", choices=AGAINST, help="compare A with kicad-cli's own import of it (needs kicad-cli 10)"
    )
    parser.add_argument("--kicad-cli", metavar="PATH", help="the kicad-cli of --against")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS")


def _usage(message: str, *, where: str = "", hint: str | None = None) -> CliError:
    return CliError("FEN-2001", message, where=where, hint=hint)


def _path(given: str, ctx: Context) -> Path:
    path = Path(given)
    path = path if path.is_absolute() else ctx.cwd / path
    if not path.exists():
        raise CliError("FEN-3001", f"{path.name} does not exist", where=path.name)
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _notices(issues: list[Issue] | tuple[Issue, ...]) -> tuple[Issue, ...]:
    """The warnings and infos of a read; a reader raises its errors."""
    return tuple(issue for issue in issues if issue.severity != "error")


def _side(path: Path) -> _Side:
    """One side: a built design, a KiCad project resolved to its board, or any file a backend reads."""
    if path.is_dir() and any((path / name).is_file() for name in BUILT_FILES):
        return _Side(path.name, None, BUILT_BACKEND, load_dir(path), (), BUILT_EVIDENCE, "fenolite_model")
    if path.is_dir() or path.suffix == ".kicad_pro":
        path = resolve_board(path)
    backend = registry.for_path(path)
    if backend is None:
        raise _usage(f"equivalent does not read {path.name}", where=path.name, hint="it reads " + READS)
    found: list[Issue] = []
    read = backend.read(path, issues=found)
    if not isinstance(read.content, Design):
        raise _usage(
            f"{path.name} is a library, not a design", where=path.name, hint="compare libraries with diff"
        )
    kind = path.suffix.lower().lstrip(".")
    return _Side(path.name, _digest(path), backend.name, read.content, _notices(found), read.evidence, kind)


def _preflight(explicit: str | None, timeout: float) -> KicadCli:
    """The ``kicad-cli`` that converts side ``a``: ``FEN-6001`` without one, ``FEN-6002`` for another
    major than 10. No import runs before both hold."""
    path = find_kicad_cli(explicit)
    if path is None:
        raise CliError("FEN-6001", "kicad-cli not found", hint=NO_TOOL_HINT)
    cli = cli_for(path, timeout=timeout)
    try:
        major = cli.major()
    except (KicadCliError, ValueError, OSError) as exc:
        raise CliError(
            "FEN-6001", f"{path.name} did not report a kicad-cli version", hint=NO_TOOL_HINT
        ) from exc
    if major != IMPORT_MAJOR:
        raise CliError(
            "FEN-6002",
            f"--against kicad-import needs kicad-cli 10.0 (pcb import); running {cli.version()}",
            hint="use kicad-cli 10.0, for example the kicad-10 job's container",
        )
    return cli


def _imported(cli: KicadCli, source: Path, name: str) -> _Side | Issue:
    """Side ``b`` of the triangle, or the ``equiv.oracle-failed`` issue of a run that gives no board."""
    try:
        found = altium_import.import_design(cli, source)
    except KicadCliVersionError:
        raise
    except FenoliteError as error:
        return equivalence_codes.issue("equiv.oracle-failed", str(error), where=name)
    read = found.read
    return _Side(
        name, None, altium_import.PROFILE, read.design, _notices(read.issues), read.evidence, "kicad_pcb",
        found.tool_version, found.messages,
    )  # fmt: skip


def _import_messages(messages: tuple[str, ...]) -> list[Issue]:
    counts = Counter(messages)
    return [
        equivalence_codes.issue("equiv.import-message", f"kicad-cli pcb import, {count} time(s): {text}")
        for text, count in sorted(counts.items())
    ]


def _user_profile(args: argparse.Namespace, ctx: Context) -> Profile | None:
    if (args.exclusions is None) != (args.profile is None):
        raise _usage("--exclusions and --profile go together", where="--exclusions")
    if args.exclusions is None:
        return None
    path = _path(args.exclusions, ctx)
    profiles = load_profiles(path.read_text(encoding="utf-8"), file=path.name)
    chosen = next((profile for profile in profiles if profile.name == args.profile), None)
    if chosen is None:
        known = ", ".join(dict.fromkeys(profile.name for profile in profiles)) or "none"
        raise _usage(
            f"{path.name} holds no profile {args.profile!r}", where="--profile", hint=f"profiles: {known}"
        )
    return chosen


def _tolerances(args: argparse.Namespace, profile: Profile | None) -> Tolerances:
    for flag, value in (
        ("--tolerance-nm", args.tolerance_nm),
        ("--tolerance-udeg", args.tolerance_udeg),
        ("--tolerance-ppm", args.tolerance_ppm),
    ):
        if value is not None and value < 0:
            raise _usage(f"{flag} is a non-negative integer", where=flag)
    length = args.tolerance_nm if args.tolerance_nm is not None else (profile.tolerance_nm if profile else 0)
    angle = args.tolerance_udeg
    if angle is None:
        angle = profile.tolerance_udeg if profile else 0
    relative = args.tolerance_ppm
    if relative is None:
        relative = profile.tolerance_ppm if profile else 0
    return Tolerances(length, angle, relative)


def _level(args: argparse.Namespace, a: _Side, b: _Side) -> int:
    highest = max_level(a.design, b.design)
    if args.level is None:
        return highest
    if args.level not in LEVELS:
        raise _usage(f"--level is one of {', '.join(map(str, LEVELS))}", where="--level")
    return int(args.level)


def _row(difference: Difference) -> dict[str, Any]:
    return {
        "level": difference.level,
        "kind": difference.kind,
        "where": difference.where,
        "field": difference.field,
        "a": difference.a,
        "b": difference.b,
    }


def _side_json(side: _Side) -> dict[str, Any]:
    board = side.design.board
    footprints = len(board.footprints) if board is not None else 0
    row: dict[str, Any] = {
        "path": side.name,
        "sha256": side.sha256,
        "backend": side.backend,
        "netlist_source": "board" if footprints else "circuit",
        "components": len(side.design.circuit.components),
        "footprints": footprints,
    }
    if side.tool_version is not None:
        row["tool_version"] = side.tool_version
    return row


def _result(a: _Side, b: _Side, report: EquivalenceReport, profile: Profile | None) -> dict[str, Any]:
    return {
        "level": report.levels[-1].level,
        "equivalent": report.equivalent,
        "sides": {"a": _side_json(a), "b": _side_json(b)},
        "tolerances": {
            "length_nm": report.tolerances.length_nm,
            "angle_udeg": report.tolerances.angle_udeg,
            "length_ppm": report.tolerances.length_ppm,
        },
        "frame": report.frame,
        "translation": [report.translation.x, report.translation.y],
        "levels": [
            {
                "level": level.level,
                "name": LEVEL_NAMES[level.level],
                "compared": level.compared,
                "differences": len(level.differences),
                "excluded": len(level.excluded),
                "notices": len(level.notices),
                "summary": dict(level.summary),
            }
            for level in report.levels
        ],
        "differences": [_row(difference) for difference in report.differences],
        "notices": [_row(notice) for notice in report.notices],
        "excluded": [{**_row(found.difference), "rule": found.rule_id} for found in report.excluded],
        "profile": None
        if profile is None
        else {"name": profile.name, "tool_version": profile.tool_version, "rules": len(profile.rules)},
    }


def _failed(a: _Side, failure: Issue, version: str) -> Result:
    """The result of a triangle whose converter gave no board: no level ran."""
    side = _side_json(a)
    result: dict[str, Any] = {
        "level": 0,
        "equivalent": False,
        "sides": {"a": side, "b": None},
        "tolerances": {"length_nm": 0, "angle_udeg": 0, "length_ppm": 0},
        "frame": "relative",
        "translation": [0, 0],
        "levels": [],
        "differences": [],
        "notices": [],
        "excluded": [],
        "profile": None,
        "tool_version": version,
    }
    evidence = Evidence(a.evidence.level, altium_import.ORACLE, a.evidence.hypotheses)
    return Result(
        result=result,
        issues=(failure, *a.issues),
        evidence=evidence,
        input=InputRef(path=a.name, sha256=a.sha256, kind=a.kind, format_version=None),
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if (args.b is None) == (args.against is None):
        raise _usage(
            "give B or --against kicad-import, not both and not neither",
            where="B",
            hint="equivalent A B, or equivalent A.PcbDoc --against kicad-import",
        )
    notices: list[Issue] = []
    path_a = _path(args.a, ctx)
    if args.against is None:
        profile = _user_profile(args, ctx)
        a, b = _side(path_a), _side(_path(args.b, ctx))
        frame = args.frame or (profile.frame if profile else "absolute")
    else:
        if args.exclusions is not None or args.profile is not None:
            raise _usage(
                "--against kicad-import uses the importer's own profile; --exclusions does not apply",
                where="--exclusions",
            )
        if not path_a.is_file() or path_a.suffix.lower() != PCB_DOCUMENT:
            raise _usage(
                f"--against kicad-import compares an Altium PCB document, and {path_a.name} is none",
                where=path_a.name,
                hint="pass a .PcbDoc file",
            )
        cli = _preflight(args.kicad_cli, args.timeout)
        a = _side(path_a)
        found = _imported(cli, path_a, a.name)
        if isinstance(found, Issue):
            return _failed(a, found, cli.version())
        b = found
        version = cli.version()
        profiles = load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE)
        profile = select_profile(profiles, altium_import.PROFILE, version)
        if profile is None:
            notices.append(
                equivalence_codes.issue(
                    "equiv.no-exclusion-profile",
                    f"no exclusion profile for kicad-cli {version}: the comparison ran with no rule, in the "
                    "relative frame and without tolerance",
                )
            )
        frame = args.frame or (profile.frame if profile else "relative")
    tolerances = _tolerances(args, profile)
    level = _level(args, a, b)
    try:
        report = compare_designs(
            a.design,
            b.design,
            level=level,
            tolerances=tolerances,
            frame=frame,
            ignore_refs=tuple(args.ignore_ref),
            rules=profile.rules if profile else (),
        )
    except ValueError as error:
        raise _usage(str(error), where="--level") from None
    notices += _import_messages(b.messages)
    evidence = Evidence.combine(a.evidence, b.evidence)
    if args.against is not None:
        evidence = Evidence(evidence.level, altium_import.ORACLE, evidence.hypotheses)
    return Result(
        result=_result(a, b, report, profile),
        issues=(*difference_issues(report), *notices, *a.issues, *b.issues),
        evidence=evidence,
        input=InputRef(path=a.name, sha256=a.sha256, kind=a.kind, format_version=None),
    )


COMMAND = Command(
    name="equivalent",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, EXAMPLE_BOARD, "--level", "4"),
)

__all__ = ["COMMAND"]
