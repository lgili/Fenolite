# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Embedded body models of a PCB document (capability altium-import, "Embedded body models"; change c0193).
The corpus documents, which embed models, are read by ``tests/corpus/test_altium_bodies.py``."""

from __future__ import annotations

import struct
from pathlib import Path

from fenolite.backends.altium import models3d
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.base import BodyModelSource

ROOT = Path(__file__).resolve().parents[4]
BODIES = ROOT / "tests" / "data" / "altium" / "body2" / "body2.PcbDoc"


def test_a_document_without_models() -> None:
    """Scenario "An authored document without models"."""
    assert isinstance(AltiumBackend(), BodyModelSource)
    assert models3d.body_models(BODIES) == ()
    assert AltiumBackend().body_models(ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc") == ()


def test_model_records() -> None:
    texts = [b"EMBED=TRUE|ID={A}|ROTZ=90.000|NAME=a.step\x00", b"ID={B}|NAME=b.step\x00"]
    data = b"".join(struct.pack("<I", len(t)) + t for t in texts)
    records = models3d.model_records(data + b"\x09\x00")  # a record cut short ends the run
    assert [r["ID"] for r in records] == ["{A}", "{B}"] and records[0]["ROTZ"] == "90.000"
