# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite verify-source SCRIPT --against ORIGINAL``: the proof that a design script rebuilds an
original project (capability fidelity-proof; change c0278; ``docs/fidelity.md``).

The command builds ``SCRIPT`` as ``fenolite build`` builds it, for the KiCad major of the original or
``--target``, into a fresh temporary folder (removed on every exit, no temporary path in the reply), reads
the build and the original as ``fenolite equivalent`` reads its sides, and compares them at every level:
1 to 7 with the strict rule of level 5, S (drawn schematics) and 8 (the viewer's pictures). A level that a
side cannot reach is skipped with ``fidelity.level-skipped`` and its reason, never passed silently.

The accepted differences of the ``fidelity`` member of ``PROVENANCE.json`` beside the script (or
``--provenance FILE``) become exclusion rules of the equivalence package (``accepted_rules``); an entry that
matches nothing in a level that ran gives ``fidelity.accepted-unused``. ``--record`` plans one write of the
provenance file with ``fidelity.proof``, through ``--dry-run`` and ``--confirm --plan``; ``--accept KEY
--reason TEXT`` adds accepted entries. No subprocess runs unless ``--upgrade`` asks ``kicad-cli`` to upgrade
a copy of an original older than KiCad 9.0.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import fenolite
from fenolite.api.sides import ReadSide, SideError, read_side
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.equivalence import (
    ALL_LEVEL_NAMES,
    LEVELS,
    PRESENTATION_LEVEL,
    SCHEMATIC_LEVEL,
    EquivalenceReport,
    LevelResult,
    Rule,
    Tolerances,
    accepted_rules,
    compare_designs,
    difference_issues,
    max_level,
)
from fenolite.checks.equivalence.exclusions import apply_rules
from fenolite.checks.equivalence.model import FRAMES, Difference, Frame, LevelId
from fenolite.cli import cmd_build
from fenolite.cli._drawn_level import DRAWN_EVIDENCE, UNREADABLE, root_schematic, schematic_level
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, board_format, supported_tool
from fenolite.cli._presentation import board_scenes, presentation_level, sheet_scenes
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.view.fidelity import DEFAULT_PIXEL_PPM

HELP = (
    "prove that a design script rebuilds an original project, level by level (writes PROVENANCE.json with "
    "--record)"
)
ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "fidelity.build-failed": ("error",),
        "fidelity.accepted-unused": ("warning",),
        "fidelity.level-skipped": ("info",),
        "fidelity.input-upgraded": ("info",),
    }
)
"""The ``fidelity.*`` codes of the command; the differences carry the ``equiv.*`` codes."""
READ_ONLY_MAJOR = 8
"""A KiCad major whose boards Fenolite reads but builds no script for: an original of it is upgraded first."""
PRESENTATION_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-FID-PLOT-AGREE",))
"""Level 8 draws both sides with one renderer: no oracle confirms the pictures yet."""
PROVENANCE = "PROVENANCE.json"
PROVENANCE_SCHEMA = "fenolite.provenance.v0"
DEFAULT_PITCH_UM = 50
ALL_LEVELS: tuple[LevelId, ...] = (*LEVELS, SCHEMATIC_LEVEL, PRESENTATION_LEVEL)
"""The levels in the order they run: 1 to 7, then S, then 8."""
KICAD_FILES = (".kicad_pcb", ".kicad_sch", ".kicad_pro", ".kicad_dru")
ALTIUM_PROJECT = ".prjpcb"
ALTIUM_DOCUMENTS = (".pcbdoc", ".schdoc")
LEFT_OUT_DIRS = ("lib", ".fenolite")
TOLERANCE_KEYS = ("length_nm", "angle_udeg", "length_ppm", "pixel_ppm")
STATUSES = ("equal", "accepted", "differs", "skipped")
OPTIONS = {"level": "--levels", "strict": "--levels", "b": "--against"}
UPGRADE_HINT = (
    "pass --upgrade to upgrade a copy with 'kicad-cli pcb upgrade' (KiCad 10), or re-save it in KiCad 9 or "
    "newer"
)
_PROVENANCE_EXAMPLE = Path(fenolite.__file__).resolve().parents[2] / "tests" / "data" / "fidelity"
EXAMPLE_SCRIPT = str(_PROVENANCE_EXAMPLE / "sensor_code" / "design.py")
EXAMPLE_ORIGINAL = str(_PROVENANCE_EXAMPLE / "sensor")


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/fidelity.md."
    parser.add_argument(
        "script", metavar="SCRIPT", help="the design script (executed in-process, as build does)"
    )
    parser.add_argument(
        "--against", required=True, metavar="ORIGINAL", help="the original: a KiCad project folder or "
        ".kicad_pro, or an Altium .PrjPcb"
    )  # fmt: skip
    parser.add_argument("--levels", metavar="SPEC", help="the levels to run, e.g. 1-7,S,8 (default: all)")
    parser.add_argument("--tolerance-nm", type=int, metavar="N", help="length tolerance per coordinate")
    parser.add_argument("--tolerance-udeg", type=int, metavar="N", help="angle tolerance in microdegrees")
    parser.add_argument("--tolerance-ppm", type=int, metavar="N", help="tolerance of a routed length (ppm)")
    parser.add_argument("--frame", choices=FRAMES, help="relative removes one translation (default absolute)")
    parser.add_argument("--pixel-ppm", type=int, metavar="N", help="level 8 pixel tolerance (default 1000)")
    parser.add_argument(
        "--render-pitch-um", type=int, metavar="N", help=f"level 8 pixel pitch (default {DEFAULT_PITCH_UM})"
    )
    parser.add_argument(
        "--provenance", metavar="FILE", help=f"the provenance file (default: {PROVENANCE} beside SCRIPT)"
    )
    parser.add_argument("--record", action="store_true", help="write fidelity.proof to the provenance file")
    parser.add_argument(
        "--accept", action="append", default=[], metavar="KEY",
        help="accept the difference <level>:<kind>:<where>",
    )  # fmt: skip
    parser.add_argument("--reason", action="append", default=[], metavar="TEXT", help="why --accept accepts")
    parser.add_argument(
        "--target", type=int, choices=versions.TARGET_MAJORS, help="the KiCad major to build for"
    )
    parser.add_argument(
        "--upgrade", action="store_true", help="upgrade a copy of an older original (kicad-cli)"
    )
    parser.add_argument("--kicad-cli", metavar="PATH", help="the kicad-cli of --upgrade")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS")


