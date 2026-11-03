# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Effective field text comes from the real project and explicit instance (c0348)."""

from __future__ import annotations

import json
from pathlib import Path

import _intersheet
import pytest

from fenolite.core.errors import FormatError
from fenolite.view import kicad_intersheet as refs
from fenolite.view import themes
from fenolite.view.kicad_schematic import build_kicad_schematic_scene


def project(tmp_path: Path, *, pages=("2",), settings=None, hidden=False, same_page_labels=False) -> Path:
    payload = _intersheet.files(
        10,
        pages,
        settings=settings if settings is not None else {"intersheets_ref_show": True},
        hidden=hidden,
        same_page_labels=same_page_labels,
    )
    for name, data in payload.items():
        (tmp_path / name).write_bytes(data)
    return tmp_path / "tiny.kicad_pro"


def field_texts(scene):
    return [prim["s"] for prim in scene["prims"] if prim.get("role") == "intersheet_refs"]


@pytest.mark.parametrize(
    "pages,options,root_expected,child_expected",
    [
        (("2",), {}, "2", "1"),
        (("2",), {"intersheets_ref_own_page": True}, "1,2", "1,2"),
        (("2",), {"intersheets_ref_prefix": "[P", "intersheets_ref_suffix": "]"}, "[P2]", "[P1]"),
        (("2", "3", "4"), {}, "2,3,4", "1,3,4"),
        (("2", "3", "4"), {"intersheets_ref_short": True}, "2..4", "1..4"),
        (("3", "12", "4"), {}, "3,4,12", "1,4,12"),
        (("B", "A2", "A1"), {}, "A1,A2,B", "1,A1,A2"),
        (("A10", "A2", "A1"), {}, "A1,A2,A10", "1,A1,A2"),
        (("02", "2", "10"), {}, "02,2,10", "1,2,10"),
        (("a10", "A2", "B"), {}, "A2,B,a10", "1,A2,B"),
        (("2.1", "2.10", "2.2"), {}, "2.1,2.2,2.10", "1,2.2,2.10"),
        (("2", "02", "10"), {}, "2,02,10", "1,02,10"),
    ],
)
def test_complete_project_settings_and_instance_text(
    pages, options, root_expected, child_expected, tmp_path
) -> None:
    path = project(tmp_path, pages=pages, settings={"intersheets_ref_show": True, **options})
    bound = refs.resolve_project(path)
    root = bound.select("tiny.kicad_sch")
    child = bound.select("child.kicad_sch", instance=(f"PAGE{pages[0]}",))
    assert root.reference("AUTH_SHARED") == root_expected
    assert child.reference("AUTH_SHARED") == child_expected
    assert child.instance == (f"PAGE{pages[0]}",) and child.page == pages[0]


def test_same_page_labels_are_deduplicated_and_empty_affixes_survive(tmp_path) -> None:
    path = project(
        tmp_path,
        same_page_labels=True,
        settings={"intersheets_ref_show": True, "intersheets_ref_prefix": "[", "intersheets_ref_suffix": "]"},
    )
    bound = refs.resolve_project(path)
    root = bound.select("tiny.kicad_sch")
    assert root.reference("AUTH_SHARED") == "[2]" and root.reference("AUTH_ROOT_ONLY") == "[]"


def test_repeated_file_requires_an_explicit_instance(tmp_path) -> None:
    bound = refs.resolve_project(project(tmp_path, pages=("2", "3", "4")))
    assert len(bound.for_file("child.kicad_sch")) == 3
    with pytest.raises(FormatError, match="instance"):
        bound.select("child.kicad_sch")
    with pytest.raises(FormatError, match="instance"):
        bound.select("child.kicad_sch", instance=("MISSING",))


@pytest.mark.parametrize("defect", ["duplicate-page", "missing-page", "missing-child", "escape", "cycle"])
def test_missing_or_ambiguous_project_metadata_refuses(defect: str, tmp_path) -> None:
    path = project(tmp_path, pages=("2", "2") if defect == "duplicate-page" else ("2",))
    root = tmp_path / "tiny.kicad_sch"
    child = tmp_path / "child.kicad_sch"
    if defect == "missing-page":
        root.write_text(root.read_text().replace('(page "2")', ""))
    elif defect == "missing-child":
        child.unlink()
    elif defect == "escape":
        root.write_text(root.read_text().replace('"child.kicad_sch"', '"../outside.kicad_sch"'))
    elif defect == "cycle":
        root.write_text(root.read_text().replace('"child.kicad_sch"', '"tiny.kicad_sch"'))
    with pytest.raises(FormatError):
        refs.resolve_project(path)


