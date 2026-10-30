# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library generate`` (change c0260, requirements "Library generate command", "Library verb
dispatch", "Library generate result" and "Generated footprints in an Altium PCB library")."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.backends import step as step_mod
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.kicad.mod import prepare_authored_definition, read_footprint, write_footprint
from fenolite.catalog.footprints import generate, read_package

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ROOT / "tests" / "data" / "packages"
SOIC = "SOIC8_B4.9x3.9_P1.27"


def _records(tmp_path: Path, *names: str) -> None:
    folder = tmp_path / "packages"
    folder.mkdir()
    for name in names:
        shutil.copyfile(PACKAGES / name, folder / name)


def _files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_plan_and_confirm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _records(tmp_path, "soic8.toml")
    before = _files(tmp_path)
    args = ("library", "generate", "packages/soic8.toml", "--out", "lib", "--no-pcblib")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, env
    assert _files(tmp_path) == before
    plan = env["result"]["plan"]
    paths = [w["path"] for w in plan]
    assert paths == [f"lib/Local.pretty/{SOIC}.kicad_mod", f"lib/Local.3dshapes/{SOIC}.step"]
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, env
    receipt = {w["path"]: w["sha256"] for w in env["receipt"]["written"]}
    assert set(receipt) == set(paths)
    for path in paths:
        assert hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() == receipt[path]
    footprint = generate(read_package((PACKAGES / "soic8.toml").read_text(encoding="utf-8"))).footprint
    assert footprint is not None
    mod = (tmp_path / paths[0]).read_text(encoding="utf-8")
    assert mod == write_footprint(prepare_authored_definition(footprint), target=10)
    assert (tmp_path / paths[1]).read_bytes() == step_mod.write_bodies(SOIC, footprint.bodies)
    back = read_footprint(tmp_path / paths[0], library="Local")
    assert [p.number for p in back.pads] == [p.number for p in footprint.pads]
    assert back.models == (f"${{KIPRJMOD}}/lib/Local.3dshapes/{SOIC}.step",)


def test_result_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _records(tmp_path, "soic8.toml", "chip0603.toml")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "generate", "packages/soic8.toml", "packages/chip0603.toml",
        "--out", "lib", "--library", "Mine", "--dry-run",
    )  # fmt: skip
    assert code == 0, env
    result = env["result"]
    assert (result["library"], result["out"], result["pcblib"]) == ("Mine", "lib", "lib/Mine.PcbLib")
    soic, chip = result["packages"]
    assert (soic["name"], soic["family"], soic["id"]) == (SOIC, "gullwing", f"Mine:{SOIC}")
    assert soic["stamp"] == "gullwing/1 manufacturer drawing/1"
    assert soic["land"]["source"] == "manufacturer" and soic["land"]["pad"] == [1520000, 600000]
    assert set(soic["land"]["deltas"]) == {"pad_length", "pad_width", "row_spacing"}
    assert soic["bodies"] == {"count": 17, "top": 1750000}
    assert soic["issues"] == ["package.land-override"]
    assert chip["stamp"] == "chip/1 lands/1 drawing/1 nominal"
    assert chip["land"]["source"] == "calculated" and chip["land"]["table"] == 1
    x0, y0, x1, y1 = chip["courtyard"]
    assert x0 < 0 < x1 and y0 < 0 < y1
    assert chip["files"] == [
        "lib/Mine.pretty/CHIP0603_B1.6x0.8.kicad_mod",
        "lib/Mine.3dshapes/CHIP0603_B1.6x0.8.step",
    ]


def test_result_of_a_connector_series(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "packages"
    folder.mkdir()
    text = (PACKAGES / "connector_xh.toml").read_text(encoding="utf-8")
    assert 'positions = "3..16"' in text
    (folder / "xh.toml").write_text(
        text.replace('positions = "3..16"', 'positions = "2..4"'), encoding="utf-8"
    )
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "generate", "packages/xh.toml", "--out", "lib", "--dry-run"
    )
    assert code == 0, env
    rows = env["result"]["packages"]
    assert [r["name"] for r in rows] == ["CONN2_XH_P2.5", "CONN3_XH_P2.5", "CONN4_XH_P2.5"]
    assert len({r["id"] for r in rows}) == 3
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "generate", "packages/xh.toml", "--out", "lib", "--positions", "3",
        "--dry-run",
    )  # fmt: skip
    assert code == 0 and [r["name"] for r in env["result"]["packages"]] == ["CONN3_XH_P2.5"]


