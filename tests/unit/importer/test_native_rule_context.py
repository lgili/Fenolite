# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Complete source custom-rule context must not silently disappear (c0359)."""

from pathlib import Path

import pytest
from _importcode import copy_project

from fenolite import api


def test_native_rule_file_is_not_projected_to_supported_subset(tmp_path: Path):
    source = copy_project(tmp_path)
    native = source.with_suffix(".kicad_dru")
    original = (
        b"(version 1)\n# Fenolite authored native-rule context control.\n"
        b'(rule "Authored first" (constraint hole_size (min 0.2mm) (max 6.3mm)))\n'
        b'(rule "Authored native condition"\n'
        b" # Comment deliberately makes this rule native-owned.\n"
        b" (condition \"A.Type == 'track' && B.Type == A.Type\")\n"
        b" (constraint clearance (min 0.127mm)))\n"
    )
    native.write_bytes(original)
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    assert plan.envelope["evidence"]["level"] == "INFERRED"
    assert "H-K-DRU-IMMUTABLE-CONTEXT" in plan.envelope["evidence"]["hypotheses"]
    reply = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
    preserved = tmp_path / "code/native/project.kicad_dru"
    assert preserved.is_file(), "the native-only rule and its original order/comments were discarded"
    assert preserved.read_bytes() == original
    assert native.read_bytes() == original


