# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite roles PATH``: infer, show, confirm and check the net roles of a board (change c0222; capability
cli-contract, "Roles command" and "Roles measuring options"; capability net-roles, "Roles show and confirm";
``docs/roles.md``, ``docs/cli-contract.md``, "roles").

Without an accept, set, reject or current option the command is read-only: it shows one row per net and the
groups, and with ``--check`` judges the board against them (``result.measures`` and ``result.summary``),
running no tool. With one of those options it is a writing command of the mutation protocol: it plans the
role document (``<board stem>.roles.json`` beside the board, or ``--roles FILE``), or ``.fenolite/rules.json``
of a project that Fenolite built, and writes nothing else. The reply then shows the roles as they will be
stored. A script's declared roles cannot be changed here: the script is their source.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from fenolite.analysis.copper import ARC_TOL_NM
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad
from fenolite.backends.kicad.projectset import ProjectNotFoundError, ProjectResolutionError, resolve_board
from fenolite.cli._documents import built_cache, find_documents
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_analyze import (
    copper_thickness_option,
    length_option,
    record_json,
    requirements_option,
    temp_rise_option,
)
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.requirement_table import joined
from fenolite.model.design import Design
from fenolite.model.rules import (
    PART_CLASSES,
    ROLE_KINDS,
    GateLoop,
    HotLoop,
    KelvinPair,
    NetRole,
    PartClass,
    RoleKind,
    RoleSet,
)
from fenolite.roles.judge import EVIDENCE, Judged, run, split_roles
from fenolite.roles.measure import Inputs
from fenolite.roles.store import Stored, dumps_document, merged, stored_roles, updated_rules

HELP = "infer, show, confirm and check the net roles of a board (read-only without an accept or set)"
SET_KEYS = ("milliamps", "working_mv", "sensitive")
MEASURING = (
    ("--requirements", "requirements"),
    ("--temp-rise", "temp_rise"),
    ("--copper-thickness", "copper_thickness"),
    ("--via-plating", "via_plating"),
    ("--board-thickness", "board_thickness"),
    ("--pour-grid", "pour_grid"),
    ("--split", "split"),
    ("--arc-tol", "arc_tol"),
)
"""The measuring options of ``analyze`` that ``--check`` takes, and their argument names."""
_LEVELS = {"high": 2, "medium": 1, "low": 0, "": 0}


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        HELP + ". Roles are inferred from the circuit; you confirm or declare them, and --check measures the "
        "board's copper against them through the analyses; see docs/roles.md."
    )
    parser.add_argument(
        "path", metavar="PATH", help="a board, or a built project folder, that a backend reads"
    )
    parser.add_argument("--roles", default=None, metavar="FILE", help="the role document to read and write")
    parser.add_argument(
        "--net",
        dest="nets",
        action="append",
        default=[],
        metavar="GLOB",
        help="show the nets whose name matches this pattern (repeatable)",
    )
    parser.add_argument("--kinds", default=None, metavar="KIND,KIND", help="show the roles of these kinds")
    parser.add_argument(
        "--class",
        dest="classes",
        action="append",
        default=[],
        metavar="REF=CLASS",
        help="state a part's class for the inference (repeatable)",
    )
    parser.add_argument("--check", action="store_true", help="measure and judge the board against its roles")
    parser.add_argument(
        "--requirements", default=None, metavar="FILE", help="with --check: your requirements"
    )
    parser.add_argument(
        "--temp-rise",
        default=None,
        metavar="KELVIN",
        help="with --check: judge currents by the capacity fit at this rise",
    )
    parser.add_argument(
        "--copper-thickness",
        action="append",
        default=[],
        metavar="[LAYER=]LENGTH",
        help="with --check: copper thickness of every layer, or of one (repeatable)",
    )
    parser.add_argument("--via-plating", default=None, metavar="LENGTH", help="with --check: via plating")
    parser.add_argument(
        "--board-thickness", default=None, metavar="LENGTH", help="with --check: board thickness"
    )
    parser.add_argument(
        "--pour-grid", default=None, metavar="LENGTH", help="with --check: raster cell of pours"
    )
    parser.add_argument(
        "--split", action="store_true", help="with --check and a rise: shares of parallel copper"
    )
    parser.add_argument("--arc-tol", default=None, metavar="LENGTH", help="with --check: chord error of arcs")
    parser.add_argument(
        "--current",
        dest="currents",
        action="append",
        default=[],
        metavar="NET=AMPS",
        help="store a net's current, e.g. VOUT=2 (repeatable)",
    )
    parser.add_argument(
        "--accept",
        action="append",
        default=[],
        metavar="NET[,NET...]",
        help="store these inferred roles as confirmed (repeatable)",
    )
    parser.add_argument("--accept-all", action="store_true", help="store every inferred role and group")
    parser.add_argument(
        "--min-confidence",
        choices=("high", "medium"),
        default=None,
        help="with --accept-all: only roles and groups of at least this confidence",
    )
    parser.add_argument(
        "--set",
        dest="sets",
        action="append",
        default=[],
        metavar="NET=KIND[:KEY=N]",
        help="store a role you choose, e.g. SW=switch_node or VBUS=power:working_mv=400000 (repeatable)",
    )
    parser.add_argument(
        "--reject",
        action="append",
        default=[],
        metavar="NET",
        help="store the net as a confirmed signal, so it is not inferred again (repeatable)",
    )
    parser.add_argument(
        "--accept-group",
        action="append",
        default=[],
        metavar="NAME",
        help="store this inferred group as confirmed (repeatable)",
    )
    parser.add_argument(
        "--reject-group",
        action="append",
        default=[],
        metavar="NAME",
        help="never infer this group again (repeatable)",
    )


