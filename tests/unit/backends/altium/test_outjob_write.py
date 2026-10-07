# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output-job writer (capability altium-project-reader, "Output job written"; changes c0087 and c0138).

The proof is own readback (``H-A-OUTJOB-READBACK``, ``H-A-OUTJOB-GERBER-READBACK``): ``read_outjob`` of the
written bytes gives the groups that were written, and ``record_fields`` the 44 fields of the Gerber record.
``FENOLITE_GOLDEN_WRITE=1`` rewrites the committed sample.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
from pathlib import Path

import pytest

from fenolite.backends.altium import libboard, outjob
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.outjob import (
    GERBER_FIELDS,
    LAYER_SET_HEAD,
    OUTPUT_KINDS,
    from_preset,
    gerber_record,
    plot_layers,
    unmapped,
    write_outjob,
)
from fenolite.backends.altium.read.outjob import (
    JobOutput,
    OutputGroup,
    OutputMedium,
    OutputSetting,
    read_outjob,
    record_fields,
)
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.evidence import Level
from fenolite.exports.preset import TABLES, Preset, read_preset

ROOT = Path(__file__).resolve().parents[4]
SAMPLE = ROOT / "tests" / "data" / "altium" / "outjob" / "blink.OutJob"
SAMPLES = ROOT / "tests" / "data" / "altium"
FACTS = ROOT / "docs" / "formats" / "altium" / "output-job.md"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"
KINDS = ("gerbers", "drill", "pos", "bom", "schematic_print", "pcb_print")
TWO = (1, 32)
FOUR = (1, 2, 3, 32)
SIX = (1, 2, 39, 4, 5, 32)

# The plotted layers of the three committed boards, entry by entry (design of change c0138, "Tests").
ABOVE = [(16973830, "Top Overlay"), (16973832, "Top Paste"), (16973834, "Top Solder")]
BELOW = [(16973835, "Bottom Solder"), (16973833, "Bottom Paste"), (16973831, "Bottom Overlay")]
MECHANICAL = [
    (16908301, "Mechanical 13"),
    (16908302, "Mechanical 14"),
    (16908303, "Mechanical 15"),
    (16908304, "Mechanical 16"),
]
EXPECTED_LAYERS: dict[str, list[tuple[int, str]]] = {
    "blink": [*ABOVE, (16777217, "Top Layer"), (16842751, "Bottom Layer"), *BELOW, *MECHANICAL],
    "routed": [
        *ABOVE,
        (16777217, "Top Layer"),
        (16777218, "Mid-Layer 1"),
        (16777219, "Mid-Layer 2"),
        (16842751, "Bottom Layer"),
        *BELOW,
        *MECHANICAL,
    ],
    "board6": [
        *ABOVE,
        (16777217, "Top Layer"),
        (16777218, "Mid-Layer 1"),
        (16842753, "Internal Plane 1"),
        (16777220, "Mid-Layer 3"),
        (16777221, "Mid-Layer 4"),
        (16842751, "Bottom Layer"),
        *BELOW,
        *MECHANICAL,
    ],
}
STACKS = {"blink": TWO, "routed": FOUR, "board6": SIX}

C0087_PLAIN_SHA256 = "9dcab93af5537c6f69ee81e3108a427548b6027febc367e1047d7471e7ea0825"
"""The SHA-256 of ``_plain()`` as the writer of change c0087 wrote it (commit ``9aba2dff``, pinned on
2026-10-07 before the writer was edited): a job without a Gerber output."""
C0087_SAMPLE_SHA256 = "e6ac379aeb0e508866b8c45e6bc1e6516da1e50a2b3cf9f6117e68a81051db9e"
"""The SHA-256 of the committed sample ``blink.OutJob`` as change c0087 wrote it (the same commit)."""


def _record(copper: tuple[int, ...] = TWO, decimals: int = 4) -> OutputSetting:
    return OutputSetting(1, outjob.SETTING_NAME, gerber_record(plot_layers(copper), decimals=decimals))


