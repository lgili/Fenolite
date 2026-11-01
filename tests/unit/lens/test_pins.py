# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pin solve and its place in ``fenolite build`` (capability pin-assignment; change c0257). The designs
and devices are authored for Fenolite: ``examples/pins`` and the records below."""

from __future__ import annotations

import io
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.catalog.devices import parse_device
from fenolite.lens.pins import PIN_ISSUE_CODES, LockedChoice, TakeRequest, solve
from fenolite.model.library import DeviceDef, DeviceOption, DevicePin

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "pins"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))


def copy_example(tmp_path: Path) -> Path:
    folder = tmp_path / "pins"
    shutil.copytree(EXAMPLE, folder, ignore=shutil.ignore_patterns("__pycache__", "*.lock"))
    return folder


def run(monkeypatch: pytest.MonkeyPatch, *argv: str) -> tuple[int, dict[str, Any]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main([*argv, "--json"])
    text = stdout.getvalue() or stderr.getvalue().strip().splitlines()[-1]
    return code, json.loads(text)


def build(monkeypatch: pytest.MonkeyPatch, script: Path, *flags: str) -> tuple[int, dict[str, Any]]:
    return run(monkeypatch, "build", str(script), "--out", str(script.parent / "out"), *flags)


def variant(folder: Path, name: str, *changes: tuple[str, str]) -> Path:
    text = (folder / "design.py").read_text(encoding="utf-8")
    for old, new in changes:
        assert old in text, old
        text = text.replace(old, new)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


DEBUG = 'debug = mcu.take(UART, option="UART2", name="debug")\n'
I2C_TAKE = "i2c = mcu.take(I2C)  # one of the device's i2c alternatives, chosen at build\n"


# -- the solve


def test_second_alternative_under_three_seeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Second alternative when the first is taken"."""
    folder = copy_example(tmp_path)
    script = variant(folder, "second.py", (I2C_TAKE, 'connect(Net("LED"), mcu.PB7)\n' + I2C_TAKE))
    found = []
    for seed in ("1", "2", "3"):
        code, env = build(monkeypatch, script, "--dry-run", "--seed", seed)
        assert code == 0, env["issues"]
        found.append(env["result"]["pins"])
    i2c = next(row for row in found[0] if row["key"] == "mcu/i2c#0")
    assert i2c == {
        "key": "mcu/i2c#0",
        "kind": "i2c",
        "option": "I2C1",
        "alternative": 1,
        "pins": {"scl": "PB8", "sda": "PB9"},
        "source": "solved",
    }
    assert found[0] == found[1] == found[2]


def _device(pins: int, options: list[DeviceOption]) -> DeviceDef:
    return DeviceDef(
        id="Proj:MCU",
        evidence="INFERRED",
        pins=tuple(DevicePin(f"P{n}", (str(n),)) for n in range(1, pins + 1)),
        options=tuple(options),
    )


def _i2c(name: str, *pairs: tuple[int, int]) -> DeviceOption:
    return DeviceOption("i2c", name, tuple({"scl": f"P{a}", "sda": f"P{b}"} for a, b in pairs), "INFERRED")


def test_search_limit() -> None:
    device = _device(8, [_i2c("I2C1", (1, 2), (3, 4))])
    takes = [TakeRequest("mcu", f"i2c#{n}", "i2c") for n in range(3)]
    found = solve(takes, {"mcu": device}, {}, {}, max_steps=3)
    assert [i.code for i in found.issues] == ["pins.search-limit"] and found.choices == ()


