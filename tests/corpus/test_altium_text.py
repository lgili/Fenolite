# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Counts-only corpus check of the public Altium text files (capability altium-project-reader, "Altium
text corpus rows", change c0042).

Each row is read with the reader of its kind: the bytes must come back, every issue code must be one of
``TEXT_READ_CODES``, and the per-kind checks must hold. Messages name rows by id and give counts and key
names only, never a path, a header line or a value of a file. With ``FENOLITE_CENSUS_OUT`` set, the counts
of each row are written there (section ``altium_text``) for ``docs/evidence/altium-project-read.md``.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pytest
from _boards import census
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium import outjob as job_writer
from fenolite.backends.altium.read.outjob import OutJobFile, read_outjob, record_fields
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.rules import RULE_KIND_MAP, map_rules
from fenolite.backends.altium.read.stackup import read_stackup
from fenolite.backends.altium.read.textfile import TEXT_READ_CODES
from fenolite.core.errors import Issue

pytestmark = pytest.mark.needs_corpus
ITEMS = manifest_items("altium-text")
_ABSOLUTE = re.compile(r"^([A-Za-z]:|\\\\|/)")
OUTJOB_SECTIONS = ("OutputJobFile", "OutputGroup1", "PublishSettings", "GeneratedFilesSettings")
GROUP_KEYS = (
    "Name",
    "Description",
    "TargetOutputMedium",
    "VariantName",
    "VariantScope",
    "CurrentConfigurationName",
    "TargetPrinter",
    "PrinterOptions",
)
MEDIUM_TYPES = ("Printer", "Publish", "GeneratedFiles", "Multimedia")
OUTPUT_KEYS = (
    "OutputType",
    "OutputName",
    "OutputCategory",
    "OutputDocumentPath",
    "OutputVariantName",
    "OutputEnabled",
    "OutputDefault",
)


def _kind(item: CorpusItem) -> str:
    return item.id.split("-")[-2]


def _codes(issues: tuple[Issue, ...]) -> dict[str, int]:
    return dict(sorted(Counter(issue.code for issue in issues).items()))


def _check_codes(item: CorpusItem, issues: tuple[Issue, ...]) -> None:
    unknown = sorted({issue.code for issue in issues} - set(TEXT_READ_CODES))
    assert not unknown, f"{item.id}: codes outside TEXT_READ_CODES: {unknown}"
    wrong = sorted({i.code for i in issues if i.severity != TEXT_READ_CODES.get(i.code, i.severity)})
    assert not wrong, f"{item.id}: severities differ from the table for {wrong}"


def _prjpcb(item: CorpusItem, data: bytes) -> dict[str, Any]:
    project = read_project(data)
    assert project.to_bytes() == data, f"{item.id}: the bytes do not come back"
    _check_codes(item, project.issues)
    kinds = Counter(document.kind for document in project.documents)
    assert kinds["schematic"] + kinds["pcb"] >= 1, f"{item.id}: no schematic or PCB document"
    # The rows of project.md, "The project file as Altium saves it", that the label CORPUS-VERIFIED rests on.
    assert project.ini.sections[0].name == "Design", f"{item.id}: [Design] is not the first section"
    assert [key for key, _value in project.options.raw[:2]] == ["Version", "HierarchyMode"], item.id
    assert project.version == "1.0", item.id
    sections = project.ini.numbered("Document")
    assert sorted(n for n, _section in sections) == list(range(1, len(sections) + 1)), item.id
    for _n, section in sections:
        assert section.keys()[0] == "DocumentPath" and section.keys()[-1] == "DocumentUniqueId", item.id
    assert not any(_ABSOLUTE.match(d.path) for d in project.documents), f"{item.id}: an absolute path"
    assert kinds["other"] == 0, f"{item.id}: a document of an unknown kind"
    return {
        "encoding": project.ini.form.encoding,
        "bom": bool(project.ini.form.bom),
        "line_ends": sorted({repr(line.end) for line in project.ini.form.lines if line.end}),
        "sections": len(project.ini.sections),
        "design_keys": len(project.options.raw),
        "hierarchy_mode": project.options.hierarchy_mode,
        "documents": dict(sorted(kinds.items())),
        "generated": len(project.generated),
        "parameters": len(project.parameters),
        "parameters_named": sum(1 for p in project.parameters if p.name),
        "issues": _codes(project.issues),
    }


