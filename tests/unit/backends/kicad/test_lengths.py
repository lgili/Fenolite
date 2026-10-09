# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net lengths as KiCad counts them (capability board-frame, "KiCad net lengths"; capability
backend-protocol, "Length facts source"; change c0106). The hermetic half of the length benches: the
values are those the canaries of ``tests/kicad/length/test_length_parity.py`` bracket."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import _lengthbench as lb
import pytest

from fenolite.backends.base import LengthFacts
from fenolite.backends.kicad import lengths
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.model.board import Stackup

MAJORS = (10, 9)


def facts(case: str, major: int, **more: object) -> tuple[LengthFacts, list[Issue]]:
    issues: list[Issue] = []
    found = KicadBackend().length_facts(lb.read_bench(case, major), major=major, issues=issues, **more)  # type: ignore[arg-type]
    return found, issues


def test_via_heights_per_major() -> None:
    ten, _ = facts("four-explicit", 10)
    nine, _ = facts("four-explicit", 9)
    assert (ten.stackup, nine.stackup) == ("board", "board")
    assert dict(ten.depths) == {"F.Cu": 0, "In1.Cu": 153_750, "In2.Cu": 1_401_250, "B.Cu": 1_600_000}
    assert dict(nine.depths) == {"F.Cu": 17_500, "In1.Cu": 153_750, "In2.Cu": 1_401_250, "B.Cu": 1_582_500}
    assert (ten.nets["V_F_IN1"].vias, ten.nets["V_F_B"].vias) == (153_750, 1_600_000)
    assert (nine.nets["V_F_IN1"].vias, nine.nets["V_F_B"].vias) == (0, 1_565_000)
    assert nine.nets["V_BLIND"].vias == 136_250
    # the other rows of the four-layer table of the design
    assert [ten.nets[n].vias for n in ("V_F_IN2", "V_IN1_IN2", "V_IN1_B", "V_BLIND", "V_F_F", "V_THREE")] == [
        1_401_250, 1_247_500, 1_446_250, 153_750, 0, 1_600_000,
    ]  # fmt: skip
    nine_nets = ("V_F_IN2", "V_IN1_IN2", "V_IN1_B", "V_F_F", "V_THREE", "V_SERIES")
    assert [nine.nets[n].vias for n in nine_nets] == [
        0, 0, 0, 0, 1_565_000, 0,
    ]  # fmt: skip
    assert (ten.nets["V_SERIES"].vias, ten.nets["V_SERIES"].via_count) == (1_600_000, 2)
    # a zone fill is not copper a via joins
    assert (ten.nets["V_ZONE"].vias, nine.nets["V_ZONE"].vias, ten.nets["V_ZONE"].via_count) == (0, 0, 1)


def test_default_stackup() -> None:
    for major, height in ((10, 1_580_000), (9, 1_545_000)):
        found, issues = facts("two", major)
        assert found.stackup == "default" and found.major == major and found.count_vias
        assert [i.code for i in issues] == ["kicad.length.default-stackup"]
        assert issues[0].severity == "info"
        assert found.nets["L_VIA2"].vias == height
    four, _ = facts("four", 10)
    assert dict(four.depths) == {"F.Cu": 0, "In1.Cu": 532_500, "In2.Cu": 1_047_500, "B.Cu": 1_580_000}
    four9, _ = facts("four", 9)
    assert dict(four9.depths) == {"F.Cu": 17_500, "In1.Cu": 532_500, "In2.Cu": 1_047_500, "B.Cu": 1_562_500}
    assert four9.nets["V_BLIND"].vias == 515_000


def test_default_stackup_follows_the_file_thickness() -> None:
    text = lb.bench_text("two", 10)
    assert text.count("(thickness 1.6)") == 1
    from fenolite.backends.kicad.pcb import read_board

    thin = read_board(text.replace("(thickness 1.6)", "(thickness 1)"))
    assert thin.board is not None and lengths.board_thickness(thin.board) == 1_000_000
    found = lengths.length_facts(thin, major=10)
    assert found.nets["L_VIA2"].vias == 980_000
    created = lb.bench("two", 10)
    assert created.board is not None and lengths.board_thickness(created.board) == 1_600_000


def test_unknown_depths() -> None:
    design = lb.bench("four-explicit", 10)
    assert design.board is not None and isinstance(design.board.stackup, Stackup)
    short = dataclasses.replace(design.board.stackup, layers=design.board.stackup.layers[:3])
    broken = dataclasses.replace(design, board=dataclasses.replace(design.board, stackup=short))
    issues: list[Issue] = []
    found = lengths.length_facts(broken, major=10, issues=issues)
    assert found.stackup == "none" and not found.depths and not issues
    assert found.nets["V_F_B"].vias == 0 and found.nets["V_F_B"].via_count == 1


def test_unread_stackup_node_claims_no_depth() -> None:
    """A node the reader projects no stack-up from: KiCad 10.0.6 counts its thicknesses (the probe
    ``length-via-four-unprojected``), so the facts hold no depth and no default."""
    found, issues = facts("four-unprojected", 10)
    design = lb.read_bench("four-unprojected", 10)
    assert design.board is not None and design.board.stackup is None
    assert lengths.has_unread_stackup(design.board)
    assert found.stackup == "none" and not found.depths and not issues
    assert found.nets["V_F_B"].vias == 0 and found.nets["V_F_B"].total == 20_000_000


