# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite equivalent A [B]``: whether two designs are equivalent, level by level, with every
difference located at ``REF`` or ``REF-PIN``, and at the net for routing (capability design-equivalence,
"Equivalent command", "Level 5 in the equivalent command" and "Triangle oracle";
``docs/cli-contract.md``, "equivalent"; ``docs/equivalence.md``).

The command parses its arguments, calls ``fenolite.api.equivalent`` and replies with
``EquivalenceResult.to_json()`` (change c0158). With two paths no tool runs unless a KiCad schematic side
needs ``kicad-cli``. With ``--against kicad-import`` side ``b`` is the board that ``kicad-cli pcb import``
converts ``A`` to, compared under the importer's exclusion profile of the running version line. It writes
no file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fenolite.api.equivalence import AGAINST, equivalent
from fenolite.api.sides import READS, SIDE_KINDS, SideError
from fenolite.checks.equivalence import LEVELS, Profile, load_profiles
from fenolite.checks.equivalence.model import FRAMES
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef

HELP = "say whether two designs are equivalent, level by level, and locate each difference"
PCB_DOCUMENT = ".pcbdoc"
OPTIONS = {
    "level": "--level",
    "b": "B",
    "profile": "--exclusions",
    "frame": "--frame",
    "against": "--against",
}
"""The option of the command that a parameter of ``fenolite.api.equivalent`` named in an error stands for."""


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


def _tolerances(args: argparse.Namespace) -> dict[str, int]:
    """The tolerances given on the command line; the others come from the profile, else 0."""
    given: dict[str, int] = {}
    for flag, field, value in (
        ("--tolerance-nm", "length_nm", args.tolerance_nm),
        ("--tolerance-udeg", "angle_udeg", args.tolerance_udeg),
        ("--tolerance-ppm", "length_ppm", args.tolerance_ppm),
    ):
        if value is not None and value < 0:
            raise _usage(f"{flag} is a non-negative integer", where=flag)
        if value is not None:
            given[field] = value
    return given


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if (args.b is None) == (args.against is None):
        raise _usage(
            "give B or --against kicad-import, not both and not neither",
            where="B",
            hint="equivalent A B, or equivalent A.PcbDoc --against kicad-import",
        )
    path_a = _path(args.a, ctx)
    profile: Profile | None = None
    path_b: Path | None = None
    if args.against is None:
        profile = _user_profile(args, ctx)
        path_b = _path(args.b, ctx)
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
    tolerances = _tolerances(args)
    if args.level is not None and args.level not in LEVELS:
        raise _usage(f"--level is one of {', '.join(map(str, LEVELS))}", where="--level")
    try:
        found = equivalent(
            path_a,
            path_b,
            level=args.level,
            tolerances=tolerances,
            frame=args.frame,
            ignore_refs=tuple(args.ignore_ref),
            profile=profile,
            against=args.against,
            kicad_cli=args.kicad_cli,
            timeout=args.timeout,
        )
    except SideError as error:
        where = OPTIONS.get(error.where, error.where)
        raise CliError(error.cli_code, error.message, where=where, hint=error.hint) from None
    return Result(
        result=found.to_json(),
        issues=found.issues,
        evidence=found.evidence,
        input=InputRef(path=found.a.name, sha256=found.a.sha256, kind=found.a.kind, format_version=None),
    )


COMMAND = Command(
    name="equivalent",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, EXAMPLE_BOARD, "--level", "4"),
    discovery=(("levels", LEVELS), ("sides", SIDE_KINDS)),
)

__all__ = ["COMMAND"]
