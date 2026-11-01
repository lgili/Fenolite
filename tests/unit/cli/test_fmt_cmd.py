# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite fmt`` (capability cli-contract, "Fmt command"; change c0066). Hermetic."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

from fenolite.backends.kicad import sexpr
from fenolite.backends.kicad.sexpr import Atom, Node, canonical, parse, tree_equal

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
PROJECT = DATA / "kicad" / "project" / "empty_10.kicad_pro"
FILES = [
    TWO_LAYER,
    DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod",
    DATA / "libs" / "Mini.kicad_sym",
    DATA / "kicad" / "sheets" / "all_items.kicad_wks",
    DATA / "kicad" / "tokens" / "old" / "old.kicad_sch",
]


def _canonical_copy(tmp_path: Path) -> tuple[Path, str]:
    text = canonical(TWO_LAYER.read_text(encoding="utf-8"))
    target = tmp_path / "board.kicad_pcb"
    target.write_bytes(text.encode("utf-8"))
    return target, text


def test_canonical_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target, text = _canonical_copy(tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", str(target), "--check")
    assert code == 0 and env["issues"] == []
    assert env["result"] == {
        "kind": "kicad_pcb",
        "formatted": True,
        "lines": len(text.splitlines()),
        "first_difference": None,
    }
    assert (
        env["evidence"]["hypotheses"] == ["H-K-FMT-IDEMPOTENT"] and env["input"]["path"] == "board.kicad_pcb"
    )


def test_file_that_would_change_then_formatting_twice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target, text = _canonical_copy(tmp_path)
    loose = text.replace("(kicad_pcb\n", "(kicad_pcb  \n", 1)
    target.write_bytes(loose.encode("utf-8"))
    before = folder_snapshot(tmp_path)

    code, env, err, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--check")
    assert code == 5 and err["code"] == "FEN-5001" and env["result"]["formatted"] is False
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("fmt.would-change", "error", "board.kicad_pcb:1")
    ]
    assert env["result"]["first_difference"] == 1 and "plan" not in env["result"]
    assert folder_snapshot(tmp_path) == before
    # --check plans nothing, so it never asks for a confirmation and never writes with one
    assert run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--check", "--confirm")[0] == 5
    assert folder_snapshot(tmp_path) == before

    code, env, err, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb")
    assert code == 4 and err["code"] == "FEN-4001" and folder_snapshot(tmp_path) == before
    assert [(p["path"], p["kind"], p["overwrite"]) for p in env["result"]["plan"]] == [
        ("board.kicad_pcb", "kicad_pcb", True)
    ]

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--confirm")
    assert code == 0 and env["result"]["formatted"] is False
    assert target.read_bytes() == text.encode("utf-8")
    assert (tmp_path / "board.kicad_pcb.bak").read_bytes() == loose.encode("utf-8")
    assert env["receipt"]["backup"] == ["board.kicad_pcb.bak"]
    assert tree_equal(parse(target.read_text(encoding="utf-8")), parse(loose))

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--confirm")
    assert code == 0 and env["result"]["formatted"] is True
    assert env["receipt"] is None and "plan" not in env["result"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.suffix[1:])
def test_every_kind_is_formatted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    target = tmp_path / path.name
    target.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", path.name, "--confirm")
    assert code == 0 and env["result"]["kind"] == path.suffix[1:], env
    assert target.read_bytes() == canonical(text).encode("utf-8")
    assert run(monkeypatch, tmp_path, "fmt", path.name, "--check")[0] == 0


def test_refused_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(PROJECT), "--check")
    assert code == 2 and err["code"] == "FEN-2001" and "byte for byte" in err["hint"]
    rules = tmp_path / "x.kicad_dru"
    rules.write_text("(version 1)\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(rules), "--check")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", "missing.kicad_pcb", "--check")
    assert code == 3 and err["code"] == "FEN-3001"
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(unbalanced), "--check")
    assert code == 3 and err["code"] == "FEN-3004"


def test_comments_below_the_root_are_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target, _ = _canonical_copy(tmp_path)
    nested = Node(Atom.symbol("kicad_pcb"), (replace(parse("(b 1)"), comments=("# x",)),))
    monkeypatch.setattr("fenolite.cli.cmd_fmt.parse_bytes", lambda data, file="": nested)
    before = folder_snapshot(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(target), "--confirm")
    assert code == 7 and err["code"] == "FEN-7001" and folder_snapshot(tmp_path) == before
    assert sexpr.first_line_difference("a", "a") is None


# --- device records: v0 rewritten as v1 (change c0259, open question 3 decided on 2026-10-29) -------------

DEVICES = DATA / "devices"
V0_FILES = sorted(DEVICES.glob("*.toml"))