def _outjob(item: CorpusItem, data: bytes) -> dict[str, Any]:
    job = read_outjob(data)
    assert job.to_bytes() == data, f"{item.id}: the bytes do not come back"
    _check_codes(item, job.issues)
    assert job.groups, f"{item.id}: no output group"
    assert all(o.type for g in job.groups for o in g.outputs), f"{item.id}: an output without its type"
    # The rows of output-job.md that the label CORPUS-VERIFIED rests on.
    assert {line.end for line in job.ini.form.lines} == {b"\n"} and max(data) < 0x80, item.id
    assert data.endswith(b"\n\n") and job.version == "1.0", item.id
    assert {s.name for s in job.ini.sections} >= set(OUTJOB_SECTIONS), item.id
    for index, section in job.ini.numbered("OutputGroup"):
        group = next(g for g in job.groups if g.index == index)
        assert all(section.get(key) is not None for key in GROUP_KEYS), item.id
        assert all(m.type in MEDIUM_TYPES for m in group.media), item.id
        printers = [m.index for m in group.media if m.type == "Printer"]
        assert printers, item.id
        for j in printers:
            assert section.get(f"OutputMedium{j}_Printer") is not None, item.id
            assert section.get(f"OutputMedium{j}_PrinterOptions") is not None, item.id
        for output in group.outputs:
            assert all(section.get(f"{key}{output.index}") is not None for key in OUTPUT_KEYS), item.id
            for medium in group.media:
                assert section.get(f"OutputEnabled{output.index}_OutputMedium{medium.index}") is not None
        # c0087: per container, the values that are not 0 are the positions 1 to n, each once.
        for medium in group.media:
            keys = [f"OutputEnabled{output.index}_OutputMedium{medium.index}" for output in group.outputs]
            sent = sorted(int(value) for key in keys if (value := section.get(key) or "0") != "0")
            assert sent == list(range(1, len(sent) + 1)), f"{item.id}: container {medium.index}"
    # c0087: every section, the last one included, is followed by one empty line.
    texts = job.ini.form.texts()
    starts = [section.line - 1 for section in job.ini.sections]
    assert all(texts[start - 1] == "" for start in starts[1:]) and texts[-1] == "", item.id
    return {
        "encoding": job.ini.form.encoding,
        "sections": len(job.ini.sections),
        "groups": len(job.groups),
        "media": sum(len(g.media) for g in job.groups),
        "outputs": sum(len(g.outputs) for g in job.groups),
        "enabled_outputs": sum(1 for g in job.groups for o in g.outputs if o.enabled),
        "issues": _codes(job.issues),
    }


def _rules(item: CorpusItem, data: bytes) -> dict[str, Any]:
    rules = read_rule_file(data)
    assert rules.to_bytes() == data, f"{item.id}: the bytes do not come back"
    _check_codes(item, rules.issues)
    mapping = map_rules([r.fields for r in rules.records], origin=item.id, summary=rules.kind == "summary")
    _check_codes(item, mapping.issues)
    sources = set(mapping.sources)
    unmapped = [u.index for u in mapping.unmapped]
    assert len(unmapped) == len(set(unmapped)), f"{item.id}: a record is listed twice"
    assert not sources & set(unmapped), f"{item.id}: a record is both mapped and unmapped"
    assert sources | set(unmapped) == set(range(len(rules.records))), f"{item.id}: a record is dropped"
    key = "RuleKind" if rules.kind == "summary" else "RULEKIND"
    kinds = Counter(r.get(key) or "" for r in rules.records)
    return {
        "form": rules.kind,
        "encoding": rules.form.encoding,
        "records": len(rules.records),
        "kinds": dict(sorted(kinds.items())),
        "kinds_in_table": sorted(k for k in kinds if k in RULE_KIND_MAP),
        "mapped_records": len(sources),
        "rules": dict(sorted(Counter(rule.kind for rule in mapping.ruleset.rules).items())),
        "unmapped": dict(sorted(Counter(u.reason for u in mapping.unmapped).items())),
        "issues": _codes(rules.issues),
    }


