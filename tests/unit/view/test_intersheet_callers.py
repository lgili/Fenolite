# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path-aware effective field context, explicit instances and dependent cache/live invalidation."""

from __future__ import annotations

import json

import _intersheet
import pytest

from fenolite.cli._presentation import sheet_scenes
from fenolite.cli.cmd_view import scene_of
from fenolite.core.errors import FormatError


def project(folder, *, repeated=False):
    for name, data in _intersheet.files(
        10, ("2", "3") if repeated else ("2",), settings={"intersheets_ref_show": True}, hidden=True
    ).items():
        (folder / name).write_bytes(data)
    return folder / "tiny.kicad_pro"


def texts(scene):
    return [p["s"] for p in scene["prims"] if p.get("role") == "intersheet_refs"]


def test_path_scene_reads_actual_project_and_hidden_field_override(tmp_path):
    project(tmp_path)
    assert texts(scene_of(tmp_path / "tiny.kicad_sch")) == ["2"]


def test_presentation_expands_each_actual_repeated_instance(tmp_path):
    project(tmp_path, repeated=True)
    scenes = sheet_scenes(tmp_path)
    assert len(scenes) == 3
    assert sorted(tuple(texts(scene)) for scene in scenes.values()) == [("1,2", "2"), ("1,3", "3"), ("2,3",)]
    assert {tuple(scene["meta"]["instance"]["path"]) for scene in scenes.values()} == {
        (),
        ("PAGE2",),
        ("PAGE3",),
    }


def test_direct_repeated_child_requires_explicit_instance(tmp_path):
    project(tmp_path, repeated=True)
    with pytest.raises(FormatError, match="instance"):
        scene_of(tmp_path / "child.kicad_sch")


def test_path_context_does_not_use_a_disabled_fallback_after_invalid_project(tmp_path):
    path = project(tmp_path)
    path.write_text('{"schematic":{"drawing":{"intersheets_ref_show":"wrong"}}}')
    with pytest.raises(FormatError):
        scene_of(tmp_path / "tiny.kicad_sch")


def exported(base, source, *, name="view.html", doc=None):
    from fenolite.api import run
    from fenolite.view.export import embedded

    args = ("--doc", doc) if doc else ()
    planned = run(
        "view",
        str(source),
        "--export",
        name,
        "--cache",
        "project",
        "--no-models",
        *args,
        "--dry-run",
        cwd=base,
    )
    assert planned.exit_code == 0, planned.error
    confirmed = run(
        "view",
        str(source),
        "--export",
        name,
        "--cache",
        "project",
        "--no-models",
        *args,
        "--confirm",
        "--plan",
        planned.result["plan_id"],
        cwd=base,
    )
    assert confirmed.exit_code == 0, confirmed.error
    payload = embedded((base / name).read_text(encoding="utf-8"))
    assert payload is not None
    return payload, confirmed


def test_actual_cli_exports_explicit_repeated_instances_and_refuses_ambiguous_alias(tmp_path):
    from fenolite.api import run

    source = project(tmp_path, repeated=True)
    payload, _ = exported(tmp_path, source)
    scenes = payload["scenes"]
    assert len(scenes) == 3 and all(":instance:" in key for key in scenes)
    assert sorted(tuple(texts(scene)) for scene in scenes.values()) == [("1,2", "2"), ("1,3", "3"), ("2,3",)]
    child = next(key for key, scene in scenes.items() if scene["meta"]["instance"]["path"] == ["PAGE2"])
    chosen, _ = exported(tmp_path, source, name="one.html", doc=child)
    assert chosen["open"] == child
    for path, doc in ((source, "child.kicad_sch"), (tmp_path / "child.kicad_sch", None)):
        args = ("--doc", doc) if doc else ()
        refused = run("view", str(path), *args, cwd=tmp_path)
        assert refused.exit_code == 3 and refused.error["code"] == "FEN-3004"


def test_actual_cli_cache_binds_project_only_and_hierarchy_changes(tmp_path):
    source = project(tmp_path)
    original, _ = exported(tmp_path, source)
    before = {key: tuple(texts(scene)) for key, scene in original["scenes"].items()}
    data = json.loads(source.read_text())
    data["schematic"]["drawing"]["intersheets_ref_prefix"] = "CHANGED["
    data["schematic"]["drawing"]["intersheets_ref_suffix"] = "]"
    source.write_text(json.dumps(data))
    changed, reply = exported(tmp_path, source, name="changed.html")
    assert reply.result["cache"]["misses"] == 2
    assert {key: tuple(texts(scene)) for key, scene in changed["scenes"].items()} != before
    assert all(text.startswith("CHANGED[") for scene in changed["scenes"].values() for text in texts(scene))
    root = tmp_path / "tiny.kicad_sch"
    root.write_text(root.read_text().replace('(page "2")', '(page "7")'))
    hierarchy, reply = exported(tmp_path, source, name="hierarchy.html")
    assert reply.result["cache"]["misses"] == 2
    assert any("7" in text for scene in hierarchy["scenes"].values() for text in texts(scene))


