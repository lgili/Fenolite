# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original physical/native project context across the actual portable DSL boundary (c0355)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from _importcode import PROJECT, board_only

from fenolite import api
from fenolite.backends.kicad.derived_teardrops import native_net
from fenolite.backends.kicad.sexpr import parse_bytes

STAMP = "2026-11-03T00:00:00Z"


def authored(
    tmp_path: Path, assignment: object = "Quiet", *, native_rules: bool = False, spelling: str = "/AUTH/P"
) -> Path:
    board = board_only(tmp_path)
    board.write_bytes(board.read_bytes().replace(b'"GND"', json.dumps(spelling).encode()))
    data = json.loads(PROJECT.read_bytes())
    quiet = dict(data["net_settings"]["classes"][0])
    quiet.update(name="Quiet", clearance=0.2032)
    data["net_settings"]["classes"].append(quiet)
    data["net_settings"]["netclass_assignments"] = {spelling: assignment}
    data["net_settings"]["netclass_patterns"] = []
    project = board.with_suffix(".kicad_pro")
    project.write_text(json.dumps(data))
    if native_rules:
        board.with_suffix(".kicad_dru").write_text(
            '(version 1)\n(rule "Authored context"\n # Native-owned original comment\n'
            " (constraint clearance (min 0.127mm)))\n"
        )
    return project


def imported(
    tmp_path: Path, assignment: object = "Quiet", *, native_rules: bool = False, spelling: str = "/AUTH/P"
) -> Path:
    source = authored(tmp_path, assignment, native_rules=native_rules, spelling=spelling)
    before = {p: p.read_bytes() for p in source.parent.iterdir() if p.is_file()}
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert plan.exit_code == 0, plan.error
    reply = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 0, reply.error
    assert all(p.read_bytes() == raw for p, raw in before.items())
    return tmp_path / "code"


def build(tmp_path: Path, code: Path, *, out: str = "built", target: int = 10):
    return api.run(
        "build",
        str(code / "design.py"),
        "--out",
        out,
        "--kicad-version",
        str(target),
        "--schematic",
        "skip",
        "--dry-run",
        cwd=tmp_path,
        timestamp=STAMP,
    )


