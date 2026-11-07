# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Public context mirrors bind their actual schema, never silently rewrite identities (c0217)."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest
from _contextual_symbols import code

from fenolite.backends.kicad import symbol_contexts
from fenolite.core.errors import FormatError
from fenolite.lens.drawn import read_drawn


def write(path: Path, data: dict) -> None:
    lines = [f"{key} = {json.dumps(value)}" for key, value in data.items() if key != "symbol"]
    for row in data["symbol"]:
        lines.extend(("", "[[symbol]]", *(f"{key} = {json.dumps(value)}" for key, value in row.items())))
    path.write_text("\n".join(lines) + "\n")


def rebind(data: dict) -> None:
    for row in data["symbol"]:
        value = {
            "schema": data["schema"],
            "drawing": data["drawing"],
            "target": data["target"],
            **{key: value for key, value in row.items() if key != "binding_sha256"},
        }
        row["binding_sha256"] = hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()


def load(folder: Path):
    drawing = folder / "schematic.toml"
    return symbol_contexts.read(
        folder / symbol_contexts.FILE,
        drawing_path=drawing,
        drawn=read_drawn(drawing.read_text()),
        project_folder=folder,
    )


@pytest.mark.parametrize("target", (9, 10))
def test_v1_context_requires_explicit_rebinding_and_keeps_native_snapshots(
    tmp_path: Path, target: int
) -> None:
    folder = tmp_path / "code"
    code(folder, target)
    path = folder / symbol_contexts.FILE
    original = path.read_bytes()
    before = load(folder)
    data = tomllib.loads(original.decode())
    data["schema"] = "fenolite.symbol-contexts.v1"
    write(path, data)
    with pytest.raises(FormatError):
        load(folder)
    rebind(data)
    write(path, data)
    after = load(folder)
    assert before.symbols == after.symbols
    assert before.definition_digests == after.definition_digests
    assert path.read_bytes() != original
    code(tmp_path / "repeat" / "code", target)
    assert (tmp_path / "repeat/code" / symbol_contexts.FILE).read_bytes() == original


@pytest.mark.parametrize(
    "defect", ("future", "bool-target", "wrong-target", "unknown", "binding", "asset", "definition")
)
def test_mirror_context_refuses_tampered_or_invalid_fields(tmp_path: Path, defect: str) -> None:
    folder = tmp_path / "code"
    code(folder)
    data = tomllib.loads((folder / symbol_contexts.FILE).read_text())
    data["schema"] = "fenolite.symbol-contexts.v1"
    rebind(data)
    if defect == "future":
        data["schema"] = "fenolite.symbol-contexts.v2"
    elif defect == "bool-target":
        data["target"] = True
    elif defect == "wrong-target":
        data["target"] = 10
        rebind(data)
    elif defect == "unknown":
        data["unknown"] = "no"
    else:
        field = {"binding": "binding_sha256", "asset": "asset_sha256", "definition": "definition_sha256"}[
            defect
        ]
        data["symbol"][0][field] = "0" * 64
        if defect != "binding":
            rebind(data)
    write(folder / symbol_contexts.FILE, data)
    with pytest.raises(FormatError):
        load(folder)


def test_context_descriptor_is_closed_typed_and_nonempty(tmp_path: Path) -> None:
    import copy

    import _schema

    folder = tmp_path / "code"
    code(folder)
    data = tomllib.loads((folder / symbol_contexts.FILE).read_text())
    data["schema"] = "fenolite.symbol-contexts.v1"
    rebind(data)
    schema = _schema.load("formats/fenolite.symbol-contexts.v1.json")
    assert _schema.validate(data, schema) == []
    variants = []
    for key, value in (
        ("schema", "fenolite.symbol-contexts.v2"),
        ("target", True),
        ("symbol", []),
        ("extra", "no"),
    ):
        changed = copy.deepcopy(data)
        changed[key] = value
        variants.append(changed)
    changed = copy.deepcopy(data)
    changed["symbol"][0]["extra"] = "no"
    variants.append(changed)
    changed = copy.deepcopy(data)
    changed["symbol"][0]["asset_sha256"] = "X" * 64
    variants.append(changed)
    assert all(_schema.validate(changed, schema) for changed in variants)
