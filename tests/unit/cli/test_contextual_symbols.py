# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Required contextual native inputs never fall back to a global snapshot (c0327)."""

from __future__ import annotations

import hashlib
import shutil
import tomllib
from pathlib import Path

import pytest
from _contextual_symbols import code, project

from fenolite.api import run
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.cli import cmd_build, cmd_import, plans
from fenolite.core.state import state_dir

STAMP = "2026-11-02T00:00:00Z"


def build(tmp: Path, script: Path, *args: str):
    return run(
        "build", str(script), "--out", "built", "--kicad-version", "9", *args, cwd=tmp, timestamp=STAMP
    )


def staged(reply):
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    found = plans.load(state_dir(), reply.result["plan_id"])
    assert found is not None
    return found


def assets(script: Path) -> list[Path]:
    data = tomllib.loads((script.parent / "symbol-contexts.toml").read_text(encoding="utf-8"))
    return [script.parent / row["asset"] for row in data["symbol"]]


def forbidden(*args, **kwargs):
    pytest.fail("confirmation executed the producer instead of the reviewed bytes")


def test_build_binds_all_context_inputs_and_replays_exact_bytes(tmp_path: Path, monkeypatch) -> None:
    script = code(tmp_path / "code")
    planned = build(tmp_path, script, "--dry-run")
    saved = staged(planned)
    required = [
        script,
        script.parent / "schematic.toml",
        script.parent / "symbol-contexts.toml",
        *assets(script),
        *script.parent.glob("sheets/*.py"),
    ]
    recorded = dict(saved.depends)
    for path in required:
        assert (
            recorded[path.relative_to(tmp_path).as_posix()] == hashlib.sha256(path.read_bytes()).hexdigest()
        )
    expected = {row["path"]: row["sha256"] for row in planned.result["plan"]}
    monkeypatch.setattr(cmd_build, "run_design_script", forbidden)
    done = build(tmp_path, script, "--confirm", "--plan", saved.id)
    assert done.exit_code == 0, done.error
    assert {row["path"]: row["sha256"] for row in done.envelope["receipt"]["written"]} == expected
    assert done.envelope["receipt"]["plan"] == saved.id
    assert done.envelope["issues"] == planned.envelope["issues"]
    for relative, digest in expected.items():
        assert hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("which", ["script", "drawing", "index", "factory", 0, 1, 2, 3])