def _plain() -> OutputGroup:
    """Scenario "One key per output": one container, an NC drill output and a schematic print."""
    return OutputGroup(
        1,
        "plain.OutJob",
        "",
        "[No Variations]",
        (OutputMedium(1, "out", "GeneratedFiles"),),
        (
            JobOutput(1, "NC Drill", "NC Drill Files", "Fabrication", "plain.PcbDoc", "", True, (1,)),
            JobOutput(2, "Schematic Print", "Schematic Prints", "Documentation", "", "", False, ()),
        ),
    )


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
            JobOutput(2, "Gerber", "Gerber Files", "Fabrication", "a.PcbDoc", "", True, (5,), (_record(),)),
            JobOutput(4, "PCB Print", "PCB Prints", "Documentation", "a.PcbDoc", "", True, (2, 5)),
            JobOutput(7, "Schematic Print", "", "Documentation", "", "[No Variations]", False, (2,)),
        ),
    )
    empty = OutputGroup(1, "empty", "", "", (), ())
    return [from_preset(Preset(), name="blink", copper=TWO, disabled=("pos",)), (sparse,), (empty, sparse)]


def _gerber(groups: tuple[OutputGroup, ...]) -> JobOutput:
    return next(o for g in groups for o in g.outputs if o.type == "Gerber")


def _fields(groups: tuple[OutputGroup, ...]) -> tuple[tuple[str, str], ...]:
    (setting,) = _gerber(groups).settings
    return record_fields(setting.item)


def _without(groups: tuple[OutputGroup, ...], settings: tuple[OutputSetting, ...]) -> tuple[OutputGroup, ...]:
    """``groups`` with the settings of the Gerber output replaced."""
    (group,) = groups
    outputs = tuple(
        dataclasses.replace(o, settings=settings) if o.type == "Gerber" else o for o in group.outputs
    )
    return (dataclasses.replace(group, outputs=outputs),)


def test_readback() -> None:
    """Scenario "Default preset" and ``H-A-OUTJOB-READBACK``: the default job and three authored ones."""
    default = from_preset(Preset(), name="blink", copper=TWO)
    for groups in (default, *_authored()):
        data = write_outjob(groups)
        job = read_outjob(data)
        assert job.groups == tuple(groups)
        assert job.issues == () and job.version == "1.0" and job.to_bytes() == data
    (group,) = default
    assert [(m.name, m.type) for m in group.media] == [("fab", "GeneratedFiles"), ("doc", "Publish")]
    assert len(group.outputs) == 6 and all(output.enabled for output in group.outputs)
    gerber = group.outputs[0]
    assert (gerber.type, gerber.document_path, gerber.enabled_media) == ("Gerber", "blink.PcbDoc", (1,))
    assert group.name == "blink.OutJob" and group.variant_name == "[No Variations]"
    assert [bool(output.settings) for output in group.outputs] == [True, False, False, False, False, False]


@pytest.mark.parametrize("copper", [TWO, FOUR, SIX], ids=["two", "four", "six"])
def test_gerber_readback(copper: tuple[int, ...]) -> None:
    """``H-A-OUTJOB-GERBER-READBACK``: for the three stacks the written job reads back to equal groups and
    equal bytes, and the Gerber setting to 44 fields with the names of ``GERBER_FIELDS``."""
    groups = from_preset(Preset(), name="b", copper=copper)
    data = write_outjob(groups)
    job = read_outjob(data)
    assert job.groups == groups and job.to_bytes() == data and job.issues == ()
    fields = _fields(job.groups)
    assert len(fields) == 44 and [name for name, _ in fields] == [f.name for f in GERBER_FIELDS]
    assert outjob.plotted_layers(_gerber(job.groups).settings[0].item) == plot_layers(copper)
    section = job.ini.section("OutputGroup1")
    assert section is not None
    assert [section.get(f"OutputDefault{i}") for i in range(1, 7)] == ["0"] * 6


