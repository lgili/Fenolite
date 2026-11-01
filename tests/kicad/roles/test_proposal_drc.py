# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Proposals on the reference boards judged by the running ``kicad-cli`` (change c0280; capability net-roles,
"Proposals on the reference boards", scenario "KiCad finds no unconnected item"; hypothesis
``H-K-PROP-DRC``).

Each role-copper variant (``good_roles.py``, ``bad_roles.py``) is built for the tool's major, its inferred
roles and groups confirmed, its critical routes written (phase 2), then ``route --propose`` runs and the test
accepts, per proposal that holds an open connection, the first candidate that lowers ``open`` with no new
copper-check or role finding of warning or above, and rejects each ``group`` proposal, as
``tests/unit/roles/test_proposal_reference.py`` does. KiCad's DRC of the accepted board, after a refill
(``fenolite fill`` with ``kicad-cli`` 10; on 9, which refills no zone, the board carries the fill of the unit
tests, ``fill_as_outline``, on the copy that DRC reads), finds no unconnected item, and on both majors no
violation type with more entries than the board after phase 2. The proposals are made on the board as built,
its zones unfilled (the simulated pour), on both majors.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _probes import runner
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main
from fenolite.geometry import available_backends

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "roles"))
from _roleboards import EXAMPLES, fill_as_outline  # noqa: E402

pytestmark = pytest.mark.needs_kicad
CASES = [(board, variant) for board in ("buck_shunt", "half_bridge", "bms") for variant in ("good", "bad")]
ROUTE = ("--router", "octilinear")
UNCONNECTED = "unconnected_items"


def _fenolite(*args: str) -> tuple[int, dict[str, Any], str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue() or "{}"), stderr.getvalue()


def _planned(board: Path, *args: str) -> None:
    code, env, err = _fenolite("route", str(board), *ROUTE, *args, "--dry-run")
    assert code == 0, (err, env.get("issues"))
    plan = env["result"].get("plan_id")
    if plan:
        code, _, err = _fenolite("route", str(board), *ROUTE, *args, "--confirm", "--plan", plan)
        assert code == 0, err


def _build(board: str, variant: str, folder: Path, major: int) -> Path:
    source = EXAMPLES / board
    src = folder / "src"
    src.mkdir(parents=True)
    libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
    for table in ("sym-lib-table", "fp-lib-table"):
        text = (source / table).read_text(encoding="utf-8")
        (src / table).write_text(text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8")
    for name in (f"{board}_board.py", "requirements.toml", f"{variant}_roles.py"):
        if (source / name).is_file():
            shutil.copy(source / name, src / name)
    out = folder / "out"
    code, env, err = _fenolite(
        "build",
        str(src / f"{variant}_roles.py"),
        "--out",
        str(out),
        "--kicad-version",
        str(major),
        "--confirm",
    )
    assert code == 0, (env, err)
    (pcb,) = sorted(out.glob("*.kicad_pcb"))
    code, _, err = _fenolite("roles", str(pcb), "--accept-all", "--confirm")
    assert code == 0, err
    _planned(pcb, "--roles", "critical")
    return pcb


def _drc(board: Path, cli: str, major: int, folder: Path) -> Counter[str]:
    """KiCad's DRC of a copy of ``board``, refilled by ``kicad-cli`` 10 first; on 9, which refills no zone,
    with the fill of the unit tests (``fill_as_outline``)."""
    copy = folder / board.parent.name
    shutil.copytree(board.parent, copy)
    target = copy / board.name
    if major >= 10:
        code, env, err = _fenolite("fill", str(target), "--kicad-cli", cli, "--confirm")
        assert code == 0, (env, err)
    else:
        target.write_text(fill_as_outline(target.read_text(encoding="utf-8")), encoding="utf-8")
    report = runner().drc(
        target, files={target.with_suffix(".kicad_pro").name: target.with_suffix(".kicad_pro")}
    )
    assert report.report is not None
    return Counter(item.type for item in report.report.violations if not item.excluded)


def _clean(candidate: dict[str, Any]) -> bool:
    facts = candidate["facts"]
    roles = facts.get("roles", {}).get("new", [])
    return (
        facts["open"]["after"] < facts["open"]["before"]
        and not facts["copper_check"]["new"]
        and not [row for row in roles if row["severity"] in ("warning", "error")]
    )


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_accepted_proposals_pass_drc(tmp_path: Path, board: str, variant: str) -> None:
    """``H-K-PROP-DRC``: zero ``unconnected_items`` and no violation type with more entries than after
    phase 2."""
    if "clipper" not in available_backends():
        pytest.skip(
            "the role-copper planner needs the geo extra (clipper) to make the reference boards' copper"
        )
    cli = kicad_cli()
    major = kicad_cli_major()
    assert cli is not None and major is not None
    pcb = _build(board, variant, tmp_path / "build", major)
    before = _drc(pcb, cli, major, tmp_path / "before")
    code, env, err = _fenolite("route", str(pcb), *ROUTE, "--propose", "--candidates", "2")
    assert code == 0, err
    args: list[str] = []
    rejected: list[str] = []
    for proposal in env["result"]["proposals"]:
        if proposal["kind"] == "group":
            rejected.append(proposal["id"])
            continue
        chosen = next((c for c in proposal["candidates"] if _clean(c)), None)
        assert chosen is not None, proposal["subject"]
        args.append(f"--accept={chosen['id']}")
    if rejected:
        args += [*(f"--reject={i}" for i in rejected), "--reason", "recorded by the reference gate"]
    assert args
    _planned(pcb, *args)
    after = _drc(pcb, cli, major, tmp_path / "after")
    if major >= 10:  # on 9 the outline fill of the unit tests stands for KiCad's: only no growth is claimed
        assert after[UNCONNECTED] == 0, (dict(before), dict(after))
    worse = {kind: count for kind, count in after.items() if count > before.get(kind, 0)}
    assert not worse, (dict(before), dict(after))
