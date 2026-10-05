# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The export plan against the fake ``kicad-cli`` (capability manufacturing-exports, "Export kinds and their
arguments"; change c0024). Hermetic."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import FIXTURE, created_board
from _fakecli import GERBER, calls, fake_kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board
from fenolite.exports import ISSUE_CODES, plan
from fenolite.exports.plan import KINDS, Kind, arguments, gerber_layers, layer_suffixes, run_kind
from fenolite.model.design import Design

FORBIDDEN = ("--check-zones", "--board-plot-params")


@pytest.fixture(scope="module")
def design() -> Design:
    return read_board(FIXTURE)


def _without(design: Design, *names: str) -> Design:
    assert design.board is not None
    layers = tuple(layer for layer in design.board.layers if layer.name not in names)
    return dataclasses.replace(design, board=dataclasses.replace(design.board, layers=layers))


def test_gerber_layers_of_a_two_copper_board(design: Design) -> None:
    layers = gerber_layers(design)
    assert layers[:2] == ("F.Cu", "B.Cu") and layers[-1] == "Edge.Cuts"
    assert layers[2:-1] == ("F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS")
    assert not any("Fab" in name or "CrtYd" in name for name in layers)


def test_gerber_layers_keep_the_stack_order_of_inner_copper() -> None:
    layers = gerber_layers(created_board(4))
    assert layers[:4] == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def test_gerber_layers_of_a_board_without_paste(design: Design) -> None:
    layers = gerber_layers(_without(design, "F.Paste", "B.Paste"))
    assert "F.Paste" not in layers and "B.Paste" not in layers and "F.Mask" in layers


def test_layer_suffixes_know_the_shown_name(design: Design) -> None:
    suffixes = layer_suffixes(design)
    assert suffixes["F_Cu"] == "F.Cu" and suffixes["F_SilkS"] == "F.SilkS"
    assert suffixes["F_Silkscreen"] == "F.SilkS" and suffixes["Edge_Cuts"] == "Edge.Cuts"
    bare = dataclasses.replace(
        design,
        board=dataclasses.replace(
            design.board,  # type: ignore[arg-type]
            layers=tuple(dataclasses.replace(la, ext={}) for la in design.board.layers),  # type: ignore[union-attr]
        ),
    )
    assert layer_suffixes(bare)["B_Silkscreen"] == "B.SilkS"


def test_arguments_per_kind() -> None:
    assert arguments("gerbers", stem="b", layers=("F.Cu", "Edge.Cuts")) == [
        "pcb", "export", "gerbers", "-o", "gerbers/", "--no-protel-ext", "--layers", "F.Cu,Edge.Cuts",
    ]  # fmt: skip
    assert arguments("drill", stem="b") == [
        "pcb", "export", "drill", "-o", "drill/", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "--drill-origin", "absolute",
    ]  # fmt: skip
    assert arguments("pos", stem="b") == [
        "pcb", "export", "pos", "-o", "pos/b-pos.csv", "--format", "csv", "--units", "mm", "--side", "both",
    ]  # fmt: skip
    assert arguments("ipcd356", stem="b") == ["pcb", "export", "ipcd356", "-o", "netlist/b.d356"]


def test_forbidden_options_are_absent() -> None:
    """One argument table serves both majors, and no kind passes an option that changes the board."""
    assert list(KINDS) == ["gerbers", "drill", "pos", "ipcd356"]
    for kind, entry in KINDS.items():
        assert entry.majors == (9, 10)
        args = arguments(kind, stem="b", layers=("F.Cu",))
        assert not set(FORBIDDEN) & set(args), kind