def test_a_pad_joins_a_via() -> None:
    ten, _ = facts("four-explicit", 10)
    nine, _ = facts("four-explicit", 9)
    assert (ten.nets["VIP"].vias, nine.nets["VIP"].vias) == (307_500, 0)
    assert (ten.nets["VIP"].total, nine.nets["VIP"].total) == (18_707_500, 18_400_000)
    assert (ten.nets["DOGBONE"].total, nine.nets["DOGBONE"].total) == (18_707_500, 18_400_000)
    assert (ten.nets["VIP_BOT"].total, nine.nets["VIP_BOT"].total) == (20_000_000, 19_965_000)
    design = lb.read_bench("four-explicit", 10)
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    pads = board_pads(design)
    joined = sorted(
        lengths.joined_layers(design, via, pads)
        for via in design.board.vias
        if names[via.net_id or ""] == "VIP"
    )
    assert joined == [("F.Cu", "In1.Cu"), ("F.Cu", "In1.Cu")]


def test_die_length_and_the_project_switch(tmp_path: Path) -> None:
    found, _ = facts("two", 10)
    assert (found.nets["L_DIE"].die, found.nets["L_DIE"].total) == (1_500_000, 19_900_000)
    assert list(found.die.values()) == [1_500_000]
    project = lb.write_case("two-noheight", 10, tmp_path)
    switched, _ = facts("two-noheight", 10, project=project)
    assert switched.count_vias is False
    assert (switched.nets["L_VIA2"].vias, switched.nets["L_VIA2"].total) == (0, 20_000_000)
    assert switched.nets["L_DIE"].total == 19_900_000
    assert (
        lengths.counts_via_heights(None)
        and lengths.counts_via_heights("{}")
        and lengths.counts_via_heights("{")
    )
    assert lengths.counts_via_heights(lb.NO_HEIGHT_PROJECT) is False
    assert lengths.counts_via_heights(lb.NO_HEIGHT_PROJECT.replace("false", "true"))


def test_bad_die_length() -> None:
    from fenolite.backends.kicad.pcb import read_board

    text = lb.bench_text("two", 10)
    assert text.count("(die_length 1.5)") == 1
    issues: list[Issue] = []
    found = lengths.length_facts(
        read_board(text.replace("(die_length 1.5)", "(die_length -2)")), major=10, issues=issues
    )
    assert found.nets["L_DIE"].die == 0
    bad = [i for i in issues if i.code == "kicad.length.bad-die"]
    assert len(bad) == 1 and bad[0].severity == "warning" and "R12-2" in bad[0].message


def test_major_from_the_project_then_the_file(tmp_path: Path) -> None:
    nine = lb.read_bench("two", 9)
    assert lengths.length_facts(nine).major == 9  # the board's source format
    assert lengths.length_facts(lb.bench("two", 9)).major == 10  # a created design: the default target
    project = lb.write_case("two", 9, tmp_path)  # a ``{}`` project names no major
    assert lengths.length_facts(nine, project=project).major == 9
    assert lengths.length_facts(nine, project=project, major=10).major == 10
    missing = dataclasses.replace(
        project, files={**project.files, "bench.kicad_pro": tmp_path / "gone.kicad_pro"}
    )
    assert lengths.length_facts(nine, project=missing).count_vias  # a file that fails to read never raises


@pytest.mark.parametrize("case", ["two", "two-stackup", "four", "four-explicit"])
def test_the_total_is_the_sum_of_its_parts(case: str) -> None:
    for major in MAJORS:
        found, _ = facts(case, major)
        design = lb.read_bench(case, major)
        assert design.board is not None
        used = {
            item.net_id
            for item in (*design.board.tracks, *design.board.arcs, *design.board.vias)
            if item.net_id is not None
        } | {pad.net_id for fp in design.board.footprints for pad in fp.pads if pad.net_id is not None}
        names = {net.id: net.name for net in design.circuit.nets}
        assert set(found.nets) == {names[net_id] for net_id in used}
        for length in found.nets.values():
            assert length.total == length.routed + length.vias + length.die
        assert found.evidence.level is Level.INFERRED


def test_only_the_nets_asked_for() -> None:
    found, _ = facts("two", 10, nets=("L_VIA2", "L_CC", "NOPE"))
    assert sorted(found.nets) == ["L_CC", "L_VIA2"]
    assert found.nets["L_VIA2"].total == 21_580_000


def test_codes_evidence_and_imports() -> None:
    assert dict(lengths.LENGTH_ISSUE_CODES) == {
        "kicad.length.default-stackup": "info",
        "kicad.length.bad-die": "warning",
    }
    assert lengths.EVIDENCE.level is Level.INFERRED
    assert lengths.EVIDENCE.hypotheses == (
        "H-K-NETLEN-STACKUP", "H-K-NETLEN-TOTAL", "H-K-NETLEN-VIA10", "H-K-NETLEN-VIA9",
    )  # fmt: skip
    assert (lengths.DEFAULT_COPPER_NM, lengths.DEFAULT_MASKS_NM) == (35_000, 20_000)
    tree = ast.parse(Path(lengths.__file__).read_text(encoding="utf-8"))
    allowed = (
        "fenolite.core",
        "fenolite.model",
        "fenolite.geometry",
        "fenolite.backends.base",
        "fenolite.backends.kicad",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("fenolite"):
            assert node.module.startswith(allowed), node.module
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
