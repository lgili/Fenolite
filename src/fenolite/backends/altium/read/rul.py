# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule files (``.RUL``) in both forms, read byte for byte (capability altium-project-reader, c0042).

The export form of the PCB rules editor holds one rule record per line, ended by a pilcrow sign; the
summary form written beside Gerber outputs holds a header line and short records without units
(``docs/formats/altium/rule-file.md``). ``read_rule_file`` interprets no value: ``rules.map_rules``
maps the records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.read.proptext import PropRecord, parse_fields
from fenolite.backends.altium.read.textfile import SUMMARY_HEADER, TextBytes, split_text, text_issue
from fenolite.core.errors import FormatError, Issue

RuleFileKind = Literal["export", "summary"]
END_MARKS = (b"\xc2\xb6", b"\xb6")
"""The end mark of an export record: the pilcrow sign in UTF-8, or the single byte of a one-byte code
page (only in a file that is not UTF-8)."""
RULE_KIND_KEY = "RULEKIND="


@dataclass(frozen=True, slots=True)
class RuleFile:
    """A rule file: its bytes (``form``), its kind, the header line of the summary form (``""`` for the
    export form), one record per rule line in file order, and the issues of reading it."""

    form: TextBytes
    kind: RuleFileKind
    header: str
    records: tuple[PropRecord, ...]
    issues: tuple[Issue, ...]

    def to_bytes(self) -> bytes:
        return self.form.to_bytes()


def _without_mark(raw: bytes, form: TextBytes) -> bytes:
    if raw.endswith(END_MARKS[0]):
        return raw[: -len(END_MARKS[0])]
    if form.encoding == "latin-1" and raw.endswith(END_MARKS[1]):
        return raw[: -len(END_MARKS[1])]
    return raw


def read_rule_file(data: bytes, *, file: str = "") -> RuleFile:
    """Read the rule file ``data`` in the export or the summary form; ``to_bytes()`` of the result equals
    ``data``. ``FormatError`` for data in neither form, a compound file or a NUL byte. Warning
    ``altium.rule.record-malformed`` for a line of an export file without a rule kind."""
    issues: list[Issue] = []
    form = split_text(data, file=file, issues=issues)
    numbered = [(number, line) for number, line in enumerate(form.lines, start=1) if line.raw]
    if form.lines and form.lines[0].raw.startswith(SUMMARY_HEADER):
        header = form.lines[0].text(form.encoding)
        summary = tuple(parse_fields(line.text(form.encoding)) for number, line in numbered if number > 1)
        return RuleFile(form, "summary", header, summary, tuple(issues))
    if not any(RULE_KIND_KEY.encode() in line.raw for _number, line in numbered):
        raise FormatError(
            "not a rule file: neither the summary header line nor a line with RULEKIND= was found",
            file=file,
        )
    records: list[PropRecord] = []
    for number, line in numbered:
        text = _without_mark(line.raw, form).decode(form.encoding, errors="replace")
        record = parse_fields(text)
        if record.get("RULEKIND") is None:
            issues.append(
                text_issue(
                    "altium.rule.record-malformed",
                    f"line {number} holds no rule kind; kept and listed as record {len(records)}",
                    f"{file}:{number}" if file else f"line {number}",
                )
            )
        records.append(record)
    return RuleFile(form, "export", "", tuple(records), tuple(issues))


__all__ = ["END_MARKS", "RuleFile", "RuleFileKind", "read_rule_file"]
