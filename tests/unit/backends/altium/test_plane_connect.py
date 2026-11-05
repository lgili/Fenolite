# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The internal plane's net region and connect rules in the Altium PCB document (change c0389, task 2.7).

Case C6 (``docs/evidence/altium-pcb.md``) reported Starved Thermal on the ``GND`` via and on ``D1`` pad 1
and an Un-Routed Net between them: the document held no ``Split Plane`` polygon and no plane rule. Every
case here is authored for Fenolite; the expected keys and values are the facts of ``pcb-copper.md``
("Layer stack").
"""

from __future__ import annotations

import math
import struct
import tempfile
from pathlib import Path

from _altium_board6 import bare_spec, read_back
from _altium_copper import NAME, PLANE, plane_model, routed_build

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.libboard import StackSpec
from fenolite.backends.altium.read.pcb import PadRecord, PcbDocument, ViaRecord, read_pcbdoc

LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
COMMON = ("SELECTION", "LAYER", "LOCKED", "POLYGONOUTLINE", "USERROUTED", "KEEPOUT", "UNIONINDEX")
MIL = rec.UNITS_PER_MIL


def plane_spec(*, rules: bool = True) -> pcbdoc.PcbDocSpec:
    """A bare four-layer document whose second layer is a plane on ``GND``."""
    stack = StackSpec.default(rec.copper_stack(LAYERS, ("In1.Cu",)), ("GND",))
    return bare_spec(copper_layers=LAYERS, stack=stack, nets=("GND", "SIG"), rules=rules)


def split_planes(document: PcbDocument) -> list[dict[str, str]]:
    return [dict(p.fields) for p in document.polygons if p.polygon_type == "Split Plane"]


def test_a_plane_gets_one_split_plane_on_its_net() -> None:
    document, _ = read_back(plane_spec())
    (polygon,) = [p for p in document.polygons if p.polygon_type == "Split Plane"]
    assert polygon.layer == "PLANE1" and document.net_name(polygon.net) == "GND"
    board = [(v.x, v.y) for v in document.board.outline]
    assert [(v.x, v.y) for v in polygon.vertices] == board  # the closed outline, as Board6 holds it
    keys = [key for key, _value in polygon.fields]
    assert tuple(keys[:7]) == COMMON and keys[7:9] == ["PRIMITIVELOCK", "POLYGONTYPE"]
    assert keys[9] == "KIND0" and keys[-1] == "NET"
    assert dict(polygon.fields)["PRIMITIVELOCK"] == "TRUE"


def test_two_planes_each_get_their_net_top_to_bottom() -> None:
    layers = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
    stack = StackSpec.default(rec.copper_stack(layers, ("In1.Cu", "In4.Cu")), ("VCC", "GND"))
    document, _ = read_back(bare_spec(copper_layers=layers, stack=stack, nets=("GND", "VCC")))
    found = [
        (p.layer, document.net_name(p.net)) for p in document.polygons if p.polygon_type == "Split Plane"
    ]
    assert found == [("PLANE1", "VCC"), ("PLANE2", "GND")]


def test_a_split_plane_follows_the_zone_pours() -> None:
    """The pour indexes of the zones keep their positions: the split planes come after every pour."""
    document, _ = read_back(plane_spec())
    assert document.polygons[-1].polygon_type == "Split Plane"


def test_no_plane_no_split_plane_and_no_plane_rule() -> None:
    document, _ = read_back(bare_spec(copper_layers=LAYERS, nets=("GND",)))
    assert not split_planes(document)
    kinds = {dict(r.fields)["RULEKIND"] for r in document.rules}
    assert not kinds & {"PlaneConnect", "PlaneClearance"}


def rules_of(spec: pcbdoc.PcbDocSpec) -> dict[str, tuple[int, dict[str, str]]]:
    out: dict[str, tuple[int, dict[str, str]]] = {}
    for record in pcbdoc.rule_records(spec, "x.PcbDoc"):
        (kind,) = struct.unpack_from("<H", record)
        text = record[6:].rstrip(b"\x00").decode("ascii")  # kind, 32-bit length, the property text
        fields = {
            key: value for key, _sep, value in (part.partition("=") for part in text.split("|") if part)
        }
        out[fields["RULEKIND"]] = (kind, fields)
    return out


def test_a_plane_writes_the_plane_connect_and_clearance_rules() -> None:
    rules = rules_of(plane_spec())
    kind, connect = rules["PlaneConnect"]
    assert kind == 6 and connect["NAME"] == "PlaneConnect" and connect["PRIORITY"] == "1"
    assert connect["SCOPE1EXPRESSION"] == connect["SCOPE2EXPRESSION"] == "All"
    assert connect["NETSCOPE"] == "AnyNet" and connect["LAYERKIND"] == "SameLayer"
    assert connect["PAD.PLANECONNECTSTYLE"] == "Relief" and connect["VIA.PLANECONNECTSTYLE"] == "Direct"
    for part in ("PAD", "VIA"):
        assert connect[f"{part}.RELIEFEXPANSION"] == "20mil" and connect[f"{part}.RELIEFENTRIES"] == "4"
        assert connect[f"{part}.RELIEFCONDUCTORWIDTH"] == connect[f"{part}.RELIEFAIRGAP"] == "10mil"
    kind, clearance = rules["PlaneClearance"]
    assert kind == 12 and clearance["CLEARANCE"] == "20mil" and clearance["SCOPE1EXPRESSION"] == "All"
    assert list(rules)[-2:] == ["PlaneConnect", "PlaneClearance"]


def test_rules_off_still_gives_the_plane_its_net() -> None:
    """The bisection variants without rules keep the split plane: it is no rule."""
    spec = plane_spec(rules=False)
    assert pcbdoc.rule_records(spec, "x.PcbDoc") == []
    document, _ = read_back(spec)
    assert len(split_planes(document)) == 1


def _p0() -> PcbDocument:
    with tempfile.TemporaryDirectory() as folder:
        output = routed_build(Path(folder), plane_model(), planes=PLANE)
    return read_pcbdoc(output.files[f"{NAME}.PcbDoc"])


def test_case_c6_thermals_have_room() -> None:
    """The geometry of C6 under the public rule definitions (S-1652): a relief reaches the hole radius plus
    the expansion (20 mil) and an antipad the hole radius plus the clearance (20 mil). ``D1`` pad 1's relief
    meets no antipad of another net, and the antipad of the ``VIN`` via stays outside the copper ring of the
    ``GND`` via (hole radius plus expansion minus the 10 mil air gap): the sample's own holes starve neither
    thermal. The ``GND`` via connects directly by the written rule, so it has no relief at all."""
    document = _p0()
    plane = "GND"
    expansion = clearance = 20 * MIL
    gap = 10 * MIL
    holes: list[tuple[str, int, int, int, str]] = []
    for item in (*document.pads, *document.vias):
        if isinstance(item, PadRecord) and item.hole:
            kind = "pad"
        elif isinstance(item, ViaRecord):
            kind = "via"
        else:
            continue
        holes.append((kind, item.x, item.y, item.hole, document.net_name(item.prefix.net) or ""))
    ours = [h for h in holes if h[4] == plane]
    others = [h for h in holes if h[4] != plane]
    assert sorted(h[0] for h in ours) == ["pad", "via"] and others
    for kind, x, y, hole, _net in ours:
        relief = hole / 2 + expansion
        for _kind, ox, oy, other_hole, _other in others:
            antipad = other_hole / 2 + clearance
            distance = math.hypot(x - ox, y - oy)
            if kind == "pad":
                assert distance > relief + antipad
            else:
                assert distance - antipad > relief - gap
    rules = {dict(r.fields)["RULEKIND"]: dict(r.fields) for r in document.rules}
    assert rules["PlaneConnect"]["VIA.PLANECONNECTSTYLE"] == "Direct"
    assert [document.net_name(p.net) for p in document.polygons if p.polygon_type == "Split Plane"] == [plane]