def test_gerber_fields_table() -> None:
    """The table: 44 positions, 37 names in code-point order, seven of them twice and adjacent, 31 constant
    positions, and no ``DocumentPath``."""
    names = [field.name for field in GERBER_FIELDS]
    assert len(names) == 44 and len(set(names)) == 37 and names == sorted(names)
    twice = sorted({name for name in names if names.count(name) == 2})
    assert twice == [
        "GenerateDRCRulesFile",
        "GerberUnit",
        "MinusApertureTolerance",
        "NumberOfDecimals",
        "OptimizeChangeLocationCommands",
        "PlusApertureTolerance",
        "Sorted",
    ]
    assert all(names.count(name) <= 2 for name in names) and "DocumentPath" not in names
    rules = [field.rule for field in GERBER_FIELDS]
    assert {rule: rules.count(rule) for rule in sorted(set(rules))} == {
        "choice": 8,
        "constant": 31,
        "decimals": 2,
        "layers": 1,
        "unit": 2,
    }
    assert all(field.value for field in GERBER_FIELDS if field.rule in ("constant", "choice", "unit"))
    assert not any(field.value for field in GERBER_FIELDS if field.rule in ("decimals", "layers"))


def _page_rows() -> list[list[str]]:
    """The rows of the field table of the facts page (the table whose second header cell is ``field``)."""
    rows: list[list[str]] = []
    inside = False
    for line in FACTS.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if cells[:2] == ["#", "field"]:
            inside = True
            assert cells[2:] == [
                "row 01",
                "row 03",
                "Fenolite writes",
                "rule",
                "source",
                "label",
                "hypothesis",
            ]
        elif inside and not cells:
            break
        elif inside and not set(line) <= set("|-"):
            rows.append(cells)
    return rows


def test_gerber_fields_equal_the_facts_page() -> None:
    """``GERBER_FIELDS`` is the field table of ``output-job.md``: names, positions, rules and written
    values; every row has its sources, the label ``INFERRED`` and a hypothesis of this change."""
    spoken = {
        "one space": " ",
        "the head, no entry": LAYER_SET_HEAD,
        "the decimals": "",
        "the head and the board's layers": "",
    }
    found: list[outjob.GerberField] = []
    rows = _page_rows()
    assert len(rows) == 37
    for cells in rows:
        positions = [int(text) for text in cells[0].split(",")]
        name = re.fullmatch(r"`([^`]+)`( \(written twice\))?", cells[1])
        assert name is not None, cells[1]
        assert (len(positions) == 2) == (name.group(2) is not None), cells[1]
        assert positions[0] == len(found) + 1 and positions == list(
            range(positions[0], positions[0] + len(positions))
        )
        written = cells[4]
        value = written[1:-1] if written.startswith("`") else spoken[written]
        found += [outjob.GerberField(name.group(1), cells[5], value)] * len(positions)
        assert {"S-0187", "S-0299"} <= set(re.findall(r"S-\d{4}", cells[6])), cells[1]
        assert cells[7] == "INFERRED", cells[1]
        assert re.fullmatch(r"H-A-OUTJOB-GERBER-(RECORD|LAYERS|DECIMALS)", cells[8]), cells[1]
        if cells[5] == "constant":
            assert cells[2] == cells[3] == cells[4], cells[1]
        else:
            assert cells[2] != cells[3], cells[1]
    assert tuple(found) == GERBER_FIELDS
    page = FACTS.read_text(encoding="utf-8")
    for text in (LAYER_SET_HEAD, outjob.SETTING_NAME, "OutputDefault<i>", outjob.GERBER_UNIT):
        assert f"`{text}`" in page, text


