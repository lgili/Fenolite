# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite net``, ``region`` and ``neighbors`` (capability cli-contract, "Net command", "Region command"
and "Neighbors command"; change c0066). Hermetic."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import hide_kicad, run, without_elapsed
from _projects import authored_project, tree_snapshot

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
WHOLE = "0mm,0mm,300mm,200mm"
FRAME = ["H-G-BOTTOM-PLACE", "H-G-FRAME-CRTYD-2", "H-G-FRAME-SHAPE", "H-G-PAD-ANGLE-ABS", "H-G-ROT-DIR"]


def test_net_list_of_the_authored_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "net", str(TWO_LAYER))
    assert code == 0 and env["ok"] is True
    nets = env["result"]["nets"]
    assert [n["name"] for n in nets] == ["GND", "LED_A", "VCC"]
    assert [(n["pads"], n["tracks"], n["vias"], n["zones"]) for n in nets] == [
        (1, 1, 1, 1),
        (2, 2, 0, 0),
        (1, 1, 0, 0),
    ]
    assert set(nets[0]) == {"name", "class", "pads", "tracks", "vias", "zones", "length", "islands", "open"}
    # scenario "Rows of the authored board" (c0108): the open connections of each net
    assert [(n["open"], n["islands"]) for n in nets] == [(0, 1), (1, 2), (0, 1)]
    assert nets[2]["length"] == 5_000_000 and all(isinstance(n["length"], int) for n in nets)
    assert env["evidence"]["level"] == "INFERRED"
    assert env["evidence"]["hypotheses"] == [*FRAME, "H-K-CONN-PARITY", "H-K-PCB-READ"]
    assert env["input"]["path"] == "two_layer.kicad_pcb"
    assert not [i for i in env["issues"] if i["code"].startswith("model.")]


def test_one_net(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "net", str(TWO_LAYER), "GND")
    net = env["result"]["net"]
    assert code == 0 and set(net) == {
        "name", "class", "pads", "copper", "vias", "zones", "box", "islands", "fill_islands", "open",
    }  # fmt: skip
    assert (net["islands"], net["fill_islands"], net["open"]) == (1, 0, [])
    assert [p["where"] for p in net["pads"]] == ["D1-1"] and "F.Cu" in net["pads"][0]["layers"]
    assert net["pads"][0]["position"] == {"x": 35_000_000, "y": 15_000_000}
    assert net["copper"] == [{"layer": "B.Cu", "tracks": 1, "arcs": 0, "length": 7_071_068}]
    assert [(v["layers"], v["diameter"]) for v in net["vias"]] == [(["F.Cu", "B.Cu"], 600_000)]
    assert net["zones"] == [{"name": "GND_B", "layers": ["B.Cu"], "filled": True}]
    assert set(net["box"]) == {"x0", "y0", "x1", "y1"} and net["box"]["x1"] == 40_300_000
    code, env, _, _ = run(monkeypatch, tmp_path, "net", str(TWO_LAYER), "LED_A")
    assert [c["layer"] for c in env["result"]["net"]["copper"]] == ["F.Cu"]
    assert env["result"]["net"]["copper"][0]["arcs"] == 1
    # scenario "One open net" (c0108): D1-2 and an end of the arc
    led = env["result"]["net"]
    assert led["islands"] == 2 and len(led["open"]) == 1
    (link,) = led["open"]
    ends = {link["a"]["kind"]: link["a"], link["b"]["kind"]: link["b"]}
    assert set(ends) == {"pad", "arc"} and ends["pad"]["where"] == "D1-2"
    assert set(link["a"]) == {"kind", "where", "position", "layers"} and link["length"] == 3_012_203
    assert env["evidence"]["hypotheses"] == [*FRAME, "H-K-CONN-PARITY", "H-K-PCB-READ"]


def test_unconnected_pins_have_one_island_and_nothing_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Pins on no net": the nets ``unconnected-(…)`` of a built board hold one pad each."""
    design = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"
    code, _env, error, _ = run(
        monkeypatch, tmp_path, "build", str(design), "--out", str(tmp_path / "blink"), "--confirm"
    )
    assert code == 0, error
    code, env, _, _ = run(monkeypatch, tmp_path, "net", str(tmp_path / "blink" / "blink.kicad_pcb"))
    assert code == 0
    lone = [row for row in env["result"]["nets"] if row["name"].startswith("unconnected-(")]
    assert lone and all((row["pads"], row["islands"], row["open"]) == (1, 1, 0) for row in lone)
    assert any(row["open"] for row in env["result"]["nets"]), "the built blink is not routed"


def test_unknown_net(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "net", str(TWO_LAYER), "GDN")
    assert code == 2 and err["code"] == "FEN-2001" and "GND" in err["hint"] and env["ok"] is False


