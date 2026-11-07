# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact immutable rule binding, closed receipts and capture isolation (c0359)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest
from _importcode import PROJECT

from fenolite.api import read_board
from fenolite.core.errors import FormatError
from fenolite.lens.native_rule_context import (
    CERTIFICATE,
    after_write,
    before_write,
    build_scope,
    capture_import,
    certificate,
    fingerprint,
    import_owner,
    read_binding,
)
from fenolite.model import canonical
from fenolite.model.design import Design


def model() -> Design:
    return read_board(PROJECT.with_suffix(".kicad_pcb")).design


def bundle(tmp_path: Path, design: Design):
    project = tmp_path / "project.kicad_pro"
    project.write_bytes(PROJECT.read_bytes())
    rules = tmp_path / "project.kicad_dru"
    rules.write_bytes(
        b'(version 1)\n# Authored CC0\n(rule "A"\n # opaque authored comment\n'
        b" (constraint clearance (min 0.2mm)))\n"
    )
    receipt = tmp_path / CERTIFICATE
    receipt.write_bytes(
        certificate(
            project.read_bytes(),
            rules.read_bytes(),
            design,
            10,
            [
                {
                    "path": "authored.kicad_pro",
                    "sha256": hashlib.sha256(project.read_bytes()).hexdigest(),
                    "kind": "kicad_pro",
                },
                {
                    "path": "authored.kicad_dru",
                    "sha256": hashlib.sha256(rules.read_bytes()).hexdigest(),
                    "kind": "kicad_dru",
                },
                {"path": "authored.kicad_pcb", "sha256": "0" * 64, "kind": "kicad_pcb"},
            ],
            emitted_pcb=PROJECT.with_suffix(".kicad_pcb").read_bytes(),
            emitted_project=project.read_bytes(),
        )
    )
    return project, rules, receipt


def test_only_tool_version_metadata_is_neutral():
    design = model()
    header = design.header
    changed = dataclasses.replace(design, header=dataclasses.replace(header, fenolite_version="9.9.9"))
    assert fingerprint(changed) == fingerprint(design)
    assert canonical.dumps(design) != canonical.dumps(changed)
    for key, value in (("name", header.name + "x"), ("schema_version", "2.0"), ("id", "dsn_" + "0" * 26)):
        changed = dataclasses.replace(design, header=dataclasses.replace(header, **{key: value}))
        assert fingerprint(changed) != fingerprint(design)
    neutral = dataclasses.replace(design, header=dataclasses.replace(header, fenolite_version=""))
    import hashlib

    assert fingerprint(design) == hashlib.sha256(canonical.dumps(neutral).encode()).hexdigest()
    assert design.header == header  # Never mutate the actual model or canonical output.


def test_every_authored_model_field_is_bound_or_constructor_refused():
    design = model()
    original = fingerprint(design)
    checked = 0

    def mutations(value, path=()):
        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                for candidate, refused, leaf in mutations(getattr(value, field.name), (*path, field.name)):
                    if refused:
                        yield None, True, leaf
                        continue
                    try:
                        yield dataclasses.replace(value, **{field.name: candidate}), False, leaf
                    except (ValueError, TypeError, FormatError):
                        yield None, True, leaf
        elif isinstance(value, (tuple, list)):
            if not value:
                yield (
                    ("AUTHORED_EMPTY_CHANGE",) if isinstance(value, tuple) else ["AUTHORED_EMPTY_CHANGE"],
                    False,
                    path,
                )
            for index, child in enumerate(value):
                for candidate, refused, leaf in mutations(child, (*path, index)):
                    changed = list(value)
                    changed[index] = candidate
                    yield tuple(changed) if isinstance(value, tuple) else changed, refused, leaf
        elif isinstance(value, dict):
            if not value:
                yield {"authored_empty_change": "changed"}, False, path
            for key, child in value.items():
                changed = dict(value)
                changed[str(key) + "__authored_context"] = changed.pop(key)
                yield changed, False, (*path, "<mapping-key>", key)
                for candidate, refused, leaf in mutations(child, (*path, key)):
                    changed = dict(value)
                    changed[key] = candidate
                    yield changed, refused, leaf
        elif isinstance(value, (str, int, bool)) or value is None:
            changed = (
                not value
                if isinstance(value, bool)
                else value + 1
                if isinstance(value, int)
                else value + "x"
                if isinstance(value, str)
                else "AUTHORED_NONE_CHANGE"
            )
            yield changed, False, path

    for changed, refused, path in mutations(design):
        if path == ("header", "fenolite_version"):
            continue
        if not refused:
            assert fingerprint(changed) != original, path
        checked += 1
    # Includes optional/default fields and actual mapping keys, not only populated JSON leaves.
    assert checked > 1000


