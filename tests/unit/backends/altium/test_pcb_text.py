# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Free texts of the Altium PCB document (capability altium-pcb-writer, "Board text records"; change
c0085)."""

from __future__ import annotations

import dataclasses

import pytest
from _altium import blink_pcbdoc_spec
from _altium_board6 import IMPORT_LAYERS, at, bare_spec, imported_point, near, read_back

from fenolite.backends.altium.pcbdoc import TEXT_SIZE, PcbDocSpec, short_text, text_problem_of, write_pcbdoc
from fenolite.core.coords import Size
from fenolite.model.board import Text


def text(key: str, string: str, layer: str = "F.SilkS", **changes: object) -> Text:
    fields: dict[str, object] = {
        "id": f"txt_{key}",
        "text": string,
        "position": at(10, 10),
        "layer": layer,
        "size": Size(1_000_000, 1_000_000),
        "thickness": 150_000,
    }
    return Text(**{**fields, **changes})  # type: ignore[arg-type]


def test_accented_text() -> None:
    """Scenario "Accented text": the string, the top overlay and the place within 2 nm."""
    wanted = text("a", "Tensão 5 V")
    document, design = read_back(bare_spec(texts=(wanted,)))
    (record,) = document.texts
    assert record.text == "Tensão 5 V" and record.short_text == "Tensão 5 V"
    assert record.prefix.layer == 33 and record.prefix.component is None
    assert (record.is_designator, record.is_comment, record.font_type, record.mirrored) == (
        False,
        False,
        0,
        False,
    )
    assert len(record.raw) == 1 + 4 + TEXT_SIZE + 4 + 1 + len("Tensão 5 V".encode("iso-8859-1"))
    assert dict(document.wide_strings) == {0: "Tensão 5 V"}
    assert design.board is not None
    (read,) = design.board.texts
    assert read.text == wanted.text and read.layer == "F.SilkS"
    assert near(read.position, imported_point(wanted.position))


def test_a_string_outside_latin_1_survives_in_the_wide_string() -> None:
    wanted = text("o", "10 kΩ ±1 % – 日本")
    document, design = read_back(bare_spec(texts=(wanted,)))
    (record,) = document.texts
    assert record.text == wanted.text and record.short_text == "10 k? ±1 % ? ??"
    assert design.board is not None and design.board.texts[0].text == wanted.text
    assert short_text("é") == b"\x01\xe9" and len(short_text("x" * 300)) == 256


def test_height_stroke_rotation_layer_and_mirror() -> None:
    texts = (
        text("a", "TOP", "F.Fab", size=Size(800_000, 2_000_000), thickness=200_000, rotation=90_000_000),
        text("b", "BACK", "B.SilkS", position=at(20, 10), rotation=-45_000_000),
        text("c", "PASTE", "B.Paste", position=at(30, 10)),
    )
    document, design = read_back(bare_spec(texts=texts))
    by_text = {record.text: record for record in document.texts}
    assert [by_text[t.text].prefix.layer for t in texts] == [69, 34, 36]
    assert [by_text[t.text].mirrored for t in texts] == [False, True, True]  # bottom-side layers
    assert [by_text[t.text].rotation for t in texts] == [90.0, 315.0, 0.0]
    assert design.board is not None
    read = {t.text: t for t in design.board.texts}
    for wanted in texts:
        found = read[wanted.text]
        assert found.layer == IMPORT_LAYERS.get(wanted.layer, wanted.layer)
        assert abs(found.size.h - wanted.size.h) <= 2 and abs(found.thickness - wanted.thickness) <= 2
        assert found.rotation == wanted.rotation % 360_000_000
        assert near(found.position, imported_point(wanted.position))
    assert sorted(document.wide_strings) == [0, 1, 2]


def test_texts_follow_the_component_texts_in_the_wide_strings() -> None:
    """The wide-string index of a free text continues after the designators and comments."""
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    outline = spec.outline
    free = text("f", "Olá", position=outline[0])
    document, _ = read_back(dataclasses.replace(spec, texts=(free,)), "blink.PcbDoc")
    component_texts = 2 * len(spec.components)
    assert len(document.texts) == component_texts + 1
    last = document.texts[-1]
    assert last.wide_index == component_texts and last.text == "Olá"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"text": ""}, "the text is empty"),
        ({"text": "two\nlines"}, "a control character or a line break"),
        ({"size": Size(0, 0)}, "a height of 0 nm is not positive"),
        ({"thickness": 0}, "a stroke width of 0 nm is not positive"),
    ],
)
def test_texts_the_writer_refuses(changes: dict[str, object], message: str) -> None:
    bad = text("bad", "X", **changes)
    assert message in (text_problem_of(bad) or "")
    with pytest.raises(ValueError, match="txt_bad: "):
        write_pcbdoc(bare_spec(texts=(bad,)))
    with pytest.raises(ValueError, match="txt_cu: the layer F.Cu has no layer in the document"):
        write_pcbdoc(bare_spec(texts=(text("cu", "X", "F.Cu"),)))
