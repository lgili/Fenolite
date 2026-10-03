# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Harness interfaces in the DSL (capability design-dsl, "Harness interfaces in the DSL"; change c0037)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.dsl import Design, DslError, Harness, Interface, Net, to_model
from fenolite.dsl.convert import key_id
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"


def test_harness_becomes_an_interface() -> None:
    d = Design("t")
    mosi, miso, sck = Net("SPI_MOSI"), Net("SPI_MISO"), Net("SPI_SCK")
    d.add(Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck}))
    model = to_model(d)
    (itf,) = model.circuit.interfaces
    assert (itf.name, itf.kind) == ("SPI", "harness")
    assert itf.id == key_id("interface", "harness", "SPI")
    assert itf.members == {
        "MOSI": key_id("net", "SPI_MOSI"),
        "MISO": key_id("net", "SPI_MISO"),
        "SCK": key_id("net", "SPI_SCK"),
    }
    assert {n.name for n in model.circuit.nets} == {"SPI_MOSI", "SPI_MISO", "SPI_SCK"}


def test_harness_is_an_interface_of_the_dsl() -> None:
    harness = Harness("SPI", {"SCK": Net("SPI_SCK")})
    assert isinstance(harness, Interface) and harness.kind == "harness"
    assert Harness.__module__ == "fenolite.dsl.interfaces"
    assert repr(harness) == "Harness('SPI')"


def test_empty_harness_refused() -> None:
    with pytest.raises(DslError, match="SPI"):
        Harness("SPI", {})


@pytest.mark.parametrize("entry", ["", 1])
def test_entry_name_must_be_a_non_empty_string(entry: object) -> None:
    with pytest.raises(DslError, match="entry name"):
        Harness("SPI", {entry: Net("A")})  # type: ignore[dict-item]


def test_member_must_be_a_net() -> None:
    with pytest.raises(DslError, match="not a Net"):
        Harness("SPI", {"SCK": "SPI_SCK"})  # type: ignore[dict-item]


def test_name_is_required() -> None:
    with pytest.raises(DslError):
        Harness("", {"SCK": Net("SPI_SCK")})
    with pytest.raises(TypeError):
        Harness({"SCK": Net("SPI_SCK")})  # type: ignore[call-arg]


def test_entry_order_survives_the_canonical_form() -> None:
    """The model stores a mapping and canonical JSON sorts keys: the entry order carries no meaning."""
    nets = {name: Net(f"SPI_{name}") for name in ("MOSI", "MISO", "SCK", "CS")}
    first, second = Design("t"), Design("t")
    first.add(Harness("SPI", nets))
    second.add(Harness("SPI", dict(reversed(list(nets.items())))))
    assert canonical.dump_texts(to_model(first)) == canonical.dump_texts(to_model(second))


# --- the KiCad build keeps the harness in the model only --------------------------------------------


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _build(monkeypatch: pytest.MonkeyPatch, script: Path, out: Path) -> tuple[int, dict[str, object]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    code = cli_main.main(["build", str(script), "--out", str(out), "--confirm", "--json"])
    return code, json.loads(stdout.getvalue())


def _files(out: Path) -> dict[str, bytes]:
    return {
        p.relative_to(out).as_posix(): p.read_bytes()
        for p in sorted(out.rglob("*"))
        if p.is_file() and ".fenolite" not in p.relative_to(out).parts
    }


@pytest.mark.usefixtures("isolated")
def test_kicad_build_ignores_the_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "repo" / "examples" / "blink_2layer"
    shutil.copytree(BLINK_DIR, folder)
    shutil.copytree(ROOT / "tests" / "data" / "libs", tmp_path / "repo" / "tests" / "data" / "libs")
    plain = folder / "design.py"
    variant = folder / "variant.py"
    text = plain.read_text(encoding="utf-8")
    assert "import Design, Net" in text
    text = text.replace("import Design, Net", "import Design, Harness, Net")
    added = 'design.add(Harness("LED", {"DRV": led_drv, "A": led_a}))'
    variant.write_text(f"{text}\n{added}\n", encoding="utf-8")

    code_a, env_a = _build(monkeypatch, plain, tmp_path / "A")
    code_b, env_b = _build(monkeypatch, variant, tmp_path / "B")
    assert code_a == code_b == 0
    assert env_b["issues"] == env_a["issues"]
    assert _files(tmp_path / "B") == _files(tmp_path / "A")
    circuit = json.loads((tmp_path / "B" / ".fenolite" / "circuit.json").read_text(encoding="utf-8"))
    assert '"harness"' in json.dumps(circuit) and '"harness"' not in json.dumps(
        json.loads((tmp_path / "A" / ".fenolite" / "circuit.json").read_text(encoding="utf-8"))
    )
