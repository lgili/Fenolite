# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``Pad.fab_property`` (capability design-model, "Assembly and test pad properties in the model";
change c0118)."""

from __future__ import annotations

import dataclasses
import json
import typing
from pathlib import Path

import pytest

from fenolite.core.coords import Point, Size
from fenolite.model import canonical
from fenolite.model.board import Board, FootprintInstance, Pad, PadFabProperty
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = {
    "0.2.0": ROOT / "tests" / "data" / "model" / "v0.2.0" / "blink_2layer.board.json",
    "0.2.1": ROOT / "tests" / "data" / "model" / "v0.2.1" / "blink_2layer.board.json",
}
SCHEMAS = ROOT / "schemas" / "fenolite.model.v0"
VALUES = (
    "bga", "fiducial_global", "fiducial_local", "test_point", "heatsink", "castellated", "mechanical",
    "press_fit",
)  # fmt: skip
PAD = Pad(id="pad_1", number="1", shape="rect", size=Size(1_000_000, 1_000_000), position=Point(0, 0))


def design_with(pad: Pad) -> Design:
    design = Design.new("marks", seed=1)
    assert design.board is not None
    instance = FootprintInstance(
        id="fpi_1", component_id="", lib_ref="Local:TP", position=Point(0, 0), pads=(pad,)
    )
    return dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(instance,)))


def test_the_eight_values() -> None:
    assert typing.get_args(PadFabProperty) == VALUES


def test_no_mark_by_default() -> None:
    """Scenario "No mark by default"; the field is the last one of ``Pad``."""
    assert PAD.fab_property is None
    assert dataclasses.fields(Pad)[-1].name == "fab_property"
    assert all("fab_property" not in text for text in canonical.dump_texts(design_with(PAD)).values())


def test_a_test_point_pad_in_board_json(tmp_path: Path) -> None:
    """Scenario "A test-point pad in board.json"."""
    design = design_with(dataclasses.replace(PAD, fab_property="test_point"))
    texts = canonical.dump_texts(design)
    assert '"fab_property": "test_point"' in texts["board.json"]
    canonical.dump_dir(design, tmp_path)
    assert canonical.load_dir(tmp_path) == design


@pytest.mark.parametrize("value", VALUES)
def test_every_value_round_trips(value: PadFabProperty) -> None:
    pad = dataclasses.replace(PAD, fab_property=value)
    assert canonical.loads(canonical.dumps(pad), Pad) == pad


def test_the_model_does_not_judge_the_mark() -> None:
    """A mark that KiCad's DRC flags (``castellated`` on an SMD pad) is still a valid model value."""
    assert dataclasses.replace(PAD, fab_property="castellated").kind == "smd"


@pytest.mark.parametrize("release", sorted(FIXTURES))
def test_fixture_of_an_earlier_release_keeps_its_bytes(release: str) -> None:
    """A model document of an earlier release loads as it is. The fixture of 0.2.0 comes with change
    c0126, which is not on this base: its case runs once the file exists."""
    path = FIXTURES[release]
    if not path.is_file():
        pytest.skip(f"{path.relative_to(ROOT)} comes with change c0126")
    text = path.read_text(encoding="utf-8")
    assert canonical.dumps(canonical.loads(text, Board)) == text


@pytest.mark.parametrize("name", ["board.json", "library.json"])
def test_the_schemas_list_the_key(name: str) -> None:
    """Board pads and library pads alike: an optional property with the eight values."""
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    pad = schema["$defs"]["Pad"]
    assert "fab_property" not in pad.get("required", ())
    assert pad["properties"]["fab_property"]["anyOf"][0]["enum"] == list(VALUES)


def test_the_design_model_page() -> None:
    page = " ".join((ROOT / "docs" / "design-model.md").read_text(encoding="utf-8").split())
    assert page.count("fab_property") >= 2
    assert all(f"`{value}`" in page for value in VALUES)
    assert "cannot read a model document that carries the key `fab_property`" in page
