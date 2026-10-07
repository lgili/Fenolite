# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pins and the stamp of the fetched 3D models (capability kicad-library-resolution, "3D model pins";
change c0116). Hermetic."""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

import pytest

from fenolite.backends.kicad import libcache
from fenolite.backends.kicad.libcache import ModelPin, load_model_pins, load_pins


def _pins_text() -> str:
    return resources.files("fenolite.backends.kicad").joinpath("data/libraries.toml").read_text("utf-8")


def _file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "pins.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_model_pins_of_both_tags() -> None:
    pins = load_model_pins()
    assert [(pin.tag, pin.major, pin.project) for pin in pins] == [
        ("10.0.6", 10, "kicad/libraries/kicad-packages3D"),
        ("9.0.9", 9, "kicad/libraries/kicad-packages3D"),
    ]
    assert all(isinstance(pin, ModelPin) and re.fullmatch(r"[0-9a-f]{40}", pin.commit) for pin in pins)
    assert len({pin.commit for pin in pins}) == 2
    assert len(load_pins()) == 4  # the library pins are what they were
    assert {pin.tag for pin in load_pins()} == {pin.tag for pin in pins}


def test_malformed_model_pin_names_the_file_and_the_key(tmp_path: Path) -> None:
    text = _pins_text()
    commit = load_model_pins()[0].commit
    with pytest.raises(ValueError, match=r"pins\.toml: models\[0\]\.commit"):
        load_model_pins(_file(tmp_path, text.replace(commit, commit[:39])))
    with pytest.raises(ValueError, match=r"models\[0\]\.project"):
        load_model_pins(_file(tmp_path, text.replace("kicad-packages3D", "kicad-templates", 1)))
    wrong_major = text.replace('tag = "9.0.9"\nmajor = 9\nproject', 'tag = "9.0.9"\nmajor = 10\nproject')
    assert wrong_major != text
    with pytest.raises(ValueError, match=r"models\[1\]\.major"):
        load_model_pins(_file(tmp_path, wrong_major))
    with pytest.raises(ValueError, match=r"models\[1\]\.tree: unknown key"):
        load_model_pins(_file(tmp_path, text + 'tree = "x"\n'))  # the key lands in the last table
    with pytest.raises(ValueError, match=r"models\[1\]\.commit: missing key"):
        load_model_pins(_file(tmp_path, text[: text.rindex("commit = ")]))


def test_one_model_pin_per_tag(tmp_path: Path) -> None:
    text = _pins_text()
    first = text.index("[[models]]")
    second = text.index("[[models]]", first + 1)
    with pytest.raises(ValueError, match="tag 9.0.9 has no model pin"):
        load_model_pins(_file(tmp_path, text[:second]))
    with pytest.raises(ValueError, match="pinned twice"):
        load_model_pins(_file(tmp_path, text + "\n" + text[first:second]))
    with pytest.raises(ValueError, match=r"models: must be a non-empty array"):
        load_model_pins(_file(tmp_path, text[:first]))
    other = text[first:second].replace('"10.0.6"', '"8.0.9"').replace("major = 10", "major = 8")
    with pytest.raises(ValueError, match=r"models\[2\]\.tag"):
        load_model_pins(_file(tmp_path, text + "\n" + other))
    assert len(load_pins(_file(tmp_path, text[:first]))) == 4  # load_pins ignores the model tables


def test_model_stamp_round_trip(tmp_path: Path) -> None:
    assert libcache.read_model_stamp(tmp_path) == {}
    entries = {"B.3dshapes/b.step": "b" * 64, "A.3dshapes/a.step": "a" * 64}
    libcache.write_model_stamp(tmp_path, entries)
    assert libcache.read_model_stamp(tmp_path) == entries
    text = (tmp_path / libcache.MODEL_STAMP).read_text(encoding="utf-8")
    assert list(json.loads(text)) == sorted(entries) and text.endswith("\n")
    assert libcache.MODEL_STAMP == ".fenolite-models.json" and libcache.MODEL_REPO == "kicad-packages3D"


def test_model_stamp_that_is_not_such_an_object(tmp_path: Path) -> None:
    stamp = tmp_path / libcache.MODEL_STAMP
    stamp.write_text("[]", encoding="utf-8")
    assert libcache.read_model_stamp(tmp_path) == {}
    stamp.write_text("{broken", encoding="utf-8")
    assert libcache.read_model_stamp(tmp_path) == {}
    stamp.write_text(json.dumps({"a.step": "a" * 64, "b.step": "short", "c.step": 3}), encoding="utf-8")
    assert libcache.read_model_stamp(tmp_path) == {"a.step": "a" * 64}


def test_file_sha256(tmp_path: Path) -> None:
    path = tmp_path / "x.bin"
    path.write_bytes(b"abc")
    assert libcache.file_sha256(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
