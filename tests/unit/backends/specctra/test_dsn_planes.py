# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plane layers and routing layers in a Specctra design file (capability specctra-dsn, "Plane layers in
design files" and "Routing layers in design files"; change c0107). Hermetic: the bench is built in process
from the built-in catalog."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Mapping
from pathlib import Path

import _planebench as pb
import pytest
from _specctra import DEFAULTS

from fenolite.backends.specctra.dsn import DsnResult, write_dsn
from fenolite.backends.specctra.lexer import SNode, dumps, parse

ROUTED = (*pb.SIGNALS, *pb.HIGH)


@pytest.fixture(scope="module")
def found(tmp_path_factory: pytest.TempPathFactory) -> Iterator[pb.Loaded]:
    folder = tmp_path_factory.mktemp("planebench")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("KICAD_CONFIG_HOME", str(folder / "kicad-config"))
        yield pb.load(pb.build_project(folder))


def write(found: pb.Loaded, **more: object) -> DsnResult:
    return write_dsn(
        found.design,
        pads=found.pads,
        outline=found.outline,
        selected=ROUTED,
        defaults=DEFAULTS,
        **more,  # type: ignore[arg-type]
    )


def lists(result: DsnResult, section: str, head: str) -> list[SNode]:
    node = parse(result.text).first(section)
    assert node is not None
    return [child for child in node.lists if child.head == head]


def flat(node: SNode) -> str:
    """A list on one line."""
    return " ".join(dumps(node).split()).replace("( ", "(").replace(" )", ")")


def classes(result: DsnResult) -> dict[str, str]:
    return {str(node.items[0]): flat(node) for node in lists(result, "network", "class")}


def codes(result: DsnResult) -> list[str]:
    return [issue.code for issue in result.issues]


def without_outline(found: pb.Loaded, net: str) -> pb.Loaded:
    board = found.design.board
    assert board is not None
    zones = tuple(
        dataclasses.replace(zone, outline=()) if zone.net_id == found.net_id(net) else zone
        for zone in board.zones
    )
    design = dataclasses.replace(found.design, board=dataclasses.replace(board, zones=zones))
    return dataclasses.replace(found, design=design)


# -- plane layers


def test_two_planes(found: pb.Loaded) -> None:
    """Scenario "Two plane layers"."""
    result = write(found, plane_layers=pb.PLANE_LAYERS)
    structure = [flat(node) for node in lists(result, "structure", "layer")]
    assert structure == [
        "(layer F.Cu (type signal))",
        "(layer In1.Cu (type power))",
        "(layer In2.Cu (type power))",
        "(layer B.Cu (type signal))",
    ]
    planes = lists(result, "structure", "plane")
    assert [str(node.items[0]) for node in planes] == ["GND", "VCC"]
    for node, layer in zip(planes, pb.PLANE_LAYERS, strict=True):
        (polygon,) = node.lists
        assert polygon.head == "polygon" and polygon.items[:2] == (layer, "0")
        assert len(polygon.items) == 2 + 8, "the four corners of the board"
    xs = {float(v) for v in planes[0].lists[0].items[2::2]}
    ys = {float(v) for v in planes[0].lists[0].items[3::2]}
    assert max(xs) - min(xs) == pb.WIDTH_MM * 1000 and max(ys) - min(ys) == pb.HEIGHT_MM * 1000
    assert "specctra.plane-skipped" not in codes(result)
    heads = [node.head for node in parse(result.text).first("structure").lists]  # type: ignore[union-attr]
    assert heads.index("plane") > max(i for i, head in enumerate(heads) if head == "boundary")
    assert heads.index("plane") < heads.index("via")


