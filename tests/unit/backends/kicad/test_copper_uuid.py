# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper uuids (capability manual-copper, "Copper uuids and ids"; change c0028): RFC 9562 version 8 with
the Fenolite marker, the same in every process."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import uuid

import pytest

from fenolite.backends.kicad.copper import COPPER_MARKER, copper_uuid, is_copper_uuid
from fenolite.backends.kicad.embed import placement_uuid

SCRIPT = "from fenolite.backends.kicad.copper import copper_uuid; print(copper_uuid('gnd_main', 'seg[0]'))"


def _in_process(seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    run = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True, text=True, check=True)
    return run.stdout.strip()


def test_marker_and_determinism() -> None:
    one, two = _in_process("1"), _in_process("2")
    assert one == two == copper_uuid("gnd_main", "seg[0]")
    assert one.startswith("66656e6f-6c69-8") and is_copper_uuid(one)
    parsed = uuid.UUID(one)
    assert parsed.version == 8 and parsed.variant == uuid.RFC_4122


def test_bit_layout() -> None:
    value = uuid.UUID(copper_uuid("k", "via")).int
    assert COPPER_MARKER == int.from_bytes(b"fenoli", "big") == value >> 80
    assert (value >> 76) & 0xF == 8 and (value >> 62) & 0b11 == 0b10
    digest = int.from_bytes(hashlib.sha256(b"kicad-copper:k:via").digest(), "big") >> (256 - 74)
    assert (value >> 64) & 0xFFF == digest >> 62  # custom_b: the first 12 hash bits
    assert value & ((1 << 62) - 1) == digest & ((1 << 62) - 1)  # custom_c: the next 62


def test_keys_and_locators_share_no_uuid() -> None:
    names = [(key, loc) for key in ("a", "b", "a:b") for loc in ("seg[0]", "seg[1]", "via", "via[0,1]")]
    assert len({copper_uuid(key, loc) for key, loc in names}) == len(names)
    assert copper_uuid("a", "seg[0]") == copper_uuid("a", "seg[0]")


@pytest.mark.parametrize(
    "text",
    [
        str(uuid.UUID("2c1b9a54-3f7e-4d21-9c0a-5b6e7f8091a2")),  # version 4
        placement_uuid("R1", "/footprint"),  # version 5, the placed copies of c0017
        "66656e6f-6c69-4000-8000-000000000000",  # the marker with version 4
        "66656e6f-6c69-8000-0000-000000000000",  # the marker and version 8 with the wrong variant
        "66656E6F-6C69-8000-8000-000000000000",  # not canonical: upper case
        "{66656e6f-6c69-8000-8000-000000000000}",
        "66656e6f6c6980008000000000000000",
        "",
    ],
)
def test_other_uuids_are_not_copper_uuids(text: str) -> None:
    assert is_copper_uuid(text) is False


def test_minimal_copper_uuid_is_recognised() -> None:
    assert is_copper_uuid("66656e6f-6c69-8000-8000-000000000000")