def _stackup(item: CorpusItem, data: bytes) -> dict[str, Any]:
    stack = read_stackup(data)
    assert stack.to_bytes() == data, f"{item.id}: the bytes do not come back"
    _check_codes(item, stack.issues)
    copper = [e for e in stack.layers if e.kind == "copper" and e.thickness is not None]
    assert len(copper) >= 2, f"{item.id}: fewer than two copper entries with a thickness"
    return {
        "encoding": stack.form.encoding,
        "bom": bool(stack.form.bom),
        "fields": len(stack.record.fields),
        "copper": len(copper),
        "dielectric": sum(1 for e in stack.layers if e.kind == "dielectric"),
        "units": sorted({u for e in stack.record.fields for u in ("mil", "mm") if (e[1] or "").endswith(u)}),
        "issues": _codes(stack.issues),
    }


READERS = {"prjpcb": _prjpcb, "outjob": _outjob, "rules": _rules, "stackup": _stackup}


def test_twelve_rows() -> None:
    assert sorted(Counter(_kind(item) for item in ITEMS).items()) == [
        ("outjob", 3),
        ("prjpcb", 3),
        ("rules", 3),
        ("stackup", 3),
    ]


@pytest.mark.parametrize("item", ITEMS, ids=lambda item: item.id)
def test_public_text_rows(item: CorpusItem) -> None:
    data = require(item).read_bytes()
    counts = READERS[_kind(item)](item, data)
    census("altium_text", item.id, counts)


# --- the Gerber settings record (change c0138; output-job.md, "The Gerber settings record") --------------

JOBS = [item for item in ITEMS if _kind(item) == "outjob"]
GERBER_JOBS = ("altium-third-party-outjob-01", "altium-third-party-outjob-03")
"""The two public jobs that hold a Gerber output."""
OUTPUTS_PER_JOB = {
    "altium-third-party-outjob-01": 12,
    "altium-third-party-outjob-02": 3,
    "altium-third-party-outjob-03": 9,
}
_CONTAINER_KEY = re.compile(r"OutputEnabled([1-9][0-9]*)_OutputMedium[1-9][0-9]*")


def _jobs() -> dict[str, OutJobFile]:
    return {item.id: read_outjob(require(item).read_bytes()) for item in JOBS}


def _gerber_records(jobs: dict[str, OutJobFile]) -> dict[str, tuple[tuple[str, str], ...]]:
    """The fields of the record of the Gerber output of each public job that has one."""
    found: dict[str, tuple[tuple[str, str], ...]] = {}
    for ident, job in jobs.items():
        outputs = [o for g in job.groups for o in g.outputs if o.type == job_writer.GERBER_TYPE]
        if not outputs:
            continue
        assert len(outputs) == 1, f"{ident}: {len(outputs)} Gerber outputs"
        (output,) = outputs
        assert len(output.settings) == 1, f"{ident}: {len(output.settings)} settings on the Gerber output"
        (setting,) = output.settings
        assert (setting.index, setting.name) == (1, job_writer.SETTING_NAME), ident
        assert all(0x20 <= ord(ch) <= 0x7E for ch in setting.item), f"{ident}: the record is not ASCII"
        found[ident] = record_fields(setting.item)
    return found