def _names(values: Sequence[str], option: str) -> tuple[str, ...]:
    names: list[str] = []
    for text in values:
        parts = [name.strip() for name in text.split(",")]
        if not all(parts):
            raise CliError("FEN-2001", f"{option}: empty name in {text!r}", where=option)
        names += parts
    return tuple(dict.fromkeys(names))


def _kinds(text: str | None) -> tuple[str, ...]:
    if text is None:
        return ROLE_KINDS
    names = [name.strip() for name in text.split(",")]
    bad = [name for name in names if name not in ROLE_KINDS]
    if bad or not names:
        raise CliError(
            "FEN-2001",
            f"--kinds: unknown kind {', '.join(bad) or text!r}",
            where="--kinds",
            hint=f"kinds: {','.join(ROLE_KINDS)}",
        )
    return tuple(names)


def _classes(values: Sequence[str]) -> tuple[PartClass, ...]:
    found: dict[str, PartClass] = {}
    for text in values:
        ref, eq, cls = text.partition("=")
        if not eq or not ref.strip() or cls.strip() not in PART_CLASSES:
            raise CliError(
                "FEN-2001",
                f"--class: {text!r} is not REF=CLASS",
                where="--class",
                hint=f"classes: {','.join(PART_CLASSES)}",
            )
        found[ref.strip()] = PartClass(ref.strip(), cast(Any, cls.strip()), ())
    return tuple(found.values())


def _milliamps(text: str, option: str) -> int:
    hint = "a current in amperes with at most three decimals: 2 or 0.5"
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise CliError("FEN-2001", f"{option}: cannot read {text!r}", where=option, hint=hint) from None
    scaled = value * 1000
    if not value.is_finite() or scaled != scaled.to_integral_value() or scaled <= 0:
        raise CliError("FEN-2001", f"{option}: cannot use {text!r}", where=option, hint=hint)
    return int(scaled)


