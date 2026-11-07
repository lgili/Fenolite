# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native owner/child annotation controls (c0276 task 7.4)."""

from __future__ import annotations

import hashlib

import _drawn_context as context
import _drawn_corpus as census
import pytest
from _probes import runner

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize(("name", "instances"), (("hier", 1), ("repeat", 2)))
def test_child_keeps_native_owner_and_all_repeated_instances(name, instances, tmp_path) -> None:
    cli = runner()
    _, files, child, owner = context.authored(name, cli.major())
    inputs = []
    for file, data in files.items():
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        inputs.append(census.Input(file, file, hashlib.sha256(data).hexdigest()))
    report = census.measure(
        tmp_path,
        owner.root.id,
        inputs,
        cli,
        ident=child.id,
        major=cli.major(),
        native_version=cli.version(),
    )
    assert report["status"] == "equal", report
    assert owner.registered and owner.data(child.id)["target_instances"] == instances
    assert all(report[key]["equal"] for key in ("partition", "lowered_partition", "lowered_native_partition"))
    assert report["partition"]["drawn_pins"] > 0
    assert report["partition"]["drawn_pins"] == report["lowered_partition"]["drawn_pins"]