def test_error_finding_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "packages"
    folder.mkdir()
    text = (PACKAGES / "soic8.toml").read_text(encoding="utf-8")
    (folder / "bad.toml").write_text(text.replace('span = "5.80mm..6.20mm"', 'span = "3.00mm..3.50mm"'))
    shutil.copyfile(PACKAGES / "chip0603.toml", folder / "chip0603.toml")
    before = _files(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "generate", "packages/chip0603.toml", "packages/bad.toml",
        "--out", "lib", "--confirm",
    )  # fmt: skip
    assert code == 5, env
    assert "package.dimensions-inconsistent" in [i["code"] for i in env["issues"]]
    assert env["result"]["packages"][1]["files"] == []
    assert _files(tmp_path) == before


def test_unreadable_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text('schema = "fenolite.package.v0"\nfamily = "chip"\n', encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "library", "generate", "bad.toml", "--out", "lib")
    assert code == 3 and error["code"] == "FEN-3004"
    code, _, error, _ = run(monkeypatch, tmp_path, "library", "generate", "none.toml", "--out", "lib")
    assert code == 3 and error["code"] == "FEN-3001"


@pytest.mark.parametrize(
    "extra",
    [
        (),
        ("--out", "/abs"),
        ("--out", "lib/Local.pretty"),
        ("--out", "lib", "--library", "a/b"),
        ("--out", "lib", "--positions", "3"),
        ("--out", "lib", "--diff", "x.pretty"),
    ],
)
def test_usage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra: tuple[str, ...]) -> None:
    _records(tmp_path, "soic8.toml")
    before = _files(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "library", "generate", "packages/soic8.toml", *extra)
    assert code == 2 and error["code"] == "FEN-2001", error
    assert _files(tmp_path) == before


def test_generate_flags_belong_to_generate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for args in (("x.kicad_pcb", "--out", "x.pretty", "--no-step"), ("symbol", "p.toml", "--no-pcblib")):
        code, _, error, _ = run(monkeypatch, tmp_path, "library", *args)
        assert code == 2 and error["code"] == "FEN-2001" and "library generate" in error["message"]


def test_board_form_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A board path is still the c0223 form, and a board folder named ``generate`` is passed as
    ``./generate``."""
    import sys

    sys.path.insert(0, str(ROOT / "tests" / "unit" / "library"))
    from test_derive import board_text  # pyright: ignore[reportMissingImports]

    board = tmp_path / "generate"
    board.mkdir()
    (board / "board.kicad_pcb").write_text(board_text(), encoding="utf-8", newline="\n")
    code, env, _, _ = run(monkeypatch, tmp_path, "library", "./generate", "--out", "lib.pretty", "--dry-run")
    assert code == 0, env
    assert env["result"]["board"] == "board.kicad_pcb"
    assert [w["path"] for w in env["result"]["plan"]] == [
        "lib.pretty/LED_THT_3mm.kicad_mod",
        "lib.pretty/R_0603.kicad_mod",
    ]


def test_pcblib_planned_with_the_footprints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _records(tmp_path, "soic8.toml", "qfn16.toml", "dip8.toml")
    args = ("library", "generate", "packages/soic8.toml", "packages/qfn16.toml", "packages/dip8.toml")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--out", "lib", "--dry-run")
    assert code == 0, env
    kinds = {w["path"]: w["kind"] for w in env["result"]["plan"]}
    assert kinds["lib/Local.PcbLib"] == "altium_pcblib"
    code, env, _, _ = run(
        monkeypatch, tmp_path, *args, "--out", "lib", "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, env
    assert "lib/Local.PcbLib" in [w["path"] for w in env["receipt"]["written"]]
    library = read_pcblib((tmp_path / "lib" / "Local.PcbLib").read_bytes(), file="Local.PcbLib")
    assert not [i for i in library.issues if i.severity == "error"]
    names = [r["name"] for r in env["result"]["packages"]]
    assert sorted(library.names) == sorted(names)
    dropped = [i for i in env["issues"] if i["code"] == "altium.primitive-dropped"]
    assert [i["where"] for i in dropped] == ["Local:QFN16_B3x3_P0.5_EP1.68x1.68"]
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--out", "lib2", "--no-pcblib", "--dry-run")
    assert code == 0 and env["result"]["pcblib"] is None
    assert not [w for w in env["result"]["plan"] if w["path"].endswith(".PcbLib")]
