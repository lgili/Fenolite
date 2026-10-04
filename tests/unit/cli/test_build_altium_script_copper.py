# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script copper in ``fenolite build --target altium`` (change c0053; capability altium-build, "Script
copper in an Altium build" and "Script copper sample and author report"; design-dsl, "Zones in a build").

The copper that a design script declares (``Design.track``, ``Design.via``, ``Design.stitch``) is resolved
by the KiCad build of the script, run in memory, and handed to the Altium build as a ``CopperSource`` of
origin ``script``. The script is a copy of ``examples/blink_routed`` (``tests/_routed.py``): four intents,
11 tracks and 7 vias. ``kicad-cli`` is not run; the written document is read back with the test reader.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import pytest
from _altium_pcb_read import PcbDoc, read_pcbdoc
from _routed import NAME, ROOT, Routed

import fenolite.cli.main as cli_main
from fenolite.backends.altium import pcbrecords
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.cli._script import run_design_script
from fenolite.dsl import copper, placements, to_model
from fenolite.lens.build import build_design

PROTOCOL = ROOT / "docs" / "evidence" / "altium-pcb.md"
DOCUMENT = f"{NAME}.PcbDoc"
CORNER = 10_000_000
"""Where the document puts the outline's bottom-left corner, in its units, on both axes (1000 mil)."""
ZONE = 'design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))\n'


def altium(routed: Routed, *flags: str, out: Path | None = None) -> tuple[int, dict[str, Any], str]:
    """``fenolite build --target altium`` of the routed blink into ``out`` (default: ``routed.out``)."""
    stdout, stderr = io.StringIO(), io.StringIO()
    routed.monkeypatch.setattr("sys.stdout", stdout)
    routed.monkeypatch.setattr("sys.stderr", stderr)
    args = ["build", str(routed.script), "--out", str(out or routed.out), "--target", "altium"]
    code = cli_main.main([*args, *flags, "--json"])
    return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()


def codes(envelope: dict[str, Any]) -> list[str]:
    return [found["code"] for found in envelope["issues"]]


def net_names(doc: PcbDoc, indexes: list[int]) -> set[str]:
    return {doc.nets[index]["NAME"] for index in indexes}


