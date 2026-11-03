# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0354: resource reads are explicit, bounded, exact and confined."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest
from _project_resources import WORKSHEET

from fenolite.core.errors import FormatError
from fenolite.lens.project_resources import MAX_RESOURCE_BYTES, ProjectResource, validate_resources
from fenolite.lens.project_template import read_project_template


def given(tmp_path, reference="frames/authored.kicad_wks", body=WORKSHEET):
    script = tmp_path / "design.py"
    script.write_text("# Authored for Fenolite\n")
    project = tmp_path / "native/project.kicad_pro"
    project.parent.mkdir()
    text = json.dumps(
        {
            "meta": {"version": 3},
            "net_settings": {"meta": {"version": 5}},
            "pcbnew": {"page_layout_descr_file": reference},
            "schematic": {"page_layout_descr_file": ""},
        }
    )
    project.write_text(text)
    resource = project.parent / "frames/authored.kicad_wks"
    resource.parent.mkdir()
    resource.write_bytes(body)
    return script, project, resource, ("native/project.kicad_pro", hashlib.sha256(text.encode()).hexdigest())


def test_exact_snapshot_has_no_filesystem_reads_at_validation(tmp_path) -> None:
    script, project, resource, request = given(tmp_path)
    read = read_project_template(script, request)
    assert read.text == project.read_text()
    assert read.resources == (ProjectResource("frames/authored.kicad_wks", resource, WORKSHEET),)
    resource.unlink()
    validate_resources(read.text, read.resources)
    with pytest.raises(FormatError, match="missing"):
        read_project_template(script, request)


@pytest.mark.parametrize(
    "reference",
    [
        "../authored.kicad_wks",
        "/authored.kicad_wks",
        "Z:/authored.kicad_wks",
        "${OTHER}/authored.kicad_wks",
        "frames/../authored.kicad_wks",
        "frames//authored.kicad_wks",
        "frames/./authored.kicad_wks",
        "frames/a:b.kicad_wks",
        "frames/CON.kicad_wks",
        "frames/authored.kicad_wks ",
        "frames/authored.txt",
        "frames\\authored.kicad_wks",
    ],
)
def test_nonportable_or_wrong_resource_kind_refuses(tmp_path, reference) -> None:
    script, project, resource, request = given(tmp_path, reference)
    before = resource.read_bytes()
    with pytest.raises(FormatError):
        read_project_template(script, request)
    assert resource.read_bytes() == before and project.exists()


@pytest.mark.parametrize(
    "body",
    [
        b"\xff",
        b"(kicad_pcb (version 20260206))",
        b"(kicad_wks (version 29990101))",
        b"(bad",
        b"",
    ],
)
def test_invalid_or_future_worksheet_refuses(tmp_path, body) -> None:
    script, project, resource, request = given(tmp_path, body=body)
    with pytest.raises(FormatError):
        read_project_template(script, request)
    assert resource.read_bytes() == body and project.exists()


@pytest.mark.parametrize("parent", [False, True])
def test_even_in_project_resource_symlinks_refuse(tmp_path, parent) -> None:
    script, project, resource, request = given(tmp_path)
    if parent:
        moved = project.parent / "real-frames"
        resource.parent.rename(moved)
        resource.parent.symlink_to(moved, target_is_directory=True)
    else:
        moved = resource.with_name("real.kicad_wks")
        resource.rename(moved)
        resource.symlink_to(moved)
    with pytest.raises(FormatError, match="symlink"):
        read_project_template(script, request)
    assert moved.exists()


def test_case_collisions_and_extra_or_duplicate_bundle_members_refuse(tmp_path) -> None:
    script, project, resource, request = given(tmp_path)
    read = read_project_template(script, request)
    item = read.resources[0]
    for invalid in ((item, item), (dataclasses.replace(item, name="extra.kicad_wks"),), ()):
        with pytest.raises(FormatError, match="exact references"):
            validate_resources(read.text, invalid)
    data = json.loads(read.text)
    data["schematic"]["page_layout_descr_file"] = "frames/AUTHORED.kicad_wks"
    with pytest.raises(FormatError, match="collide"):
        validate_resources(json.dumps(data), read.resources)
    with pytest.raises(FormatError, match="byte limit"):
        validate_resources(read.text, (dataclasses.replace(item, data=b" " * (MAX_RESOURCE_BYTES + 1)),))
    assert resource.read_bytes() == WORKSHEET


def test_managed_frame_never_reads_obsolete_native_resources(tmp_path) -> None:
    script, project, resource, request = given(tmp_path)
    resource.unlink()
    read = read_project_template(script, request, managed_frame=True)
    assert read.text == project.read_text() and read.resources == ()
    validate_resources(read.text, (), managed_frame=True)


def test_missing_reference_never_searches_script_root_or_unreferenced_files(tmp_path) -> None:
    script, project, resource, request = given(tmp_path)
    unrelated = project.parent / "unreferenced.kicad_wks"
    unrelated.write_bytes(b"(authored-not-to-be-read")
    read = read_project_template(script, request)
    assert [item.path for item in read.resources] == [resource]
    resource.unlink()
    same_name_elsewhere = tmp_path / "frames/authored.kicad_wks"
    same_name_elsewhere.parent.mkdir()
    same_name_elsewhere.write_bytes(WORKSHEET)
    with pytest.raises(FormatError, match="missing"):
        read_project_template(script, request)
    assert unrelated.read_bytes() == b"(authored-not-to-be-read"
