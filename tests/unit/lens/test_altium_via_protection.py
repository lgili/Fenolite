# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via protection in ``fenolite build --target altium`` (capability altium-build, "Via protection in an
Altium build"; altium-import, "Via tenting of imported vias"; change c0112).

The design is a copy of ``examples/blink_routed`` (``tests/_routed.py``: four intents, 7 vias) with two via
intents added; ``examples/altium_sample`` declares no board, so it cannot carry script copper. The written
document is read back with the product reader.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from _routed import NAME, Routed

import fenolite.cli.main as cli_main
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ViaRecord
from fenolite.model.board import ViaProtection

DOCUMENT = f"{NAME}.PcbDoc"
IMPORT = "from fenolite.dsl import protect\n"
TP1 = (
    'design.via("tp1", mm(6), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4),'
    ' protection=protect(tenting="front", filling=True, capping=True))\n'
)
TP2 = 'design.via("tp2", mm(9), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4))\n'
PLAIN = (
    'design.via("tp1", mm(6), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4))\n'
    'design.via("tp2", mm(9), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4))\n'
)
DEFAULT = "design.via_protection(protect(tenting=True))\n"
SIZE = 314_961  # 0.8 mm in the document's units (1/10 000 mil), within one unit


def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, append: str) -> Routed:
    routed = Routed(tmp_path / name, monkeypatch, confirm=False)
    text = routed.script.read_text(encoding="utf-8")
    routed.script.write_text(text + IMPORT + append, encoding="utf-8")
    return routed