def test_output_default() -> None:
    """Scenario "The key in the public jobs" (the ``CORPUS-VERIFIED`` row of ``OutputDefault<i>``): all 24
    outputs of the three public jobs hold the key with the value ``0``, directly after the last
    ``OutputEnabled<i>_OutputMedium<j>`` of the output; then ``PageOptions<i>`` or the first setting."""
    jobs = _jobs()
    assert sorted(jobs) == sorted(OUTPUTS_PER_JOB)
    following: Counter[str] = Counter()
    for ident, job in jobs.items():
        outputs = 0
        for index, section in job.ini.numbered("OutputGroup"):
            group = next(g for g in job.groups if g.index == index)
            keys = list(section.keys())
            for output in group.outputs:
                outputs += 1
                i = output.index
                where = f"{ident}: output {i}"
                assert keys.count(f"OutputDefault{i}") == 1, where
                assert section.get(f"OutputDefault{i}") == job_writer.OUTPUT_DEFAULT, where
                at = keys.index(f"OutputDefault{i}")
                last = max(
                    n
                    for n, key in enumerate(keys)
                    if (match := _CONTAINER_KEY.fullmatch(key)) and int(match.group(1)) == i
                )
                assert at == last + 1, f"{where}: OutputDefault is not directly after the last container key"
                following[re.sub(r"[0-9]+", "#", keys[at + 1]) if at + 1 < len(keys) else ""] += 1
        assert outputs == OUTPUTS_PER_JOB[ident], f"{ident}: {outputs} outputs"
    assert sum(OUTPUTS_PER_JOB.values()) == 24
    assert dict(following) == {"PageOptions#": 14, "Configuration#_Name#": 10}


def test_gerber_records() -> None:
    """``H-A-OUTJOB-GERBER-RECORD``: the two public jobs with a Gerber output hold one setting whose first
    44 fields have the names of ``GERBER_FIELDS`` in order; one job adds ``DocumentPath`` as a 45th field.
    The record stands after ``OutputDefault<i>``, and the layer sets have the recorded form."""
    jobs = _jobs()
    records = _gerber_records(jobs)
    assert tuple(sorted(records)) == GERBER_JOBS
    wanted = [field.name for field in job_writer.GERBER_FIELDS]
    assert len(wanted) == 44 and wanted == sorted(wanted)
    extra: dict[str, list[str]] = {}
    for ident, fields in records.items():
        names = [name for name, _value in fields]
        assert names[:44] == wanted, f"{ident}: the names of the first 44 fields differ from GERBER_FIELDS"
        extra[ident] = names[44:]
        values = dict(fields[:44])
        for index, field in enumerate(job_writer.GERBER_FIELDS[:-1]):
            if field.name == job_writer.GERBER_FIELDS[index + 1].name:
                assert fields[index][1] == fields[index + 1][1], f"{ident}: the two {field.name} differ"
        head = job_writer.LAYER_SET_HEAD
        assert values["Mirror.Set"] == head and values["AddToAllPlots.Set"] == head, ident
        entries = values["Plot.Set"].removeprefix(head)
        assert values["Plot.Set"].startswith(head) and re.fullmatch(r"(,[0-9]+~1)+", entries), ident
    assert extra == {GERBER_JOBS[0]: ["DocumentPath"], GERBER_JOBS[1]: []}
    plots = {ident: job_writer.plotted_layers(fields_item(fields)) for ident, fields in records.items()}
    assert [len(plots[ident]) for ident in GERBER_JOBS] == [22, 12]
    # the first ten entries are equal in both and are those of a four-layer board without planes
    ten = job_writer.plot_layers((1, 2, 3, 32))[:10]
    assert plots[GERBER_JOBS[0]][:10] == plots[GERBER_JOBS[1]][:10] == ten
    # Every entry is explained by the long-id rows of pcb-library.md (family, number): copper 0x0100,
    # mechanical 0x0102, the other layers 0x0103 (6 to 11 overlay, paste and solder; 13 Keep-Out Layer; 24
    # and 25 the pad masters). No internal plane (0x0101), and so no entry left for a board outline.
    rest = {ident: [(layer >> 16, layer & 0xFFFF) for layer in plots[ident][10:]] for ident in GERBER_JOBS}
    assert rest[GERBER_JOBS[0]] == [
        *((0x0102, n) for n in (1, 3, 5, 6, 13, 14, 15, 31, 32)),
        (0x0103, 13),
        (0x0103, 24),
        (0x0103, 25),
    ]
    assert rest[GERBER_JOBS[1]] == [(0x0102, 1), (0x0102, 2)]
    assert not any(layer >> 16 == 0x0101 for found in plots.values() for layer in found)
    for ident in GERBER_JOBS:
        job = jobs[ident]
        (index, section), *_rest = job.ini.numbered("OutputGroup")
        output = next(o for g in job.groups for o in g.outputs if o.type == job_writer.GERBER_TYPE)
        keys = list(section.keys())
        at = keys.index(f"OutputDefault{output.index}")
        assert keys[at + 1 : at + 3] == [
            f"Configuration{output.index}_Name1",
            f"Configuration{output.index}_Item1",
        ], ident
        assert output.document_path == "" and output.variant_name == "", ident
        assert index >= 1


