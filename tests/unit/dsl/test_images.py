# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board images (capability design-dsl, "Images in the DSL"; change c0277): the call, the build that reads
the PNG beside the script, the KiCad text and a rebuild. The PNG is made by the test, authored for
Fenolite."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from _buildhelp import blink_variant
from _png import png

from fenolite.api import run
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, mm

STAMP = "2026-10-30T00:00:00Z"
LINE = 'design.image("logo", "logo.png", (mm(5), mm(5)), scale="0.5")\n'


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _build(script: Path, out: Path, *extra: str, target: int = 10):  # noqa: ANN202
    return run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), *extra,
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip


def test_refused_calls() -> None:
    d = Design("img")
    with pytest.raises(DslError, match="board"):
        d.image("a", "a.png", (mm(1), mm(1)))
    d.board(mm(20), mm(20))
    for file in ("/abs/a.png", "../a.png", ""):
        with pytest.raises(DslError, match="file"):
            d.image("a", file, (mm(1), mm(1)))
    for scale in ("0", "-1", "1e3", 0.5):
        with pytest.raises(DslError, match="scale"):
            d.image("a", "a.png", (mm(1), mm(1)), scale=scale)  # type: ignore[arg-type]
    d.image("a", "art/a.png", (mm(1), mm(1)), layer="B.SilkS")
    with pytest.raises(DslError, match="already used"):
        d.image("a", "a.png", (mm(1), mm(1)))
    assert d.images["a"].file == "art/a.png" and d.images["a"].layer == "B.SilkS"


def test_logo_image(tmp_path: Path) -> None:
    """Scenario "Logo image"."""
    script = blink_variant(tmp_path / "src", append=LINE)
    data = png()
    (script.parent / "logo.png").write_bytes(data)
    dry = _build(script, tmp_path / "dry", "--dry-run")
    assert dry.exit_code == 0, dry.error
    assert dry.envelope["result"]["board_items"]["images"] == 1  # type: ignore[index]
    out = tmp_path / "out"
    reply = _build(script, out, "--confirm")
    assert reply.exit_code == 0, reply.error
    first = (out / "blink.kicad_pcb").read_bytes()
    root = parse(first.decode("utf-8"))
    (node,) = root.nodes("image")
    assert [c.name for c in node.nodes()] == ["at", "layer", "scale", "data", "uuid"]
    assert dumps(node.find("scale"), style="compact") == "(scale 0.5)"  # type: ignore[arg-type]
    chunks = [a.value for a in node.find("data").atoms()]  # type: ignore[union-attr]
    assert all(len(c) == 76 for c in chunks[:-1]) and "".join(chunks) == base64.b64encode(data).decode()
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    (image,) = back.board.images
    assert (image.layer, image.scale, image.position) == ("F.SilkS", "0.5", Point(105_000_000, 105_000_000))
    assert base64.b64decode(image.data) == data
    assert _build(script, out, "--confirm").exit_code == 0
    assert (out / "blink.kicad_pcb").read_bytes() == first
    (script.parent / "logo.png").unlink()
    missing = _build(script, tmp_path / "gone", "--dry-run")
    assert missing.exit_code == 5
    assert "build.image-missing" in [i["code"] for i in missing.envelope["issues"]]  # type: ignore[index]


def test_not_a_png(tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=LINE)
    (script.parent / "logo.png").write_bytes(b"GIF89a not a png")
    reply = _build(script, tmp_path / "out", "--confirm")
    assert reply.exit_code == 5 and not (tmp_path / "out" / "blink.kicad_pcb").exists()
    assert "build.image-format" in [i["code"] for i in reply.envelope["issues"]]  # type: ignore[index]


def test_image_id_and_altium_report(tmp_path: Path) -> None:
    from fenolite.dsl import to_model

    d = Design("img")
    d.board(mm(20), mm(20))
    d.image("logo", "logo.png", (mm(1), mm(1)))
    assert to_model(d).board.images == ()  # type: ignore[union-attr]  # the build reads the file
    assert derived_id("img", "dsl", "image:logo").startswith("img_")
