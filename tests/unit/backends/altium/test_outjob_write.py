# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output-job writer (capability altium-project-reader, "Output job written"; change c0087).

The proof is own readback (``H-A-OUTJOB-READBACK``): ``read_outjob`` of the written bytes gives the groups
that were written. ``FENOLITE_GOLDEN_WRITE=1`` rewrites the committed sample.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fenolite.backends.altium import outjob
from fenolite.backends.altium.outjob import OUTPUT_KINDS, from_preset, unmapped, write_outjob
from fenolite.backends.altium.read.outjob import JobOutput, OutputGroup, OutputMedium, read_outjob
from fenolite.core.evidence import Level
from fenolite.exports.preset import Preset, read_preset

ROOT = Path(__file__).resolve().parents[4]
SAMPLE = ROOT / "tests" / "data" / "altium" / "outjob" / "blink.OutJob"
FACTS = ROOT / "docs" / "formats" / "altium" / "output-job.md"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"
KINDS = ("gerbers", "drill", "pos", "bom", "schematic_print", "pcb_print")


def _authored() -> list[tuple[OutputGroup, ...]]:
    """Three authored jobs: a disabled kind, an output in two containers with sparse indexes, two groups."""
    media = (OutputMedium(2, "PDF", "Publish"), OutputMedium(5, "Files", "GeneratedFiles"))
    sparse = OutputGroup(
        3,
        "",
        "two containers",
        "",
        media,
        (
            JobOutput(2, "Gerber", "Gerber Files", "Fabrication", "a.PcbDoc", "", True, (5,)),
            JobOutput(4, "PCB Print", "PCB Prints", "Documentation", "a.PcbDoc", "", True, (2, 5)),
            JobOutput(7, "Schematic Print", "", "Documentation", "", "[No Variations]", False, (2,)),
        ),
    )
    empty = OutputGroup(1, "empty", "", "", (), ())
    return [from_preset(Preset(), name="blink", disabled=("pos",)), (sparse,), (empty, sparse)]


def test_readback() -> None:
    """Scenario "Default preset" and ``H-A-OUTJOB-READBACK``: the default job and three authored ones."""
    default = from_preset(Preset(), name="blink")
    for groups in (default, *_authored()):
        job = read_outjob(write_outjob(groups))
        assert job.groups == tuple(groups)
        assert job.issues == () and job.version == "1.0"
    (group,) = default
    assert [(m.name, m.type) for m in group.media] == [("fab", "GeneratedFiles"), ("doc", "Publish")]
    assert len(group.outputs) == 6 and all(output.enabled for output in group.outputs)
    gerber = group.outputs[0]
    assert (gerber.type, gerber.document_path, gerber.enabled_media) == ("Gerber", "blink.PcbDoc", (1,))
    assert group.name == "blink.OutJob" and group.variant_name == "[No Variations]"


def test_kinds_and_bindings() -> None:
    """The closed table, in order, and what each kind is bound to and sent to."""
    assert tuple(OUTPUT_KINDS) == KINDS
    (group,) = from_preset(None, name="b")
    bound = {outjob.kind_of(o): (o.document_path, o.enabled_media) for o in group.outputs}
    assert bound == {
        "gerbers": ("b.PcbDoc", (1,)),
        "drill": ("b.PcbDoc", (1,)),
        "pos": ("b.PcbDoc", (1,)),
        "bom": ("", (1,)),
        "schematic_print": ("", (2,)),
        "pcb_print": ("b.PcbDoc", (2,)),
    }
    assert outjob.kind_of(JobOutput(1, "ODB", "", "", "", "", True, ())) is None


def test_kind_names_are_recorded() -> None:
    """Every type, name and category of the table stands on the facts page."""
    page = FACTS.read_text(encoding="utf-8")
    for kind in OUTPUT_KINDS.values():
        for text in (kind.type, kind.name, kind.category):
            assert f"`{text}`" in page, f"{kind.key}: {text!r} is not on the facts page"
    for text in (outjob.FOLDER_TYPE, outjob.PDF_TYPE, outjob.NO_VARIANT):
        assert f"`{text}`" in page


