# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role-copper reference builds (change c0243) read back for the tests: the board, its pads, the roles
its model stores, the plan of the same board without its role items, and the judgement on the simulated
pour as the reference tests of c0222 judge (every inferred role and group confirmed, the board's
requirements file)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _roleboards import EXAMPLES, Built, read
from _rolecheck import confirmed, inputs

from fenolite.backends.base import BoardPad
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet
from fenolite.roles import copper
from fenolite.roles.judge import Judged, run, split_roles


@dataclass(frozen=True, slots=True)
class Board:
    """A built board read back: the design, its pads, the circuit of its model and its roles by source."""

    design: Design
    pads: tuple[BoardPad, ...]
    circuit: object
    declared: RoleSet | None
    stored: RoleSet | None


def board(built: Built) -> Board:
    design, pads = read(built)
    model = load_dir(built.out / ".fenolite")
    declared, stored = split_roles(model.rules.roles if model.rules is not None else None)
    return Board(design, pads, model.circuit, declared, stored)


OUTCOMES: dict[Path, copper.Outcome | None] = {}
"""The planner's outcome of each role-copper build of the session, by output folder (``conftest``)."""


def build_role(script: Path, out: Path, *, target: str = "kicad") -> Built:
    """Build ``script`` as ``_roleboards.build_script`` does, without fills, keeping the planner's outcome in
    ``OUTCOMES``."""
    from _roleboards import build_script

    original = copper.run
    captured: list[copper.Outcome] = []

    def capture(*args: Any, **kwargs: Any) -> copper.Outcome:
        found = original(*args, **kwargs)
        captured.append(found)
        return found

    copper.run = capture  # type: ignore[assignment]
    try:
        built = build_script(script, out, target=target, fill=False)
    finally:
        copper.run = original
    OUTCOMES[built.out] = captured[-1] if captured else None
    return built


def variant(tmp: Path, name: str, body: str) -> Path:
    """A role-copper script of the reference board ``name`` in ``tmp``: its board module and library tables
    copied (the tables pointing at the repository's libraries), and ``body`` after ``make(...)``."""
    folder = EXAMPLES / name
    libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
    for table in ("sym-lib-table", "fp-lib-table"):
        text = (folder / table).read_text(encoding="utf-8")
        (tmp / table).write_text(text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8")
    module = f"{name}_board.py"
    (tmp / module).write_text((folder / module).read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp / "variant_roles.py"
    script.write_text(
        "# SPDX-License-Identifier: CC0-1.0\n"
        "# Authored for Fenolite as a test board; no file, value, name or layout comes from any other "
        "project.\n"
        f"from {name}_board import make\n\nfrom fenolite.dsl import Design, Net, amp, mm\n\n{body}\n",
        encoding="utf-8",
    )
    if (folder / "requirements.toml").is_file():
        (tmp / "requirements.toml").write_text((folder / "requirements.toml").read_text(encoding="utf-8"))
    return script


def outcome(built: Built) -> copper.Outcome:
    found = OUTCOMES.get(built.out)
    assert found is not None, built.out
    return found


def resolved(built: Built, *, accept: bool = True) -> tuple[Board, Judged]:
    """The board and its roles resolved as the reference tests resolve them (``accept``: every inferred role
    and group confirmed)."""
    held = board(built)
    found = run(
        held.design, held.pads, circuit=held.circuit, declared=held.declared, stored=held.stored, check=False
    )
    if accept:
        found = run(
            held.design,
            held.pads,
            circuit=held.circuit,
            declared=held.declared,
            stored=confirmed(found),
            check=False,
        )
    return held, found


def judged(built: Built, name: str) -> Judged:
    """The role findings of a built role-copper board on its simulated pour, every inferred role confirmed."""
    held = board(built)
    design = copper.with_simulated_fills(held.design, held.pads)
    first = run(
        design, held.pads, circuit=held.circuit, declared=held.declared, stored=held.stored, check=False
    )
    return run(
        design,
        held.pads,
        circuit=held.circuit,
        declared=held.declared,
        stored=confirmed(first),
        inputs=inputs(name),
    )


def findings(found: Judged) -> set[tuple[str, str, str]]:
    return {(i.code, i.severity, i.where) for i in found.issues if i.severity in ("warning", "error")}


__all__ = [
    "OUTCOMES",
    "Board",
    "board",
    "build_role",
    "findings",
    "judged",
    "outcome",
    "plan_on",
    "resolved",
    "variant",
]


def plan_on(
    built: Built, name: str, request: object | None = None, roles: RoleSet | None = None
) -> copper.RoleCopperPlan:
    """The planner on a built board read back (its role zones are then its own copper and obstacles of the
    other nets), every inferred role confirmed unless ``roles`` are given."""
    held, found = resolved(built)
    return copper.plan(
        held.design,
        held.pads,
        roles if roles is not None else found.resolved.roles,
        request,
        requirements=inputs(name).requirements,
        classes=found.resolved.classes,
    )


BARE_BUCK = (
    'design = make(Design("buck_bare"), "good", power=False)\ndesign.net_role(design.nets["GND"], "ground")'
)
"""The good buck without its power copper and without ``role_copper()``: a board drawn by hand, bare."""


def cli(*args: str) -> tuple[int, dict[str, Any]]:
    """``fenolite <args> --json`` in-process: the exit code and the envelope."""
    import contextlib
    import io
    import json

    import fenolite.cli.main as cli_main

    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--json"])
    text = stdout.getvalue()
    envelope: dict[str, Any] = json.loads(text) if text else {}
    envelope["stderr"] = stderr.getvalue()
    return code, envelope


def bare_buck(tmp: Path) -> Path:
    """The KiCad build of ``BARE_BUCK`` in ``tmp / "out"``; returns that folder."""
    script = variant(tmp, "buck_shunt", BARE_BUCK)
    out = tmp / "out"
    code, envelope = cli("build", str(script), "--out", str(out), "--confirm")
    assert code == 0, envelope
    return out