def test_unsatisfiable_minimal_set_and_option_filters() -> None:
    device = _device(
        12, [_i2c("I2C1", (1, 2), (3, 4)), DeviceOption("uart", "U", ({"tx": "P5", "rx": "P6"},))]
    )
    takes = [TakeRequest("mcu", f"i2c#{n}", "i2c") for n in range(3)] + [TakeRequest("mcu", "dbg", "uart")]
    found = solve(list(reversed(takes)), {"mcu": device}, {}, {})
    (unsat,) = found.issues
    assert unsat.code == "pins.unsatisfiable" and "dbg" not in unsat.message
    assert all(f"mcu/i2c#{n}" in unsat.message for n in range(3))
    assert all(f"mcu:P{n}" in unsat.message for n in range(1, 5))
    wrong = solve(
        [TakeRequest("mcu", "a", "i2c", option="I2C9"), TakeRequest("mcu", "b", "i2c", pins={"sda": "P6"})],
        {"mcu": device},
        {},
        {},
    )
    assert [i.code for i in wrong.issues] == ["pins.option-unknown", "pins.pinned-conflict"]
    hand = solve(
        [TakeRequest("mcu", "a", "i2c", pins={"sda": "P2"})], {"mcu": device}, {"mcu": frozenset({"P2"})}, {}
    )
    assert [i.code for i in hand.issues] == ["pins.pinned-conflict"] and "by hand" in hand.issues[0].message
    pinned = solve([TakeRequest("mcu", "a", "i2c", pins={"sda": "P4"})], {"mcu": device}, {}, {})
    assert [(c.alternative, c.source) for c in pinned.choices] == [(1, "pinned")]


def test_unsatisfiable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Three I2C takes on two alternatives": exit 5, one finding naming the takes and the pins."""
    folder = copy_example(tmp_path)
    takes = "".join(f'extra{n} = mcu.take(I2C, option="I2C1", name="t{n}")\n' for n in range(3))
    script = variant(
        folder,
        "three.py",
        (I2C_TAKE, I2C_TAKE + takes),
        ("i2c = mcu.take(I2C)", "i2c = mcu.take(UART)"),
        ("connect(i2c, sen.i2c)", "pass"),
        ("pull_up(i2c, v33, r_sda, r_scl)", "pass"),
    )
    code, env = build(monkeypatch, script, "--dry-run")
    assert code == 5
    (unsat,) = [i for i in env["issues"] if i["code"] == "pins.unsatisfiable"]
    assert unsat["severity"] == "error"
    assert all(f"mcu/t{n}" in unsat["message"] for n in range(3))
    assert all(f"mcu:{pin}" in unsat["message"] for pin in ("PB6", "PB7", "PB8", "PB9"))


def test_bench_64_pins_eight_takes() -> None:
    """Risk "Exponential worst case": an authored 64-pin device with eight takes (steps in design.md)."""
    options = [
        _i2c("I2C1", (1, 2), (3, 4), (5, 6)),
        _i2c("I2C2", (5, 6), (7, 8), (9, 10)),
        _i2c("I2C3", (9, 10), (11, 12), (1, 2)),
        DeviceOption("uart", "UART1", tuple({"tx": f"P{a}", "rx": f"P{a + 1}"} for a in (13, 15, 3, 7))),
        DeviceOption("uart", "UART2", tuple({"tx": f"P{a}", "rx": f"P{a + 1}"} for a in (15, 17, 11))),
        DeviceOption("spi", "SPI1", tuple({"sck": f"P{a}", "mosi": f"P{a + 1}", "miso": f"P{a + 2}"}
                                          for a in (19, 22, 13))),
        DeviceOption("pin", "ADC", tuple({"io": f"P{n}"} for n in range(25, 41))),
    ]  # fmt: skip
    device = _device(64, options)
    takes = [TakeRequest("mcu", f"i2c#{n}", "i2c") for n in range(3)]
    takes += [TakeRequest("mcu", f"uart#{n}", "uart") for n in range(2)]
    takes += [TakeRequest("mcu", "spi#0", "spi")] + [TakeRequest("mcu", f"pin#{n}", "pin") for n in range(2)]
    found = solve(takes, {"mcu": device}, {}, {})
    assert found.issues == () and len(found.choices) == 8
    used = [pin for choice in found.choices for pin in choice.pins.values()]
    assert len(used) == len(set(used))
    assert found.steps == 13  # recorded in design.md, risk "Exponential worst case"
    assert solve(list(reversed(takes)), {"mcu": device}, {}, {}) == found