def test_record_of_a_two_layer_board() -> None:
    """Scenario "The record of a two-layer board"."""
    fields = _fields(from_preset(Preset(), name="blink", copper=TWO))
    assert len(fields) == 44 and [name for name, _ in fields] == [f.name for f in GERBER_FIELDS]
    assert [value for name, value in fields if name == "GerberUnit"] == ["Metric", "Metric"]
    assert [value for name, value in fields if name == "NumberOfDecimals"] == ["4", "4"]
    values = dict(fields)
    entries = (
        "16973830~1,16973832~1,16973834~1,16777217~1,16842751~1,16973835~1,16973833~1,16973831~1,"
        "16908301~1,16908302~1,16908303~1,16908304~1"
    )
    assert values["Plot.Set"] == f"{LAYER_SET_HEAD},{entries}"
    assert values["Mirror.Set"] == values["AddToAllPlots.Set"] == LAYER_SET_HEAD
    assert values["AddToAllLayerClasses.Set"] == values["LayerClassesMirror.Set"] == " "
    assert values["LayerClassesPlot.Set"] == " " and values["Record"] == "GerberView"
    for field, (name, value) in zip(GERBER_FIELDS, fields, strict=True):
        if field.rule in ("constant", "choice"):
            assert (name, value) == (field.name, field.value)


@pytest.mark.parametrize("sample", ["blink", "routed", "board6"])
def test_plot_set_of_the_committed_boards(sample: str) -> None:
    """``Plot.Set`` of the three committed boards, entry by entry: only layers the board has, in the order
    the design gives, the copper read from the committed PCB document."""
    document = read_pcbdoc((SAMPLES / sample / f"{sample}.PcbDoc").read_bytes())
    copper = tuple(document.board.copper_chain)
    assert copper == STACKS[sample]
    expected = EXPECTED_LAYERS[sample]
    assert list(plot_layers(copper)) == [long for long, _name in expected]
    numbers = outjob.plot_layer_numbers(copper)
    assert [rec.LAYER_NAMES[number] for number in numbers] == [name for _long, name in expected]
    assert [libboard.long_id(number) for number in numbers] == [long for long, _name in expected]
    record = gerber_record(plot_layers(copper), decimals=4)
    value = dict(record_fields(record))["Plot.Set"]
    assert value == LAYER_SET_HEAD + "".join(f",{long}~1" for long, _name in expected)
    # no entry for the board outline, a drill layer, the keep-out layer or Multi-Layer
    assert not {rec.LAYER_NAMES[n] for n in numbers} & {"Keep-Out Layer", "Multi-Layer", "Drill Drawing"}
    assert set(numbers) - set(copper) == {33, 34, 35, 36, 37, 38, 69, 70, 71, 72}


def test_first_ten_entries_of_the_four_layer_list() -> None:
    """The first ten entries of the four-layer list are the first ten of both public jobs (facts page)."""
    assert list(plot_layers(FOUR))[:10] == [
        16973830,
        16973832,
        16973834,
        16777217,
        16777218,
        16777219,
        16842751,
        16973835,
        16973833,
        16973831,
    ]


def test_plane_among_the_copper_layers() -> None:
    """Scenario "A plane among the copper layers"."""
    ids = plot_layers(SIX)
    assert len(ids) == 16
    assert ids[3:9] == (16777217, 16777218, 16842753, 16777220, 16777221, 16842751)
    for bad in ((), (1,), (32, 1), (1, 3, 32), (1, 2, 32), (1, 1, 32, 32)):
        with pytest.raises(ValueError, match="copper stack"):
            plot_layers(bad)


def test_gerber_record_refusals() -> None:
    layers = plot_layers(TWO)
    for decimals in (0, 3, 7, True):
        with pytest.raises(ValueError, match="decimals"):
            gerber_record(layers, decimals=decimals)
    with pytest.raises(ValueError, match="without a plotted layer"):
        gerber_record((), decimals=4)
    with pytest.raises(ValueError, match="repeated"):
        gerber_record((*layers, layers[0]), decimals=4)