@pytest.mark.parametrize("assignment", ["Quiet", ["Quiet"]])
@pytest.mark.parametrize("spelling", ["/AUTH/P", "{slash}AUTH{slash}P"])
def test_moved_folder_keeps_native_names_and_assignment_representation(tmp_path: Path, assignment, spelling):
    code = imported(tmp_path, assignment, spelling=spelling)
    context = code / "native/project.context.json"
    assert context.is_file(), "portable import lost its original native project context"
    moved = tmp_path / "moved"
    shutil.move(str(code), moved)
    shutil.rmtree(tmp_path / "board_only")
    plan = build(tmp_path, moved)
    assert plan.exit_code == 0, plan.error
    confirmed = api.run(
        "build",
        str(moved / "design.py"),
        "--out",
        "built",
        "--kicad-version",
        "10",
        "--schematic",
        "skip",
        "--confirm",
        "--plan",
        plan.result["plan_id"],
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert confirmed.exit_code == 0, confirmed.error
    root = parse_bytes(next((tmp_path / "built").glob("*.kicad_pcb")).read_bytes())
    names = {native_net(pad, root) for fp in root.nodes("footprint") for pad in fp.nodes("pad")}
    assert spelling in names
    assert ({"/AUTH/P", "{slash}AUTH{slash}P"} - {spelling}).isdisjoint(names)
    project = json.loads(next((tmp_path / "built").glob("*.kicad_pro")).read_bytes())
    assert project["net_settings"]["netclass_assignments"] == {spelling: assignment}
    assert project["net_settings"]["netclass_patterns"] == []


def test_context_stale_confirmation_and_edited_model_refuse(tmp_path: Path):
    code = imported(tmp_path)
    context = code / "native/project.context.json"
    assert context.is_file()
    raw = context.read_bytes()
    plan = build(tmp_path, code)
    assert plan.exit_code == 0, plan.error
    context.write_bytes(raw + b"\n")
    reply = api.run(
        "build",
        str(code / "design.py"),
        "--out",
        "built",
        "--confirm",
        "--plan",
        plan.result["plan_id"],
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert reply.exit_code == 4 and reply.error["code"] == "FEN-4002"
    context.write_bytes(raw)
    script = code / "design.py"
    script.write_text(script.read_text() + '\ndesign.add(Net("AUTHORED_CHANGED_NET"))\n')
    reply = build(tmp_path, code)
    assert reply.exit_code == 3 and reply.error["code"] == "FEN-3004"
    assert not reply.result.get("plan")


@pytest.mark.parametrize(
    "change", ["missing", "tamper", "symlink", "oversize", "unknown", "duplicate", "collision", "target"]
)
def test_closed_context_refuses_before_plan(tmp_path: Path, change: str):
    code = imported(tmp_path)
    context = code / "native/project.context.json"
    assert context.is_file()
    raw = context.read_bytes()
    if change == "missing":
        context.unlink()
    elif change == "tamper":
        context.write_bytes(raw + b" ")
    elif change == "symlink":
        other = tmp_path / "other.json"
        other.write_bytes(raw)
        context.unlink()
        context.symlink_to(other)
    else:
        data = json.loads(raw)
        if change == "oversize":
            modified = raw + b" " * (16 * 1024 * 1024)
        elif change == "duplicate":
            modified = raw.replace(b'"version": 1', b'"version": 1, "version": 1')
        else:
            if change == "unknown":
                data["unknown"] = 1
            elif change == "collision":
                data["nets"].append(data["nets"][0])
            elif change == "target":
                data["target"] = 9
            modified = json.dumps(data).encode()
        context.write_bytes(modified)
        # Exercise the closed consumer, not only the generated literal digest guard.
        script = code / "design.py"
        script.write_text(
            script.read_text().replace(hashlib.sha256(raw).hexdigest(), hashlib.sha256(modified).hexdigest())
        )
    reply = build(tmp_path, code)
    assert reply.exit_code == 3 and reply.error["code"] == "FEN-3004", reply.error
    assert not reply.result.get("plan") and not (tmp_path / "built").exists()


def test_rule_context_composes_on_same_restored_model(tmp_path: Path):
    code = imported(tmp_path, native_rules=True)
    assert (code / "native/project.context.json").is_file()
    assert (code / "native/project.rules-context.json").is_file()
    plan = build(tmp_path, code)
    assert plan.exit_code == 0, plan.error
    original = (code / "design.py").read_text()
    (code / "design.py").write_text(original + '\ndesign.rules.minimum(clearance=mm("0.31"))\n')
    refused = build(tmp_path, code)
    assert refused.exit_code == 3 and refused.error["code"] == "FEN-3004"
    assert not refused.result.get("plan")


@pytest.mark.parametrize("change", ["class-values", "class-members", "net-name", "physical", "reference"])
def test_changed_model_refuses_without_changing_ids_or_canonical_names(tmp_path: Path, change: str):
    import dataclasses

    from fenolite.core.errors import FormatError
    from fenolite.lens import native_project_context as context
    from fenolite.lens.native_rule_context import fingerprint
    from fenolite.model.base import ExtBag

    code = imported(tmp_path)
    path = code / "native/project.kicad_pro"
    binding = context.read_binding(path, path.read_bytes())
    assert binding is not None
    # Observe the exact lowered input to restoration during a real build; never synthesize a baseline.
    seen = []
    original_restore = context.restore

    def observe(design, *args):
        seen.append(design)
        return original_restore(design, *args)

    from unittest.mock import patch

    with patch.object(context, "restore", observe):
        reply = build(tmp_path, code)
    assert reply.exit_code == 0, reply.error
    model = seen[0]
    restored, _ = original_restore(model, binding, path.read_text(), 10)
    assert [(n.id, n.name) for n in restored.circuit.nets] == [(n.id, n.name) for n in model.circuit.nets]
    cleaned = dataclasses.replace(
        restored,
        circuit=dataclasses.replace(
            restored.circuit,
            nets=tuple(
                dataclasses.replace(n, ext=old.ext)
                for n, old in zip(restored.circuit.nets, model.circuit.nets, strict=True)
            ),
        ),
    )
    assert cleaned == model
    assert fingerprint(model) == binding.baseline
    if change == "class-values":
        cls = model.circuit.netclasses[0]
        changed = dataclasses.replace(
            model,
            circuit=dataclasses.replace(
                model.circuit,
                netclasses=(
                    dataclasses.replace(cls, clearance=(cls.clearance or 0) + 1),
                    *model.circuit.netclasses[1:],
                ),
            ),
        )
    elif change == "class-members":
        index = next(i for i, n in enumerate(model.circuit.nets) if n.netclass_id is not None)
        changed = dataclasses.replace(
            model,
            circuit=dataclasses.replace(
                model.circuit,
                nets=tuple(
                    dataclasses.replace(n, netclass_id=None) if i == index else n
                    for i, n in enumerate(model.circuit.nets)
                ),
            ),
        )
    elif change == "net-name":
        changed = dataclasses.replace(
            model,
            circuit=dataclasses.replace(
                model.circuit,
                nets=(dataclasses.replace(model.circuit.nets[0], name="CHANGED"), *model.circuit.nets[1:]),
            ),
        )
    elif change == "reference":
        changed = dataclasses.replace(
            model,
            circuit=dataclasses.replace(
                model.circuit,
                components=(
                    dataclasses.replace(model.circuit.components[0], ref="CHANGED1"),
                    *model.circuit.components[1:],
                ),
            ),
        )
    else:
        fp = model.board.footprints[0]
        changed = dataclasses.replace(
            model,
            board=dataclasses.replace(
                model.board,
                footprints=(dataclasses.replace(fp, pads=fp.pads[1:]), *model.board.footprints[1:]),
            ),
        )
    with pytest.raises(FormatError, match="unchanged complete"):
        original_restore(changed, binding, path.read_text(), 10)
    # Updating an untrusted baseline does not bypass the complete partitions/classes checks.
    forged = dataclasses.replace(binding, baseline=fingerprint(changed))
    with pytest.raises(FormatError):
        original_restore(changed, forged, path.read_text(), 10)
    net = model.circuit.nets[0]
    changed = dataclasses.replace(
        model,
        circuit=dataclasses.replace(
            model.circuit,
            nets=(
                dataclasses.replace(net, ext={"kicad": ExtBag(payload=(("stored", "COLLISION"),))}),
                *model.circuit.nets[1:],
            ),
        ),
    )
    with pytest.raises(FormatError, match="conflicts"):
        original_restore(
            changed, dataclasses.replace(binding, baseline=fingerprint(changed)), path.read_text(), 10
        )


@pytest.mark.parametrize(
    "change",
    [
        "version-bool",
        "target-bool",
        "project-ref",
        "source-path",
        "source-duplicate",
        "source-kind",
        "source-hash",
        "physical-empty",
        "physical-shape",
        "name-collision",
        "nonfinite",
        "baseline-encoding",
    ],
)
def test_decoder_rejects_untrusted_closed_metadata(tmp_path: Path, change: str):
    from fenolite.core.errors import FormatError
    from fenolite.lens.native_project_context import read_binding

    code = imported(tmp_path)
    path = code / "native/project.kicad_pro"
    context = path.with_name("project.context.json")
    data = json.loads(context.read_bytes())
    if change == "version-bool":
        data["version"] = True
    elif change == "target-bool":
        data["target"] = True
    elif change == "project-ref":
        data["project"]["path"] = "../elsewhere.kicad_pro"
    elif change == "source-path":
        data["source_inputs"][0]["path"] = "../elsewhere.kicad_pcb"
    elif change == "source-duplicate":
        data["source_inputs"].append(data["source_inputs"][0])
    elif change == "source-kind":
        data["source_inputs"][0]["kind"] = {"bad": "type"}
    elif change == "source-hash":
        for row in data["source_inputs"]:
            row["sha256"] = "0" * 64
    elif change == "physical-empty":
        data["nets"][0]["physical"] = []
    elif change == "physical-shape":
        data["nets"][0]["physical"] = [["U1", "1", "unexpected"]]
    elif change == "name-collision":
        data["nets"][1]["stored"] = data["nets"][0]["stored"]
    elif change == "nonfinite":
        data["nets"][0]["class"] = float("nan")
    else:
        data["baseline"]["encoding"] = "unknown"
    context.write_text(json.dumps(data))
    with pytest.raises(FormatError):
        read_binding(path, path.read_bytes())


def test_nested_capture_and_scope_refuse_and_release_state(tmp_path: Path):
    from fenolite.core.errors import FormatError
    from fenolite.importer.source import read_kicad
    from fenolite.lens.native_project_context import build_scope, capture_import

    source = read_kicad(authored(tmp_path))
    inputs = [{"path": row.file, "sha256": row.sha256, "kind": row.format} for row in source.inputs]
    with pytest.raises(FormatError, match="nested native project baseline"):
        with capture_import(
            "authored", 10, source.design, source.board_text.encode(), source.project_text, inputs
        ):
            with capture_import(
                "authored", 10, source.design, source.board_text.encode(), source.project_text, inputs
            ):
                pass
    with build_scope(tmp_path / "design.py", "authored", 10, None, None):
        with pytest.raises(FormatError, match="nested native project build"):
            with build_scope(tmp_path / "design.py", "authored", 10, None, None):
                pass
    # Exception cleanup must not poison another independent build owner/target.
    with build_scope(tmp_path / "next.py", "next", 9, None, None):
        pass


def test_guide_teaches_portable_private_context_without_extra_claims():
    from fenolite.agent import guide

    page = guide.page("equivalent-s")
    for words in (
        "native/project.context.json",
        "never opens or fetches",
        "pre-restoration model",
        "reviewed re-import",
        "independent of `preserve_minimums`",
        "proves no geometry",
    ):
        assert words in page.text


def test_project_context_tool_version_is_neutral_but_native_output_bound(tmp_path: Path, monkeypatch):
    import fenolite.dsl.convert as convert
    import fenolite.model.canonical as canonical

    code = imported(tmp_path, native_rules=True)
    before = build(tmp_path, code)
    assert before.exit_code == 0, before.error
    monkeypatch.setattr(convert, "__version__", "0.7.0")
    monkeypatch.setattr(canonical, "__version__", "0.7.0")
    after = build(tmp_path, code)
    assert after.exit_code == 0, after.error

    def native(reply):
        return {
            Path(row["path"]).suffix: row["sha256"]
            for row in reply.result["plan"]
            if row["path"].endswith((".kicad_pcb", ".kicad_pro", ".kicad_dru"))
        }

    assert set(native(before)) == {".kicad_pcb", ".kicad_pro", ".kicad_dru"}
    assert native(before) == native(after)
