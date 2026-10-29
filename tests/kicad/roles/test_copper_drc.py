# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role-copper scripts on ``kicad-cli`` (change c0243, task 5.4; capability net-roles, "Role copper
evidence", scenario "DRC on the bench").

Each ``<variant>_roles.py`` script is built for the running KiCad major, beside the same script without its
``design.role_copper()`` call (the board without role copper). KiCad 10 fills both (``fenolite fill``);
``kicad-cli`` 9 refills no zone, so there the role zones stay unfilled and what only their fill reaches
dangles. KiCad's DRC then finds no violation type with more entries on the board with role copper than on
the board without it, unconnected items aside (the board without role copper lacks its power copper, so its
count of those says nothing), and on KiCad 9 the dangling vias and tracks of the unfilled zones too.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "roles"))
from _roleboards import BOARDS, EXAMPLES, VARIANTS  # noqa: E402

pytestmark = pytest.mark.needs_kicad
CASES = [(board, variant) for board in BOARDS for variant in VARIANTS]
UNCONNECTED = "kicad.drc.unconnected-items"
UNFILLED = ("kicad.drc.via-dangling", "kicad.drc.track-dangling")
"""What an unfilled zone leaves dangling: a stitching via or a joining track that only the fill reaches.
``kicad-cli`` 9 refills no zone, so these are set aside there."""


def _fenolite(*args: str) -> tuple[int, dict[str, object]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {"stderr": stderr.getvalue()}


def _scripts(board: str, variant: str, folder: Path) -> tuple[Path, Path]:
    """The role script and the same script without ``design.role_copper(...)``, beside a copy of the board
    module, its requirements and library tables that point at the repository's libraries."""
    source = EXAMPLES / board
    folder.mkdir(parents=True)
    libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
    for table in ("sym-lib-table", "fp-lib-table"):
        text = (source / table).read_text(encoding="utf-8")
        (folder / table).write_text(
            text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8"
        )
    for name in (f"{board}_board.py", "requirements.toml"):
        if (source / name).is_file():
            shutil.copy(source / name, folder / name)
    text = (source / f"{variant}_roles.py").read_text(encoding="utf-8")
    with_copper = folder / f"{variant}_roles.py"
    with_copper.write_text(text, encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("design.role_copper(")]
    assert len(lines) == len(text.splitlines()) - 1
    without = folder / f"{variant}_bare.py"
    without.write_text(
        "\n".join(lines).replace(f'"{board}_{variant}_roles"', f'"{board}_{variant}_bare"') + "\n"
    )
    return with_copper, without


def _violations(script: Path, out: Path, cli: str, major: int) -> Counter[str]:
    code, envelope = _fenolite(
        "build", str(script), "--out", str(out), "--kicad-version", str(major), "--confirm"
    )
    assert code == 0, [
        i for i in envelope.get("issues", []) if isinstance(i, dict) and i["severity"] == "error"
    ]
    if major >= 10:
        code, envelope = _fenolite("fill", str(out), "--kicad-cli", cli, "--confirm")
        assert code == 0, envelope
    code, envelope = _fenolite("check", str(out), "--stages", "drc.kicad", "--kicad-cli", cli)
    assert code in (0, 5), envelope
    issues = envelope.get("issues", [])
    assert isinstance(issues, list)
    return Counter(str(i["code"]) for i in issues if str(i["code"]).startswith("kicad.drc."))


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_role_copper_on_kicad(tmp_path: Path, board: str, variant: str) -> None:
    cli = kicad_cli()
    major = kicad_cli_major()
    assert cli is not None and major is not None
    with_copper, without = _scripts(board, variant, tmp_path / "src")
    found = _violations(with_copper, tmp_path / "roles", cli, major)
    base = _violations(without, tmp_path / "bare", cli, major)
    aside = {UNCONNECTED, *(UNFILLED if major < 10 else ())}
    worse = {kind: count for kind, count in found.items() if kind not in aside and count > base.get(kind, 0)}
    assert not worse, (dict(found), dict(base))
