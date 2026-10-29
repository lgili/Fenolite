# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tests for the authored fixture; no CAD install or pytest plugin is needed."""

from pathlib import Path

from fenolite.testing import assert_render, load

HERE = Path(__file__).resolve().parent


def test_connections():
    with load(HERE / "design.py") as d:
        assert d.net("GND").pins == ("R1-1", "R2-1")
        assert d.ref("R1")[1].net == "GND"
        assert d.connected("R1-1", "R2-1")
        assert d.connected("R1-1", "R2-1", copper=True)
        assert not d.findings("build.unattached")


def test_ground_picture():
    assert_render(HERE / "design.py", HERE / "golden/net-GND.svg", net="GND")