def test_locked_choice_kept_and_stale() -> None:
    device = _device(8, [_i2c("I2C1", (1, 2), (3, 4))])
    takes = [TakeRequest("mcu", "a", "i2c"), TakeRequest("mcu", "b", "i2c")]
    locked = {"mcu/b": LockedChoice("i2c", "I2C1", 0, {"scl": "P1", "sda": "P2"})}
    found = solve(takes, {"mcu": device}, {}, locked)
    assert [(c.key, c.alternative, c.source) for c in found.choices] == [
        ("mcu/a", 1, "solved"),
        ("mcu/b", 0, "locked"),
    ]
    stale = solve(takes, {"mcu": device}, {"mcu": frozenset({"P1"})}, locked)
    assert [i.code for i in stale.issues][:1] == ["pins.lock-stale"] and stale.stale == ("mcu/b",)


# -- the build


def test_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Reviewed before writing"."""
    folder = copy_example(tmp_path)
    code, env = build(monkeypatch, folder / "design.py", "--dry-run")
    assert code == 0, env["issues"]
    pins = env["result"]["pins"]
    assert [row["key"] for row in pins] == ["mcu/debug", "mcu/i2c#0"]
    assert pins[0]["pins"] == {"rx": "PA3", "tx": "PA2"} and pins[1]["pins"] == {"scl": "PB6", "sda": "PB7"}
    lock = [w for w in env["result"]["plan"] if w["kind"] == "lock"]
    assert [Path(w["path"]).name for w in lock] == ["design.lock"]
    assert env["evidence"]["level"] == "UNVERIFIED"  # the example's options carry the device's UNVERIFIED


def test_locked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A new take does not move a locked one"."""
    folder = copy_example(tmp_path)
    code, env = build(monkeypatch, folder / "design.py", "--confirm")
    assert code == 0, env["issues"]
    text = (folder / "design.lock").read_text(encoding="utf-8")
    assert '[pins."mcu/i2c#0"]\nkind = "i2c"\noption = "I2C1"\nalternative = 0\n' in text
    added = (DEBUG, DEBUG + 'env = mcu.take(I2C, name="env")\nconnect(Net("ENV_SDA"), env.sda)\n')
    script = variant(folder, "design.py", added)
    code, env = build(monkeypatch, script, "--dry-run")
    assert code == 0, env["issues"]
    rows = {row["key"]: row for row in env["result"]["pins"]}
    assert (rows["mcu/i2c#0"]["alternative"], rows["mcu/i2c#0"]["source"]) == (0, "locked")
    assert (rows["mcu/env"]["option"], rows["mcu/env"]["alternative"], rows["mcu/env"]["source"]) == (
        "I2C1",
        1,
        "solved",
    )
    (folder / "design.lock").unlink()  # without the lock, the canonical order gives env the first pair
    code, env = build(monkeypatch, script, "--dry-run")
    rows = {row["key"]: row for row in env["result"]["pins"]}
    assert rows["mcu/env"]["alternative"] == 0 and rows["mcu/i2c#0"]["alternative"] == 1


def test_frozen_refusal_and_stale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Frozen refusal": the hand connection of the locked pin PB7."""
    folder = copy_example(tmp_path)
    assert build(monkeypatch, folder / "design.py", "--confirm")[0] == 0
    before = (folder / "design.lock").read_bytes()
    variant(folder, "design.py", (I2C_TAKE, 'connect(Net("LED"), mcu.PB7)\n' + I2C_TAKE))
    code, env = build(monkeypatch, folder / "design.py", "--frozen", "--dry-run")
    assert code == 7 and env["result"] == {} and "plan" not in env["result"]
    (changed,) = env["issues"]
    assert changed["code"] == "lock.changed" and changed["where"] == "pins:mcu/i2c#0"
    code, env = build(monkeypatch, folder / "design.py", "--dry-run")
    assert code == 0
    assert [i["code"] for i in env["issues"] if i["code"].startswith("pins.")] == ["pins.lock-stale"]
    changes = [c for c in env["result"]["lock"]["changes"] if c["section"] == "pins"]
    assert changes == [
        {
            "section": "pins",
            "key": "mcu/i2c#0",
            "before": "I2C1 on PB6/PB7",
            "after": "I2C1 on PB8/PB9",
            "reason": "stale",
        }
    ]
    assert (folder / "design.lock").read_bytes() == before


