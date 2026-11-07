# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native full root-port partitions before/after lowering on the actual supported major (c0350)."""

import hashlib

import _bus_scope
import _drawn_corpus
import _probes
import _root_hlabels
import pytest

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("equal", [False, True])
def test_native_root_hierarchical_ports_preserve_complete_connectivity(equal, tmp_path) -> None:
    file, files, refs = _bus_scope.native_drawing(_root_hlabels.drawing(equal=equal), _probes.major())
    inputs = []
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        inputs.append(_drawn_corpus.Input(name, name, hashlib.sha256(data).hexdigest()))
    report = _drawn_corpus.measure(
        tmp_path,
        file,
        inputs,
        _probes.runner(),
        ident="authored-root-port",
        major=_probes.major(),
        native_version=_probes.runner().version(),
    )
    print(report)
    assert report["partition"]["drawn_pins"] == report["partition"]["native_pins"] == 40
    assert report["partition"]["equal"] and report["partition"]["naming_equal"]
    assert report["status"] == "equal", report
    for key in ("lowered_partition", "lowered_native_partition"):
        assert report[key]["equal"] and report[key]["naming_equal"], (key, report)
        assert report[key]["native_only_pins"] == report[key]["drawn_unlisted_pins"] == 0
    assert all((tmp_path / name).read_bytes() == data for name, data in files.items())
