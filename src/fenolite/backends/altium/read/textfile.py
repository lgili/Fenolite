# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bytes of an Altium text file, kept byte for byte (capability altium-project-reader, change c0042).

The four text files of a project (project file, output job, rule file, stack-up file) are read from
their bytes: ``split_text`` keeps the byte-order mark and every line with its own line end, and
``TextBytes.to_bytes()`` joins the stored bytes, so a file that mixes line ends or holds bytes outside
UTF-8 comes back equal. The typed text is UTF-8 when the bytes allow it, else Latin-1, which maps every
byte (``docs/formats/altium/project.md``, "The project file as Altium saves it").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from fenolite.core.errors import FormatError, Issue, Severity

BOM = b"\xef\xbb\xbf"
COMPOUND_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
LINE_ENDS = (b"\r\n", b"\n", b"\r")
TextEncoding = Literal["utf-8", "latin-1"]
TextKind = Literal["prjpcb", "outjob", "rul-export", "rul-summary", "stackup", "compound", "unknown"]
TEXT_KINDS: tuple[TextKind, ...] = (
    "prjpcb",
    "outjob",
    "rul-export",
    "rul-summary",
    "stackup",
    "compound",
    "unknown",
)
SUMMARY_HEADER = b"DRC Rules Export File for PCB:"
STACKUP_START = b"|STACKUPVERSION="

TEXT_READ_CODES: dict[str, Severity] = {
    "altium.text.encoding-assumed": "warning",
    "altium.text.mixed-line-ends": "info",
    "altium.text.duplicate-key": "info",
    "altium.text.stray-line": "info",
    "altium.project.no-design-section": "warning",
    "altium.project.hierarchy-mode-unknown": "warning",
    "altium.project.document-kind-unknown": "info",
    "altium.project.document-missing": "warning",
    "altium.project.document-outside": "warning",
    "altium.project.companion-unreadable": "warning",
    "altium.outjob.output-incomplete": "warning",
    "altium.rule.record-malformed": "warning",
    "altium.rule.summary-form": "info",
    "altium.rule.unmapped": "info",
    "altium.stackup.unknown-form": "warning",
    "altium.stackup.length-unreadable": "warning",
}
"""Every issue code of the text readers with its severity. None is an error: malformed input raises
``FormatError`` instead."""


def text_issue(code: str, message: str, where: str = "") -> Issue:
    """An issue of ``TEXT_READ_CODES`` with the severity of its code."""
    return Issue(code, TEXT_READ_CODES[code], message, where=where)


@dataclass(frozen=True, slots=True)
class TextLine:
    """The bytes of one line without its line end, and the line end (``b""`` only on the last line)."""

    raw: bytes
    end: bytes

    def text(self, encoding: TextEncoding) -> str:
        """The line decoded; the raw bytes stay the source of ``TextBytes.to_bytes()``."""
        return self.raw.decode(encoding, errors="replace")


@dataclass(frozen=True, slots=True)
class TextBytes:
    """A text file as bytes: the byte-order mark (or ``b""``), the encoding of the typed text, the lines."""

    bom: bytes
    encoding: TextEncoding
    lines: tuple[TextLine, ...]

    def to_bytes(self) -> bytes:
        return self.bom + b"".join(line.raw + line.end for line in self.lines)

    def texts(self) -> tuple[str, ...]:
        """Every line decoded with ``encoding``."""
        return tuple(line.text(self.encoding) for line in self.lines)


def _where(file: str, line: int | None = None) -> str:
    if line is None:
        return file
    return f"{file}:{line}" if file else f"line {line}"


def refuse_binary(data: bytes, *, file: str = "") -> None:
    """``FormatError`` for data that is a compound file or holds a NUL byte: no text file does."""
    if data.startswith(COMPOUND_SIGNATURE):
        raise FormatError(
            "the file is a compound file (MS-CFB), not a text file; it is read by the compound reader "
            "(fenolite.backends.altium.read.cfb)",
            file=file,
            offset=0,
        )
    nul = data.find(b"\0")
    if nul >= 0:
        raise FormatError("a text file holds no NUL byte", file=file, offset=nul)


