# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Interface options of a device record (capability pin-assignment, "Interface options in device records";
change c0257). The records are authored for Fenolite and illustrative."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.catalog.devices import DeviceFormatError, device_text, parse_device

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "pins" / "devices" / "example_mcu_qfn32.toml"
HEAD = """schema = "fenolite.device.v0"
id = "Proj:MCU"
summary = "Illustrative microcontroller"
symbol = "Proj:MCU"
footprint = "Fenolite:SOIC_8"
ref_prefix = "U"
evidence = "INFERRED"

[pins]
VDD = "1"
VSS = "2"
PB6 = "3"
PB7 = "4"
PB8 = "5"
PB9 = "6"
PA2 = "7"
PA3 = "8"
"""
I2C = """
[[options]]
kind = "i2c"
name = "I2C1"
alternatives = [{ sda = "PB7", scl = "PB6" }, { sda = "PB9", scl = "PB8" }]
"""


def _refused(text: str) -> DeviceFormatError:
    with pytest.raises(DeviceFormatError) as caught:
        parse_device(text, file="mcu.toml")
    assert caught.value.code == "FEN-3004"
    return caught.value


def test_options_load_in_file_order() -> None:
    uart = '\n[[options]]\nkind = "uart"\nname = "UART2"\nalternatives = [{ tx = "PA2", rx = "PA3" }]\n'
    pin = '\n[[options]]\nkind = "pin"\nname = "ADC"\nalternatives = [{ io = "PA3" }]\n'
    pin += 'evidence = "UNVERIFIED"\n'
    device = parse_device(HEAD + uart + I2C + pin, file="mcu.toml")
    assert [(o.kind, o.name) for o in device.options] == [("i2c", "I2C1"), ("pin", "ADC"), ("uart", "UART2")]
    i2c = device.options[0]
    assert i2c.alternatives == ({"scl": "PB6", "sda": "PB7"}, {"scl": "PB8", "sda": "PB9"})
    assert i2c.evidence == "INFERRED" and device.options[1].evidence == "UNVERIFIED"
    text = device_text(device)
    assert parse_device(text, file="mcu.toml") == device
    assert (
        '[[options]]\nkind = "i2c"\nname = "I2C1"\nalternatives = [\n  { scl = "PB6", sda = "PB7" },' in text
    )


def test_unknown_pin() -> None:
    """Scenario "A malformed option": the load names the device, the option and the pin."""
    error = _refused(HEAD + I2C.replace('"PB9"', '"PB99"'))
    assert "Proj:MCU" in str(error) and "I2C1" in str(error) and "PB99" in str(error)


@pytest.mark.parametrize(
    ("change", "words"),
    [
        (('sda = "PB7", scl = "PB6"', 'sda = "PB7"'), "lacks the role 'scl'"),
        (('sda = "PB7", scl = "PB6"', 'sda = "PB7", scl = "PB6", tx = "PA2"'), "extra role 'tx'"),
        (('{ sda = "PB9", scl = "PB8" }', '{ sda = "PB7", scl = "PB6" }'), "twice"),
        (('sda = "PB7", scl = "PB6"', 'sda = "PB7", scl = "PB7"'), "two roles"),
        (('kind = "i2c"', 'kind = "power"'), "not an option kind"),
    ],
)
def test_malformed_options(change: tuple[str, str], words: str) -> None:
    error = _refused(HEAD + I2C.replace(*change))
    assert words in str(error) and "options[0]" in str(error)


def test_option_declared_twice() -> None:
    assert "declared twice" in str(_refused(HEAD + I2C + I2C))


def test_example_device_loads() -> None:
    device = parse_device(EXAMPLE.read_text(encoding="utf-8"), file=EXAMPLE.name)
    assert device.id == "Example:MCU_QFN32"
    assert {(o.kind, o.name) for o in device.options} >= {("i2c", "I2C1"), ("uart", "UART2")}