def test_every_precision_of_the_preset_is_written() -> None:
    """Scenario "Decimals of the preset", for every value the export preset allows: the value is written in
    both places, nothing is clamped, and the record is whole. 4 is the default; 5 and 6 beside ``Metric``
    are in no public job (``H-A-OUTJOB-GERBER-DECIMALS``, unknown U6 of the facts page)."""
    allowed = TABLES["gerbers"]["precision"]
    assert allowed == (5, 6) and set(allowed) | {outjob.DEFAULT_DECIMALS} == set(outjob.DECIMALS)
    for precision in allowed:
        preset = read_preset(
            'schema = "fenolite.export-preset.v0"\n'
            f'[gerbers]\nprecision = {precision}\n[drill]\nunits = "in"\n'
        )
        groups = from_preset(preset, name="blink", copper=TWO)
        fields = _fields(read_outjob(write_outjob(groups)).groups)
        assert [value for name, value in fields if name == "NumberOfDecimals"] == [str(precision)] * 2
        assert [value for name, value in fields if name == "GerberUnit"] == ["Metric", "Metric"]
        assert len(fields) == 44 and unmapped(preset) == ("drill.units",)
    assert "U6" in FACTS.read_text(encoding="utf-8")


def test_kinds_and_bindings() -> None:
    """The closed table, in order, and what each kind is bound to and sent to."""
    assert tuple(OUTPUT_KINDS) == KINDS
    (group,) = from_preset(None, name="b", copper=TWO)
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
    assert OUTPUT_KINDS["gerbers"].type == outjob.GERBER_TYPE


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
    data = write_outjob(from_preset(Preset(), name="blink", copper=TWO, disabled=("pos",)))
    (group,) = read_outjob(data).groups
    pos = group.outputs[2]
    assert (pos.type, pos.enabled, pos.enabled_media) == ("Pick Place", False, ())
    lines = data.decode("ascii").split("\n")
    assert "OutputEnabled3=0" in lines and "OutputEnabled3_OutputMedium1=0" in lines
    assert "OutputEnabled4_OutputMedium1=3" in lines and "OutputEnabled6_OutputMedium2=2" in lines
    assert "OutputDefault3=0" in lines
    with pytest.raises(ValueError, match="unknown output kind"):
        from_preset(Preset(), name="blink", copper=TWO, disabled=("step",))
    # a disabled Gerber output still carries the complete record
    (group,) = from_preset(Preset(), name="blink", copper=TWO, disabled=("gerbers",))
    assert not group.outputs[0].enabled and len(record_fields(group.outputs[0].settings[0].item)) == 44


def test_form_and_keys() -> None:
    """LF line ends, 7-bit ASCII, one empty line after each section, and no key without a recorded row."""
    data = write_outjob(from_preset(Preset(), name="blink", copper=TWO))
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
    allowed += ("OutputCategory", "OutputDocumentPath", "OutputVariantName", "OutputEnabled", "OutputDefault")
    keys = job.ini.sections[1].keys()
    configuration = [key for key in keys if key.startswith("Configuration")]
    assert configuration == ["Configuration1_Name1", "Configuration1_Item1"]
    for key in keys:
        if key in configuration:
            continue
        assert (
            key.rstrip("0123456789").removesuffix("_Type").removesuffix("_OutputMedium").rstrip("0123456789")
            in allowed
        ), key
    assert not any(key.startswith("PageOptions") for key in keys)
    assert "DocumentPath=" not in (job.ini.sections[1].get("Configuration1_Item1") or "DocumentPath=")


def test_keys_of_the_gerber_output() -> None:
    """Scenario "The keys of the Gerber output": the three lines after the last container key, one
    ``OutputDefault<i>=0`` per output, and the bytes come back."""
    groups = from_preset(Preset(), name="blink", copper=TWO)
    data = write_outjob(groups)
    lines = data.decode("ascii").split("\n")
    at = lines.index("OutputEnabled1_OutputMedium2=0")
    assert lines[at + 1] == "OutputDefault1=0"
    assert lines[at + 2] == "Configuration1_Name1=OutputConfigurationParameter1"
    assert lines[at + 3] == "Configuration1_Item1=" + _gerber(groups).settings[0].item
    assert lines[at + 4] == "OutputType2=NC Drill"
    for i in range(1, 7):
        last = next(n for n, line in enumerate(lines) if line.startswith(f"OutputEnabled{i}_OutputMedium2="))
        assert lines[last + 1] == f"OutputDefault{i}=0"
    assert sum(line.startswith("OutputDefault") for line in lines) == 6
    assert sum(line.startswith("Configuration") for line in lines) == 2
    job = read_outjob(data)
    assert job.groups == groups and job.to_bytes() == data


