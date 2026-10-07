# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Output job read (capability altium-project-reader, "Output job read")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium.read.outjob import (
    JobOutput,
    OutputMedium,
    OutputSetting,
    read_outjob,
    record_fields,
)
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[4] / "data" / "altium" / "read"


def test_outputs_of_one_group() -> None:
    """Scenario "Outputs of one group"."""
    data = (DATA / "jobs.OutJob").read_bytes()
    job = read_outjob(data, file="jobs.OutJob")
    assert job.to_bytes() == data and job.version == "1.0" and job.issues == ()
    (group,) = job.groups
    assert (group.index, group.name, group.description, group.variant_name) == (
        1,
        "jobs.OutJob",
        "",
        "[No Variations]",
    )
    assert group.media == (OutputMedium(1, "Print Job", "Printer"), OutputMedium(2, "PDF", "Publish"))
    assert group.outputs == (
        JobOutput(1, "SchematicPrint", "Schematic Print", "Documentation", "Top.SchDoc", "", True, (2,)),
        JobOutput(
            2,
            "Gerber",
            "Gerber",
            "Fabrication",
            "Board.PcbDoc",
            "",
            False,
            (),
            (OutputSetting(1, "OutputConfigurationParameter1", "Record=GerberView|Units=Imperial"),),
        ),
    )


def test_settings_of_an_output() -> None:
    """Scenario "Settings of an output" (change c0138): typed, and still reachable through the INI view."""
    job = read_outjob((DATA / "jobs.OutJob").read_bytes())
    printed, gerber = job.groups[0].outputs
    assert printed.settings == ()
    assert gerber.settings == (
        OutputSetting(1, "OutputConfigurationParameter1", "Record=GerberView|Units=Imperial"),
    )
    assert record_fields(gerber.settings[0].item) == (("Record", "GerberView"), ("Units", "Imperial"))
    group = job.ini.section("OutputGroup1")
    assert group is not None and group.get("Configuration2_Name1") == "OutputConfigurationParameter1"
    assert group.get("OutputDefault1") == "0" and group.get("OutputDefault2") == "0"


def test_a_field_written_twice() -> None:
    """Scenario "A field written twice": doubles and spaces kept, a part without ``=``, the empty text."""
    assert record_fields("A=1|A=1|B= |C") == (("A", "1"), ("A", "1"), ("B", " "), ("C", ""))
    assert record_fields("") == ()
    assert record_fields("A=b=c") == (("A", "b=c"),)
    assert record_fields("A=1|") == (("A", "1"), ("", ""))


def test_settings_in_ascending_order_and_absent_halves() -> None:
    """One setting per ``k`` with a name or an item, in ascending ``k``; the absent half is empty, a value
    keeps its spaces, and a setting of an index without an output key lists no output."""
    data = (
        b"[OutputJobFile]\nVersion=1.0\n\n[OutputGroup1]\nOutputType1=Gerber\n"
        b"Configuration1_Item3=A= |B=2\nConfiguration1_Name1=first\nConfiguration1_Name3=third\n"
        b"Configuration1_Item2=only an item\nConfiguration9_Name1=nobody\n"
    )
    job = read_outjob(data)
    assert job.to_bytes() == data
    (output,) = job.groups[0].outputs
    assert output.settings == (
        OutputSetting(1, "first", ""),
        OutputSetting(2, "", "only an item"),
        OutputSetting(3, "third", "A= |B=2"),
    )
    assert record_fields(output.settings[2].item) == (("A", " "), ("B", "2"))


def test_other_sections_and_keys_stay_raw() -> None:
    job = read_outjob((DATA / "jobs.OutJob").read_bytes())
    publish = job.ini.section("PublishSettings")
    assert publish is not None and publish.keys() == ("OutputFilePath2", "OutputBasePath2")
    group = job.ini.section("OutputGroup1")
    assert group is not None and group.get("PageOptions1") == "Record=PageOptions|PrintScaleMode=1"


def test_not_an_output_job() -> None:
    """Scenario "Not an output job"."""
    data = (DATA / "project_utf8.PrjPcb").read_bytes()
    with pytest.raises(FormatError, match="OutputJobFile") as caught:
        read_outjob(data, file="p.OutJob")
    assert caught.value.file == "p.OutJob"


def test_output_without_type_is_listed() -> None:
    data = (
        b"[OutputJobFile]\nVersion=1.0\n\n[OutputGroup3]\nName=G\nOutputName2=Late\nOutputEnabled2=1\n"
        b"OutputEnabled2_OutputMedium4=3\nOutputEnabled2_OutputMedium1=0\nOutputType5=Bom\n"
        b"OutputMedium4=Files\n"
    )
    job = read_outjob(data, file="j.OutJob")
    (group,) = job.groups
    assert group.index == 3 and group.media == (OutputMedium(4, "Files", ""),)
    assert [(o.index, o.type, o.name, o.enabled, o.enabled_media) for o in group.outputs] == [
        (2, "", "Late", True, (4,)),
        (5, "Bom", "", False, ()),
    ]
    assert [(i.code, i.severity) for i in job.issues] == [("altium.outjob.output-incomplete", "warning")]
    assert "output 2" in job.issues[0].message


def test_enabled_only_for_one() -> None:
    data = (
        b"[OutputJobFile]\n[OutputGroup1]\nOutputType1=A\nOutputEnabled1=2\nOutputType2=B\nOutputEnabled2=1\n"
    )
    job = read_outjob(data)
    assert job.version is None
    assert [o.enabled for o in job.groups[0].outputs] == [False, True]


def test_groups_in_file_order() -> None:
    data = b"[OutputJobFile]\nVersion=1.0\n[OutputGroup2]\nName=b\n[OutputGroup1]\nName=a\n"
    assert [(g.index, g.name) for g in read_outjob(data).groups] == [(2, "b"), (1, "a")]
