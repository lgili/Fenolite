# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas, board items and the area selector in the model (capability design-model; change c0103)."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id, new_id
from fenolite.model import canonical
from fenolite.model.board import Board, Dimension, Keepout, Text
from fenolite.model.rules import LEAF_OPS, Rule, RuleSet, RuleSubject, Selector

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "data" / "model"
V020 = FIXTURES / "v0.2.0" / "blink_2layer.board.json"
"""The fixture that change c0126 commits; that change is not on this base."""
V021 = FIXTURES / "v0.2.1" / "blink_2layer.board.json"
SQUARE = (Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))
NEW_KEYS = ('"name"', '"h_justify"', '"v_justify"', '"dimensions"')


def board() -> Board:
    rng = random.Random(3)
    return Board(
        id=new_id("brd", rng),
        keepouts=(Keepout(id=new_id("kpo", rng), outline=SQUARE, layers=("F.Cu",), no_tracks=True),),
        texts=(
            Text(id=new_id("txt", rng), text="A", position=Point(1, 2), layer="F.SilkS", size=Size(10, 10),
                 thickness=2),
        ),
    )  # fmt: skip


def test_defaults() -> None:
    made = board()
    assert made.keepouts[0].name == "" and made.dimensions == ()
    assert (made.texts[0].h_justify, made.texts[0].v_justify) == ("center", "center")
    dimension = Dimension(id="dim_x", kind="aligned", layer="Dwgs.User", start=Point(0, 0), end=Point(5, 0),
                          offset=-2)  # fmt: skip
    assert (dimension.direction, dimension.units, dimension.precision) == (None, "mm", 4)
    assert (dimension.size, dimension.thickness, dimension.width) == (None, None, None)
    assert "area" in LEAF_OPS


def test_old_documents_still_load() -> None:
    """Scenario "Old documents still load": the canonical writer omits the defaults, so a document
    written before the new keys is the text a board without them gives."""
    text = canonical.dumps(board())
    assert not any(key in text for key in NEW_KEYS)
    loaded = canonical.loads(text, Board)
    assert loaded == board() and canonical.dumps(loaded) == text
    rules = RuleSet(
        id="rst_x",
        rules=(Rule(id="rul_x", name="r", kind="clearance", selector_a=Selector("net", "A"), min=1),),
    )
    assert canonical.loads(canonical.dumps(rules), RuleSet) == rules


@pytest.mark.parametrize("fixture", [V020, V021], ids=["v0.2.0", "v0.2.1"])
def test_v020_board_items(fixture: Path) -> None:
    """Scenario "A document of 0.2.0 still loads": a board document of a release keeps its bytes. The
    0.2.0 fixture comes with change c0126; the 0.2.1 fixture is the one this base holds."""
    if not fixture.is_file():
        pytest.skip(f"{fixture.relative_to(ROOT).as_posix()} comes with change c0126")
    text = fixture.read_text(encoding="utf-8")
    assert not any(key in text for key in NEW_KEYS[1:])
    loaded = canonical.loads(text, Board)
    assert canonical.dumps(loaded) == text
    assert loaded.dimensions == () and all(k.name == "" for k in loaded.keepouts)
    sentence = "0.2.x cannot read a model document that carries"
    for page in ("docs/design-model.md", "CHANGELOG.md"):
        assert sentence in " ".join((ROOT / page).read_text(encoding="utf-8").split()), page


def test_new_keys_round_trip() -> None:
    made = board()
    dimension = Dimension(
        id=derived_id("dim", "dsl", "dimension:width"), kind="orthogonal", layer="Dwgs.User",
        start=Point(0, 0), end=Point(50, 3), offset=-5, direction="horizontal", units="in", precision=2,
        size=Size(2, 2), thickness=1, width=1,
    )  # fmt: skip
    full = dataclasses.replace(
        made,
        keepouts=(dataclasses.replace(made.keepouts[0], name="ANT"),),
        texts=(dataclasses.replace(made.texts[0], h_justify="left", v_justify="bottom"),),
        dimensions=(dimension,),
    )
    text = canonical.dumps(full)
    assert all(key in text for key in NEW_KEYS)
    assert canonical.loads(text, Board) == full
    assert _schema.validate(json.loads(text), _schema.load("fenolite.model.v0/board.json")) == []


def test_area_selector_against_a_subject() -> None:
    """Scenario "Area selector against a subject": letter case counts and ``*`` is a glob."""
    selector = Selector("area", "H*")
    subjects = (
        RuleSubject("track", areas=frozenset({"HV"})),
        RuleSubject("track", areas=frozenset({"hv"})),
        RuleSubject("track"),
    )
    assert [selector.matches(s) for s in subjects] == [True, False, False]
    assert Selector("area", "HV").matches(RuleSubject("via", areas=frozenset({"ANT", "HV"})))
    assert Selector("not", items=(Selector("area", "HV"),)).matches(RuleSubject("via"))
    with pytest.raises(ValueError, match="needs a value"):
        Selector("area")
    assert hash(RuleSubject("track", areas=frozenset({"HV"}))) == hash(
        RuleSubject("track", areas=frozenset({"HV"}))
    )


def test_unknown_dimension_kind_rejected_by_the_schema() -> None:
    """Scenario "Unknown dimension kind rejected by the schema"."""
    schema = _schema.load("fenolite.model.v0/board.json")
    dimension = Dimension(id=derived_id("dim", "dsl", "dimension:x"), kind="aligned", layer="Dwgs.User",
                          start=Point(0, 0), end=Point(5, 0), offset=1)  # fmt: skip
    data = json.loads(canonical.dumps(dataclasses.replace(board(), dimensions=(dimension,))))
    assert _schema.validate(data, schema) == []
    data["dimensions"][0]["kind"] = "radial"
    (error,) = _schema.validate(data, schema)
    assert error.startswith("/dimensions/0/kind")


def test_dimension_prefix() -> None:
    """Scenario "Dimension prefix"."""
    assert derived_id("dim", "dsl", "dimension:width").startswith("dim_")
    with pytest.raises(ValueError):
        new_id("dimx", random.Random(1))


def test_schemas_list_the_new_fields() -> None:
    """Scenario "Schemas regenerated"."""
    schema = _schema.load("fenolite.model.v0/board.json")
    assert "dimensions" in schema["properties"] and "Dimension" in schema["$defs"]
    assert "h_justify" in schema["$defs"]["Text"]["properties"]
    assert "name" in schema["$defs"]["Keepout"]["properties"]
    assert '"area"' in json.dumps(_schema.load("fenolite.model.v0/rules.json"))