def test_live_uses_explicit_documents_and_rebuilds_project_only_changes(tmp_path):
    from fenolite.view.intersheet_bindings import Bindings
    from fenolite.view.project import load_tree
    from fenolite.view.server import Live

    source = project(tmp_path, repeated=True)
    binding = Bindings(load_tree(source))

    def build_document(doc):
        return scene_of(doc.file, intersheet_context=binding.context(doc.file, doc))

    live = Live(
        binding.tree,
        lambda _path: pytest.fail("instance collapsed to physical path"),
        document_builder=build_document,
        dependency_key=binding.dependency_key,
    )
    before = {}
    for doc in binding.tree.documents:
        if doc.viewable:
            before[doc.id] = live.scene(doc.id)
    assert len(before) == 3 and len(set(before.values())) == 3
    data = json.loads(source.read_text())
    data["schematic"]["drawing"]["intersheets_ref_prefix"] = "LIVE["
    source.write_text(json.dumps(data))
    assert live.check() == []
    assert set(live.check()) == set(before)
    for identity, old in before.items():
        new = live.scene(identity)
        assert new != old and live.version(identity)["error"] is None
        assert all(text.startswith("LIVE[") for text in texts(json.loads(new)))


def test_live_retains_last_good_and_recovers_when_new_required_sheet_appears(tmp_path):
    from fenolite.view.intersheet_bindings import Bindings
    from fenolite.view.project import load_tree
    from fenolite.view.server import Live

    source = project(tmp_path)
    binding = Bindings(load_tree(source))
    root = next(doc for doc in binding.tree.documents if doc.path == "tiny.kicad_sch")
    live = Live(
        binding.tree,
        lambda _path: pytest.fail("document context required"),
        document_builder=lambda doc: scene_of(doc.file, intersheet_context=binding.context(doc.file, doc)),
        dependency_key=binding.dependency_key,
    )
    original = live.scene(root.id)
    path = tmp_path / "tiny.kicad_sch"
    path.write_text(path.read_text().replace('"child.kicad_sch"', '"new-child.kicad_sch"'))
    for _ in range(3):
        live.check()
    assert "missing or unreadable" in live.version(root.id)["error"]
    assert live.scene(root.id) == original
    (tmp_path / "new-child.kicad_sch").write_bytes((tmp_path / "child.kicad_sch").read_bytes())
    for _ in range(3):
        live.check()
    assert live.version(root.id)["error"] is None
    assert live.scene(root.id) is not None


def test_export_staged_context_inputs_are_bound_to_review(tmp_path):
    from fenolite.api import run

    source = project(tmp_path)
    planned = run("view", str(source), "--export", "view.html", "--dry-run", "--no-models", cwd=tmp_path)
    assert planned.exit_code == 0, planned.error
    source.write_bytes(source.read_bytes() + b" ")
    confirmed = run(
        "view",
        str(source),
        "--export",
        "view.html",
        "--confirm",
        "--plan",
        planned.result["plan_id"],
        "--no-models",
        cwd=tmp_path,
    )
    assert confirmed.exit_code == 4 and confirmed.error["code"] == "FEN-4002"
    assert not (tmp_path / "view.html").exists()


def test_explicit_project_keeps_unowned_documents_and_refuses_them_only_when_selected(tmp_path):
    from fenolite.api import run
    from fenolite.view.intersheet_bindings import Bindings
    from fenolite.view.project import load_tree

    source = project(tmp_path)
    (tmp_path / "unowned.kicad_sch").write_bytes((tmp_path / "child.kicad_sch").read_bytes())
    (tmp_path / "unowned.kicad_pro").write_text('{"schematic":{"drawing":{"intersheets_ref_show":false}}}')
    binding = Bindings(load_tree(source))
    assert any(doc.path == "unowned.kicad_sch" for doc in binding.tree.documents)
    root = binding.tree.document("tiny.kicad_sch")
    assert root is not None and texts(
        scene_of(root.file, intersheet_context=binding.context(root.file, root))
    ) == ["2"]
    shown = run("view", str(source), "--doc", "tiny.kicad_sch", cwd=tmp_path)
    assert shown.exit_code == 0, shown.error
    refused = run("view", str(source), "--doc", "unowned.kicad_sch", cwd=tmp_path)
    assert refused.exit_code == 3 and refused.error["code"] == "FEN-3004"
    assert "owning project instance" in refused.error["message"]
    exported = run("view", str(source), "--export", "all.html", "--dry-run", cwd=tmp_path)
    assert exported.exit_code == 3 and not (tmp_path / "all.html").exists()