@pytest.mark.parametrize("path", V0_FILES, ids=lambda p: p.stem)
def test_device_v0_rewritten_as_v1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: Path) -> None:
    """Scenario "A v0 device file is rewritten as v1": the dry run plans one write, --confirm --plan writes
    the reviewed bytes, the v1 record gives the same device, and a second run plans nothing."""
    from fenolite.catalog.records import DeviceRecord, parse_record

    text = path.read_text(encoding="utf-8")
    target = tmp_path / path.name
    target.write_bytes(text.encode("utf-8"))
    before = folder_snapshot(tmp_path)

    code, env, err, _ = run(monkeypatch, tmp_path, "fmt", path.name, "--check")
    assert code == 5 and err["code"] == "FEN-5001" and folder_snapshot(tmp_path) == before
    assert [(i["code"], i["where"]) for i in env["issues"]] == [("fmt.would-change", f"{path.name}:3")]

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", path.name, "--dry-run")
    assert code == 0 and folder_snapshot(tmp_path) == before
    assert env["result"]["kind"] == "device" and env["result"]["schema"] == "fenolite.device.v0"
    assert env["evidence"]["hypotheses"] == ["H-G-LIBRARY-RECORDS"]
    assert [(p["path"], p["kind"]) for p in env["result"]["plan"]] == [(path.name, "device")]
    plan = env["result"]["plan_id"]

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", path.name, "--confirm", "--plan", plan)
    assert code == 0 and env["receipt"]["backup"] == [f"{path.name}.bak"]
    written = target.read_text(encoding="utf-8")
    assert written.splitlines()[:2] == text.splitlines()[:2]  # the authored-for-Fenolite comment lines stay
    old, new = parse_record(text), parse_record(written)
    assert isinstance(old, DeviceRecord) and isinstance(new, DeviceRecord)
    assert new.header.schema == "fenolite.device.v1" and new.device == old.device
    assert (new.header.version, new.header.licence) == ("1.0.0", "CC0-1.0")

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", path.name, "--check")
    assert (
        code == 0 and env["result"]["formatted"] is True and env["result"]["schema"] == "fenolite.device.v1"
    )


def test_device_rewrite_is_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = DEVICES / "example_buck.toml"
    outputs = []
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "dev.toml").write_bytes(source.read_bytes())
        assert run(monkeypatch, folder, "fmt", "dev.toml", "--confirm")[0] == 0
        outputs.append((folder / "dev.toml").read_bytes())
    assert outputs[0] == outputs[1]


def test_device_v1_left_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A v1 device file is left unchanged": no plan, exit 0, the bytes stay, even when its layout is
    not the canonical text."""
    source = DATA / "library" / "devices" / "example_reg.toml"
    target = tmp_path / "reg.toml"
    loose = source.read_text(encoding="utf-8").replace(" = ", "  =  ")
    target.write_bytes(loose.encode("utf-8"))
    before = folder_snapshot(tmp_path)
    for flags in (("--check",), ("--dry-run",), ("--confirm",)):
        code, env, _, _ = run(monkeypatch, tmp_path, "fmt", "reg.toml", *flags)
        assert code == 0 and env["result"]["formatted"] is True and "plan" not in env["result"], flags
        assert env["issues"] == [] and folder_snapshot(tmp_path) == before


def test_device_rewrite_licence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without a leading SPDX line the record says NOASSERTION; a Fenolite: id needs CC0-1.0 (FEN-3004)."""
    text = (DEVICES / "example_buck.toml").read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#")) + "\n"
    (tmp_path / "bare.toml").write_text(body, encoding="utf-8")
    assert run(monkeypatch, tmp_path, "fmt", "bare.toml", "--confirm")[0] == 0
    assert 'licence = "NOASSERTION"' in (tmp_path / "bare.toml").read_text(encoding="utf-8")

    own = body.replace("Example:BUCK", "Fenolite:BUCK").replace(
        'ground = "GND"', 'ground = "GND"\nsources = ["S-0314"]'
    )
    (tmp_path / "own.toml").write_text(own, encoding="utf-8")
    before = folder_snapshot(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", "own.toml", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004" and "SPDX" in err["hint"]
    assert folder_snapshot(tmp_path) == before


def test_device_comments_in_the_body_are_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    text = (DEVICES / "example_buck.toml").read_text(encoding="utf-8")
    hashed = text.replace('summary = "', 'summary = "# not a comment ', 1)
    (tmp_path / "hash.toml").write_text(hashed, encoding="utf-8")
    assert run(monkeypatch, tmp_path, "fmt", "hash.toml", "--dry-run")[0] == 0
    commented = text.replace('ref_prefix = "U"', 'ref_prefix = "U"  # the regulator', 1)
    (tmp_path / "dev.toml").write_text(commented, encoding="utf-8")
    before = folder_snapshot(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", "dev.toml", "--confirm")
    assert code == 7 and err["code"] == "FEN-7001" and folder_snapshot(tmp_path) == before
    assert err["where"].startswith("dev.toml:")


def test_other_toml_files_are_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pins = DATA / "library" / "pins" / "two_pin.toml"
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(pins), "--check")
    assert code == 2 and err["code"] == "FEN-2001" and "fenolite.pins.v0" in err["message"]
    (tmp_path / "other.toml").write_text('name = "x"\n', encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", "other.toml", "--check")
    assert code == 2 and err["code"] == "FEN-2001"
    (tmp_path / "broken.toml").write_text('schema = "fenolite.device.v0"\nid = \n', encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", "broken.toml", "--check")
    assert code == 3 and err["code"] == "FEN-3004"
