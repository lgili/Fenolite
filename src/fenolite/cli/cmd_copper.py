# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite copper PATH``: generate the power, switch-node, ground and high-voltage copper of a KiCad board
from its confirmed and declared net roles (change c0243; capability cli-contract, "Copper command";
capability net-roles, "Role copper plan"; ``docs/cli-contract.md``, "copper"; ``docs/roles.md``, "Role
copper").

The command is the glue of ``fenolite.roles.copper``: it reads the board, the roles that ``fenolite roles``
stored for it (or the built project's ``.fenolite/rules.json``), the net classes of the project beside it and
the manifest ``.fenolite/role-copper.json`` of the last run; it takes out the role items of that run whose
fingerprint is unchanged, keeps those the user edited, plans on what is left, applies the plan with
``lens.rolecopper.apply_plan`` and judges the result. It is a writing command of the mutation protocol: the
board, the project's design rules when the plan holds role rules, and the manifest are written together or
not at all, and a run on its own output plans no change. A ``.PcbDoc`` is refused: an Altium board gets role
copper through a build of its script with ``design.role_copper()``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fenolite.backends.base import ProjectSet
from fenolite.backends.kicad import dru
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.cli import _gate
from fenolite.cli._documents import built_cache
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_analyze import requirements_option
from fenolite.cli.cmd_roles import _board as resolve_board_path  # pyright: ignore[reportPrivateUsage]
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.units import parse_length
from fenolite.lens.rolecopper import apply_plan
from fenolite.model.design import Design
from fenolite.model.rules import RuleSet
from fenolite.roles import rolemanifest
from fenolite.roles.copper import CONNECTIONS, GROUND_FILLS, KINDS, Request, run
from fenolite.roles.judge import split_roles
from fenolite.roles.store import Stored, stored_roles

HELP = "generate the power and ground copper of a KiCad board from its net roles (writes with --confirm)"
TIMEOUT = 300.0


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/roles.md, 'Role copper', and docs/cli-contract.md, 'copper'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a built project folder")
    parser.add_argument("--roles", default=None, metavar="FILE", help="the role document to read")
    parser.add_argument("--requirements", default=None, metavar="FILE", help="your distance and current rows")
    parser.add_argument("--kinds", default=None, metavar="KIND,KIND", help=f"of {','.join(KINDS)}")
    parser.add_argument(
        "--net", dest="nets", action="append", default=[], metavar="GLOB", help="only these nets (repeatable)"
    )
    parser.add_argument(
        "--layers", action="append", default=[], metavar="KIND=L,L", help="the layers of a kind (repeatable)"
    )
    parser.add_argument(
        "--ground-layers", default=None, metavar="L,L", help="the layers of the ground planes"
    )
    parser.add_argument(
        "--ground-fill", choices=GROUND_FILLS, default=None, help="all: pour the outer area too"
    )
    parser.add_argument(
        "--connection",
        action="append",
        default=[],
        metavar="KIND=MODE",
        help=f"the pad connection of a kind, MODE of {','.join(CONNECTIONS)} (repeatable)",
    )
    parser.add_argument("--stitch-pitch", default=None, metavar="LENGTH", help="the ground stitching pitch")
    parser.add_argument("--temp-rise", default=None, metavar="KELVIN", help="size by the fit of S-0269")
    parser.add_argument("--widen", default=None, metavar="PERMILLE", help="how far power copper widens")
    parser.add_argument("--no-corridors", action="store_true", help="write no provisional corridor")
    parser.add_argument(
        "--regenerate",
        action="append",
        default=[],
        metavar="KEY",
        help="generate this edited role item again (repeatable)",
    )
    _gate.register(parser, kicad_cli=True)
    parser.add_argument("--timeout", type=float, default=TIMEOUT, metavar="SECONDS", help="per kicad-cli run")


def _list(text: str | None, option: str) -> tuple[str, ...] | None:
    if text is None:
        return None
    names = tuple(name.strip() for name in text.split(",") if name.strip())
    if not names:
        raise CliError("FEN-2001", f"{option}: empty list", where=option)
    return names


def _pairs(values: list[str], option: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for text in values:
        kind, eq, value = text.partition("=")
        if not eq or kind.strip() not in KINDS or not value.strip():
            raise CliError(
                "FEN-2001",
                f"{option}: {text!r} is not KIND=VALUE",
                where=option,
                hint=f"kinds: {','.join(KINDS)}",
            )
        found[kind.strip()] = value.strip()
    return found


def _request(args: argparse.Namespace, copper: tuple[str, ...]) -> Request:
    kinds = _list(args.kinds, "--kinds") or KINDS
    bad = [kind for kind in kinds if kind not in KINDS]
    if bad:
        raise CliError("FEN-2001", f"--kinds: unknown kind {bad[0]!r}", where="--kinds", hint=",".join(KINDS))
    layers: dict[str, tuple[str, ...]] = {}
    for kind, value in _pairs(args.layers, "--layers").items():
        names = tuple(name.strip() for name in value.split(","))
        for name in names:
            if name not in copper:
                raise CliError("FEN-2001", f"--layers: no copper layer {name!r}", where="--layers")
        layers[kind] = names
    ground = _list(args.ground_layers, "--ground-layers")
    for name in ground or ():
        if name not in copper:
            raise CliError("FEN-2001", f"--ground-layers: no copper layer {name!r}", where="--ground-layers")
    connection = _pairs(args.connection, "--connection")
    for mode in connection.values():
        if mode not in CONNECTIONS:
            raise CliError("FEN-2001", f"--connection: unknown mode {mode!r}", where="--connection")
    pitch = None
    if args.stitch_pitch is not None:
        try:
            pitch = parse_length(args.stitch_pitch)
        except ValueError as error:
            raise CliError("FEN-2001", f"--stitch-pitch: {error}", where="--stitch-pitch") from None
        if pitch <= 0:
            raise CliError("FEN-2001", "--stitch-pitch must be above 0", where="--stitch-pitch")
    rise = None
    if args.temp_rise is not None:
        try:
            value = Decimal(args.temp_rise) * 1000
        except InvalidOperation:
            raise CliError(
                "FEN-2001", f"--temp-rise: cannot read {args.temp_rise!r}", where="--temp-rise"
            ) from None
        if value <= 0 or value != value.to_integral_value():
            raise CliError(
                "FEN-2001", "--temp-rise: a rise above 0 K, at most three decimals", where="--temp-rise"
            )
        rise = int(value)
    widen = None
    if args.widen is not None:
        if not args.widen.isdigit() or int(args.widen) < 1000:
            raise CliError("FEN-2001", "--widen is a per mille of at least 1000", where="--widen")
        widen = int(args.widen)
    return Request(
        kinds=kinds,
        layers=layers,
        ground_layers=ground,
        ground_fill=args.ground_fill or "reference",
        connection=connection,
        stitch_pitch=pitch,
        temp_rise=rise,
        widen=widen,
        corridors=not args.no_corridors,
        regenerate=tuple(args.regenerate),
        nets=tuple(args.nets),
    )


def _without(design: Design, ids: set[str]) -> Design:
    board = design.board
    assert board is not None
    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            zones=tuple(z for z in board.zones if z.id not in ids),
            keepouts=tuple(k for k in board.keepouts if k.id not in ids),
            vias=tuple(v for v in board.vias if v.id not in ids),
            tracks=tuple(t for t in board.tracks if t.id not in ids),
        ),
    )


def _rules_text(path: Path, rules: Any, target: int, allow_lossy: bool, issues: list[Issue]) -> str | None:
    """The project's design rules with the role rules of the plan in place of those of an earlier run, or
    ``None`` when neither holds a role rule."""
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    current = dru.read_rules(old, file=path.name) if old is not None else RuleSet(id="rules_role_copper")
    kept = tuple(rule for rule in current.rules if not rule.name.startswith("role."))
    if not rules and len(kept) == len(current.rules):
        return None
    updated = dataclasses.replace(current, rules=(*kept, *rules))
    return dru.write_rules(updated, target=target, allow_lossy=allow_lossy, issues=issues)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if path.suffix.lower() == ".pcbdoc":
        raise CliError(
            "FEN-2001",
            f"{given.name}: the copper command edits KiCad boards only",
            where=given.name,
            hint="build the board's script with design.role_copper() for --target altium",
        )
    if not path.exists():
        raise CliError("FEN-3001", f"{args.path} does not exist", where=path.name)
    board_path = resolve_board_path(path)
    if board_path.suffix != ".kicad_pcb":
        raise CliError("FEN-2001", f"{board_path.name} is not a KiCad board", where=board_path.name)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=issues)
    source = source_info(design)
    assert design.board is not None
    copper = tuple(
        la.name for la in sorted(design.board.layers, key=lambda la: la.ordinal) if la.kind == "copper"
    )
    request = _request(args, copper)
    requirements = requirements_option(args.requirements, ctx.cwd)
    _gate.preflight(args, board_path, args.timeout, own_option=True)
    root = board_path.parent
    built, model, cache_error = built_cache(root)
    if cache_error:
        raise CliError("FEN-3004", f".fenolite: {cache_error}", where=".fenolite")
    roles_file = (
        None
        if args.roles is None
        else (Path(args.roles) if Path(args.roles).is_absolute() else ctx.cwd / args.roles)
    )
    try:
        stored: Stored = stored_roles(
            board_path,
            model_roles=model.rules.roles if model is not None and model.rules is not None else None,
            built=built,
            root=root,
            given=roles_file,
        )
    except FormatError as error:
        raise CliError("FEN-3004", str(error), where=error.locator or error.file) from None
    declared, confirmed = split_roles(stored.roles) if stored.built else (None, stored.roles)
    manifest_path = root / rolemanifest.FILE
    manifest = None
    if manifest_path.is_file():
        try:
            manifest = rolemanifest.loads(manifest_path.read_text(encoding="utf-8"))
        except FormatError as error:
            raise CliError("FEN-3004", str(error), where=rolemanifest.FILE) from None
    project = ProjectSet(
        root=root,
        board=board_path.name,
        files={
            board_path.name: board_path,
            **{
                p.name: p
                for p in (board_path.with_suffix(s) for s in (".kicad_pro", ".kicad_dru"))
                if p.is_file()
            },
        },
    )
    sorted_items = rolemanifest.sort(design, manifest, regenerate=request.regenerate)
    base = _without(design, set(sorted_items.replace))
    classed = dataclasses.replace(base, circuit=KicadBackend().design_rules(base, project).design.circuit)
    request = dataclasses.replace(request, keep=sorted_items.kept)
    pads = tuple(KicadBackend().board_pads(classed, issues=issues))
    outcome = run(
        classed,
        pads,
        request,
        lambda d, p: apply_plan(d, p),
        stored=confirmed,
        declared=declared,
        requirements=requirements,
        circuit=model.circuit if model is not None else None,
    )
    issues += [*sorted_items.issues, *outcome.issues]
    after, _ = apply_plan(base, outcome.plan)
    evidence = outcome.evidence
    gated: _gate.Gated | None = None
    if args.gate == "drc" and not outcome.refused:
        gated = _gate.gate(board_path, design, after, kicad_cli=args.kicad_cli, timeout=args.timeout)
        after = gated.design
        issues += gated.issues
        if gated.evidence is not None:
            evidence = gated.evidence
    major = source.major if source is not None and source.major is not None else ctx.kicad_target
    refused = any(found.severity == "error" for found in issues)
    board_text = write_board(after, target=major, allow_lossy=ctx.allow_lossy).text
    found_corridors = {c.key for c in outcome.plan.corridors if c.origin == "found"}
    record = rolemanifest.record(after, before=base, kept=sorted_items.kept, found=found_corridors)
    manifest_text = record.dumps()
    dru_path = board_path.with_suffix(".kicad_dru")
    rules_text = _rules_text(dru_path, outcome.plan.rules, major, ctx.allow_lossy, issues)
    old_rules = dru_path.read_text(encoding="utf-8") if dru_path.is_file() else None
    old_manifest = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else None
    changed = (
        board_text != text
        # an empty manifest where there was none records nothing: a run that generates nothing writes nothing
        or (manifest_text != old_manifest and (old_manifest is not None or bool(record.items)))
        or (rules_text is not None and rules_text != old_rules)
    )
    writes: tuple[PlannedWrite, ...] = ()
    if changed and not refused:
        rel = _relative(board_path, ctx.cwd)
        planned = [PlannedWrite(rel, board_text.encode("utf-8"), "kicad_pcb")]
        if rules_text is not None and rules_text != old_rules:
            planned.append(
                PlannedWrite(_relative(dru_path, ctx.cwd), rules_text.encode("utf-8"), "kicad_dru")
            )
        planned.append(
            PlannedWrite(_relative(manifest_path, ctx.cwd), manifest_text.encode("utf-8"), "fenolite")
        )
        writes = tuple(planned)
    summary = dict(outcome.summary)
    result: dict[str, Any] = {
        "board": board_path.name,
        **summary,
        "kept": list(sorted_items.kept),
        "replaced": len(sorted_items.replace),
        "changed": changed and not refused,
        "next": ["fenolite fill", "fenolite check"] if changed and not refused else [],
        "gate": None if args.gate is None else gated.result if gated is not None else _gate.untouched(),
    }
    return Result(
        result=result,
        issues=tuple(dict.fromkeys(issues)),
        evidence=evidence,
        input=InputRef(
            board_path.name,
            hashlib.sha256(data).hexdigest(),
            "kicad_pcb",
            str(source.version) if source is not None else None,
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, board_path, stored.source, args.requirements),
    )


def _relative(path: Path, cwd: Path) -> str:
    import os

    try:
        return Path(os.path.relpath(path, cwd)).as_posix()
    except ValueError:
        return path.as_posix()


COMMAND = Command(
    name="copper",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD,),
)

__all__ = ["COMMAND", "HELP"]
