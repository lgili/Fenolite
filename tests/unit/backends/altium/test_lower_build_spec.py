# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium build through the lowering writes the PCB documents of the former path (capability
altium-build, "Altium build through the lowering", scenario "The two paths give one specification"; change
c0126, tasks 1.1, 6.1 and 6.2).

Task 1.1 compared, for every script under ``examples/`` in both sheet modes, the ``PcbDocSpec`` of the
former path (``lens.altium.pcb_document``) with the one of ``backends.altium.lower.from_design`` on the
stored model, field by field, and wrote the table "The two build paths, field by field" of the design. Task
6.1 compared the former path with ``lens.altium.lowered_pcb`` (``place_footprints``, then ``from_design``
with the build's ``lower.LowerOptions``): equal in the written view with no listed exception, with the same
issues and the same bytes of ``pcbdoc.write_pcbdoc``, on every build that writes a PCB document
(2026-10-08). The build then switched to the lowering and ``pcb_document`` was removed (task 6.2).

This file keeps what that comparison measured: ``FORMER_DOCUMENTS`` holds the SHA-256 of each example's
PCB document as the former path wrote it, measured with ``pcb_document`` in place, and the build through the
lowering must write the same bytes from the specification it lowered.

The written view (``written_view``) is what ``pcbdoc`` writes records from: every field of the
specification but the placed footprints, every field of a placed component but its footprint and its two
net maps, and of each placed footprint its pattern, the pads and graphics that ``pcblib.check_footprint``
keeps without their ids, bags and provenance, the corner percentage and the net of each pad. The ids of the
entities of a placed footprint were not compared: an instance's pads have ids of their own (design, "Found
on 2026-10-08", 1).
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
from _altium_built import EXAMPLES, build_altium_example

import fenolite.lens.altium as lens_altium
from fenolite.backends.altium import pcbdoc, pcblib
from fenolite.backends.altium import pcbrecords as rec

SCRIPTS = tuple(sorted(EXAMPLES.rglob("*.py")))
SHEET_MODES = ("flat", "modules")
INTERNAL = ("id", "native_ids", "provenance", "ext", "net_id", "corner_ratio")
"""Fields of a pad or a graphic of a placed footprint that no record is written from. A pad record takes
its corner from the pad's extras, which the view holds as ``corner_percent``: ``Pad.corner_ratio`` is where
the lowering takes those extras from (change c0126)."""
FORMER_DOCUMENTS: dict[tuple[str, str], str] = {
    (
        "altium_hier_board/design.py",
        "flat",
    ): "7afea34178a0b6e3502fb5301fd7791d14a7cd4c6554d1382a522e7f332f700c",
    ("blink_2layer/design.py", "flat"): "642ce93cdfd14136c421406e3ba261aab055fcdb437dff9cfc9fefebdd3e0a32",
    ("blink_routed/design.py", "flat"): "6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a",
    ("board_40parts/design.py", "flat"): "4c536e64a5a41ffa86b03054a69e334f6048b88d46b0cf5273a2fe3e972a19b8",
    ("kit/board6/design.py", "flat"): "b936f2aab597591304a522a6155cec200d79cd5c10cd2112cacca826573a2e61",
    ("kit/flat/design.py", "flat"): "afe2c1d88355f2cc7d01a72f3b068c423da753b053fd4e264bca6925323b4b87",
    ("kit/libs/design.py", "flat"): "a7218f03522a6039d8da3aa871cb960d7265fb2a5737077840ae7c4f93ba8c97",
    ("kit/routed/design.py", "flat"): "22364b8ffbfb3088d1df64561a5499906d7dd6e9c0c8a9cd4239fd2e108415ad",
    (
        "altium_hier_board/design.py",
        "modules",
    ): "17b8395b823e69d38171ac87296bbd43077f80a61174114f78107b306dda577c",
    ("blink_2layer/design.py", "modules"): "642ce93cdfd14136c421406e3ba261aab055fcdb437dff9cfc9fefebdd3e0a32",
    ("blink_routed/design.py", "modules"): "6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a",
    (
        "board_40parts/design.py",
        "modules",
    ): "fc999ff008fa4134cf5aeb6d3c95c15fd06615d99a55664d10685b228232f258",
    ("kit/board6/design.py", "modules"): "b936f2aab597591304a522a6155cec200d79cd5c10cd2112cacca826573a2e61",
    ("kit/flat/design.py", "modules"): "afe2c1d88355f2cc7d01a72f3b068c423da753b053fd4e264bca6925323b4b87",
    ("kit/libs/design.py", "modules"): "a7218f03522a6039d8da3aa871cb960d7265fb2a5737077840ae7c4f93ba8c97",
    ("kit/routed/design.py", "modules"): "22364b8ffbfb3088d1df64561a5499906d7dd6e9c0c8a9cd4239fd2e108415ad",
}
"""(example script, sheet mode) → the SHA-256 of its PCB document as ``lens.altium.pcb_document`` wrote it,
measured on 2026-10-08 before the switch of task 6.2. ``blink_official/design.py`` needs KiCad's official
libraries; where they are absent its build exits 3 and it is not compared."""


def _plain(entity: object) -> dict[str, object]:
    return {
        item.name: getattr(entity, item.name)
        for item in dataclasses.fields(entity)  # type: ignore[arg-type]
        if item.name not in INTERNAL
    }


def written_view(spec: pcbdoc.PcbDocSpec) -> dict[str, object]:
    """What the records of the document are written from, as plain values."""
    view: dict[str, object] = {
        item.name: getattr(spec, item.name) for item in dataclasses.fields(spec) if item.name != "components"
    }
    components: list[dict[str, object]] = []
    for placed in spec.components:
        footprint = placed.footprint
        check = pcblib.check_footprint(footprint.defn, footprint.extras, texts=footprint.texts)
        pads: list[dict[str, object]] = []
        for pad in check.pads:
            ratio = footprint.extras.get(pad.id, pcblib.PadExtras()).corner_ratio
            net = (
                placed.nets_by_pad.get(pad.id)
                if placed.nets_by_pad is not None
                else placed.pad_nets.get(pad.number)
            )
            percent = rec.corner_percent(ratio) if ratio is not None else None
            pads.append({**_plain(pad), "corner_percent": percent, "net": net})
        item = {
            name.name: getattr(placed, name.name)
            for name in dataclasses.fields(placed)
            if name.name not in ("footprint", "pad_nets", "nets_by_pad")
        }
        item["pattern"] = footprint.defn.name
        item["refusal"] = check.refusal
        item["pads"] = pads
        item["graphics"] = [_plain(graphic) for graphic in check.graphics]
        components.append(item)
    view["components"] = components
    return view


def built_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: Path, sheets: str
) -> tuple[Path | None, pcbdoc.PcbDocSpec | None, str]:
    """``(the built PCB document, the specification the build lowered, a note)`` for one build."""
    captured: list[pcbdoc.PcbDocSpec | None] = []
    original = lens_altium.lowered_pcb

    def keeping(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        captured.append(result[0])
        return result

    with monkeypatch.context() as patch:
        patch.setattr(lens_altium, "lowered_pcb", keeping)
        code, folder, error = build_altium_example(monkeypatch, tmp_path, script, "--altium-sheets", sheets)
    if code != 0:
        return None, None, f"the build exits {code}: {error.strip()[:120]}"
    documents = sorted(folder.glob("*.PcbDoc"))
    if not documents or not captured or captured[-1] is None:
        return None, None, "the build plans no PCB document"
    return documents[0], captured[-1], ""


@pytest.mark.parametrize("sheets", SHEET_MODES)
def test_the_lowering_writes_the_former_documents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sheets: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every example build that writes a PCB document writes, through ``lower.from_design``, the bytes the
    former path wrote, from the specification it lowered; every placed footprint of that specification
    keeps every pad of its definition, and none is refused."""
    assert SCRIPTS
    compared = 0
    lines: list[str] = []
    for number, script in enumerate(SCRIPTS):
        name = script.relative_to(EXAMPLES).as_posix()
        folder = tmp_path / f"{sheets}-{number}"
        folder.mkdir()
        document, spec, note = built_document(monkeypatch, folder, script, sheets)
        if document is None or spec is None:
            assert (name, sheets) not in FORMER_DOCUMENTS or "exits" in note, f"{name}: {note}"
            lines.append(f"{name}: not compared ({note})")
            continue
        data = document.read_bytes()
        assert hashlib.sha256(data).hexdigest() == FORMER_DOCUMENTS[(name, sheets)], name
        assert pcbdoc.write_pcbdoc(spec, filename=document.name) == data, name
        components = written_view(spec)["components"]
        assert isinstance(components, list) and len(components) == len(spec.components) > 0, name
        for placed, item in zip(spec.components, components, strict=True):
            assert item["refusal"] is None and len(item["pads"]) == len(placed.footprint.defn.pads), name
        compared += 1
        lines.append(f"{name}: the former bytes")
    with capsys.disabled():
        print(f"\n== sheets={sheets}: {compared} of {len(SCRIPTS)} builds compared")
        for line in lines:
            print("  " + line)
    assert compared, "no example build wrote a PCB document"