def fields_item(fields: tuple[tuple[str, str], ...]) -> str:
    return "|".join(f"{name}={value}" for name, value in fields)


def test_gerber_constants() -> None:
    """Scenario "Constant fields equal the public jobs" and ``H-A-OUTJOB-GERBER-READBACK``: every field
    whose rule is ``constant`` holds in both public records the value Fenolite writes, at 31 positions; the
    13 other positions differ between the two records, and every written ``choice`` and unit value is the
    value of one of them. The written decimals without a preset are those of the metric record."""
    records = _gerber_records(_jobs())
    first, third = (records[ident][:44] for ident in GERBER_JOBS)
    written = record_fields(job_writer.gerber_record(job_writer.plot_layers((1, 2, 3, 32)), decimals=4))
    assert len(written) == 44
    equal = [n for n in range(44) if first[n][1] == third[n][1]]
    constant = [n for n, field in enumerate(job_writer.GERBER_FIELDS) if field.rule == "constant"]
    assert len(equal) == 31 and equal == constant
    for n in constant:
        field = job_writer.GERBER_FIELDS[n]
        assert first[n] == third[n] == written[n] == (field.name, field.value), f"position {n + 1}"
    differing = sorted({first[n][0] for n in range(44) if n not in equal})
    assert len(differing) == 9 and 44 - len(equal) == 13
    for n, field in enumerate(job_writer.GERBER_FIELDS):
        if field.rule in ("choice", "unit"):
            assert written[n][1] in (first[n][1], third[n][1]), f"position {n + 1}: a value of no public job"
    unit = {n: field for n, field in enumerate(job_writer.GERBER_FIELDS) if field.rule == "unit"}
    decimals = [n for n, field in enumerate(job_writer.GERBER_FIELDS) if field.rule == "decimals"]
    metric = first if first[next(iter(unit))][1] == job_writer.GERBER_UNIT else third
    assert all(metric[n][1] == job_writer.GERBER_UNIT for n in unit)
    assert all(metric[n][1] == str(job_writer.DEFAULT_DECIMALS) == written[n][1] for n in decimals)
    # what the public jobs show of the decimals: 4 beside Metric and 5 beside Imperial; 6 in neither
    seen = {(job[next(iter(unit))][1], job[decimals[0]][1]) for job in (first, third)}
    assert seen == {("Metric", "4"), ("Imperial", "5")}
    census(
        "altium_text", "gerber-record", {"fields": 44, "equal": len(equal), "differing_names": len(differing)}
    )