def test_planes_change_no_other_list(found: pb.Loaded) -> None:
    """ "No other list of the file changes because of ``plane_layers``", and via padstacks keep a shape on
    every copper layer."""
    plain, planes = write(found), write(found, plane_layers=pb.PLANE_LAYERS)
    for section in ("placement", "library", "network", "wiring"):
        assert dumps(parse(plain.text).first(section)) == dumps(parse(planes.text).first(section))  # type: ignore[arg-type]
    via = next(n for n in lists(planes, "library", "padstack") if str(n.items[0]).startswith("Via_"))
    assert [shape.lists[0].items[0] for shape in via.lists] == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert plain.names == planes.names
    assert write(found, plane_layers=pb.PLANE_LAYERS).text == planes.text


def test_plane_only_for_a_zone_on_a_plane_layer(found: pb.Loaded) -> None:
    result = write(found, plane_layers=("In1.Cu",))
    assert [str(node.items[0]) for node in lists(result, "structure", "plane")] == ["GND"]
    assert "(layer In2.Cu (type signal))" in [flat(n) for n in lists(result, "structure", "layer")]
    assert lists(write(found), "structure", "plane") == []


def test_zone_without_an_outline(found: pb.Loaded) -> None:
    """Scenario "Zone without an outline"."""
    result = write(without_outline(found, "GND"), plane_layers=pb.PLANE_LAYERS)
    assert [str(node.items[0]) for node in lists(result, "structure", "plane")] == ["VCC"]
    (issue,) = [i for i in result.issues if i.code == "specctra.plane-skipped"]
    assert issue.severity == "warning" and "GND" in issue.message and "In1.Cu" in issue.message


def test_zone_of_a_net_without_pins_gives_no_plane(found: pb.Loaded) -> None:
    pads = tuple(pad for pad in found.pads if pad.net != "GND")
    result = write(dataclasses.replace(found, pads=pads), plane_layers=pb.PLANE_LAYERS)
    assert [str(node.items[0]) for node in lists(result, "structure", "plane")] == ["VCC"]
    assert "specctra.plane-skipped" not in codes(result)


def test_unknown_plane_layer(found: pb.Loaded) -> None:
    """Scenario "Unknown plane layer"."""
    with pytest.raises(ValueError, match=r"In3\.Cu"):
        write(found, plane_layers=("In3.Cu",))


# -- routing layers


def test_use_layer_for_a_whole_class(found: pb.Loaded) -> None:
    """Scenario "A class kept on the top layer"."""
    plain = write(found, plane_layers=pb.PLANE_LAYERS)
    result = write(found, plane_layers=pb.PLANE_LAYERS, net_layers={name: ("F.Cu",) for name in pb.SIGNALS})
    assert sorted(classes(result)) == sorted(classes(plain)) == ["HV", "PWR", "SIG"]
    sig = classes(result)["SIG"]
    assert all(f" {name}" in sig for name in pb.SIGNALS)
    assert "(circuit (use_via Via_600_300) (use_layer F.Cu))" in sig
    assert "use_layer" not in classes(result)["HV"] and "use_layer" not in plain.text
    assert "specctra.renamed" not in codes(result)


