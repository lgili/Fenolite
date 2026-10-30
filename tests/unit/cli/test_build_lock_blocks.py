# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block versions in ``fenolite build`` (capability design-dsl, "Block versions in the design lock",
"Locked block versions in a build" and "Deprecated blocks in a build"; change c0268)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

SCRIPT = """\
from fenolite.dsl import Design, Net, block, connect, mm

design = Design("sensor")
design.board(mm(40), mm(20))
GND = Net("GND")


@block(id="Acme:divider", version="{version}", summary="A divider", licence="CC0-1.0"{extra})
def divider(b):
    hi = b.port("HI", direction="in")
    mid = b.net("MID")
    top = b.part("top", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
    bot = b.part("bot", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
    connect(hi, top[1])
    connect(mid, top[2], bot[1])
    connect(GND, bot[2])


vin = Net("VIN")
for n, name in enumerate(({names})):
    d = design.use(divider, name)
    connect(vin, d.HI)
    d.part("top").place(mm(10 + 10 * n), mm(6))
    d.part("bot").place(mm(10 + 10 * n), mm(14))
{tail}"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def write(
    tmp_path: Path,
    *,
    version: str = "1.0.0",
    names: str = '"sense_a", "sense_b"',
    extra: str = "",
    tail: str = "",
) -> Path:
    script = tmp_path / "design.py"
    script.write_text(SCRIPT.format(version=version, names=names, extra=extra, tail=tail), encoding="utf-8")
    return script


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def issues(env: dict[str, object]) -> list[dict[str, str]]:
    return list(env.get("issues", []))  # type: ignore[arg-type]


def test_first_build_pins_the_versions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "First build pins the versions"."""
    write(tmp_path)
    code, env, err = run(monkeypatch, "design.py", "--out", "B", "--dry-run")
    assert code == 0, err
    result = env["result"]
    assert isinstance(result, dict)
    assert any(w["path"] == "design.lock" and w["kind"] == "lock" for w in result["plan"])
    changes = [c for c in result["lock"]["changes"] if c["section"] == "blocks"]
    assert [(c["key"], c["after"], c["reason"]) for c in changes] == [
        ("sense_a", "Acme:divider@1.0.0", "block-locked"),
        ("sense_b", "Acme:divider@1.0.0", "block-locked"),
    ]
    code, env, err = run(monkeypatch, "design.py", "--out", "B", "--confirm")
    assert code == 0, err
    text = (tmp_path / "design.lock").read_text(encoding="utf-8")
    assert '[blocks]\n"sense_a" = "Acme:divider@1.0.0"\n"sense_b" = "Acme:divider@1.0.0"\n' in text
    circuit = json.loads((tmp_path / "B" / ".fenolite" / "circuit.json").read_text(encoding="utf-8"))
    versions = {m["path"]: m.get("block_version") for m in circuit["modules"]}
    assert versions == {"sense_a": "1.0.0", "sense_b": "1.0.0"}


def test_newer_block_version_is_not_taken(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Newer block version is not taken"."""
    write(tmp_path)
    assert run(monkeypatch, "design.py", "--out", "B", "--confirm")[0] == 0
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and "kicad-config" not in p.parts}
    write(tmp_path, version="1.1.0")
    before[tmp_path / "design.py"] = (tmp_path / "design.py").read_bytes()
    code, env, _ = run(monkeypatch, "design.py", "--out", "B", "--confirm")
    assert code == 5
    found = [i for i in issues(env) if i["code"] == "lock.block-version"]
    assert len(found) == 2 and all(t in found[0]["message"] for t in ("sense_a", "1.0.0", "1.1.0"))
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and "kicad-config" not in p.parts}
    assert after == before
    assert env["receipt"] is None or not env["receipt"]["written"]  # type: ignore[index]


def test_frozen_build_and_a_first_pin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Frozen build and a first pin": a lock without ``[blocks]`` and a recorded block."""
    write(tmp_path)
    assert run(monkeypatch, "design.py", "--out", "B", "--confirm")[0] == 0
    lock = tmp_path / "design.lock"
    text = lock.read_text(encoding="utf-8")
    lock.write_text(text.split("\n[blocks]\n", 1)[0] + "\n", encoding="utf-8")
    code, env, err = run(monkeypatch, "design.py", "--out", "B", "--frozen")
    assert code == 7 and json.loads(err.strip().splitlines()[-1])["code"] == "FEN-7004"
    changed = [i for i in issues(env) if i["code"] == "lock.changed"]
    assert changed and all(i["where"].startswith("blocks:") for i in changed)


def test_moved_instance_keeps_its_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Moved instance keeps its entry"."""
    write(tmp_path)
    assert run(monkeypatch, "design.py", "--out", "B", "--confirm")[0] == 0
    write(tmp_path, names='"adc_a", "sense_b"', tail='design.moved("sense_a", "adc_a")\n')
    code, _, err = run(monkeypatch, "design.py", "--out", "B", "--confirm")
    assert code == 0, err
    text = (tmp_path / "design.lock").read_text(encoding="utf-8")
    assert '"adc_a" = "Acme:divider@1.0.0"' in text and '"sense_a"' not in text


def test_deprecated_block_used_twice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Deprecated block used twice"."""
    gone = ', deprecated={"by": "Acme:div2", "since": "1.1.0", "reason": "port renamed"}'
    write(tmp_path, extra=gone)
    code, env, err = run(monkeypatch, "design.py", "--out", "B", "--confirm")
    assert code == 0, err
    found = [i for i in issues(env) if i["code"] == "block.deprecated"]
    assert len(found) == 1 and found[0]["severity"] == "warning" and "Acme:div2" in found[0]["message"]