def test_every_context_input_invalidates_review(which, tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    saved = staged(build(tmp_path, script, "--dry-run"))
    if isinstance(which, int):
        path = assets(script)[which]
    else:
        path = {
            "script": script,
            "drawing": script.parent / "schematic.toml",
            "index": script.parent / "symbol-contexts.toml",
            "factory": next(script.parent.glob("sheets/*.py")),
        }[which]
    path.write_bytes(path.read_bytes() + b"\n")
    reply = build(tmp_path, script, "--confirm", "--plan", saved.id)
    assert reply.exit_code == 4 and (reply.error or {})["code"] == "FEN-4002"
    assert not (tmp_path / "built").exists()


@pytest.mark.parametrize("which", ["index", "asset", "ancestor"])
def test_same_byte_symlink_replacement_invalidates_review(which: str, tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    saved = staged(build(tmp_path, script, "--dry-run"))
    path = script.parent / "symbol-contexts.toml" if which == "index" else assets(script)[0]
    probe = path
    if which == "ancestor":
        path = path.parent
    moved = path.with_name(path.name + ".owned")
    before = probe.read_bytes()
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    assert probe.read_bytes() == before
    reply = build(tmp_path, script, "--confirm", "--plan", saved.id)
    assert reply.exit_code == 4 and (reply.error or {})["code"] == "FEN-4002"
    assert not (tmp_path / "built").exists()


@pytest.mark.parametrize("args", [("--schematic", "skip"), ("--target", "altium")])
def test_contexts_are_not_ignored_by_other_output_modes(args, tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    reply = build(tmp_path, script, *args, "--dry-run")
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert not (tmp_path / "built").exists()


def test_build_needs_no_original_cad_after_import(tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    shutil.rmtree(tmp_path / "original")
    assert build(tmp_path, script, "--dry-run").exit_code == 0


def test_ordinary_drawing_with_the_index_basename_keeps_existing_replay_contract(tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    for path in set(assets(script)):
        path.unlink()
    index = script.parent / "symbol-contexts.toml"
    index.unlink()
    (script.parent / "schematic.toml").rename(index)
    text = script.read_text(encoding="utf-8")
    script.write_text(
        text.replace(
            'load_schematic("schematic.toml", symbol_contexts="symbol-contexts.toml")',
            'load_schematic("symbol-contexts.toml")',
        ),
        encoding="utf-8",
    )
    saved = staged(build(tmp_path, script, "--dry-run"))
    moved = index.with_suffix(".owned")
    index.rename(moved)
    index.symlink_to(moved)
    done = build(tmp_path, script, "--confirm", "--plan", saved.id)
    assert done.exit_code == 0, done.error


def test_import_replays_all_asset_writes_and_preserves_all_nine_levels(tmp_path: Path, monkeypatch) -> None:
    original = project(tmp_path / "original")
    args = (str(original), "--to", "python", "--out", "code")
    planned = run("import", *args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    saved = staged(planned)
    assert planned.result["unexpressed"] == []
    assert any(row["path"] == "code/symbol-contexts.toml" for row in saved.writes)
    assert any("/.symbol-contexts/" in row["path"] for row in saved.writes)
    originals = set(
        path.relative_to(tmp_path).as_posix()
        for path in original.parent.rglob("*")
        if path.suffix in (".kicad_sch", ".kicad_pro", ".kicad_pcb")
    )
    assert originals <= {path for path, _ in saved.depends}
    monkeypatch.setattr(cmd_import, "emit", forbidden)
    done = run("import", *args, "--confirm", "--plan", saved.id, cwd=tmp_path, timestamp=STAMP)
    assert done.exit_code == 0, done.error
    assert {row["path"]: row["sha256"] for row in done.envelope["receipt"]["written"]} == {
        row["path"]: row["sha256"] for row in saved.writes
    }
    proof = run(
        "verify-source",
        "code/design.py",
        "--against",
        str(original.parent),
        "--kicad-version",
        "9",
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert proof.exit_code == 0, (proof.error, proof.result.get("differences"))
    assert {str(row["level"]): row["status"] for row in proof.result["levels"]} == {
        **{str(level): "equal" for level in range(1, 9)},
        "S": "equal",
    }


def test_original_context_sheet_change_invalidates_import_review(tmp_path: Path) -> None:
    original = project(tmp_path / "original")
    args = (str(original), "--to", "python", "--out", "code")
    saved = staged(run("import", *args, "--dry-run", cwd=tmp_path, timestamp=STAMP))
    sheet = original.parent / "sheets/channel_authored_second.kicad_sch"
    sheet.write_bytes(sheet.read_bytes() + b"\n")
    reply = run("import", *args, "--confirm", "--plan", saved.id, cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 4 and (reply.error or {})["code"] == "FEN-4002"
    assert not (tmp_path / "code").exists()


@pytest.mark.parametrize("after_review", [False, True])
def test_import_never_writes_through_an_asset_output_symlink(after_review: bool, tmp_path: Path) -> None:
    original = project(tmp_path / "original")
    args = (str(original), "--to", "python", "--out", "code")
    saved = staged(run("import", *args, "--dry-run", cwd=tmp_path, timestamp=STAMP)) if after_review else None
    outside = tmp_path / "outside"
    outside.mkdir()
    folder = tmp_path / "code"
    folder.mkdir()
    (folder / "lib").symlink_to(outside, target_is_directory=True)
    flags = ("--confirm", "--plan", saved.id) if saved else ("--dry-run",)
    reply = run("import", *args, *flags, cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == (4 if after_review else 3)
    assert (reply.error or {})["code"] == ("FEN-4002" if after_review else "FEN-3004")
    assert list(outside.iterdir()) == [] and not (folder / "symbol-contexts.toml").exists()


def move_reference_field(path: Path) -> None:
    root = parse(path.read_text(encoding="utf-8"))
    instance = root.nodes("symbol")[0]
    reference = next(p for p in instance.nodes("property") if p.atoms()[0].value == "Reference")
    at = reference.find("at")
    assert at is not None
    changed_at = at.with_children((Atom.from_nm(75_000_000), *at.children[1:]))
    changed_ref = reference.with_children(tuple(changed_at if c is at else c for c in reference.children))
    changed = instance.with_children(tuple(changed_ref if c is reference else c for c in instance.children))
    path.write_text(
        dumps(root.with_children(tuple(changed if c is instance else c for c in root.children))),
        encoding="utf-8",
    )


def test_sync_binds_context_assets_and_native_drawings(tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    assert build(tmp_path, script, "--confirm").exit_code == 0
    native = tmp_path / "built/sheets/channel_authored_second.kicad_sch"
    move_reference_field(native)
    args = (str(script), "--out", "built", "--to-source")
    saved = staged(run("sync", *args, "--dry-run", cwd=tmp_path, timestamp=STAMP))
    assert any(Path(row["path"]) == script.parent / "schematic.toml" for row in saved.writes)
    required = [
        script.parent / "schematic.toml",
        script.parent / "symbol-contexts.toml",
        *assets(script),
        native,
    ]
    assert {path.relative_to(tmp_path).as_posix() for path in required} <= {path for path, _ in saved.depends}
    before = (script.parent / "schematic.toml").read_bytes()
    asset = assets(script)[0]
    asset.write_bytes(asset.read_bytes() + b"\n")
    reply = run("sync", *args, "--confirm", "--plan", saved.id, cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 4 and (reply.error or {})["code"] == "FEN-4002"
    assert (script.parent / "schematic.toml").read_bytes() == before


def test_sync_refuses_to_drop_edited_native_library_metadata(tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    assert build(tmp_path, script, "--confirm").exit_code == 0
    native = tmp_path / "built/sheets/channel_authored_second.kicad_sch"
    text = native.read_text(encoding="utf-8")
    assert "Authored sheet metadata snapshot B" in text
    native.write_text(
        text.replace("Authored sheet metadata snapshot B", "EDITED_NATIVE_METADATA"), encoding="utf-8"
    )
    reply = run(
        "sync", str(script), "--out", "built", "--to-source", "--dry-run", cwd=tmp_path, timestamp=STAMP
    )
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert "changed contextual native definitions" in (reply.error or {})["message"]


def test_missing_required_context_index_never_uses_a_global_default(tmp_path: Path) -> None:
    script = code(tmp_path / "code")
    (script.parent / "symbol-contexts.toml").unlink()
    reply = run("build", str(script), "--out", "refused", "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert "context" in (reply.error or {})["message"]
    assert not (tmp_path / "refused").exists()