def test_one_key_per_output() -> None:
    """Scenario "One key per output": against the writer of change c0087 a job without a Gerber output
    differs by one ``OutputDefault<i>=0`` line per output, after its last container key, and by nothing
    else: without those lines the text has the digest pinned from that writer."""
    data = write_outjob((_plain(),))
    lines = data.decode("ascii").split("\n")
    assert lines[lines.index("OutputEnabled1_OutputMedium1=1") + 1] == "OutputDefault1=0"
    assert lines[lines.index("OutputEnabled2_OutputMedium1=0") + 1] == "OutputDefault2=0"
    assert not any(line.startswith("Configuration") for line in lines)
    added = [line for line in lines if line.startswith("OutputDefault")]
    assert added == ["OutputDefault1=0", "OutputDefault2=0"]
    before = "\n".join(line for line in lines if not line.startswith("OutputDefault")).encode("ascii")
    assert hashlib.sha256(before).hexdigest() == C0087_PLAIN_SHA256
    job = read_outjob(data)
    assert job.groups == (_plain(),) and job.to_bytes() == data


def test_sample_differs_from_c0087_by_eight_lines() -> None:
    """Scenario "Only the job changes", for the committed sample: six ``OutputDefault<i>=0`` lines and the
    two configuration lines of the Gerber output, and without them the bytes of change c0087."""
    lines = write_outjob(from_preset(Preset(), name="blink", copper=TWO)).decode("ascii").split("\n")
    added = [line for line in lines if line.startswith(("OutputDefault", "Configuration"))]
    assert len(added) == 8 and [line.partition("=")[0] for line in added] == [
        "OutputDefault1",
        "Configuration1_Name1",
        "Configuration1_Item1",
        "OutputDefault2",
        "OutputDefault3",
        "OutputDefault4",
        "OutputDefault5",
        "OutputDefault6",
    ]
    before = "\n".join(line for line in lines if line not in added).encode("ascii")
    assert hashlib.sha256(before).hexdigest() == C0087_SAMPLE_SHA256