def _usage(message: str, *, where: str = "", hint: str | None = None) -> CliError:
    return CliError("FEN-2001", message, where=where, hint=hint)


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of ``ISSUE_CODES``, with its only severity."""
    return Issue(code, ISSUE_CODES[code][0], message, where=where, hint=hint)


def _path(given: str, ctx: Context) -> Path:
    path = Path(given)
    path = path if path.is_absolute() else ctx.cwd / path
    if not path.exists():
        raise CliError("FEN-3001", f"{path.name} does not exist", where=path.name)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shown(path: Path, cwd: Path) -> str:
    """A path as the reply and a planned write name it: relative to the working folder when inside it."""
    return depends_on(cwd, path)[0]


# --- inputs ----------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Original:
    """The original as given: its folder (a KiCad project) or file (an Altium project), its backend, and
    the files read, by path relative to its folder."""

    path: Path
    root: Path
    backend: str
    files: tuple[Path, ...]


def _kicad_files(root: Path) -> tuple[Path, ...]:
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).parts
        if not path.is_file() or path.suffix not in KICAD_FILES:
            continue
        if rel[0] in LEFT_OUT_DIRS or any(part.startswith(".") or part.endswith("-backups") for part in rel):
            continue
        found.append(path)
    return tuple(found)


def _original(path: Path) -> Original:
    if path.is_file() and path.suffix.lower() == ALTIUM_PROJECT:
        files = [path, *(p for p in sorted(path.parent.iterdir()) if p.suffix.lower() in ALTIUM_DOCUMENTS)]
        return Original(path, path.parent, "altium", tuple(files))
    if path.is_dir() or path.suffix == ".kicad_pro":
        root = path if path.is_dir() else path.parent
        return Original(path, root, "kicad", _kicad_files(root))
    raise _usage(
        f"{path.name} is not an original verify-source reads",
        where="--against",
        hint="pass a KiCad project folder or .kicad_pro, or an Altium .PrjPcb",
    )


def _board_major(board: Path) -> int | None:
    version = board_format(board)
    return None if version is None else versions.major_for(versions.FileKind.BOARD, version)


def _upgraded(
    original: Original, board: Path, work: Path, args: argparse.Namespace
) -> tuple[Original, Issue]:
    """A copy of a KiCad original whose board ``kicad-cli pcb upgrade`` re-saved, and the issue that says
    so with the tool version and both SHA-256."""
    cli = supported_tool(args.kicad_cli, args.timeout)
    copy = work / "original"
    shutil.copytree(original.root, copy)
    target = copy / board.relative_to(original.root)
    data = cli.upgrade_board(target)
    target.write_bytes(data)
    found = issue(
        "fidelity.input-upgraded",
        f"{board.name} was upgraded on a copy by kicad-cli {cli.version()}: "
        f"{_sha256(board)} -> {hashlib.sha256(data).hexdigest()}",
        where=board.name,
    )
    path = copy if original.path.is_dir() else copy / original.path.name
    return Original(path, copy, original.backend, _kicad_files(copy)), found


# --- the build -------------------------------------------------------------------------------------


def _build(script: Path, out: Path, ctx: Context, major: int) -> tuple[Result, int, str]:
    """``fenolite build SCRIPT --out OUT`` for ``major`` without the confirmation step: the build's result,
    the count of files written under ``out`` and, for a build that refused, its error. A write outside the
    temporary folder (a design lock beside the script) is left out."""
    parser = argparse.ArgumentParser(add_help=False)
    cmd_build.COMMAND.register(parser)
    namespace = parser.parse_args([os.fspath(script), "--out", os.fspath(out)])
    try:
        built = cmd_build.COMMAND.run(namespace, dataclasses.replace(ctx, cwd=out.parent, kicad_target=major))
    except FenoliteError as error:
        found: object = getattr(error, "issues", None)
        items = tuple(cast(Sequence[object], found)) if isinstance(found, (list, tuple)) else ()
        listed = tuple(i for i in items if isinstance(i, Issue))
        return Result(issues=listed), 0, str(error)
    except CliError as error:
        return Result(), 0, f"{error.code}: {error.message}"
    if any(i.severity == "error" for i in built.issues):
        return built, 0, ""
    count = 0
    for write in built.writes:
        target = Path(write.path)
        target = target if target.is_absolute() else out.parent / target
        if not target.resolve().is_relative_to(out.parent.resolve()):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(write.source() if write.source is not None else write.data)
        count += 1
    return built, count, ""


# --- the provenance file ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Provenance:
    """The provenance file: where it is, its whole content, the tolerances and accepted entries of its
    ``fidelity`` member, and their rules."""

    path: Path
    data: dict[str, Any]
    tolerances: dict[str, int]
    accepted: list[dict[str, Any]]
    rules: tuple[Rule, ...]


def _provenance(args: argparse.Namespace, script: Path, ctx: Context) -> Provenance:
    if args.provenance is not None:
        path = Path(args.provenance)
        path = path if path.is_absolute() else ctx.cwd / path
        if not path.exists() and not args.record:
            raise CliError("FEN-3001", f"{path.name} does not exist", where="--provenance")
    else:
        path = script.parent / PROVENANCE
    if not path.exists():
        return Provenance(path, {"schema": PROVENANCE_SCHEMA}, {}, [], ())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CliError("FEN-3004", f"{path.name} is not JSON: {error}", where=path.name) from None
    if not isinstance(data, dict):
        raise CliError("FEN-3004", f"{path.name} is not a JSON object", where=path.name)
    root = cast(dict[str, Any], data)
    fidelity = root.get("fidelity", {})
    if not isinstance(fidelity, dict):
        raise CliError("FEN-3004", f"{path.name}: fidelity is an object", where=path.name)
    member = cast(dict[str, Any], fidelity)
    tolerances = member.get("tolerances", {})
    if not isinstance(tolerances, dict):
        raise CliError("FEN-3004", f"{path.name}: fidelity.tolerances is an object", where=path.name)
    given = cast(dict[str, Any], tolerances)
    for key, value in given.items():
        if key not in TOLERANCE_KEYS or type(value) is not int or value < 0:
            raise CliError(
                "FEN-3004",
                f"{path.name}: fidelity.tolerances.{key} is not one of {', '.join(TOLERANCE_KEYS)} as a "
                "non-negative integer",
                where=path.name,
            )
    accepted = member.get("accepted", [])
    try:
        rules = accepted_rules(accepted, file=path.name)
    except FormatError as error:
        raise CliError("FEN-3004", error.message, where=path.name) from None
    return Provenance(path, root, dict(given), list(accepted), rules)


def _accepted_entries(
    keys: Sequence[str], reasons: Sequence[str], report: Sequence[Difference],
    taken: Sequence[Mapping[str, Any]], date: str,
) -> list[dict[str, Any]]:  # fmt: skip
    """The new accepted entries of ``--accept``: each key ``<level>:<kind>:<where>`` names a difference."""
    numbers = [int(str(e.get("id", ""))[1:]) for e in taken if str(e.get("id", ""))[1:].isdigit()]
    next_number = max(numbers, default=0) + 1
    out: list[dict[str, Any]] = []
    for index, key in enumerate(keys):
        level, _, rest = key.partition(":")
        kind, _, where = rest.partition(":")
        found = next(
            (d for d in report if str(d.level) == level and d.kind == kind and d.where == where), None
        )
        if found is None:
            raise _usage(f"--accept {key}: the run reports no such difference", where="--accept")
        reason = reasons[index] if len(reasons) == len(keys) else reasons[0]
        out.append(
            {
                "id": f"A{next_number:03d}",
                "level": found.level,
                "kind": found.kind,
                "where": found.where,
                "field": found.field,
                "reason": reason,
                "attribution": "undecided",
                "decided": date,
            }
        )
        next_number += 1
    return out


# --- levels ----------------------------------------------------------------------------------------


def _levels(spec: str | None) -> tuple[LevelId, ...]:
    if spec is None:
        return ALL_LEVELS
    chosen: set[LevelId] = set()
    for token in spec.split(","):
        token = token.strip()
        if token == SCHEMATIC_LEVEL:
            chosen.add(SCHEMATIC_LEVEL)
            continue
        low, _, high = token.partition("-")
        try:
            first, last = int(low), int(high or low)
        except ValueError:
            raise _usage(f"--levels: {token!r} is not a level or a range", where="--levels") from None
        if not (1 <= first <= last <= PRESENTATION_LEVEL):
            raise _usage(f"--levels: {token!r} names a level outside 1 to 8", where="--levels")
        chosen.update(range(first, last + 1))
    return tuple(level for level in ALL_LEVELS if level in chosen)


def _status(level: LevelResult | None) -> str:
    if level is None:
        return "skipped"
    if level.differences:
        return "differs"
    return "accepted" if level.excluded else "equal"


def _row(difference: Difference) -> dict[str, Any]:
    return {
        "level": difference.level,
        "kind": difference.kind,
        "where": difference.where,
        "field": difference.field,
        "a": difference.a,
        "b": difference.b,
    }


def _has_sheets(root: Path) -> bool:
    return any(p.suffix == ".kicad_sch" for p in _kicad_files(root))


def _drawn_level(
    original: Original, out: Path, a: Design, b: Design, wanted: Sequence[LevelId],
    skipped: dict[LevelId, str], tolerances: Tolerances,
) -> LevelResult | None:  # fmt: skip
    """Level S (drawn schematics, c0276) of the original's sheets against the build's, before any rule;
    ``None`` with the skip reason in ``skipped`` when a side has no sheets that extraction reads."""
    if SCHEMATIC_LEVEL not in wanted:
        return None
    root_a, root_b = root_schematic(original.path), root_schematic(out)
    if original.backend != "kicad":
        skipped[SCHEMATIC_LEVEL] = "altium-drawing-unread"
    elif root_a is None or root_b is None or not (_has_sheets(original.root) and _has_sheets(out)):
        skipped[SCHEMATIC_LEVEL] = "no-schematic"
    else:
        found = schematic_level(root_a, root_b, a.circuit, b.circuit, tolerances=tolerances)
        if found is None:
            skipped[SCHEMATIC_LEVEL] = UNREADABLE
        return found
    return None


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    script = _path(args.script, ctx)
    if not script.is_file() or script.suffix != ".py":
        raise _usage(f"{script.name} is not a design script", where="SCRIPT", hint="pass a design.py")
    original = _original(_path(args.against, ctx))
    wanted = _levels(args.levels)
    if args.accept and not args.reason:
        raise _usage("--accept needs --reason", where="--accept", hint="say why the difference is accepted")
    if args.reason and len(args.reason) not in (1, len(args.accept)):
        raise _usage("give one --reason, or one per --accept", where="--reason")
    for flag, value in (
        ("--tolerance-nm", args.tolerance_nm), ("--tolerance-udeg", args.tolerance_udeg),
        ("--tolerance-ppm", args.tolerance_ppm), ("--pixel-ppm", args.pixel_ppm),
    ):  # fmt: skip
        if value is not None and value < 0:
            raise _usage(f"{flag} is a non-negative integer", where=flag)
    if args.render_pitch_um is not None and args.render_pitch_um <= 0:
        raise _usage("--render-pitch-um is a positive integer", where="--render-pitch-um")
    provenance = _provenance(args, script, ctx)
    given = provenance.tolerances

    def chosen(value: int | None, key: str, default: int) -> int:
        return value if value is not None else given.get(key, default)

    tolerances = Tolerances(
        chosen(args.tolerance_nm, "length_nm", 0),
        chosen(args.tolerance_udeg, "angle_udeg", 0),
        chosen(args.tolerance_ppm, "length_ppm", 0),
    )
    pixel_ppm = chosen(args.pixel_ppm, "pixel_ppm", DEFAULT_PIXEL_PPM)
    pitch_um = args.render_pitch_um if args.render_pitch_um is not None else DEFAULT_PITCH_UM
    frame: Frame = args.frame or "absolute"
    with tempfile.TemporaryDirectory(prefix="fenolite-verify-") as temporary:
        work = Path(temporary)
        return _verify(
            args, ctx, script, original, wanted, provenance, tolerances, pixel_ppm, pitch_um, frame, work
        )


def _verify(
    args: argparse.Namespace, ctx: Context, script: Path, original: Original, wanted: Sequence[LevelId],
    provenance: Provenance, tolerances: Tolerances, pixel_ppm: int, pitch_um: int, frame: Frame, work: Path,
) -> Result:  # fmt: skip
    notes: list[Issue] = []
    major = args.target or versions.DEFAULT_TARGET
    if original.backend == "kicad":
        try:
            board = resolve_board(original.path)
        except FormatError as error:
            raise CliError("FEN-2001", str(error), where="--against") from None
        found_major = _board_major(board)
        version = board_format(board)
        too_old = version is not None and (
            versions.classify(versions.FileKind.BOARD, version) is versions.VersionStatus.TOO_OLD
            or found_major == READ_ONLY_MAJOR
        )
        if too_old:
            if not args.upgrade:
                raise CliError(
                    "FEN-3003",
                    f"{board.name} (format {version}) is older than KiCad 9.0, the oldest original "
                    "verify-source proves against",
                    where=board.name,
                    hint=UPGRADE_HINT,
                )
            original, upgraded = _upgraded(original, board, work, args)
            notes.append(upgraded)
            found_major = versions.DEFAULT_TARGET
        if args.target is None and found_major in versions.TARGET_MAJORS:
            major = found_major
    out = work / "build" / script.stem
    out.parent.mkdir(parents=True)
    built, count, refused = _build(script, out, ctx, major)
    build_issues = tuple(i for i in built.issues if i.severity != "info" or count == 0)
    sha = _sha256(script)
    against_files = {p.relative_to(original.root).as_posix(): _sha256(p) for p in original.files}
    base: dict[str, Any] = {
        "script": {"name": script.name, "sha256": sha},
        "against": {"name": original.path.name, "backend": original.backend, "files": against_files},
        "build": {"target": f"kicad-{major}", "files": count},
        "tolerances": {
            "length_nm": tolerances.length_nm,
            "angle_udeg": tolerances.angle_udeg,
            "length_ppm": tolerances.length_ppm,
            "pixel_ppm": pixel_ppm,
            "render_pitch_um": pitch_um,
            "frame": frame,
        },
        "provenance": {
            "path": _shown(provenance.path, ctx.cwd) if provenance.path.exists() or args.record else None,
            "accepted": len(provenance.rules),
            "record": bool(args.record),
        },
    }
    if count == 0:
        failed = issue(
            "fidelity.build-failed",
            f"the build of {script.name} wrote no file, so no level ran"
            + (f": {refused}" if refused else ""),
            where=script.name,
            hint="fix the build's errors listed beside this issue, then verify again",
        )
        empty: dict[str, Any] = {}
        levels: list[dict[str, Any]] = [
            {"level": level, "name": ALL_LEVEL_NAMES[level], "status": "skipped", "compared": 0,
             "differences": 0, "excluded": 0, "notices": 0, "reason": "build-failed", "summary": empty}
            for level in wanted
        ]  # fmt: skip
        result: dict[str, Any] = {
            **base,
            "levels": levels,
            "equivalent": False,
            "differences": [],
            "accepted": [],
            "notices": [],
        }
        return Result(
            result=result, issues=(failed, *build_issues, *notes), evidence=built.evidence,
            input=InputRef(path=script.name, sha256=sha, kind="design-script", format_version=None),
        )  # fmt: skip
    try:
        side_a = read_side(original.path, kicad_cli=args.kicad_cli, timeout=args.timeout)
        side_b = read_side(out)
    except SideError as error:
        where = OPTIONS.get(error.where, error.where)
        raise CliError(error.cli_code, error.message, where=where, hint=error.hint) from None
    return _compare(args, ctx, script, sha, original, out, side_a, side_b, wanted, provenance, tolerances,
                    pixel_ppm, pitch_um, frame, base, built, build_issues, notes)  # fmt: skip


def _compare(
    args: argparse.Namespace, ctx: Context, script: Path, sha: str, original: Original, out: Path,
    side_a: ReadSide, side_b: ReadSide, wanted: Sequence[LevelId], provenance: Provenance,
    tolerances: Tolerances, pixel_ppm: int, pitch_um: int, frame: Frame, base: dict[str, Any], built: Result,
    build_issues: Sequence[Issue], notes: list[Issue],
) -> Result:  # fmt: skip
    a, b = side_a.design, side_b.design
    skipped: dict[LevelId, str] = {}
    highest = max_level(a, b)
    footprints = highest >= 4
    model_levels = [level for level in wanted if isinstance(level, int) and level in LEVELS]
    for level in model_levels:
        if level in (3, 4, 6, 7) and not footprints:
            skipped[level] = "no-footprints"
        elif level == 5 and highest < 5:
            skipped[level] = "no-copper"
    top = max((level for level in model_levels if level not in skipped), default=0)
    rules = provenance.rules

    def run(extra: tuple[Rule, ...]) -> tuple[EquivalenceReport | None, LevelResult | None]:
        report = None
        if top:
            report = compare_designs(a, b, level=top, tolerances=tolerances, frame=frame, rules=extra,
                                     strict=top >= 5 and highest == 5)  # fmt: skip
        rendered = None
        if PRESENTATION_LEVEL in wanted:
            if a.board is None or b.board is None:
                skipped[PRESENTATION_LEVEL] = "no-board"
            else:
                scenes_a = dict(board_scenes(a, side_a.backend))
                scenes_b = dict(board_scenes(b, side_b.backend))
                if original.backend == "kicad" and _has_sheets(original.root) and _has_sheets(out):
                    scenes_a.update(sheet_scenes(original.root))
                    scenes_b.update(sheet_scenes(out))
                level8 = presentation_level(scenes_a, scenes_b, pixel_ppm=pixel_ppm, pitch_nm=pitch_um * 1000)
                rendered = apply_rules(level8, extra)
        return report, rendered

    drawn = _drawn_level(original, out, a, b, wanted, skipped, tolerances)
    report, rendered = run(rules)
    new_entries: list[dict[str, Any]] = []
    if args.accept:
        found = [*(report.differences if report else ()), *(rendered.differences if rendered else ())]
        found += drawn.differences if drawn else ()
        date = ctx.timestamp.strftime("%Y-%m-%d")
        new_entries = _accepted_entries(args.accept, args.reason, found, provenance.accepted, date)
        rules = (*rules, *accepted_rules(new_entries, file="--accept"))
        report, rendered = run(rules)
    by_level: dict[LevelId, LevelResult] = {}
    if report is not None:
        by_level.update({level.level: level for level in report.levels if level.level in wanted})
    if drawn is not None:
        by_level[SCHEMATIC_LEVEL] = apply_rules(drawn, rules)
    if rendered is not None:
        by_level[PRESENTATION_LEVEL] = rendered
    ran = [by_level[level] for level in wanted if level in by_level]
    levels: list[dict[str, Any]] = []
    for level in wanted:
        found_level = by_level.get(level)
        row: dict[str, Any] = {
            "level": level,
            "name": ALL_LEVEL_NAMES[level],
            "status": _status(found_level) if level not in skipped else "skipped",
            "compared": found_level.compared if found_level else 0,
            "differences": len(found_level.differences) if found_level else 0,
            "excluded": len(found_level.excluded) if found_level else 0,
            "notices": len(found_level.notices) if found_level else 0,
            "reason": skipped.get(level, ""),
            "summary": dict(found_level.summary) if found_level else {},
        }
        levels.append(row)
    shown = EquivalenceReport(
        tuple(ran), tolerances, frame, report.translation if report else EquivalenceReport(()).translation
    )
    fidelity_issues: list[Issue] = []
    used = {excluded.rule_id for excluded in shown.excluded}
    ran_levels = {level.level for level in ran}
    for rule in rules:
        if rule.id not in used and rule.level in ran_levels:
            fidelity_issues.append(
                issue(
                    "fidelity.accepted-unused",
                    f"accepted entry {rule.id} ({rule.level}:{rule.kind}:{rule.where}) matched no difference",
                    where=rule.id,
                    hint="the difference is gone: remove the entry from fidelity.accepted",
                )
            )
    for level in wanted:
        if level in skipped:
            fidelity_issues.append(
                issue(
                    "fidelity.level-skipped", f"level {level} was skipped: {skipped[level]}", where=str(level)
                )
            )
    changes: Mapping[str, Any] = rendered.summary.get("changes", {}) if rendered else {}  # type: ignore[assignment]
    equivalence = list(difference_issues(shown))
    if changes:
        hint = "; ".join(text for found in changes.values() for text in found)
        equivalence = [
            dataclasses.replace(i, hint=f"the visual diff names: {hint}")
            if i.code == "equiv.render-pixels"
            else i
            for i in equivalence
        ]
    accepted_rows = [{**_row(found.difference), "rule": found.rule_id} for found in shown.excluded]
    result = {
        **base,
        "levels": levels,
        "equivalent": shown.equivalent,
        "differences": [_row(d) for d in shown.differences],
        "accepted": accepted_rows,
        "notices": [_row(d) for d in shown.notices],
    }
    if new_entries:
        result["new_accepted"] = new_entries
    writes: tuple[PlannedWrite, ...] = ()
    if args.record:
        writes = (_record(provenance, ctx, sha, base, levels, new_entries),)
    evidence = Evidence.combine(
        side_a.evidence, side_b.evidence, built.evidence, PRESENTATION_EVIDENCE,
        *((DRAWN_EVIDENCE,) if drawn is not None else ()),
    )  # fmt: skip
    return Result(
        result=result,
        issues=(*equivalence, *fidelity_issues, *notes, *side_a.issues, *side_b.issues, *build_issues),
        evidence=evidence,
        input=InputRef(path=script.name, sha256=sha, kind="design-script", format_version=None),
        writes=writes,
        depends=depends_on(ctx.cwd, script, *original.files),
    )


def _record(
    provenance: Provenance, ctx: Context, sha: str, base: Mapping[str, Any],
    levels: Sequence[Mapping[str, Any]], new_entries: Sequence[Mapping[str, Any]],
) -> PlannedWrite:  # fmt: skip
    """The provenance file with ``fidelity.proof`` and the new accepted entries, every other member kept."""
    data = dict(provenance.data)
    data.setdefault("schema", PROVENANCE_SCHEMA)
    member = dict(data.get("fidelity") or {})
    if new_entries:
        member["accepted"] = [*provenance.accepted, *new_entries]
    member["proof"] = {
        "fenolite": fenolite.__version__,
        "date": ctx.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script_sha256": sha,
        "against": base["against"]["files"],
        "tolerances": base["tolerances"],
        "levels": {str(row["level"]): row["status"] for row in levels},
    }
    data["fidelity"] = member
    text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    return PlannedWrite(_shown(provenance.path, ctx.cwd), text.encode("utf-8"), "provenance")


COMMAND = Command(
    name="verify-source",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_SCRIPT, "--against", EXAMPLE_ORIGINAL),
    mutation_example_args=(
        EXAMPLE_SCRIPT,
        "--against",
        EXAMPLE_ORIGINAL,
        "--record",
        "--provenance",
        PROVENANCE,
    ),  # fmt: skip
    discovery=(("levels", ALL_LEVELS),),
)

__all__ = ["COMMAND", "ISSUE_CODES", "PROVENANCE", "STATUSES"]
