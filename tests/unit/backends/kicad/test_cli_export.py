# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadCli.export`` and ``render`` against the fake ``kicad-cli`` (capability kicad-oracle, "Export runs
through the package runner"; change c0024). Hermetic."""

from __future__ import annotations

from pathlib import Path

from _fakecli import GERBER, calls, fake_kicad_cli

from fenolite.backends.kicad.cli import RENDER_DIR, KicadCli
from fenolite.backends.kicad.plot import view_digest

BOARD = Path(__file__).resolve().parents[3] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
GERBERS = ["pcb", "export", "gerbers", "-o", "gerbers/", "--no-protel-ext"]


def test_output_folder_exists_for_the_run(tmp_path: Path) -> None:
    """The fake fails when its ``-o`` folder is missing, so a passing run proves the folder was created."""
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin"))
    run = cli.export(GERBERS, BOARD, out="gerbers")
    assert run.ok, run.stderr
    assert run.outputs["gerbers/two_layer-F_Cu.gbr"] == GERBER.encode()
    assert sorted(run.outputs) == [
        "gerbers/two_layer-Edge_Cuts.gbr",
        "gerbers/two_layer-F_Cu.gbr",
        "gerbers/two_layer-job.gbrjob",
    ]
    missing = cli.run([*GERBERS, BOARD.name], files={BOARD.name: BOARD})
    assert missing.returncode == 1 and "missing" in missing.stderr


def test_board_name_is_the_last_argument(tmp_path: Path) -> None:
    script = fake_kicad_cli(tmp_path / "bin")
    KicadCli(script).export(GERBERS, BOARD, out="gerbers")
    assert calls(script)[-1]["args"] == [*GERBERS, "two_layer.kicad_pcb"]


def test_extra_files_are_copied_next_to_the_board(tmp_path: Path) -> None:
    rules = tmp_path / "two_layer.kicad_dru"
    rules.write_text("(version 1)\n", encoding="utf-8")
    script = fake_kicad_cli(tmp_path / "bin")
    KicadCli(script).export(GERBERS, BOARD, files={rules.name: rules}, out="gerbers")
    assert set(calls(script)[-1]["files"]) == {"two_layer.kicad_pcb", "two_layer.kicad_dru"}


def test_non_zero_exit_is_returned(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin", export_fail=("render",)))
    run = cli.render(BOARD, side="top", width=400, height=300)
    assert run.outcome == "exit" and run.returncode == 1
    assert run.outputs == {} and "<tmp>" in run.stderr


def test_render_writes_the_side_png(tmp_path: Path) -> None:
    script = fake_kicad_cli(tmp_path / "bin")
    run = KicadCli(script).render(BOARD, side="bottom", width=400, height=300)
    assert run.ok and run.outputs[f"{RENDER_DIR}/bottom.png"].startswith(b"\x89PNG")
    args = calls(script)[-1]["args"]
    assert args[:2] == ["pcb", "render"] and args[args.index("--side") + 1] == "bottom"
    assert args[args.index("--width") + 1] == "400" and args[args.index("--height") + 1] == "300"


def test_timeout_is_an_outcome(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin", sleep=5.0), timeout=0.5)
    run = cli.export(GERBERS, BOARD, out="gerbers")
    assert run.outcome == "timeout" and run.returncode is None


def test_view_digest_ignores_the_dated_title_of_an_svg() -> None:
    one = b"<svg>\n<title>SVG Image created as front.svg date 2026/10/03 08:31:11 </title>\n<g/>\n</svg>\n"
    two = one.replace(b"08:31:11", b"09:00:00")
    assert view_digest("front.svg", one) == view_digest("front.svg", two)
    assert view_digest("front.svg", one) != view_digest("front.svg", one.replace(b"<g/>", b"<g></g>"))
    assert view_digest("top.png", one) != view_digest("top.png", two)  # a PNG is hashed as it is