def test_frozen_names_the_take(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy_example(tmp_path)
    assert build(monkeypatch, folder / "design.py", "--confirm")[0] == 0
    variant(folder, "design.py", (I2C_TAKE, 'connect(Net("LED"), mcu.PB7)\n' + I2C_TAKE))
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main(
            [
                "build",
                str(folder / "design.py"),
                "--out",
                str(folder / "out"),
                "--frozen",
                "--dry-run",
                "--json",
            ]
        )
    assert code == 7
    assert "mcu/i2c#0" in stdout.getvalue() + stderr.getvalue()


def test_locked_dropped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy_example(tmp_path)
    assert build(monkeypatch, folder / "design.py", "--confirm")[0] == 0
    variant(folder, "design.py", (DEBUG, "debug = header\n"), ("connect(debug, header.uart)", "pass"))
    code, env = build(monkeypatch, folder / "design.py", "--confirm")
    assert code == 0
    assert [i["code"] for i in env["issues"]] == ["pins.lock-dropped"]
    assert "mcu/debug" not in (folder / "design.lock").read_text(encoding="utf-8")


def test_unused_take(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy_example(tmp_path)
    script = variant(folder, "unused.py", ("connect(debug, header.uart)", "pass"))
    code, env = build(monkeypatch, script, "--dry-run")
    assert code == 0
    (unused,) = [i for i in env["issues"] if i["code"] == "pins.unused-take"]
    assert unused["severity"] == "warning" and unused["where"] == "mcu/debug"


# -- codes and the example


def test_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Closed set": every ``pins.*`` literal of the sources is a key of ``PIN_ISSUE_CODES`` with
    the severity of the spec, and ``fenolite explain`` knows each."""
    assert dict(PIN_ISSUE_CODES) == {
        "pins.unsatisfiable": "error",
        "pins.option-unknown": "error",
        "pins.pinned-conflict": "error",
        "pins.search-limit": "error",
        "pins.lock-stale": "warning",
        "pins.unused-take": "warning",
        "pins.lock-dropped": "info",
    }
    literals: set[str] = set()
    for path in (ROOT / "src" / "fenolite").rglob("*.py"):
        if path.name == "readiness.py":
            continue  # its "pins.unconnected" names a readiness check, not a finding of the build
        literals |= set(re.findall(r'"(pins\.[a-z][a-z-]*)"', path.read_text(encoding="utf-8")))
    assert literals and literals <= set(PIN_ISSUE_CODES)
    for code in PIN_ISSUE_CODES:
        status, env = run(monkeypatch, "explain", code)
        assert status == 0 and env["ok"], code


def test_example(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``examples/pins`` builds without an issue, and its device record is canonical text."""
    from fenolite.catalog.devices import device_text

    folder = copy_example(tmp_path)
    code, env = build(monkeypatch, folder / "design.py", "--confirm")
    assert code == 0 and env["issues"] == []
    assert (folder / "design.lock").is_file()
    code, env = build(monkeypatch, folder / "design.py", "--frozen", "--dry-run")
    assert code == 0 and env["issues"] == [] and env["result"]["lock"]["changes"] == []
    record = EXAMPLE / "devices" / "example_mcu_qfn32.toml"
    device = parse_device(record.read_text(encoding="utf-8"), file=record.name)
    assert parse_device(device_text(device), file=record.name) == device
