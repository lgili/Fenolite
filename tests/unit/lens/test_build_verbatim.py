# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Verbatim items through ``fenolite build`` (capability design-dsl, "Verbatim items in a build"; change
c0277). Each test builds a blink variant in ``tmp_path``, in-process."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.embed import placement_uuid
from fenolite.backends.kicad.sexpr import parse

STAMP = "2026-10-30T00:00:00Z"
QR = (
    'design.verbatim("art/qr", \'(barcode (at 120 80) (layer "F.SilkS") (text "X") (uuid '
    '"00000000-0000-4000-8000-000000000001"))\')\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _build(script: Path, out: Path, target: int = 10, *extra: str):  # noqa: ANN202
    return run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm", *extra,
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip


def test_barcode_kept(tmp_path: Path) -> None:
    """Scenario "Barcode kept"."""
    script = blink_variant(tmp_path / "src", append=QR)
    out = tmp_path / "out"
    reply = _build(script, out)
    assert reply.exit_code == 0, reply.error
    first = (out / "blink.kicad_pcb").read_bytes()
    (barcode,) = parse(first.decode("utf-8")).nodes("barcode")
    assert barcode.find("uuid") == parse(f'(uuid "{placement_uuid("art/qr", "/verbatim/0")}")')
    found = [i for i in reply.envelope["issues"] if i["code"] == "build.verbatim-item"]  # type: ignore[index]
    assert len(found) == 1 and "art/qr" in found[0]["message"] and "barcode" in found[0]["message"]
    assert _build(script, out).exit_code == 0
    assert (out / "blink.kicad_pcb").read_bytes() == first
    assert len(parse((out / "blink.kicad_pcb").read_text(encoding="utf-8")).nodes("barcode")) == 1


def test_refused_heads(tmp_path: Path) -> None:
    """Scenario "Refused heads"."""
    lines = (
        'design.verbatim("a", "(footprint \\"X\\" (layer \\"F.Cu\\"))")\n'
        'design.verbatim("b", "(setup (pad_to_mask_clearance 0))")\n'
        'design.verbatim("c", "(layers (0 \\"F.Cu\\" signal))")\n'
    )
    script = blink_variant(tmp_path / "src", append=lines)
    reply = _build(script, tmp_path / "out")
    assert reply.exit_code == 5
    codes = [i["code"] for i in reply.envelope["issues"]]  # type: ignore[index]
    assert codes.count("build.verbatim-head") == 3
    assert not (tmp_path / "out" / "blink.kicad_pcb").exists()


def test_layer_net_and_parse_refusals(tmp_path: Path) -> None:
    lines = (
        'design.verbatim("l", "(target plus (at 1 1) (size 1) (width 0.1) (layer \\"In5.Cu\\"))")\n'
        'design.verbatim("n", "(generated (type tuning_pattern) (net \\"NOPE\\"))")\n'
        'design.verbatim("p", "(unbalanced (x)")\n'
    )
    script = blink_variant(tmp_path / "src", append=lines)
    reply = _build(script, tmp_path / "out")
    assert reply.exit_code == 5
    codes = sorted(i["code"] for i in reply.envelope["issues"] if i["code"].startswith("build.verbatim"))  # type: ignore[index]
    assert codes == ["build.verbatim-invalid", "build.verbatim-layer", "build.verbatim-net"]


def test_too_new_for_target_9(tmp_path: Path) -> None:
    """Scenario "Too new for target 9": a barcode is a KiCad 10 item."""
    script = blink_variant(tmp_path / "src", append=QR)
    reply = _build(script, tmp_path / "out", 9)
    assert reply.exit_code == 7 and reply.error is not None and reply.error["code"] == "FEN-7001"
    lossy = _build(script, tmp_path / "lossy", 9, "--allow-lossy")
    assert lossy.exit_code == 0, lossy.error
    assert not parse((tmp_path / "lossy" / "blink.kicad_pcb").read_text(encoding="utf-8")).nodes("barcode")


def _ref(footprint) -> str:  # noqa: ANN001
    return next(p.atoms()[1].value for p in footprint.nodes("property") if p.atoms()[0].value == "Reference")


def test_part_item_and_rules_item(tmp_path: Path) -> None:
    lines = (
        'r1.verbatim("fab", \'(fp_line (start -1 0) (end 1 0) (stroke (width 0.1) (type solid))'
        ' (layer "F.Fab") (uuid "00000000-0000-4000-8000-000000000002"))\')\n'
        'design.verbatim("rule/hv", \'(rule "hv" (constraint clearance (min 0.1mm))'
        ' (condition "A.NetClass == \\\'PWR\\\'"))\', target="kicad_dru")\n'
        'design.verbatim("cu/net", \'(gr_text_box "T" (start 1 1) (end 4 3) (layer "F.Cu") (net "GND")'
        ' (uuid "00000000-0000-4000-8000-000000000003"))\')\n'
    )
    script = blink_variant(tmp_path / "src", append=lines)
    for target in (9, 10):
        out = tmp_path / f"out{target}"
        reply = _build(script, out, target)
        assert reply.exit_code == 0, reply.error
        root = parse((out / "blink.kicad_pcb").read_text(encoding="utf-8"))
        r1 = next(fp for fp in root.nodes("footprint") if _ref(fp) == "R1")
        marks = [
            n
            for n in r1.nodes("fp_line")
            if n.find("uuid") == parse(f'(uuid "{placement_uuid("R1/fab", "/verbatim/0")}")')
        ]
        assert len(marks) == 1
        (box,) = root.nodes("gr_text_box")
        net = box.find("net")
        assert net is not None and (
            net == parse('(net "GND")') if target == 10 else net.atoms()[0].value.isdigit()
        )
        rules = (out / "blink.kicad_dru").read_text(encoding="utf-8")
        assert '(rule "hv"' in rules