_LINE_END = re.compile(rb"\r\n|\n|\r")


def _split_lines(body: bytes) -> tuple[TextLine, ...]:
    lines: list[TextLine] = []
    start = 0
    for match in _LINE_END.finditer(body):
        lines.append(TextLine(body[start : match.start()], match.group()))
        start = match.end()
    if start < len(body):
        lines.append(TextLine(body[start:], b""))
    return tuple(lines)


def split_text(data: bytes, *, file: str = "", issues: list[Issue] | None = None) -> TextBytes:
    """Split ``data`` into a ``TextBytes`` whose ``to_bytes()`` is ``data``. ``FormatError`` naming ``file``
    for a compound file or a NUL byte. The warning ``altium.text.encoding-assumed`` and the info
    ``altium.text.mixed-line-ends`` are appended to ``issues`` when given."""
    refuse_binary(data, file=file)
    bom = BOM if data.startswith(BOM) else b""
    body = data[len(bom) :]
    found: list[Issue] = []
    encoding: TextEncoding = "utf-8"
    if not bom:
        try:
            body.decode("utf-8")
        except UnicodeDecodeError as error:
            encoding = "latin-1"
            found.append(
                text_issue(
                    "altium.text.encoding-assumed",
                    f"no byte-order mark and the bytes are not UTF-8 (first at byte {error.start}): "
                    "the text is read as Latin-1 and the bytes are kept",
                    _where(file),
                )
            )
    lines = _split_lines(body)
    ends = {line.end for line in lines if line.end}
    if len(ends) > 1:
        names = ", ".join(sorted({b"\r\n": "CR LF", b"\n": "LF", b"\r": "CR"}[end] for end in ends))
        message = f"the file mixes line ends ({names}); every line end is kept"
        found.append(text_issue("altium.text.mixed-line-ends", message, _where(file)))
    if issues is not None:
        issues.extend(found)
    return TextBytes(bom, encoding, lines)


_INI_DOCUMENT = re.compile(rb"^\[Document\d+\]$")


def text_kind(data: bytes, *, name: str = "") -> TextKind:
    """The kind of a text file of a project, from its content first and the extension of ``name``
    second: ``compound`` for the compound-file signature, ``stackup`` for a property text that starts
    with ``|STACKUPVERSION=``, ``rul-summary`` for a first line that starts with
    ``DRC Rules Export File for PCB:``, ``outjob`` for a section ``[OutputJobFile]``, ``prjpcb`` for a
    section ``[Design]`` or ``[Document<n>]``, ``rul-export`` for a line holding ``RULEKIND=``; else the
    extension (``.PrjPcb``, ``.OutJob``, ``.stackup``, without case), else ``unknown``. A ``.RUL`` file
    whose content shows neither form is ``unknown``."""
    if data.startswith(COMPOUND_SIGNATURE):
        return "compound"
    body = data[len(BOM) :] if data.startswith(BOM) else data
    if body.startswith(STACKUP_START):
        return "stackup"
    if body.startswith(SUMMARY_HEADER):
        return "rul-summary"
    lines = [line.raw for line in _split_lines(body)]
    if b"[OutputJobFile]" in lines:
        return "outjob"
    if b"[Design]" in lines or any(_INI_DOCUMENT.match(line) for line in lines):
        return "prjpcb"
    if any(b"RULEKIND=" in line for line in lines):
        return "rul-export"
    suffix = PurePosixPath(name.replace("\\", "/")).suffix.lower()
    by_suffix: dict[str, TextKind] = {".prjpcb": "prjpcb", ".outjob": "outjob", ".stackup": "stackup"}
    return by_suffix.get(suffix, "unknown")


__all__ = [
    "BOM",
    "COMPOUND_SIGNATURE",
    "LINE_ENDS",
    "TEXT_KINDS",
    "TEXT_READ_CODES",
    "TextBytes",
    "TextEncoding",
    "TextKind",
    "TextLine",
    "refuse_binary",
    "split_text",
    "text_issue",
    "text_kind",
]