def test_disabled_kind() -> None:
    """Scenario "A disabled kind": listed, not enabled, and the positions of the container close up."""
    data = write_outjob(from_preset(Preset(), name="blink", disabled=("pos",)))
    (group,) = read_outjob(data).groups
    pos = group.outputs[2]
    assert (pos.type, pos.enabled, pos.enabled_media) == ("Pick Place", False, ())
    lines = data.decode("ascii").split("\n")
    assert "OutputEnabled3=0" in lines and "OutputEnabled3_OutputMedium1=0" in lines
    assert "OutputEnabled4_OutputMedium1=3" in lines and "OutputEnabled6_OutputMedium2=2" in lines
    with pytest.raises(ValueError, match="unknown output kind"):
        from_preset(Preset(), name="blink", disabled=("step",))


def test_form_and_keys() -> None:
    """LF line ends, 7-bit ASCII, one empty line after each section, and no key without a recorded meaning."""
    data = write_outjob(from_preset(Preset(), name="blink"))
    assert b"\r" not in data and max(data) < 0x80 and data.endswith(b"\n\n")
    job = read_outjob(data)
    assert [s.name for s in job.ini.sections] == [
        "OutputJobFile",
        "OutputGroup1",
        "PublishSettings",
        "GeneratedFilesSettings",
    ]
    texts = data.decode("ascii").split("\n")
    for section in job.ini.sections[1:]:
        assert texts[section.line - 2] == ""
    assert job.ini.sections[0].keys() == ("Version",)
    assert job.ini.sections[2].keys() == job.ini.sections[3].keys() == ()
    allowed = ("Name", "Description", "VariantName", "OutputMedium", "OutputType", "OutputName")
    allowed += ("OutputCategory", "OutputDocumentPath", "OutputVariantName", "OutputEnabled")
    for key in job.ini.sections[1].keys():
        assert (
            key.rstrip("0123456789").removesuffix("_Type").removesuffix("_OutputMedium").rstrip("0123456789")
            in allowed
        ), key
    assert not any(key.startswith(("Configuration", "PageOptions")) for key in job.ini.sections[1].keys())


def test_sample_bytes() -> None:
    """The committed sample is the job of the default preset for ``blink``."""
    data = write_outjob(from_preset(Preset(), name="blink"))
    if WRITE:
        SAMPLE.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE.write_bytes(data)
        pytest.skip("output job sample rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert SAMPLE.read_bytes() == data


def test_unmapped_options() -> None:
    """No option of a preset is mapped: every one it sets is named, sorted; the groups do not change."""
    assert outjob.MAPPED_OPTIONS == frozenset()
    assert unmapped(None) == () and unmapped(Preset()) == ()
    preset = read_preset(
        'schema = "fenolite.export-preset.v0"\n[drill]\nunits = "in"\n[gerbers]\nprecision = 5\nx2 = false\n'
    )
    assert unmapped(preset) == ("drill.units", "gerbers.precision", "gerbers.x2")
    assert from_preset(preset, name="blink") == from_preset(None, name="blink")


@pytest.mark.parametrize(
    "group",
    [
        OutputGroup(1, "a\nb", "", "", (), ()),
        OutputGroup(1, "café", "", "", (), ()),
        OutputGroup(0, "", "", "", (), ()),
        OutputGroup(1, "", "", "", (OutputMedium(1, "a", "Publish"), OutputMedium(1, "b", "Publish")), ()),
        OutputGroup(1, "", "", "", (OutputMedium(1, "a", ""),), ()),
        OutputGroup(1, "", "", "", (), (JobOutput(1, "Gerber", "", "", "", "", True, (2,)),)),
        OutputGroup(1, "", "", "", (), (JobOutput(1, "", "", "", "", "", True, ()),)),
        OutputGroup(
            1,
            "",
            "",
            "",
            (OutputMedium(1, "a", "Publish"), OutputMedium(2, "b", "Publish")),
            (JobOutput(1, "Gerber", "", "", "", "", True, (2, 1)),),
        ),
    ],
)
def test_refusals(group: OutputGroup) -> None:
    """Scenario "Text that a line cannot hold", and the indexes and containers a job cannot have."""
    with pytest.raises(ValueError):
        write_outjob((group,))


def test_repeated_group_index() -> None:
    group = OutputGroup(1, "", "", "", (), ())
    with pytest.raises(ValueError, match="repeated"):
        write_outjob((group, group))


def test_evidence() -> None:
    assert outjob.EVIDENCE.level is Level.INFERRED
    assert set(outjob.EVIDENCE.hypotheses) == {
        "H-A-OUTJOB-OPEN",
        "H-A-OUTJOB-READBACK",
        "H-A-OUTJOB-RUN",
    }