def test_artifacts_from_a_fake_run(tmp_path: Path, design: Design) -> None:
    files = {"{stem}-F_Cu.gbr": GERBER, "{stem}-Edge_Cuts.gbr": GERBER}
    script = fake_kicad_cli(tmp_path / "bin", export_files={"gerbers": files}, writes=("b.kicad_prl",))
    board = tmp_path / "b.kicad_pcb"
    board.write_bytes(FIXTURE.read_bytes())
    result = run_kind(KicadCli(script), "gerbers", board, {}, major=10, design=design)
    assert result.issues == ()
    assert [(a.path, a.layer) for a in result.artifacts] == [
        ("gerbers/b-Edge_Cuts.gbr", "Edge.Cuts"),
        ("gerbers/b-F_Cu.gbr", "F.Cu"),
    ]
    assert all(
        a.kind == "gerbers" and a.data == GERBER.encode() and not a.repeatable for a in result.artifacts
    )
    assert result.tool_writes == ("b.kicad_prl",)
    args = calls(script)[-1]["args"]
    assert args[args.index("--layers") + 1].startswith("F.Cu,B.Cu,") and args[-1] == "b.kicad_pcb"


def test_job_file_and_unknown_suffix_have_no_layer(tmp_path: Path, design: Design) -> None:
    files = {"{stem}-job.gbrjob": "{}", "{stem}-Mystery.gbr": GERBER, "{stem}-F_Silkscreen.gbr": GERBER}
    script = fake_kicad_cli(tmp_path / "bin", export_files={"gerbers": files})
    result = run_kind(KicadCli(script), "gerbers", FIXTURE, {}, major=10, design=design)
    assert {a.path: a.layer for a in result.artifacts} == {
        "gerbers/two_layer-F_Silkscreen.gbr": "F.SilkS",
        "gerbers/two_layer-Mystery.gbr": None,
        "gerbers/two_layer-job.gbrjob": None,
    }


def test_single_file_kinds(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin"))
    pos = run_kind(cli, "pos", FIXTURE, {}, major=9)
    assert [(a.path, a.layer, a.repeatable) for a in pos.artifacts] == [("pos/two_layer-pos.csv", None, True)]
    netlist = run_kind(cli, "ipcd356", FIXTURE, {}, major=9)
    assert [a.path for a in netlist.artifacts] == ["netlist/two_layer.d356"]
    drill = run_kind(cli, "drill", FIXTURE, {}, major=9)
    assert [a.path for a in drill.artifacts] == ["drill/two_layer-NPTH.drl", "drill/two_layer-PTH.drl"]


def test_failed_kind(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin", export_fail=("drill",)))
    result = run_kind(cli, "drill", FIXTURE, {}, major=10)
    assert result.artifacts == ()
    (failure,) = result.issues
    assert failure.code == "export.failed" and failure.severity == "error" and failure.where == "drill"
    assert "Failed to plot" in failure.message and "two_layer.kicad_pcb" in failure.message
    assert "<tmp>" not in failure.message and "fenolite-kicad-" not in failure.message


def test_a_run_that_writes_nothing_fails(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin", export_files={"pos": {}}))
    (failure,) = run_kind(cli, "pos", FIXTURE, {}, major=10).issues
    assert failure.code == "export.failed" and "wrote no file" in failure.message


def test_timeout_is_retryable(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin", sleep=5.0), timeout=0.5)
    (failure,) = run_kind(cli, "pos", FIXTURE, {}, major=10).issues
    assert failure.code == "export.failed" and failure.retryable and "timed out" in failure.message


def test_unavailable_kind_runs_no_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    only_ten = dataclasses.replace(KINDS["pos"], majors=(10,))
    monkeypatch.setattr(plan, "KINDS", {**KINDS, "pos": only_ten})
    script = fake_kicad_cli(tmp_path / "bin")
    (failure,) = run_kind(KicadCli(script), "pos", FIXTURE, {}, major=9).issues
    assert failure.code == "export.kind-unavailable" and failure.where == "pos"
    assert calls(script) == []


def test_issue_codes() -> None:
    assert dict(ISSUE_CODES) == {
        "export.failed": "error",
        "export.kind-unavailable": "error",
        "render.failed": "warning",
        "assembly.template-invalid": "error",
        "bom.property-missing": "info",
        "pnp.no-outline": "error",
    }
    assert isinstance(KINDS["gerbers"], Kind)