def test_split_by_layer_set(found: pb.Loaded) -> None:
    """Scenario "A class split by layer set"."""
    layers: Mapping[str, tuple[str, ...]] = {"SIG1": ("F.Cu",), "SIG2": ("F.Cu",)}
    result = write(found, plane_layers=pb.PLANE_LAYERS, net_layers=layers)
    found_classes = classes(result)
    assert sorted(found_classes) == ["HV", "PWR", "SIG", "SIG@2"]
    first, second = found_classes["SIG@2"], found_classes["SIG"]
    assert first.startswith("(class SIG@2 SIG1 SIG2 (circuit (use_via Via_600_300) (use_layer F.Cu))")
    assert second.startswith("(class SIG SIG3 SIG4 SIG5 SIG6 (circuit (use_via Via_600_300))")
    assert first.endswith("(rule (width 200) (clearance 200)))") and second.endswith(
        "(rule (width 200) (clearance 200)))"
    )
    # the group that may use every signal layer keeps the name; layers are written in stack order
    other = write(found, plane_layers=pb.PLANE_LAYERS, net_layers={"SIG3": ("B.Cu", "F.Cu")})
    assert classes(other)["SIG@2"].startswith(
        "(class SIG@2 SIG3 (circuit (use_via Via_600_300) (use_layer F.Cu B.Cu))"
    )
    assert " SIG1 " in classes(other)["SIG"]
    # every net with a set: the group of the first net in name order keeps the name
    every = {name: ("F.Cu",) for name in pb.SIGNALS} | {"SIG1": ("B.Cu",)}
    both = classes(write(found, plane_layers=pb.PLANE_LAYERS, net_layers=every))
    assert "(class SIG SIG1 " in both["SIG"] and "(use_layer B.Cu)" in both["SIG"]
    assert "(class SIG@2 SIG2 SIG3 SIG4 SIG5 SIG6 " in both["SIG@2"] and "(use_layer F.Cu)" in both["SIG@2"]


def test_split_classes_pair_with_every_group(found: pb.Loaded) -> None:
    result = write(found, plane_layers=pb.PLANE_LAYERS, net_layers={"SIG1": ("F.Cu",)})
    pairs = [flat(node) for node in lists(result, "network", "class_class")]
    assert pairs == [
        "(class_class (classes HV SIG) (rule (clearance 1000)))",
        "(class_class (classes HV SIG@2) (rule (clearance 1000)))",
    ]


def test_net_without_a_class_gets_a_class_of_its_own(found: pb.Loaded) -> None:
    nets = tuple(
        dataclasses.replace(net, netclass_id=None) if net.name == "SIG5" else net
        for net in found.design.circuit.nets
    )
    design = dataclasses.replace(found.design, circuit=dataclasses.replace(found.design.circuit, nets=nets))
    bare = dataclasses.replace(found, design=design)
    result = write(bare, net_layers={"SIG5": ("B.Cu",)})
    made = classes(result)
    assert (
        "(class CLASS4 SIG5 (circuit (use_via Via_600_300) (use_layer B.Cu)) "
        "(rule (width 250) (clearance 200)))" == made["CLASS4"]
    )
    assert " SIG5" not in made["SIG"]
    assert "CLASS" not in write(bare).text.replace("(class ", "")


def test_plane_layer_in_a_layer_set(found: pb.Loaded) -> None:
    """Scenario "Plane layer in a layer set", and the other refused values."""
    with pytest.raises(ValueError, match=r"SIG1.*In1\.Cu"):
        write(found, plane_layers=("In1.Cu",), net_layers={"SIG1": ("In1.Cu",)})
    with pytest.raises(ValueError, match="SIG1"):
        write(found, net_layers={"SIG1": ()})
    with pytest.raises(ValueError, match=r"SIG1.*In7\.Cu"):
        write(found, net_layers={"SIG1": ("In7.Cu",)})


def test_deterministic(found: pb.Loaded, tmp_path: Path) -> None:
    layers = {"SIG2": ("F.Cu",), "SIG1": ("B.Cu",)}
    first = write(found, plane_layers=pb.PLANE_LAYERS, net_layers=layers)
    second = write(
        found, plane_layers=tuple(reversed(pb.PLANE_LAYERS)), net_layers=dict(reversed(layers.items()))
    )
    assert first.text == second.text


# -- with the nets outside the job left out (change c0109, "Nets outside the routing job in design files")


