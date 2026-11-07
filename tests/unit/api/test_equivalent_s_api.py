# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit S compares actual sheets, with hermetic raw reads and preserved connectivity (c0278)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from _equivalent_s import project, remove_one_junction, root
from _fidelity import snapshot
from _fidelity_corpus import materialize

from fenolite.api import SideUsageError, equivalent


def _hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        pytest.fail("level S started an external process")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


@pytest.mark.parametrize("name", ("flat", "full", "hier", "bus", "repeat"))
@pytest.mark.parametrize("raw", (False, True))
def test_actual_authored_sides_compare_all_drawn_content(
    name: str, raw: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = project(tmp_path / "original", name)
    before = snapshot(original)
    _hermetic(monkeypatch)
    side = root(original) if raw else original
    result = equivalent(side, side, level="S")
    reply = result.to_json()
    assert result.equivalent and reply["level"] == "S"
    assert len(reply["levels"]) == 1 and reply["levels"][0]["name"] == "schematic"
    assert reply["differences"] == [] and reply["excluded"] == []
    summary = reply["levels"][0]["summary"]
    assert summary["symbols"] >= 2 and summary["pins"] > 0 and summary["extraction_issues"] == 0
    assert "H-K-DRAWN-CONNECT" in result.evidence.hypotheses
    assert snapshot(original) == before


@pytest.mark.parametrize("name", ("hier", "bus", "repeat"))
def test_project_raw_root_and_built_cache_have_the_same_drawing(name: str, tmp_path: Path) -> None:
    original = project(tmp_path / "original", name, cache=True)
    for other in (root(original), original / ".fenolite", root(original).with_suffix(".kicad_pro")):
        reply = equivalent(original, other, level="S").to_json()
        assert reply["equivalent"], reply["differences"]


def test_schematic_comparison_does_not_require_or_read_a_board(tmp_path: Path) -> None:
    original = project(tmp_path / "original", "hier")
    sheet = root(original)
    board = next(original.glob("*.kicad_pcb"))
    board.write_text("deliberately unreadable board; S reads the actual schematic", encoding="utf-8")
    for side in (original, sheet.with_suffix(".kicad_pro")):
        result = equivalent(side, sheet, level="S")
        assert result.equivalent
        assert result.a.name == sheet.name and result.a.netlist_source == "schematic"
    board.unlink()
    assert equivalent(original, sheet, level="S").equivalent


def test_a_critical_junction_remains_both_a_missing_item_and_changed_net(tmp_path: Path) -> None:
    original = project(tmp_path / "original", crossing=True)
    changed = tmp_path / "changed"
    shutil.copytree(original, changed)
    assert equivalent(original, changed, level="S").equivalent
    remove_one_junction(changed, critical=True)
    result = equivalent(original, changed, level="S")
    assert not result.equivalent
    assert result.report is not None
    assert [(d.kind, d.field) for d in result.report.differences] == [
        ("item-missing", "junction"),
        ("drawn-net", "net"),
    ]


@pytest.mark.parametrize("flags", ({"strict": True}, {"ignore_refs": ("R1",)}, {"against": "kicad-import"}))
def test_s_does_not_silently_apply_a_different_comparison_rule(
    flags: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = project(tmp_path / "original")
    _hermetic(monkeypatch)
    with pytest.raises(SideUsageError):
        equivalent(original, None if "against" in flags else original, level="S", **flags)


def test_a_model_without_actual_sheets_is_not_a_schematic_side() -> None:
    from fenolite.model.design import Design

    model = Design.new("authored", seed=0)
    with pytest.raises(SideUsageError, match="side a has no drawn schematic"):
        equivalent(model, model, level="S")


@pytest.mark.parametrize("level", (True, "s", "other", "9"))
def test_unknown_levels_and_boolean_integers_stay_usage_faults(level: object) -> None:
    from fenolite.model.design import Design

    model = Design.new("authored", seed=0)
    with pytest.raises(SideUsageError, match="level is one of"):
        equivalent(model, model, level=level)


def test_a_specific_junction_exclusion_does_not_hide_changed_connectivity(tmp_path: Path) -> None:
    import _schema

    from fenolite.checks.equivalence import Profile, Rule

    original = project(tmp_path / "original", crossing=True)
    changed = tmp_path / "changed"
    shutil.copytree(original, changed)
    remove_one_junction(changed, critical=True)
    report = equivalent(original, changed, level="S").report
    assert report is not None
    (junction,) = [d for d in report.differences if d.kind == "item-missing"]
    rule = Rule(
        "authored-junction",
        "S",
        "item-missing",
        junction.where,
        "undecided",
        "planted test",
        "",
        field="junction",
    )
    profile = Profile("authored", "none", "none", "absolute", 0, 0, rules=(rule,))
    found = equivalent(original, changed, level="S", profile=profile)
    assert not found.equivalent and found.report is not None
    assert [d.kind for d in found.report.differences] == ["drawn-net"]
    assert [d.difference.kind for d in found.report.excluded] == ["item-missing"]
    assert _schema.validate(found.to_json(), _schema.load("fenolite.equivalent.v0.json")) == []


@pytest.mark.needs_corpus
@pytest.mark.parametrize("ident", ("kicad-demo-10-0-6-pcb-04", "kicad-demo-10-0-6-pcb-12"))
def test_public_native_projects_and_raw_sheets_compare_without_tools(
    ident: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = tomllib.loads((Path(__file__).resolve().parents[3] / "tests/corpus/manifest.toml").read_text())[
        "file"
    ]
    (board,) = [row for row in rows if row["id"] == ident]
    original = materialize(board, rows, tmp_path / "original")
    before = snapshot(original.parent if original.is_file() else original)
    _hermetic(monkeypatch)
    root_file = original.with_suffix(".kicad_sch") if original.is_file() else root(original)
    result = equivalent(original, root_file, level="S")
    assert result.equivalent, result.to_json()["differences"]
    assert result.report is not None
    summary = result.report.levels[0].summary
    assert summary["symbols"] > 0 and summary["pins"] > 0
    assert snapshot(original.parent if original.is_file() else original) == before


# Generated from the unchanged pre-S API at c4533497; canonical JSON of an authored fixture.
# The source module stayed only in the local proof folder; no historical implementation is vendored.
INTEGER_RESULT_SHA256 = {
    "default": "2594c14c009f167a3ce5650333ec81a3260141cc5f24818aed1e82413998ce00",
    "1": "47969e6da42801c598ee1f0cce4e28c20458c87c676fc40e8d7df8a26b2eb7e6",
    "2": "67504fab09ccfa79aea38958cd97c28c5e7dcddb27614b3493d1e1747821d89e",
    "3": "bc9c0b3389955aa9b0bd8548074391d996674c89cbdf99cc994fb4f4dc8ca125",
    "4": "5fb3fab7acac198038132b8e4e62e45a3a5bf5bf17e4b3c72f23b1be9d0d208d",
    "5": "2594c14c009f167a3ce5650333ec81a3260141cc5f24818aed1e82413998ce00",
    "6": "854c14a986bbc3bf94a153309b450b1ddec623f22f545067e172713b27bd955b",
    "7": "0ca85df1013640acb8038d5cd5d22e4d266bc0fe265819afc57c7d7e0cddc6c2",
    "5-strict": "adb164988ba6a4f59001f14642017c3c0315336e60fc2801755a1c245ed70f1d",
}


@pytest.mark.parametrize("case", tuple(INTEGER_RESULT_SHA256))
def test_integer_and_default_result_bytes_match_the_pre_s_api(case: str) -> None:
    board = Path(__file__).resolve().parents[2] / "data/kicad/board/two_layer.kicad_pcb"
    level = None if case == "default" else int(case.split("-", 1)[0])
    result = equivalent(board, board, level=level, strict=case == "5-strict").to_json()
    data = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(data).hexdigest() == INTEGER_RESULT_SHA256[case]