def test_routed_blink_built_for_altium(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Routed blink built for Altium": the records hold what the script declares."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, envelope, err = altium(routed, "--confirm")
    assert code == 0, (envelope.get("issues"), err)
    found = envelope["result"]["copper"]
    assert (found["source"], found["from"], found["placements_from_board"]) == ("script", None, 0)
    assert (found["tracks"], found["arcs"], found["vias"], found["zones"]) == (11, 0, 7, 0)
    assert "copper_input" not in envelope["result"] and "copper_check" not in envelope["result"]
    assert not [i for i in envelope["issues"] if i["severity"] == "error"]
    assert "altium.not-lowered" not in codes(envelope) and "altium.pcb-staged" not in codes(envelope)
    assert not list(routed.out.glob("*.kicad_*")), "the in-memory KiCad build writes no file"
    doc = read_pcbdoc((routed.out / DOCUMENT).read_bytes())
    assert (len(doc.free_tracks), len(doc.free_arcs), len(doc.vias), len(doc.polygons)) == (11, 0, 7, 0)
    assert net_names(doc, [t.prefix.net for t in doc.free_tracks]) == {"LED_DRV", "LED_A", "GND"}
    assert net_names(doc, [v.prefix.net for v in doc.vias]) == {"LED_A", "GND"}
    assert doc.copper_chain == [1, 32]


def test_records_equal_the_resolved_intents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every track and via record is one item of the script's resolved copper, relative to the outline's
    corner: layer, net, end points and width, or position, diameter and hole. Altium's Y axis points up."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, _envelope, _ = altium(routed, "--confirm")
    assert code == 0
    doc = read_pcbdoc((routed.out / DOCUMENT).read_bytes())
    design = run_design_script(routed.script).design
    resolver = LibraryResolver(LibraryConfig(target_major=10, project_dir=routed.script.parent))
    built = build_design(
        to_model(design),
        placements(design),
        name=NAME,
        copper=design.copper,  # type: ignore[arg-type]
        resolver=resolver,
        copper_intents=copper(design),
    )
    board = built.design.board
    assert board is not None and board.outline is not None
    names = {net.id: net.name for net in built.design.circuit.nets}
    left = min(p.x for p in board.outline.points)
    bottom = max(p.y for p in board.outline.points)
    unit = pcbrecords.to_units

    def at(x: int, y: int) -> tuple[int, int]:
        return (CORNER + unit(x - left), CORNER + unit(bottom - y))

    layers = {"F.Cu": 1, "B.Cu": 32}
    wanted_tracks = sorted(
        (layers[t.layer], names[t.net_id or ""], *sorted([at(t.start.x, t.start.y), at(t.end.x, t.end.y)]))
        + (unit(t.width),)
        for t in board.tracks
    )
    got_tracks = sorted(
        (
            t.prefix.layer,
            doc.nets[t.prefix.net]["NAME"],
            *sorted([(t.x1, t.y1), (t.x2, t.y2)]),
        )
        + (t.width,)
        for t in doc.free_tracks
    )
    assert len(wanted_tracks) == 11
    assert _close(got_tracks, wanted_tracks)
    wanted_vias = sorted(
        (names[v.net_id or ""], at(v.position.x, v.position.y), unit(v.diameter), unit(v.drill))
        for v in board.vias
    )
    got_vias = sorted((doc.nets[v.prefix.net]["NAME"], (v.x, v.y), v.diameter, v.hole) for v in doc.vias)
    assert len(wanted_vias) == 7
    assert _close(got_vias, wanted_vias)
    assert {(v.start_layer, v.end_layer) for v in doc.vias} == {(1, 32)}


def _flat(item: object) -> list[object]:
    if isinstance(item, tuple):
        return [leaf for part in item for leaf in _flat(part)]  # type: ignore[union-attr]
    return [item]


def _close(got: list[Any], wanted: list[Any]) -> bool:
    """Equal item for item; numbers within one unit of the document (2.54 nm) of rounding."""
    if len(got) != len(wanted):
        return False
    for a, b in zip(got, wanted, strict=True):
        for x, y in zip(_flat(a), _flat(b), strict=True):
            if isinstance(x, str) or isinstance(y, str):
                if x != y:
                    return False
            elif abs(x - y) > 1:  # type: ignore[operator]
                return False
    return True


def test_script_source_and_board_source_give_the_same_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Script source and board source give the same bytes": with ``--copper-from`` the board
    wins, and one ``altium.not-lowered`` info names the intents that were not resolved."""
    routed = Routed(tmp_path, monkeypatch)  # the confirmed KiCad build, in routed.out
    code, first, _ = altium(routed, "--confirm", out=tmp_path / "A")
    assert code == 0 and first["result"]["copper"]["source"] == "script"
    code, second, _ = altium(routed, "--confirm", "--copper-from", str(routed.board), out=tmp_path / "C")
    assert code == 0
    found = second["result"]["copper"]
    assert (found["source"], found["tracks"], found["vias"]) == ("board", 11, 7)
    assert (tmp_path / "A" / DOCUMENT).read_bytes() == (tmp_path / "C" / DOCUMENT).read_bytes()
    (info,) = [i for i in second["issues"] if i["code"] == "altium.not-lowered" and "intent" in i["message"]]
    assert info["severity"] == "info" and info["where"] == str(routed.board)
    assert "4 copper intent(s)" in info["message"] and str(routed.board) in info["message"]
    for key in ("gnd", "gnd_fence", "led_a", "led_drv"):
        assert key in info["message"]
    assert not [i for i in first["issues"] if "intent" in i["message"]]
    assert not [c for c in codes(second) if c.startswith("kicad.copper.")]


def test_intent_error_refuses_the_altium_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Intent error refuses the Altium build": nothing is dropped to make a document fit."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    routed.edit_script("(mm(31.2), mm(7)), r1.pad(1),", "(mm(31.2), mm(7)), d1.pad(2),")
    code, envelope, _ = altium(routed, "--confirm")
    assert code == 5
    (found,) = [i for i in envelope["issues"] if i["code"] == "kicad.copper.net-conflict"]
    assert found["severity"] == "error" and "led_drv" in found["message"]
    result = envelope["result"]
    assert result["copper"] is None and result["pcb_document"] is None and result["files"] == []
    assert result["target"] == "altium" and result["experimental"] is True
    assert not routed.out.exists()


def test_intent_to_a_staged_part_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Intent to a staged part is reported": an intent that creates nothing is never silent."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    routed.edit_script('d1.place(mm(38), mm(20), side="bottom")\n', "")
    code, envelope, _ = altium(routed, "--dry-run")
    assert code == 0, envelope.get("issues")
    (staged,) = [i for i in envelope["issues"] if i["code"] == "layout.unplaced"]
    assert "D1" in staged["message"] and staged["severity"] == "warning"
    skipped = [i for i in envelope["issues"] if i["code"] == "kicad.copper.end-unplaced"]
    assert sorted(i["message"].split(":")[0] for i in skipped) == ["gnd", "led_a"]
    found = envelope["result"]["copper"]
    assert (found["source"], found["tracks"], found["vias"]) == ("script", 4, 5)
    # warnings and infos about KiCad files that are not written do not pass
    assert not [c for c in codes(envelope) if c.startswith(("build.", "kicad.lib"))]


def test_zone_and_intents_in_one_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Zone and intents in one script" (and design-dsl, "Altium build of a script with a zone and
    copper intents"): the zone travels with the script source, so the build still takes one source."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    routed.script.write_text(routed.script.read_text(encoding="utf-8") + ZONE, encoding="utf-8")
    code, envelope, _ = altium(routed, "--confirm")
    assert code == 0, envelope.get("issues")
    found = envelope["result"]["copper"]
    assert (found["source"], found["tracks"], found["vias"], found["zones"]) == ("script", 11, 7, 1)
    assert "altium.zones-unpoured" in codes(envelope)
    doc = read_pcbdoc((routed.out / DOCUMENT).read_bytes())
    (polygon,) = doc.polygons
    assert polygon.net is not None and doc.nets[polygon.net]["NAME"] == "GND"
    assert len(doc.free_tracks) == 11 and len(doc.vias) == 7


def test_script_without_intents_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Script without intents is unchanged": no in-memory build, the committed bytes."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    blink = ROOT / "examples" / "blink_2layer" / "design.py"
    routed.script.write_text(blink.read_text(encoding="utf-8"), encoding="utf-8")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no KiCad build runs for a script without copper intents")

    monkeypatch.setattr("fenolite.cli.cmd_build.build_design", refuse)
    code, envelope, _ = altium(routed, "--confirm")
    assert code == 0, envelope.get("issues")
    assert envelope["result"]["copper"]["source"] == "none"
    golden = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"
    assert (routed.out / "blink.PcbDoc").read_bytes() == golden.read_bytes()


def test_evidence_names_the_copper_resolver(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The build stays experimental and INFERRED, and names the rows of the copper resolver and the frame."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, envelope, _ = altium(routed, "--dry-run")
    assert code == 0
    evidence = envelope["evidence"]
    assert evidence["level"] == "INFERRED" and envelope["result"]["experimental"] is True
    for row in ("H-G-FRAME-ROUTE", "H-G-FRAME-UUID", "H-A-PCB-CU-TRACK", "H-A-PCB-CU-VIA"):
        assert row in evidence["hypotheses"], row
    # without intents the resolver's rows are not named
    blink = ROOT / "examples" / "blink_2layer" / "design.py"
    routed.script.write_text(blink.read_text(encoding="utf-8"), encoding="utf-8")
    code, plain, _ = altium(routed, "--dry-run")
    assert code == 0 and "H-G-FRAME-ROUTE" not in plain["evidence"]["hypotheses"]


def test_protocol_names_the_script_copper_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Protocol names the script copper bytes": step C7 of ``docs/evidence/altium-pcb.md`` names
    the SHA-256 of a fresh build, and claims no Altium verification."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, _envelope, _ = altium(routed, "--confirm")
    assert code == 0
    digest = hashlib.sha256((routed.out / DOCUMENT).read_bytes()).hexdigest()
    page = PROTOCOL.read_text(encoding="utf-8")
    match = re.search(r"^- \*\*C7\*\*.*?(?=^- \*\*|^\S)", page, re.M | re.S)
    assert match is not None, "step C7 is missing"
    step = match.group(0)
    assert digest in step, f"step C7 does not name {digest}"
    assert "examples/blink_routed/design.py" in step and "--target altium" in step
    assert "H-A-PCB-CU-TRACK" in step and "H-A-PCB-CU-VIA" in step
    assert "pending" in step and "ALTIUM-VERIFIED" not in step
