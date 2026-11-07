# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Declared project input retains native settings, full graphs and a physical rule (c0351)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import _erc
import pytest
from _probes import major, runner
from _project_template import SETTINGS, authored, built, imported, snapshot

pytestmark = pytest.mark.needs_kicad


def payload(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()
    }


def reference_text(outputs: dict[str, bytes]) -> Counter[str]:
    return Counter(
        "".join(node.itertext())
        for name, data in outputs.items()
        if name.endswith(".svg")
        for node in ET.fromstring(data).iter()
        if node.tag.endswith("}text") and "".join(node.itertext()).startswith("AUTH[")
    )


def test_native_project_settings_survive_actual_import_and_reviewed_rebuild(
    tmp_path, record_property
) -> None:
    target, cli = major(), runner()
    source = authored(tmp_path / "original", target)
    before = snapshot(source.parent)
    code = imported(tmp_path, source, target=target)
    code_before = snapshot(code)
    rebuilt = built(tmp_path, code, target=target)
    graphs, texts, reports = [], [], []
    for project in (source, rebuilt):
        files = payload(project.parent)
        root = project.with_suffix(".kicad_sch").name
        graphs.append(_erc.netlist(cli, root, files))
        svg = cli.run(["sch", "export", "svg", "-o", "svg", root], files=files, folders=("svg",))
        assert svg.ok, svg.stderr
        texts.append(reference_text(dict(svg.outputs)))
        board = project.with_suffix(".kicad_pcb")
        report = cli.drc(board, files=_erc.tops(files, tmp_path / f"native-{len(reports)}"))
        assert report.run.ok and report.report is not None, report.run.stderr
        reports.append(
            Counter(
                (
                    section,
                    row.type,
                    row.severity,
                    row.excluded,
                    row.description,
                    tuple(sorted((item.description, item.position.x, item.position.y) for item in row.items)),
                )
                for section in ("violations", "unconnected_items", "schematic_parity")
                for row in getattr(report.report, section)
            )
        )
        settings = json.loads(project.read_text())["schematic"]["drawing"]
        assert {key: settings[key] for key in SETTINGS} == SETTINGS
    assert graphs[0] == graphs[1] and len({pin for pins in graphs[0].values() for pin in pins}) > 0
    assert texts[0] == texts[1] and texts[0]
    assert reports[0] == reports[1] and any(key[1] == "annular_width" for key in reports[0])
    assert snapshot(source.parent) == before and snapshot(code) == code_before
    record_property("native_version", cli.version())
    record_property("source_sha256", json.dumps(before, sort_keys=True))
    record_property("template_sha256", code_before["native/project.kicad_pro"])
    record_property("native_refs", json.dumps(texts[0], sort_keys=True))
    record_property(
        "native_all_drc_counts", json.dumps(sorted((str(key), count) for key, count in reports[0].items()))
    )