@pytest.mark.parametrize(
    "key,value",
    [
        ("intersheets_ref_show", 1),
        ("intersheets_ref_short", "yes"),
        ("intersheets_ref_prefix", 3),
        ("intersheets_ref_suffix", "${UNKNOWN}"),
    ],
)
def test_settings_are_not_coerced_or_rendered_as_unexpanded_variables(key, value, tmp_path) -> None:
    path = project(tmp_path, settings={"intersheets_ref_show": True, key: value})
    with pytest.raises(FormatError):
        refs.resolve_project(path)


def test_raw_none_is_explicit_no_project_and_disabled_context_keeps_exact_scene(tmp_path) -> None:
    path = project(tmp_path, settings={"intersheets_ref_show": False}, hidden=True)
    data = (tmp_path / "tiny.kicad_sch").read_bytes()
    kwargs = {"name": "tiny.kicad_sch", "data": data, "palette": themes.palette("kicad")}
    raw = build_kicad_schematic_scene(data.decode(), **kwargs)
    context = refs.resolve_project(path).select("tiny.kicad_sch")
    disabled = build_kicad_schematic_scene(data.decode(), intersheet_context=context, **kwargs)
    assert disabled == raw and not field_texts(raw)


def test_view_resolves_hidden_field_at_its_native_pose_without_literal_placeholder(tmp_path) -> None:
    path = project(tmp_path, hidden=True)
    data = (tmp_path / "tiny.kicad_sch").read_bytes()
    context = refs.resolve_project(path).select("tiny.kicad_sch")
    scene = build_kicad_schematic_scene(
        data.decode(),
        name="tiny.kicad_sch",
        data=data,
        palette=themes.palette("kicad"),
        intersheet_context=context,
    )
    assert field_texts(scene) == ["2"]
    (field,) = [prim for prim in scene["prims"] if prim.get("role") == "intersheet_refs"]
    assert (field["x"], field["y"]) == (65000, 50000)
    assert "${INTERSHEET_REFS}" not in json.dumps(scene)
    assert scene["meta"]["instance"]["page"] == "1"


def test_wrong_file_or_stale_native_bytes_cannot_reuse_a_context(tmp_path) -> None:
    path = project(tmp_path)
    bound = refs.resolve_project(path)
    data = (tmp_path / "child.kicad_sch").read_bytes()
    context = bound.select("tiny.kicad_sch")
    with pytest.raises(FormatError):
        build_kicad_schematic_scene(
            data.decode(),
            name="child.kicad_sch",
            data=data,
            palette=themes.palette("kicad"),
            intersheet_context=context,
        )
    before = context.fingerprint
    settings = json.loads(path.read_text())
    settings["schematic"]["drawing"]["intersheets_ref_own_page"] = True
    path.write_text(json.dumps(settings))
    after = refs.resolve_project(path).select("tiny.kicad_sch")
    assert after.fingerprint != before and after.reference("AUTH_SHARED") == "1,2"


def test_no_project_path_is_standalone_but_failed_or_ambiguous_owner_is_not(tmp_path) -> None:
    path = project(tmp_path)
    child = tmp_path / "child.kicad_sch"
    assert refs.contexts_for_path(child)[0].reference("AUTH_SHARED") == "1"
    (tmp_path / "other.kicad_pro").write_bytes(path.read_bytes())
    (tmp_path / "other.kicad_sch").write_bytes((tmp_path / "tiny.kicad_sch").read_bytes())
    with pytest.raises(FormatError):
        refs.contexts_for_path(child)  # A malformed candidate is never silently standalone.
    (tmp_path / "other.kicad_sch").write_text(
        (tmp_path / "tiny.kicad_sch").read_text().replace('(project "tiny"', '(project "other"')
    )
    with pytest.raises(FormatError, match="owner"):
        refs.contexts_for_path(child)
    (tmp_path / "other.kicad_pro").unlink()
    (tmp_path / "other.kicad_sch").unlink()
    path.unlink()
    assert refs.contexts_for_path(child) == (None,)
