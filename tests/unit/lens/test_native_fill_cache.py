# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The byte-bound native ordinary fill carrier (c0384 0.3, option A): carried only onto the exact emitted
bytes it was captured from, dropped (never refused) with its reason on any change."""

from __future__ import annotations

import json

import pytest

from fenolite.backends.kicad.sexpr import dumps, parse_bytes
from fenolite.lens.native_fill_cache import ORIGIN, Emitted, apply, capture

ZONE = (
    '\t(zone (net 1) (net_name "GND") (layer "B.Cu") (uuid "{uuid}") (hatch edge 0.5)\n'
    "\t\t(connect_pads (clearance 0.5)) (min_thickness 0.25)\n"
    "\t\t(fill{flag} (thermal_gap 0.5) (thermal_bridge_width 0.5))\n"
    "\t\t(polygon (pts (xy {x} 0) (xy {x2} 0) (xy {x2} 10) (xy {x} 10))){fills})\n"
)
FILL = '\n\t\t(filled_polygon (layer "B.Cu") (pts (xy {x} 1) (xy {x1} 1) (xy {x1} 9)))'
TEARDROP = (
    '\t(zone (net 1) (net_name "GND") (layer "B.Cu") (uuid "00000000-0000-4000-8000-0000000000dd")'
    " (attr (teardrop (type padvia))) (fill yes) (polygon (pts (xy 0 0) (xy 1 0) (xy 1 1)))"
    ' (filled_polygon (layer "B.Cu") (pts (xy 0 0) (xy 1 0) (xy 1 1))))\n'
)
SOURCE_IDS = ("00000000-0000-4000-8000-00000000000a", "00000000-0000-4000-8000-00000000000b")
BUILT_IDS = ("00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000b1")


def _board(ids: tuple[str, str], *, filled: bool, net: int = 1, extra: str = "") -> bytes:
    zones = "".join(
        ZONE.format(
            uuid=uuid,
            flag=" yes" if filled else "",
            x=x,
            x2=x + 10,
            fills=FILL.format(x=x + 1, x1=x + 9) if filled else "",
        ).replace("(net 1)", f"(net {net})")
        for uuid, x in zip(ids, (0, 20), strict=True)
    )
    head = f'(kicad_pcb (version 20241229) (generator "pcbnew")\n\t(net 0 "") (net {net} "GND")\n'
    text = f"{head}{zones}{extra})\n"
    return dumps(parse_bytes(text.encode())).encode()


SOURCE = _board(SOURCE_IDS, filled=True, net=7, extra=TEARDROP)
BUILT = Emitted(_board(BUILT_IDS, filled=False), b'{"project": 1}\n', b"(version 1)\n")
INPUTS = [{"path": "src.kicad_pcb", "sha256": "0" * 64, "kind": "kicad_pcb"}]


def _carrier() -> bytes:
    raw, why = capture(SOURCE, BUILT, 9, INPUTS)
    assert why == "captured" and raw is not None
    return raw


def _zones(board: bytes) -> dict[str, str]:
    root = parse_bytes(board)
    out = {}
    for zone in root.nodes("zone"):
        uuid = zone.nodes("uuid")[0].atoms()[0].value
        kept = [c for c in zone.children if getattr(c, "name", None) not in ("uuid", "net")]
        out[uuid] = dumps(zone.with_children(tuple(kept)), style="compact")
    return out


def test_round_trip_restores_the_source_fill_flag_and_caches_exactly() -> None:
    raw = _carrier()
    data = json.loads(raw)
    assert data["origin"] == ORIGIN == "native-carry-over" and data["fenolite_computed"] is False
    assert [row["zone"] for row in data["zones"]] == list(BUILT_IDS)  # the teardrop cache is never carried
    written, receipt = apply(raw, BUILT, 9)
    assert receipt == {
        "origin": "native-carry-over",
        "fenolite_computed": False,
        "status": "carried",
        "reason": None,
        "zones": 2,
        "fills": 2,
    }
    source = _zones(SOURCE)
    assert [_zones(written)[b] for b in BUILT_IDS] == [source[a] for a in SOURCE_IDS]
    assert apply(raw, BUILT, 9) == (written, receipt)  # deterministic


@pytest.mark.parametrize(
    ("emitted", "target", "reason"),
    [
        (Emitted(BUILT.pcb + b"\n", BUILT.project, BUILT.rules), 9, "board-changed"),
        (
            Emitted(BUILT.pcb.replace(b"(xy 20 10)", b"(xy 20 11)"), BUILT.project, BUILT.rules),
            9,
            "board-changed",
        ),
        (Emitted(BUILT.pcb, BUILT.project + b" ", BUILT.rules), 9, "project-changed"),
        (Emitted(BUILT.pcb, BUILT.project, b"(version 1) (rule x)\n"), 9, "rules-changed"),
        (Emitted(BUILT.pcb, BUILT.project, None), 9, "rules-changed"),
        (BUILT, 10, "target-changed"),
    ],
)
def test_any_changed_byte_or_target_drops_the_whole_carrier(
    emitted: Emitted, target: int, reason: str
) -> None:
    written, receipt = apply(_carrier(), emitted, target)
    assert written == emitted.pcb  # the ordinary no-cache board, never a partial carry
    assert receipt["status"] == "dropped" and receipt["reason"] == reason
    assert receipt["zones"] == receipt["fills"] == 0


def _edited(edit: object) -> bytes:
    data = json.loads(_carrier())
    if callable(edit):
        edit(data)
    return json.dumps(data).encode()


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"",
        b'{"version": 1, "version": 1}',
        _edited(lambda d: d.update(fenolite_computed=True)),
        _edited(lambda d: d.update(origin="fenolite")),
        _edited(lambda d: d.update(extra=1)),
        _edited(lambda d: d.update(zones=[])),
        _edited(lambda d: d["zones"][0].update(fills=["(polygon (pts (xy 0 0)))"])),
        _edited(lambda d: d["zones"][1].update(zone=d["zones"][0]["zone"])),
        _edited(lambda d: d["emitted"].update(pcb_sha256="A" * 64)),
    ],
)
def test_an_unreadable_carrier_is_dropped_not_refused(raw: bytes) -> None:
    written, receipt = apply(raw, BUILT, 9)
    assert written == BUILT.pcb and (receipt["status"], receipt["reason"]) == (
        "dropped",
        "carrier-unreadable",
    )


def test_no_carrier_is_absent() -> None:
    assert apply(None, BUILT, 9) == (
        BUILT.pcb,
        {
            "origin": ORIGIN,
            "fenolite_computed": False,
            "status": "absent",
            "reason": None,
            "zones": 0,
            "fills": 0,
        },
    )


def test_a_carried_zone_whose_fill_settings_changed_drops() -> None:
    raw = _carrier()
    data = json.loads(raw)
    data["zones"][0]["fill"] = data["zones"][0]["fill"].replace("thermal_gap 0.5", "thermal_gap 0.6")
    data["emitted"]["pcb_sha256"] = json.loads(raw)["emitted"]["pcb_sha256"]
    written, receipt = apply(json.dumps(data).encode(), BUILT, 9)
    assert written == BUILT.pcb and receipt["reason"] == "board-changed"


@pytest.mark.parametrize(
    ("source", "emitted", "reason"),
    [
        (_board(SOURCE_IDS, filled=False), BUILT.pcb, "no-source-fills"),
        (SOURCE, _board(BUILT_IDS, filled=True), "emitted-board-has-fills"),
        # the second built zone moved: one source zone has no counterpart
        (SOURCE, BUILT.pcb.replace(b"(xy 20 0)", b"(xy 21 0)"), "zone-correspondence"),
        # two source zones of equal content: ambiguous, never a first match
        (
            SOURCE.replace(b"(xy 20 ", b"(xy 0 ").replace(b"(xy 30 ", b"(xy 10 "),
            BUILT.pcb,
            "zone-correspondence",
        ),
    ],
)
def test_capture_writes_no_carrier_without_a_complete_unique_correspondence(
    source: bytes, emitted: bytes, reason: str
) -> None:
    raw, why = capture(source, Emitted(emitted, BUILT.project, BUILT.rules), 9, INPUTS)
    assert raw is None and why == reason
