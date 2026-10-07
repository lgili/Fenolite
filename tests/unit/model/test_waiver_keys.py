# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net-tie groups, waivers and check severities in the model (capability design-model, "Net-tie groups in
the model", "Waivers in the findings layer" and "Check severities in the rules layer"; change c0114)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance
from fenolite.model.canonical import dump_dir, dump_texts, dumps, load_dir, loads
from fenolite.model.design import SCHEMA_VERSION, Design
from fenolite.model.findings import Findings, Waiver
from fenolite.model.library import FootprintDef
from fenolite.model.rules import RuleSet

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "schemas" / "fenolite.model.v0"
GROUPS = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}


def footprint(**more: object) -> FootprintInstance:
    return FootprintInstance(
        id="fp_00000000-0000-4000-8000-000000000001",
        component_id="cmp_00000000-0000-4000-8000-000000000001",
        lib_ref="Tie:Two",
        position=Point(0, 0),
        **more,  # type: ignore[arg-type]
    )


def with_footprint(placed: FootprintInstance) -> Design:
    design = Design.new("t", seed=1)
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(placed,)))


def test_net_ties_old_documents_load(tmp_path: Path) -> None:
    """Scenario "Old documents load": a ``board.json`` without the key loads with ``()``, and writing the
    design again gives the same bytes."""
    design = with_footprint(footprint())
    dump_dir(design, tmp_path)
    before = (tmp_path / "board.json").read_text(encoding="utf-8")
    assert "net_ties" not in before
    loaded = load_dir(tmp_path)
    assert loaded.board is not None and all(fp.net_ties == () for fp in loaded.board.footprints)
    assert dump_texts(loaded)["board.json"] == before


def test_net_ties_round_trip_in_order(tmp_path: Path) -> None:
    groups = (("3", "4"), ("1", "2"))
    design = with_footprint(footprint(net_ties=groups))
    dump_dir(design, tmp_path)
    data = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))
    assert data["footprints"][0]["net_ties"] == [["3", "4"], ["1", "2"]]  # ordered: the source's order
    loaded = load_dir(tmp_path)
    assert loaded.board is not None and loaded.board.footprints[0].net_ties == groups
    defn = FootprintDef(id="fpd_x", name="X", net_ties=groups)
    assert loads(dumps(defn), FootprintDef) == defn and "net_ties" not in dumps(
        FootprintDef(id="a", name="X")
    )


def test_net_ties_are_not_validated_against_the_pads() -> None:
    design = with_footprint(footprint(net_ties=(("7", "8"),)))
    assert not [found for found in design.validate() if "net_tie" in found.message]


def test_net_ties_schema_in_step() -> None:
    """Scenario "Schema in step": both schemas list the key as an array of arrays of strings."""
    board = json.loads((SCHEMAS / "board.json").read_text(encoding="utf-8"))
    library = json.loads((SCHEMAS / "library.json").read_text(encoding="utf-8"))
    assert board["$defs"]["FootprintInstance"]["properties"]["net_ties"] == GROUPS
    assert library["$defs"]["FootprintDef"]["properties"]["net_ties"] == GROUPS
    assert SCHEMA_VERSION == "0"


def test_waivers_round_trip_through_the_cache(tmp_path: Path) -> None:
    """Scenario "Waivers round-trip through the cache"."""
    waivers = (
        Waiver("pitch", "copper.clearance", ("J1-3", "*"), "fixed by the mating connector", 150_000),
        Waiver("tp", "kicad.drc.via-dangling", ("*",), "test point"),
    )
    design = dataclasses.replace(Design.new("t", seed=1), findings=Findings(waivers=waivers))
    dump_dir(design, tmp_path)
    text = (tmp_path / "findings.json").read_text(encoding="utf-8")
    assert '"min_gap": 150000' in text
    assert not any(isinstance(v, float) for w in json.loads(text)["waivers"] for v in w.values())
    assert [w["name"] for w in json.loads(text)["waivers"]] == ["pitch", "tp"]
    assert load_dir(tmp_path).findings.waivers == waivers


def test_waivers_absent_keep_the_bytes() -> None:
    empty = dump_texts(Design.new("t", seed=1))["findings.json"]
    assert empty == "{}\n" and "waivers" not in empty
    schema = json.loads((SCHEMAS / "findings.json").read_text(encoding="utf-8"))
    assert "waivers" in schema["properties"] and "Waiver" in schema["$defs"]


def test_severities_round_trip() -> None:
    """Scenario "Severities round-trip": the keys are written sorted."""
    rules = RuleSet(
        id="rst_00000000-0000-4000-8000-000000000001",
        severities={"kicad.drc.via-dangling": "error", "kicad.drc.silk-overlap": "ignore"},
    )
    text = dumps(rules)
    assert text.index("kicad.drc.silk-overlap") < text.index("kicad.drc.via-dangling")
    assert loads(text, RuleSet) == rules
    assert "severities" not in dumps(RuleSet(id=rules.id))
    schema = json.loads((SCHEMAS / "rules.json").read_text(encoding="utf-8"))
    assert schema["properties"]["severities"]["additionalProperties"] == {
        "enum": ["error", "warning", "ignore"]
    }