def test_netless_keeps_the_plane_nets_and_their_planes(found: pb.Loaded) -> None:
    """``others="netless"`` leaves the nets outside the job out of the network, but a net of a plane this
    file holds stays declared, so the router counts its pins as joined there."""
    selected = ("SIG1", "SIG2")
    result = write_dsn(
        found.design, pads=found.pads, outline=found.outline, selected=selected, defaults=DEFAULTS,
        plane_layers=pb.PLANE_LAYERS, others="netless",
    )  # fmt: skip
    declared = sorted(result.names.nets.values())
    # the class HV stays too: its clearance (0.3 mm) is above the default rule, and the file pairs it with
    # the class of the selected nets (1 mm); the other nets of SIG leave the file
    assert declared == ["GND", "HV1", "HV2", "SIG1", "SIG2", "VCC"]
    assert [str(node.items[0]) for node in lists(result, "structure", "plane")] == ["GND", "VCC"]
    assert "(class_class (classes HV SIG) (rule (clearance 1000)))" in [
        flat(node) for node in lists(result, "network", "class_class")
    ]
    plain = write_dsn(
        found.design, pads=found.pads, outline=found.outline, selected=selected, defaults=DEFAULTS,
        others="netless",
    )  # fmt: skip
    assert sorted(plain.names.nets.values()) == ["HV1", "HV2", "SIG1", "SIG2"], "without planes: c0109 alone"
    assert lists(plain, "structure", "plane") == []
    only = write_dsn(
        found.design, pads=found.pads, outline=found.outline, selected=selected, defaults=DEFAULTS,
        plane_layers=("In1.Cu",), others="netless",
    )  # fmt: skip
    assert "GND" in only.names.nets.values() and "VCC" not in only.names.nets.values()


def test_netless_follows_the_lowered_clearances(found: pb.Loaded) -> None:
    """A net outside the job stays declared when the rules raise its class above the default rule, and
    leaves the file when the rules ask no more than the default (c0109's exception, on c0107's values)."""
    from fenolite.core.ids import derived_id
    from fenolite.model.rules import Rule, Selector

    def declared(*rules: Rule) -> list[str]:
        used = pb.with_rules(found, *rules, replace=True)
        result = write_dsn(
            used.design, pads=used.pads, outline=used.outline, selected=("SIG1",), defaults=DEFAULTS,
            others="netless",
        )  # fmt: skip
        return sorted(result.names.nets.values())

    assert declared() == ["HV1", "HV2", "SIG1"], "HV: 0.3 mm above the default 0.2 mm; PWR: 0.2 mm, left out"
    raised = Rule(
        id=derived_id("rul", "test", "pwr"), name="pwr", kind="clearance",
        selector_a=Selector("netclass", "PWR"), min=350_000,
    )  # fmt: skip
    assert declared(raised) == ["GND", "HV1", "HV2", "SIG1", "VCC"]
    wide = Rule(
        id=derived_id("rul", "test", "all"), name="all", kind="clearance", selector_a=Selector("all"),
        min=400_000,
    )  # fmt: skip
    assert declared(wide) == ["SIG1"], "every class and the default rule at 0.4 mm: nothing asks for more"


def test_netless_keeps_the_class_paired_with_a_selected_class(found: pb.Loaded) -> None:
    """A net outside the job stays declared when a ``class_class`` list pairs its class with the class of a
    selected net: the router keeps only the default rule from copper without a net."""
    from fenolite.core.ids import derived_id
    from fenolite.model.rules import Rule, Selector

    pair = Rule(
        id=derived_id("rul", "test", "pwr-sig"), name="pwr-sig", kind="clearance",
        selector_a=Selector("netclass", "PWR"), selector_b=Selector("netclass", "SIG"), min=800_000,
    )  # fmt: skip
    used = pb.with_rules(found, pair, replace=True)

    def declared(*selected: str) -> list[str]:
        result = write_dsn(
            used.design, pads=used.pads, outline=used.outline, selected=selected, defaults=DEFAULTS,
            others="netless",
        )  # fmt: skip
        return sorted(result.names.nets.values())

    assert declared("SIG1") == ["GND", "HV1", "HV2", "SIG1", "VCC"]
    assert declared("HV1") == ["HV1", "HV2"], "PWR and SIG are paired with each other, not with HV"
