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

from fenolite.backends.altium.read.outjob import read_outjob
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