def test_sample_bytes() -> None:
    """The committed sample is the job of the default preset for ``blink``, a two-layer board."""
    data = write_outjob(from_preset(Preset(), name="blink", copper=TWO))
    if WRITE:
        SAMPLE.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE.write_bytes(data)
        pytest.skip("output job sample rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert SAMPLE.read_bytes() == data


def test_unmapped_options() -> None:
    """One option of a preset is mapped, the Gerber precision; every other one it sets is named, sorted."""
    assert outjob.MAPPED_OPTIONS == frozenset({"gerbers.precision"})
    assert unmapped(None) == () and unmapped(Preset()) == ()
    preset = read_preset(
        'schema = "fenolite.export-preset.v0"\n[drill]\nunits = "in"\n[gerbers]\nprecision = 5\nx2 = false\n'
        'layers = ["F.Cu"]\n'
    )
    assert unmapped(preset) == ("drill.units", "gerbers.layers", "gerbers.x2")
    with_preset = from_preset(preset, name="blink", copper=TWO)
    assert with_preset != from_preset(None, name="blink", copper=TWO)
    # the preset's layers do not choose the plotted layers
    assert outjob.plotted_layers(_gerber(with_preset).settings[0].item) == plot_layers(TWO)
    assert _without(with_preset, ()) == _without(from_preset(None, name="blink", copper=TWO), ())


def _partial(drop: str) -> tuple[OutputSetting, ...]:
    fields = [f"{name}={value}" for name, value in record_fields(_record().item) if name != drop]
    return (OutputSetting(1, outjob.SETTING_NAME, "|".join(fields)),)


def _reordered() -> tuple[OutputSetting, ...]:
    fields = [f"{name}={value}" for name, value in record_fields(_record().item)]
    fields[0], fields[1] = fields[1], fields[0]
    return (OutputSetting(1, outjob.SETTING_NAME, "|".join(fields)),)


@pytest.mark.parametrize(
    "settings",
    [
        (),
        (_record(), dataclasses.replace(_record(), index=2)),
        _partial("Plot.Set"),
        _partial("Sorted"),
        _partial("GerberUnit"),
        _reordered(),
        (OutputSetting(1, outjob.SETTING_NAME, _record().item + "|DocumentPath=x.PcbDoc"),),
        (OutputSetting(1, outjob.SETTING_NAME, _record().item.replace("=GerberView", "=a|b")),),
        (OutputSetting(1, outjob.SETTING_NAME, _record().item.replace("GerberView", "café")),),
        (OutputSetting(1, outjob.SETTING_NAME, ""),),
        (OutputSetting(1, outjob.SETTING_NAME, "Record=GerberView"),),
        (OutputSetting(2, outjob.SETTING_NAME, _record().item),),
        (OutputSetting(1, "Other", _record().item),),
    ],
    ids=[
        "none",
        "two",
        "no-plot-set",
        "one-copy-of-a-double",
        "no-unit",
        "out-of-order",
        "document-path",
        "bar-in-a-value",
        "not-ascii",
        "empty",
        "one-field",
        "index-2",
        "other-name",
    ],
)
def test_partial_record_is_refused(settings: tuple[OutputSetting, ...]) -> None:
    """Scenario "A partial record is refused": a Gerber output is written with the complete record or the
    job is not written at all."""
    groups = _without(from_preset(Preset(), name="blink", copper=TWO), settings)
    with pytest.raises(ValueError):
        write_outjob(groups)


def test_setting_on_another_kind_is_refused() -> None:
    """No other output kind carries a record: a setting on the NC drill output is refused."""
    (group,) = from_preset(Preset(), name="blink", copper=TWO)
    outputs = tuple(
        dataclasses.replace(o, settings=(_record(),)) if o.type == "NC Drill" else o for o in group.outputs
    )
    with pytest.raises(ValueError, match="only a Gerber output"):
        write_outjob((dataclasses.replace(group, outputs=outputs),))
    for output in group.outputs[1:]:
        assert output.settings == ()


@pytest.mark.parametrize(
    "group",
    [
        OutputGroup(1, "a\nb", "", "", (), ()),
        OutputGroup(1, "café", "", "", (), ()),
        OutputGroup(0, "", "", "", (), ()),
        OutputGroup(1, "", "", "", (OutputMedium(1, "a", "Publish"), OutputMedium(1, "b", "Publish")), ()),
        OutputGroup(1, "", "", "", (OutputMedium(1, "a", ""),), ()),
        OutputGroup(1, "", "", "", (), (JobOutput(1, "NC Drill", "", "", "", "", True, (2,)),)),
        OutputGroup(1, "", "", "", (), (JobOutput(1, "", "", "", "", "", True, ()),)),
        OutputGroup(
            1,
            "",
            "",
            "",
            (OutputMedium(1, "a", "Publish"), OutputMedium(2, "b", "Publish")),
            (JobOutput(1, "NC Drill", "", "", "", "", True, (2, 1)),),
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


def test_outline_reason() -> None:
    """The reason constant of ``result.outjob.gerber.outline``, as the spec gives it."""
    assert outjob.OUTLINE_REASON == (
        "the PCB document holds the board outline as the board shape and on no layer, and no public source "
        "gives the entry of the board shape among the plotted layers; turn the outline on in the Gerber "
        "setup in Altium"
    )


def test_evidence() -> None:
    assert outjob.EVIDENCE.level is Level.INFERRED
    assert set(outjob.EVIDENCE.hypotheses) == {
        "H-A-OUTJOB-GERBER-ACCEPT",
        "H-A-OUTJOB-GERBER-LAYERS",
        "H-A-OUTJOB-GERBER-RECORD",
        "H-A-OUTJOB-OPEN",
        "H-A-OUTJOB-READBACK",
        "H-A-OUTJOB-RUN-2",
    }