def altium(routed: Routed, *flags: str) -> tuple[int, dict[str, Any], str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    routed.monkeypatch.setattr("sys.stdout", stdout)
    routed.monkeypatch.setattr("sys.stderr", stderr)
    args = ["build", str(routed.script), "--out", str(routed.out), "--target", "altium"]
    code = cli_main.main([*args, *flags, "--json"])
    return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()


def files(routed: Routed) -> dict[str, bytes]:
    return {
        p.relative_to(routed.out).as_posix(): p.read_bytes()
        for p in sorted(routed.out.rglob("*"))
        if p.is_file() and not p.name.endswith(".bak")
    }


def vias_of(data: bytes) -> list[ViaRecord]:
    found = read_pcbdoc(data, file=DOCUMENT, strict=True).vias
    assert all(isinstance(via, ViaRecord) for via in found)
    return sorted(found, key=lambda v: (v.x, v.y))  # type: ignore[union-attr, arg-type, return-value]


def test_points(vias: list[ViaRecord]) -> list[ViaRecord]:
    """The two added vias: the only ones of 0.8 mm, left to right."""
    return [via for via in vias if abs(via.diameter - SIZE) <= 1]


test_points.__test__ = False  # type: ignore[attr-defined]


def protection_infos(envelope: dict[str, Any]) -> list[dict[str, str]]:
    return [i for i in envelope["issues"] if i["where"] == "via-protection"]


def test_tenting_written_and_the_rest_named(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Tenting written, the rest named"."""
    stated = project(tmp_path, monkeypatch, "stated", TP1 + TP2 + DEFAULT)
    code, envelope, err = altium(stated, "--confirm")
    assert code == 0, (envelope.get("issues"), err)
    vias = vias_of((stated.out / DOCUMENT).read_bytes())
    first, second = test_points(vias)
    assert (f"{first.prefix.flags1:02X}", first.prefix.flags2) == ("2C", 0)  # top tented, bottom not
    assert (f"{second.prefix.flags1:02X}", second.prefix.flags2) == ("6C", 0)  # both, from the default
    assert {f"{via.prefix.flags1:02X}" for via in vias if via not in (first, second)} == {"6C"}
    (info,) = protection_infos(envelope)
    assert (info["code"], info["severity"]) == ("altium.not-lowered", "info")
    assert "1 via(s) hold capping, filling" in info["message"]
    assert "neither the via nor the board default" not in info["message"]
    assert "design.via_protection(protect(tenting=" in info["hint"]
    written = envelope["result"]["pcb"]["written"]
    assert written["via"] == len(vias) == 9 and "via" not in envelope["result"]["pcb"]["not_lowered"]
    assert "H-A-PCB-CU-VIATENT" in envelope["evidence"]["hypotheses"]
    assert envelope["evidence"]["level"] == "INFERRED"
    # every file outside .fenolite/ but the PCB document equals that of the design without protection,
    # and the document differs only in the first flags byte of the via records whose tenting is stated
    plain = project(tmp_path, monkeypatch, "plain", PLAIN)
    code, plain_envelope, err = altium(plain, "--confirm")
    assert code == 0, err
    assert protection_infos(plain_envelope) == []
    ours, theirs = files(stated), files(plain)
    assert set(ours) == set(theirs)
    differ = {name for name in ours if ours[name] != theirs[name] and not name.startswith(".fenolite/")}
    assert differ == {DOCUMENT}
    plain_vias = vias_of(theirs[DOCUMENT])
    assert {f"{via.prefix.flags1:02X}" for via in plain_vias} == {"0C"}
    assert len(plain_vias) == len(vias)
    for ours_via, theirs_via in zip(vias, plain_vias, strict=True):
        assert len(ours_via.raw) == len(theirs_via.raw)
        changed = [k for k, (a, b) in enumerate(zip(ours_via.raw, theirs_via.raw, strict=True)) if a != b]
        assert len(changed) == 1  # the first flags byte
        assert ours_via.raw[changed[0]] & 0x9F == theirs_via.raw[changed[0]] == 0x0C


def test_a_side_nobody_states(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A side nobody states": without the default the second via keeps ``0C 00``, and the info
    counts the vias whose tenting is stated nowhere (the second test point and the seven routed vias)."""
    routed = project(tmp_path, monkeypatch, "unstated", TP1 + TP2)
    code, envelope, err = altium(routed, "--confirm")
    assert code == 0, err
    vias = vias_of((routed.out / DOCUMENT).read_bytes())
    first, second = test_points(vias)
    assert (f"{first.prefix.flags1:02X}", f"{second.prefix.flags1:02X}") == ("2C", "0C")
    (info,) = protection_infos(envelope)
    assert "1 via(s) hold capping, filling" in info["message"]
    assert "8 via(s) have a tenting side that neither the via nor the board default states" in info["message"]
    assert "KiCad tents such a via" in info["message"] and "flag clear" in info["message"]
    dry = project(tmp_path, monkeypatch, "dry", TP1 + TP2)
    code, planned, _ = altium(dry, "--dry-run")
    assert code == 0 and [i["message"] for i in protection_infos(planned)] == [info["message"]]


def test_a_design_without_protection_names_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A design without protection keeps its bytes": no info at ``via-protection``, clear flags
    on every via (the bytes are pinned by the golden tests of the routed samples)."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, envelope, err = altium(routed, "--confirm")
    assert code == 0, err
    assert protection_infos(envelope) == []
    vias = vias_of((routed.out / DOCUMENT).read_bytes())
    assert len(vias) == 7 and {(via.prefix.flags1, via.prefix.flags2) for via in vias} == {(0x0C, 0)}


def test_stated_tenting_survives_the_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Stated tenting survives the round trip" (altium-import): the imported vias have the
    tenting of the vias they were written from."""
    append = (
        'design.via("tp1", mm(6), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4),'
        ' protection=protect(tenting="front"))\n'
        'design.via("tp2", mm(9), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4),'
        " protection=protect(tenting=False))\n"
    )
    routed = project(tmp_path, monkeypatch, "trip", append)
    code, envelope, err = altium(routed, "--confirm")
    assert code == 0, err
    assert protection_infos(envelope)[0]["message"].startswith("7 via(s) have a tenting side")
    data = (routed.out / DOCUMENT).read_bytes()
    design = import_board(
        read_pcbdoc(data, file=DOCUMENT), file=DOCUMENT, sha256=hashlib.sha256(data).hexdigest()
    )
    assert design.board is not None and design.board.via_protection is None
    found = sorted((v for v in design.board.vias if v.diameter >= 799_000), key=lambda v: v.position.x)
    assert [v.protection for v in found] == [
        ViaProtection(tenting_front=True, tenting_back=False),
        ViaProtection(tenting_front=False, tenting_back=False),
    ]