def test_immutable_native_rule_context_refuses_dsl_change_before_plan(tmp_path: Path):
    test_native_rule_file_is_not_projected_to_supported_subset(tmp_path)
    script = tmp_path / "code/design.py"
    original = script.read_bytes()
    for addition in (
        '\ndesign.rules.minimum(clearance=mm("0.3"))\n',
        '\ndesign.add(Net("AUTHORED_CHANGED_NET"))\n',
    ):
        script.write_bytes(original + addition.encode())
        reply = api.run("build", "code/design.py", "--out", "refused", "--dry-run", cwd=tmp_path)
        assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004", reply.error
        assert "unchanged complete" in reply.error["message"]
        assert not reply.result.get("plan") and not (tmp_path / "refused").exists()
    script.write_bytes(original)
    reply = api.run("build", "code/design.py", "--out", "built", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
    native = tmp_path / "code/native/project.kicad_dru"
    native.write_bytes(native.read_bytes() + b"# stale input\n")
    confirmation = api.run(
        "build",
        "code/design.py",
        "--out",
        "built",
        "--confirm",
        "--plan",
        reply.result["plan_id"],
        cwd=tmp_path,
    )
    assert confirmation.exit_code == 4 and confirmation.error and confirmation.error["code"] == "FEN-4002"
    assert not (tmp_path / "built").exists()


def test_release_tool_version_changes_only_model_metadata_not_native_pins(tmp_path: Path, monkeypatch):
    import fenolite.dsl.convert as convert
    import fenolite.model.canonical as canonical

    test_native_rule_file_is_not_projected_to_supported_subset(tmp_path)
    args = ("build", "code/design.py", "--out", "version-proof", "--dry-run")
    before = api.run(*args, cwd=tmp_path)
    assert before.exit_code == 0, before.error
    monkeypatch.setattr(convert, "__version__", "0.7.0")
    monkeypatch.setattr(canonical, "__version__", "0.7.0")
    after = api.run(*args, cwd=tmp_path)
    assert after.exit_code == 0, after.error

    def native(reply):
        return {
            Path(row["path"]).suffix: row["sha256"]
            for row in reply.result["plan"]
            if row["path"].endswith((".kicad_pcb", ".kicad_pro", ".kicad_dru"))
        }

    assert set(native(before)) == {".kicad_pcb", ".kicad_pro", ".kicad_dru"}
    assert native(before) == native(after)
    meta_before = next(
        row["sha256"]
        for row in before.result["plan"]
        if Path(row["path"]).parts[-2:] == (".fenolite", "meta.json")
    )
    meta_after = next(
        row["sha256"]
        for row in after.result["plan"]
        if Path(row["path"]).parts[-2:] == (".fenolite", "meta.json")
    )
    assert meta_before != meta_after


def test_changed_effective_project_minimums_refuse_before_plan(tmp_path: Path):
    import json

    test_native_rule_file_is_not_projected_to_supported_subset(tmp_path)
    source = tmp_path / "src/two_sheet.kicad_pro"
    data = json.loads(source.read_bytes())
    data["board"]["design_settings"]["rules"]["min_clearance"] = 0.37
    source.write_text(json.dumps(data))
    args = ("import", str(source), "--to", "python", "--out", "minimum-code", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    reply = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
    script = tmp_path / "minimum-code/design.py"
    original = script.read_text()
    assert "preserve_minimums=True" in original
    script.write_text(original.replace("preserve_minimums=True", "preserve_minimums=False"))
    reply = api.run("build", "minimum-code/design.py", "--out", "refused-minimum", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004", reply.error
    assert "declared native rules require unchanged emitted" in reply.error["message"]
    assert not reply.result.get("plan") and not (tmp_path / "refused-minimum").exists()


def test_failed_capture_keeps_primary_failure_and_issues_no_certificate(tmp_path: Path, monkeypatch):
    from fenolite.cli import cmd_import
    from fenolite.importer.codes import issue

    source = copy_project(tmp_path)
    source.with_suffix(".kicad_dru").write_text(
        '(version 1)\n(rule "Authored"\n # authored native-only record\n'
        " (constraint clearance (min 0.2mm)))\n"
    )
    monkeypatch.setattr(
        cmd_import, "_build", lambda *args: ([issue("import.unequal", "AUTHORED_BUILD_FAILURE")], None, "")
    )
    reply = api.run("import", str(source), "--to", "python", "--out", "refused", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 5 and reply.error and reply.error["code"] == "FEN-5001"
    assert any("AUTHORED_BUILD_FAILURE" in item["message"] for item in reply.envelope["issues"])
    assert not reply.result.get("plan") and not (tmp_path / "refused").exists()


@pytest.mark.parametrize(
    "removed",
    [
        ("project.kicad_dru",),
        ("project.rules-context.json",),
        ("project.kicad_dru", "project.rules-context.json"),
    ],
)
def test_missing_declared_pair_refuses_fresh_build_without_cache(tmp_path: Path, removed):
    test_native_rule_file_is_not_projected_to_supported_subset(tmp_path)
    assert not (tmp_path / "code/.fenolite").exists()
    for name in removed:
        (tmp_path / "code/native" / name).unlink()
    reply = api.run("build", "code/design.py", "--out", "missing-refused", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004", reply.error
    assert "required native rule input is missing" in reply.error["message"]
    assert not reply.result.get("plan") and not (tmp_path / "missing-refused").exists()


def test_raw_rules_without_original_project_are_not_certified(tmp_path: Path):
    from _importcode import board_only

    source = board_only(tmp_path)
    source.with_suffix(".kicad_dru").write_text(
        '(version 1)\n(rule "Authored"\n # authored native-only record\n'
        " (constraint clearance (min 0.2mm)))\n"
    )
    reply = api.run("import", str(source), "--to", "python", "--out", "refused", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004"
    assert "require their declared native project" in reply.error["message"]
    assert not reply.result.get("plan") and not (tmp_path / "refused").exists()


@pytest.mark.parametrize("condition", ["A.NetName == 'VIN'", "A.NetClass == 'Power'"])
def test_fully_modelled_rule_program_keeps_existing_editable_conversion(tmp_path: Path, condition: str):
    from fenolite.backends.kicad.sexpr import Atom, dumps
    from fenolite.importer.source import read_kicad

    source = copy_project(tmp_path)
    source.with_suffix(".kicad_dru").write_text(
        '(version 1)\n(rule "Authored modelled rule" (condition '
        + dumps(Atom.string(condition))
        + ") (constraint clearance (min 0.2mm)))\n"
    )
    assert read_kicad(source).native_rules_text is None
    args = ("import", str(source), "--to", "python", "--out", "editable", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    reply = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
    script = tmp_path / "editable/design.py"
    assert "required native rule input" not in script.read_text()
    assert not (script.parent / "native/project.kicad_dru").exists()
    # A directly declared pro with a fully modelled sibling remains the old pro-only path.
    (script.parent / "native/project.kicad_dru").write_bytes(source.with_suffix(".kicad_dru").read_bytes())
    script.write_text(script.read_text() + '\ndesign.rules.minimum(clearance=mm("0.15"))\n')
    reply = api.run("build", "editable/design.py", "--out", "editable-built", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