def _currents(values: Sequence[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for text in values:
        net, eq, amps = text.partition("=")
        if not eq or not net.strip():
            raise CliError(
                "FEN-2001", f"--current: {text!r} is not NET=AMPS", where="--current", hint="--current VOUT=2"
            )
        found[net.strip()] = _milliamps(amps, "--current")
    return found


def _sets(values: Sequence[str]) -> dict[str, NetRole]:
    found: dict[str, NetRole] = {}
    hint = f"--set NET=KIND[:KEY=N], KIND one of {','.join(ROLE_KINDS)}, KEY one of {','.join(SET_KEYS)}"
    for text in values:
        net, eq, rest = text.partition("=")
        kind, *pairs = rest.split(":")
        if not eq or not net.strip() or kind.strip() not in ROLE_KINDS:
            raise CliError("FEN-2001", f"--set: {text!r} is not NET=KIND[:KEY=N]", where="--set", hint=hint)
        role = NetRole(net.strip(), cast(RoleKind, kind.strip()), "confirmed")
        for pair in pairs:
            key, eq2, number = pair.partition("=")
            if not eq2 or key.strip() not in SET_KEYS or not number.strip().isdigit():
                raise CliError(
                    "FEN-2001", f"--set: {pair!r} of {text!r} is not KEY=N", where="--set", hint=hint
                )
            value = int(number.strip())
            if key.strip() == "sensitive":
                role = replace(role, sensitive=bool(value))
            elif value <= 0:
                raise CliError("FEN-2001", f"--set: {key.strip()} must be above 0", where="--set", hint=hint)
            else:
                role = replace(role, **{key.strip(): value})
        found[role.net] = role
    return found


def _board(path: Path) -> Path:
    found = find_documents(path)
    if found is not None:
        documents = found[1]
        if documents.board is None:
            raise CliError("FEN-2001", f"{path.name} holds no board", where=path.name, hint="pass a board")
        return documents.root / documents.board
    try:
        return resolve_board(path)
    except ProjectNotFoundError as error:
        raise CliError(
            "FEN-3001", str(error).replace(str(path.parent), "").lstrip("/"), where=path.name
        ) from None
    except ProjectResolutionError as error:
        raise CliError(
            "FEN-2001",
            f"{path.name}: {error}".replace(str(path.parent) + "/", ""),
            where=path.name,
            hint="pass a board file",
        ) from None


def _changed(
    args: argparse.Namespace, judged: Judged, declared: RoleSet | None, confirmed: RoleSet | None
) -> RoleSet | None:
    """The confirmed roles after the accept, set, reject and current options, or ``None`` without any."""
    sets, currents = _sets(args.sets), _currents(args.currents)
    accept, reject = _names(args.accept, "--accept"), _names(args.reject, "--reject")
    accept_groups, reject_groups = (
        _names(args.accept_group, "--accept-group"),
        _names(args.reject_group, "--reject-group"),
    )
    if args.min_confidence is not None and not args.accept_all:
        raise CliError("FEN-2001", "--min-confidence goes with --accept-all", where="--min-confidence")
    if not (sets or currents or accept or reject or accept_groups or reject_groups or args.accept_all):
        return None
    roles = judged.resolved.roles
    by_net = {role.net: role for role in roles.nets}
    stated = {role.net for role in (declared.nets if declared is not None else ())}
    for option, names in (
        ("--accept", accept),
        ("--reject", reject),
        ("--set", tuple(sets)),
        ("--current", tuple(currents)),
    ):
        for name in names:
            if name not in by_net:
                raise CliError("FEN-2001", f"{option}: no net {name!r} on the board", where=option)
            if name in stated:
                raise CliError(
                    "FEN-2001",
                    f"{option}: the script declares the role of {name}",
                    where=option,
                    hint="change design.net_role(...) in the script and build again",
                )
    groups: dict[str, Any] = {group.name: group for group in (*roles.loops, *roles.kelvins, *roles.gates)}
    for option, names in (("--accept-group", accept_groups), ("--reject-group", reject_groups)):
        for name in names:
            if name not in groups:
                raise CliError(
                    "FEN-2001",
                    f"{option}: no group {name!r}",
                    where=option,
                    hint=f"groups: {', '.join(sorted(groups)) or 'none'}",
                )
    floor = _LEVELS[args.min_confidence or "low"]
    old = confirmed or RoleSet()
    nets: dict[str, NetRole] = {role.net: role for role in old.nets}
    for role in roles.nets:
        if role.net in stated:
            continue
        chosen = role.net in accept or (args.accept_all and _LEVELS[role.confidence] >= floor)
        if chosen and role.source == "inferred":
            nets[role.net] = replace(role, source="confirmed")
    for name in reject:
        nets[name] = NetRole(name, "signal", "confirmed")
    nets.update(sets)
    for name, milliamps in currents.items():
        nets[name] = replace(nets.get(name) or replace(by_net[name], source="confirmed"), milliamps=milliamps)
    stored: dict[str, Any] = {group.name: group for group in (*old.loops, *old.kelvins, *old.gates)}
    for name, group in groups.items():
        if group.origin != "inferred":
            continue
        if name in accept_groups or (args.accept_all and _LEVELS[group.confidence] >= floor):
            stored[name] = replace(group, origin="confirmed")
    rejected = set(old.rejected) | set(reject_groups)
    for name in reject_groups:
        stored.pop(name, None)
    return RoleSet(
        nets=tuple(nets.values()),
        loops=tuple(g for g in stored.values() if isinstance(g, HotLoop)),
        kelvins=tuple(g for g in stored.values() if isinstance(g, KelvinPair)),
        gates=tuple(g for g in stored.values() if isinstance(g, GateLoop)),
        classes=old.classes,
        rejected=tuple(sorted(rejected)),
    )


def _inputs(args: argparse.Namespace, ctx: Context) -> Inputs | None:
    given = [option for option, name in MEASURING if getattr(args, name) not in (None, [], False)]
    if not args.check:
        if given:
            raise CliError("FEN-2001", f"{given[0]} goes with --check", where=given[0], hint="add --check")
        return None
    return Inputs(
        requirements=requirements_option(args.requirements, ctx.cwd),
        temp_rise_mk=temp_rise_option(args.temp_rise),
        copper_thickness=copper_thickness_option(args.copper_thickness),
        via_plating=None if args.via_plating is None else length_option(args.via_plating, "--via-plating"),
        board_thickness=None
        if args.board_thickness is None
        else length_option(args.board_thickness, "--board-thickness"),
        pour_grid=None if args.pour_grid is None else length_option(args.pour_grid, "--pour-grid"),
        split=bool(args.split),
        arc_tol=ARC_TOL_NM if args.arc_tol is None else length_option(args.arc_tol, "--arc-tol"),
    )


def _rows(judged: Judged, nets: Sequence[str], kinds: Sequence[str]) -> list[dict[str, Any]]:
    pads = judged.resolved.inferred.pads
    rows: list[dict[str, Any]] = []
    for role in judged.resolved.roles.nets:
        if nets and not any(fnmatch.fnmatchcase(role.net, glob) for glob in nets):
            continue
        if role.kind not in kinds:
            continue
        rows.append(
            {
                "net": role.net,
                "kind": role.kind,
                "source": role.source,
                "rule": role.rule,
                "confidence": role.confidence,
                "pads": list(pads.get(role.net, ())) if role.source == "inferred" else [],
                "milliamps": role.milliamps,
                "working_mv": role.working_mv,
                "sensitive": role.sensitive,
            }
        )
    return rows


def _relative(path: Path, cwd: Path) -> str:
    """``path`` relative to ``cwd`` in POSIX form, or absolute when it has no relative form (another drive
    on Windows)."""
    try:
        return Path(os.path.relpath(path, cwd)).as_posix()
    except ValueError:
        return path.as_posix()


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    kinds = _kinds(args.kinds)
    classes = _classes(args.classes)
    inputs = _inputs(args, ctx)
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.exists():
        raise CliError("FEN-3001", f"{args.path} does not exist", where=path.name)
    board = _board(path)
    backend = registry.for_path(board)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {board.name}", hint="pass a board file")
    read = backend.read(board)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{board.name} is not a board", hint="pass a board file")
    pad_issues: list[Issue] = []
    pads: tuple[BoardPad, ...] = (
        tuple(backend.board_pads(design, issues=pad_issues)) if isinstance(backend, BoardFrame) else ()
    )
    root = board.parent
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
            board,
            model_roles=model.rules.roles if model is not None and model.rules is not None else None,
            built=built,
            root=root,
            given=roles_file,
        )
    except FormatError as error:
        raise CliError("FEN-3004", str(error), where=error.locator or error.file) from None
    declared, confirmed = split_roles(stored.roles) if stored.built else (None, stored.roles)
    before = confirmed
    circuit = model.circuit if model is not None else None
    judged = run(
        design, pads, circuit=circuit, stored=confirmed, declared=declared, classes=classes, check=False
    )
    changed = _changed(args, judged, declared, confirmed)
    if changed is not None:
        confirmed = changed
    if changed is not None or inputs is not None:
        judged = run(
            design,
            pads,
            circuit=circuit,
            stored=confirmed,
            declared=declared,
            classes=classes,
            inputs=inputs,
            check=inputs is not None,
        )
    roles = judged.resolved.roles
    result: dict[str, Any] = {
        "roles": _rows(judged, args.nets, kinds),
        "loops": [record_json(group) for group in roles.loops],
        "kelvins": [record_json(group) for group in roles.kelvins],
        "gates": [record_json(group) for group in roles.gates],
        "classes": {
            ref: {
                "class": found.cls,
                "confidence": found.confidence,
                "evidence": found.evidence,
                "terminals": {name: list(pins) for name, pins in found.terminals.items()},
            }
            for ref, found in sorted(judged.resolved.classes.items())
        },
        "store": {  # relative to the board's folder: a reply holds no absolute path
            "file": _relative(stored.target, root),
            "built": stored.built,
            "read": None if stored.source is None else _relative(stored.source, root),
        },
    }
    if inputs is not None:
        result["measures"] = [measure.to_json() for measure in judged.measured.measures]
        result["summary"] = dict(judged.summary)
        role_rows = cast(Sequence[Mapping[str, object]], judged.summary.get("requirements", []))
        circuit_rows: Sequence[Mapping[str, object]] = []
        if model is not None:
            roles_now = merged(declared, before, classes)
            circuit_rows = circuit_requirements(model, root, roles_now, inputs, _currents(args.currents))
        result["requirements"] = joined(role_rows, circuit_rows)  # change c0253: one table
    writes: tuple[PlannedWrite, ...] = ()
    if changed is not None:
        target = _relative(stored.target, ctx.cwd)
        if stored.built:
            text = stored.target.read_text(encoding="utf-8")
            data = updated_rules(text, merged(declared, confirmed, classes), file=stored.target.name)
            writes = (PlannedWrite(target, data, "json"),)
        else:
            mine = confirmed if confirmed is not None else RoleSet()
            mine = replace(mine, classes=(*mine.classes, *classes)) if classes else mine
            writes = (PlannedWrite(target, dumps_document(_unique_classes(mine)), "json"),)
    raw = board.read_bytes()
    issues = (*[found for found in read.issues if found.severity == "error"], *pad_issues, *judged.issues)
    return Result(
        result=result,
        issues=tuple(dict.fromkeys(issues)),
        evidence=judged.evidence if inputs is not None else EVIDENCE,
        input=InputRef(
            path=board.name, sha256=hashlib.sha256(raw).hexdigest(), kind="board", format_version=None
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, board, stored.source, args.requirements),
    )


def circuit_requirements(
    model: Design, root: Path, roles: RoleSet, inputs: Inputs, given: Mapping[str, int]
) -> list[dict[str, object]]:
    """The requirement rows of the stage ``circuit.rules`` on the ``.fenolite/`` model of a built project
    (change c0253), with the roles in force and the currents of ``[[current]]`` rows and then ``--current``
    (the order of roles), each with its basis: the row's ``source`` text, ``requirements.toml`` or
    ``--current``."""
    from fenolite.analysis.requirements import Requirements
    from fenolite.checks.circuit import judge_circuit
    from fenolite.cli._contracts import classes_of, devices_of
    from fenolite.core.requirement_table import table_json

    currents: dict[str, tuple[Fraction, str]] = {}
    requirements = inputs.requirements
    if isinstance(requirements, Requirements):
        for net in model.circuit.nets:
            row = requirements.current_for(net, model.circuit)
            if row is not None:
                currents[net.name] = (Fraction(row.milliamps, 1000), row.source or "requirements.toml")
    for name, milliamps in given.items():
        currents.setdefault(name, (Fraction(milliamps, 1000), "--current"))
    rules = model.rules if model.rules is not None else None
    judged_model = model if rules is None else replace(model, rules=replace(rules, roles=roles or None))
    devices = devices_of(model, root)
    found = judge_circuit(
        judged_model, devices=devices, classes=classes_of(judged_model, devices), currents=currents
    )
    return table_json(found.rows)


def _unique_classes(roles: RoleSet) -> RoleSet:
    return replace(roles, classes=tuple({found.ref: found for found in roles.classes}.values()))


COMMAND = Command(
    name="roles",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="roles",
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--roles", "board.roles.json", "--accept-all"),
)

__all__ = ["COMMAND", "HELP"]
