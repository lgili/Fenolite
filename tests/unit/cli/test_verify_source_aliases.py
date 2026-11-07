# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Root path aliases preserve project-relative identities and reviewed input hashes (c0354)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _importcode import copy_project
from _project_resources import WORKSHEET, source_with_resource
from _project_template import STAMP, imported, snapshot

from fenolite.api import run
from fenolite.importer.source import read_kicad


@pytest.mark.parametrize("resource", (False, True))
def test_verify_root_alias_retains_relative_trace_without_internal_error(
    tmp_path: Path, resource: bool
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    source = source_with_resource(real, 10, "pcbnew") if resource else copy_project(real)
    alias = tmp_path / "alias"
    alias.symlink_to(source.parent, target_is_directory=True)
    aliased_project = alias / source.name
    before = snapshot(source.parent)
    code = imported(tmp_path, source, target=10)
    reply = run(
        "verify-source",
        str(code / "design.py"),
        "--against",
        str(aliased_project),
        "--target",
        "10",
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert reply.exit_code == 0, (reply.error, reply.envelope)
    assert reply.result["differences"] == reply.result["accepted"] == []
    files = reply.result["against"]["files"]
    assert (
        files[source.with_suffix(".kicad_pcb").name]
        == hashlib.sha256(source.with_suffix(".kicad_pcb").read_bytes()).hexdigest()
    )
    assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in files)
    if resource:
        assert files["frames/authored.kicad_wks"] == hashlib.sha256(WORKSHEET).hexdigest()
    assert snapshot(source.parent) == before


def test_importer_resource_snapshot_retains_lexical_alias_paths(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    source = source_with_resource(real, 10, "pcbnew")
    alias = tmp_path / "alias"
    alias.symlink_to(source.parent, target_is_directory=True)
    read = read_kicad(alias / source.name)
    assert read.folder == alias
    assert all(path.is_relative_to(alias) for path in read.paths)
    assert {path.relative_to(alias).as_posix() for path in read.paths} >= {
        source.name,
        "frames/authored.kicad_wks",
    }


@pytest.mark.parametrize("resource", (False, True))
def test_root_alias_rebinding_invalidates_reviewed_record_plan(tmp_path: Path, resource: bool) -> None:
    real = tmp_path / "real"
    real.mkdir()
    source = source_with_resource(real, 10, "pcbnew") if resource else copy_project(real)
    code = imported(tmp_path, source, target=10)
    other = tmp_path / "other-project"
    shutil.copytree(source.parent, other)
    changed = (
        other / "frames/authored.kicad_wks" if resource else other / source.with_suffix(".kicad_pcb").name
    )
    changed.write_bytes(changed.read_bytes() + b"\n")
    alias = tmp_path / "alias"
    alias.symlink_to(source.parent, target_is_directory=True)
    argv = (
        "verify-source",
        str(code / "design.py"),
        "--against",
        str(alias / source.name),
        "--target",
        "10",
        "--provenance",
        str(code / "PROVENANCE.json"),
        "--record",
    )
    dry = run(*argv, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert dry.exit_code == 0, (dry.error, dry.envelope)
    original_record = (code / "PROVENANCE.json").read_bytes()
    alias.unlink()
    alias.symlink_to(other, target_is_directory=True)
    reply = run(*argv, "--confirm", "--plan", dry.result["plan_id"], cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 4 and reply.error and reply.error["code"] == "FEN-4002"
    assert (code / "PROVENANCE.json").read_bytes() == original_record