def test_whole_board_region(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", WHOLE)
    result = env["result"]
    assert code == 0 and set(result) == {"box", "layer", "counts", "items"}
    assert result["counts"] == {
        "footprint": 2,
        "pad": 4,
        "track": 3,
        "arc": 1,
        "via": 1,
        "zone": 1,
        "text": 1,
    }
    assert (
        result["box"] == {"x0": 0, "y0": 0, "x1": 300_000_000, "y1": 200_000_000} and result["layer"] is None
    )
    assert len(result["items"]) == sum(result["counts"].values())
    for item in result["items"]:
        assert set(item) == {"kind", "where", "net", "layer", "box"}
        box = item["box"]
        assert box["x0"] <= 300_000_000 and box["x1"] >= 0 and box["y0"] <= 200_000_000 and box["y1"] >= 0
    assert [i["where"] for i in result["items"][:6]] == ["D1", "R1", "D1-1", "D1-2", "R1-1", "R1-2"]
    # corners in any order give the same rectangle
    code, env, _, _ = run(monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", "300mm,200mm,0mm,0mm")
    assert code == 0 and env["result"]["counts"] == result["counts"]


def test_one_layer_and_one_kind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", WHOLE, "--layer", "B.Cu", "--kinds", "track"
    )
    items = env["result"]["items"]
    assert code == 0 and items and all((i["kind"], i["layer"]) == ("track", "B.Cu") for i in items)
    assert env["result"]["counts"] == {"track": 1} and env["result"]["layer"] == "B.Cu"
    code, env, _, _ = run(monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", "1mm,1mm,2mm,2mm")
    assert code == 0 and [i["kind"] for i in env["result"]["items"]] in ([], ["zone"])


def test_region_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", "0,0,10,10")
    assert code == 2 and err["code"] == "FEN-2001" and "unit" in err["hint"]
    for box in ("0mm,0mm,0mm,10mm", "0mm,0mm,10mm", "1mm,1mm,5mm,1mm"):
        code, _, err, _ = run(monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", box)
        assert code == 2 and err["code"] == "FEN-2001", box
    code, _, err, _ = run(
        monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", WHOLE, "--kinds", "tracks"
    )
    assert code == 2 and "footprint,pad,track" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "region", str(TWO_LAYER))
    assert code == 2


def test_neighbors_of_a_resistor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "neighbors", str(TWO_LAYER), "R1", "--radius", "50mm")
    result = env["result"]
    assert code == 0 and set(result) == {"part", "radius", "neighbors"} and result["radius"] == 50_000_000
    assert set(result["part"]) == {"ref", "position", "rotation", "side", "box"}
    assert (result["part"]["ref"], result["part"]["side"], result["part"]["rotation"]) == (
        "R1",
        "top",
        90_000_000,
    )
    assert [(n["ref"], n["overlap"], n["shared_nets"]) for n in result["neighbors"]] == [
        ("D1", False, ["LED_A"])
    ]
    assert isinstance(result["neighbors"][0]["distance"], int) and result["neighbors"][0]["distance"] > 0
    assert set(result["neighbors"][0]) == {"ref", "distance", "overlap", "side", "shared_nets"}


def test_radius_too_small_and_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "neighbors", str(TWO_LAYER), "R1", "--radius", "0.01mm")
    assert code == 0 and env["result"]["neighbors"] == []
    code, env, _, _ = run(monkeypatch, tmp_path, "neighbors", str(TWO_LAYER), "R1")
    assert code == 0 and env["result"]["radius"] == 5_000_000


def test_neighbors_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "neighbors", str(TWO_LAYER), "R7")
    assert code == 2 and err["code"] == "FEN-2001" and "R1" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "neighbors", str(TWO_LAYER), "R1", "--radius", "5")
    assert code == 2 and "unit" in err["hint"]


@pytest.mark.parametrize(
    "command",
    [("net",), ("net", "GND"), ("region", "--box", WHOLE), ("neighbors", "R1")],
    ids=["net-list", "net", "region", "neighbors"],
)
def test_views_resolve_a_project_and_are_read_only_and_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: tuple[str, ...]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10, built=True)
    before = tree_snapshot(root)
    name, *rest = command
    code, env, _, first = run(monkeypatch, tmp_path, name, str(root), *rest)
    assert code == 0, env
    assert env["input"]["path"] == "board.kicad_pcb"
    second = run(monkeypatch, tmp_path, name, str(root), *rest)[3]
    assert without_elapsed(first) == without_elapsed(second)
    assert str(tmp_path) not in first and tree_snapshot(root) == before


def test_views_refuse_missing_and_other_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "net", str(tmp_path / "none.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"
    footprint = DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
    code, _, err, _ = run(monkeypatch, tmp_path, "net", str(footprint))
    assert code == 2 and err["code"] == "FEN-2001"
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "neighbors", str(unbalanced), "R1")
    assert code == 3 and err["code"] == "FEN-3004"
