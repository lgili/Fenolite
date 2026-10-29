# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exercise the exact testing example published in the agent guide."""

from fenolite.agent import guide


def test_testing_guide_example(script, monkeypatch):
    monkeypatch.chdir(script.parent)
    samples = [
        block
        for block in guide.blocks(guide.page("design-script"))
        if "from fenolite.testing import load" in block.lines
    ]
    assert len(samples) == 1
    exec(compile("\n".join(samples[0].lines), "guide-design-testing", "exec"), {})