def test_exact_binding_and_capture_do_not_bypass_validation(tmp_path: Path):
    design = model()
    project, rules, _ = bundle(tmp_path, design)
    binding = read_binding(project, project.read_bytes())
    assert binding is not None
    owner = tmp_path / "design.py"
    with (
        capture_import("authored", 10) as captured,
        import_owner(owner),
        build_scope(owner, "authored", 10, binding),
    ):
        assert before_write(design, "authored", 10) == rules.read_bytes()
        after_write(PROJECT.with_suffix(".kicad_pcb").read_bytes(), project.read_bytes(), "authored", 10)
    assert captured.count == 1 and captured.design is design
    changed = dataclasses.replace(design, header=dataclasses.replace(design.header, name="changed"))
    with pytest.raises(FormatError, match="unchanged complete"):
        with capture_import("authored", 10), import_owner(owner), build_scope(owner, "authored", 10, binding):
            before_write(changed, "authored", 10)
    assert before_write(design, "authored", 10) is None  # No context leaks after failure.


@pytest.mark.parametrize("defect", ["zero", "multiple", "owner", "name", "target", "nested"])
def test_capture_exact_ownership_and_multiplicity(tmp_path: Path, defect: str):
    design = model()
    owner = tmp_path / "design.py"
    with pytest.raises(FormatError):
        with capture_import("authored", 10), import_owner(owner):
            if defect == "zero":
                pass
            elif defect == "nested":
                with capture_import("authored", 10):
                    pass
            else:
                with build_scope(owner if defect != "owner" else tmp_path / "other.py", "authored", 10, None):
                    before_write(
                        design, "other" if defect == "name" else "authored", 9 if defect == "target" else 10
                    )
                    if defect == "multiple":
                        before_write(design, "authored", 10)
    assert before_write(design, "authored", 10) is None


@pytest.mark.parametrize(
    "defect",
    ["missing", "version", "target", "encoding", "extra", "hash", "path", "kind", "duplicate", "unsafe"],
)
def test_closed_certificate_refuses_invalid_input(tmp_path: Path, defect: str):
    project, rules, receipt = bundle(tmp_path, model())
    data = json.loads(receipt.read_bytes())
    if defect == "missing":
        receipt.unlink()
    else:
        if defect == "version":
            data["version"] = True
        elif defect == "target":
            data["target"] = 11
        elif defect == "encoding":
            data["baseline"]["encoding"] = "generic"
        elif defect == "extra":
            data["success"] = True
        elif defect == "hash":
            data["rules"]["sha256"] = "f" * 64
        elif defect == "path":
            data["rules"]["path"] = "elsewhere.kicad_dru"
        elif defect == "kind":
            data["source_inputs"][0]["kind"] = []
        elif defect == "duplicate":
            data["source_inputs"].append(data["source_inputs"][0])
        elif defect == "unsafe":
            data["source_inputs"][0]["path"] = "../private"
        receipt.write_text(json.dumps(data))
    with pytest.raises(FormatError):
        read_binding(project, project.read_bytes())
    assert rules.is_file()


def test_raw_input_changes_and_symlinks_refuse(tmp_path: Path):
    project, rules, receipt = bundle(tmp_path, model())
    rules.write_bytes(rules.read_bytes() + b"# changed\n")
    with pytest.raises(FormatError, match="binding differs"):
        read_binding(project, project.read_bytes())
    rules.unlink()
    rules.symlink_to(receipt)
    with pytest.raises(FormatError, match="symlink"):
        read_binding(project, project.read_bytes())


@pytest.mark.parametrize("which", ["pcb", "project"])
def test_actual_emitted_bytes_are_checked_in_addition_to_model(tmp_path: Path, which: str):
    design = model()
    project, _, _ = bundle(tmp_path, design)
    binding = read_binding(project, project.read_bytes())
    board_bytes = PROJECT.with_suffix(".kicad_pcb").read_bytes()
    project_bytes = project.read_bytes()
    with build_scope(tmp_path / "design.py", "authored", 10, binding):
        before_write(design, "authored", 10)
        with pytest.raises(FormatError, match="unchanged emitted"):
            after_write(
                board_bytes + (b"\n" if which == "pcb" else b""),
                project_bytes + (b"\n" if which == "project" else b""),
                "authored",
                10,
            )
