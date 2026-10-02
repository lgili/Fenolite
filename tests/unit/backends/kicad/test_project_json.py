# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact JSON for KiCad project files (capability kicad-file-backend, "Project JSON is preserved
exactly"; change c0010)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad._json import JsonNumber, dumps, get, key_paths, loads, structural_equal
from fenolite.backends.kicad.pro import read_project_text, write_project_text
from fenolite.core.errors import FormatError


def test_order_and_spellings_survive() -> None:
    text = '{"b": 1.50, "a": {"x": 1e-3, "y": -0}, "z": [1, "s", true, null]}'
    first = read_project_text(text)
    again = read_project_text(write_project_text(first))
    assert list(again) == ["b", "a", "z"]
    assert again["b"] == JsonNumber("1.50")
    assert again["a"] == {"x": JsonNumber("1e-3"), "y": JsonNumber("-0")}
    assert again["z"] == [JsonNumber("1"), "s", True, None]
    assert structural_equal(first, again)


def test_no_float_anywhere() -> None:
    def walk(value: object) -> None:
        assert not isinstance(value, float)
        if isinstance(value, dict):
            for item in value.values():  # type: ignore[union-attr]
                walk(item)
        elif isinstance(value, list):
            for item in value:  # type: ignore[union-attr]
                walk(item)

    walk(loads('{"a": [1.0, 2e5, {"b": -3.25}]}'))


def test_printer_layout() -> None:
    assert write_project_text({"a": [JsonNumber("1")], "b": {}}) == '{\n  "a": [\n    1\n  ],\n  "b": {}\n}\n'
    assert dumps({"s": 'é " \\', "e": [], "n": None, "f": False}) == (
        '{\n  "s": "é \\" \\\\",\n  "e": [],\n  "n": null,\n  "f": false\n}\n'
    )


def test_float_refused_on_print() -> None:
    with pytest.raises(TypeError):
        dumps({"a": 1.5})


def test_duplicate_key_refused() -> None:
    with pytest.raises(FormatError) as caught:
        read_project_text('{"meta": {"version": 3, "version": 4}}', file="p.kicad_pro")
    assert caught.value.file == "p.kicad_pro" and caught.value.locator == "/meta/version"
    assert "version" in caught.value.message


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_not_a_number_refused(constant: str) -> None:
    with pytest.raises(FormatError) as caught:
        read_project_text(f'{{"a": {constant}}}')
    assert caught.value.locator == "/a"


def test_nested_pointer() -> None:
    with pytest.raises(FormatError) as caught:
        loads('{"a": [0, {"b/c": NaN}]}')
    assert caught.value.locator == "/a/1/b~1c"


def test_syntax_error_located_by_offset() -> None:
    with pytest.raises(FormatError) as caught:
        read_project_text('{"a": }')
    assert caught.value.offset == 6 and caught.value.locator == ""


def test_offset_is_in_bytes() -> None:
    with pytest.raises(FormatError) as caught:
        loads('{"é": }')
    assert caught.value.offset == 7


@pytest.mark.parametrize("text", ["[]", "1", '"x"', "null"])
def test_root_must_be_an_object(text: str) -> None:
    with pytest.raises(FormatError) as caught:
        loads(text)
    assert caught.value.locator == ""


@pytest.mark.parametrize("text", ["01", "1.", ".5", "+1", "1e", "NaN", " 1"])
def test_number_grammar(text: str) -> None:
    with pytest.raises(ValueError):
        JsonNumber(text)


def test_get_and_key_paths() -> None:
    data = loads('{"net_settings": {"classes": [{"name": "Default"}], "meta": {"version": 4}}, "a/b": 1}')
    assert get(data, "/net_settings/classes/0/name") == "Default"
    assert get(data, "/net_settings/missing") is None and get(data, "/a~1b") == JsonNumber("1")
    assert get(data, "") == data
    assert key_paths(data) == {
        "/net_settings",
        "/net_settings/classes",
        "/net_settings/classes/*",
        "/net_settings/classes/*/name",
        "/net_settings/meta",
        "/net_settings/meta/version",
        "/a~1b",
    }


def test_structural_equal() -> None:
    assert not structural_equal(loads('{"a": 1, "b": 2}'), loads('{"b": 2, "a": 1}'))
    assert not structural_equal(loads('{"a": 1.0}'), loads('{"a": 1}'))
    assert not structural_equal(loads('{"a": true}'), loads('{"a": 1}'))
    assert not structural_equal(loads('{"a": "1"}'), loads('{"a": 1}'))
    assert structural_equal(loads('{"a": [true, null]}'), loads('{ "a" : [ true , null ] }'))
