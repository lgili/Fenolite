# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The minimal PCB project file (capability altium-schematic-writer, "Project file").

Facts: ``docs/formats/altium/project.md``. The file lists the schematic beside it, by its bare file name,
then the module sheets of a hierarchical project (change c0037), then the PCB document (change c0035,
``H-A-PCB-PRJ``), the libraries the build writes (change c0034, ``H-A-SCHLIB-PRJ``) and the harness
definition files (change c0037, ``H-A-SCH-HIER-PRJ``); Altium takes defaults for every other key
(``H-A-PRJ-OPEN``). The schematic documents come first and together: with this minimal file Altium
Designer took only the first module sheet into the hierarchy when the PCB document and the libraries
stood between the top sheet and the module sheets (``H-A-SCH-HIER-ORDER``).

Change c0048 adds the class generation options ("Class generation" of the fact page): three keys in the
section of every schematic document of a project with module sheets or a PCB document, so that Altium
derives a component class per sheet and no room, and the section ``[PrjClassGen]`` for a design with a net
class, so that
Altium takes the net classes from the directives of the schematic (``H-A-ECO-PRJ-KEYS``, ``H-A-ECO-ROOMS``).

Change c0166 gives projects with harness definitions explicit net-label naming priority, avoiding
additional names synthesized from harness sheet entries; projects without harnesses keep their bytes.

Change c0479 carries the settings of a converted or imported source project (``carried_settings``) and
merges them into the written file (``write_prjpcb(carried=...)``).

Change c0483 keeps the source project's layout: its document list (``documents_text``, carried beside the
settings), the documents Fenolite does not model (``carried_kind``, their bytes under ``CARRIED_FOLDER`` of
a KiCad or Python output) and the folders of every document (``laid_out``).
"""

# evidence: see project

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from fenolite.backends.altium.ascii import LINE_END, text_problem
from fenolite.backends.altium.cfb import name_key
from fenolite.backends.altium.read.ini import parse_ini

VERSION = "1.0"
SHEET_CLASS_KEYS: tuple[tuple[str, str], ...] = (
    ("ClassGenCCAutoEnabled", "1"),
    ("ClassGenCCAutoRoomEnabled", "0"),
    ("ClassGenNCAutoScope", "None"),
)
"""The class options of one schematic document of a project with module sheets or a PCB document (change
c0048): a component class for the sheet, no room, no net class of the sheet's nets."""
CLASS_SECTION = "PrjClassGen"
CLASS_GENERATION: tuple[tuple[str, str], ...] = (
    ("CompClassManualEnabled", "0"),
    ("CompClassManualRoomEnabled", "0"),
    ("NetClassAutoBusEnabled", "1"),
    ("NetClassAutoCompEnabled", "0"),
    ("NetClassAutoNamedHarnessEnabled", "0"),
    ("NetClassManualEnabled", "1"),
    ("NetClassSeparateForBusSections", "0"),
)
"""The keys of ``[PrjClassGen]`` with the values of the public saved projects (change c0048):
``NetClassManualEnabled=1`` is the option "Generate Net Classes" for user-defined classes."""


UTF8_BOM = b"\xef\xbb\xbf"
"""The byte-order mark that Altium Designer writes before a saved project file (``project.md``)."""


def _file_name(name: str, what: str) -> str:
    # a name outside 7-bit ASCII (a library a converted source names) puts the file in UTF-8 (change c0470)
    problem = text_problem(name, form="binary", read=True)
    if problem is not None or "/" in name or "\\" in name:
        raise ValueError(f"the {what} file name {name!r} cannot be written: {problem or 'a path'}")
    return name


CHANNEL_KEYS: tuple[tuple[str, str], ...] = (
    ("ChannelRoomNamingStyle", "0"),
    ("ChannelDesignatorFormatString", "$Component_$RoomName"),
    ("ChannelRoomLevelSeperator", "_"),
)
"""The designator format of a multichannel design, as the project file spells it (``connectivity.md``,
"Channels", S-0452): a component of a channel is named ``<designator>_<designator of its sheet symbol>``."""


def write_prjpcb(
    *,
    schematic: str,
    pcb: str | None = None,
    libraries: Sequence[str] = (),
    sheets: Sequence[str] = (),
    harnesses: Sequence[str] = (),
    net_classes: bool = False,
    outjob: str | None = None,
    draftsman: str | None = None,
    parameters: Sequence[tuple[str, str]] = (),
    channels: bool = False,
    carried: str = "",
) -> bytes:
    """``[Design]``, ``Version=1.0``, an empty line, ``[Document1]`` and ``DocumentPath=<schematic>``; then,
    each after an empty line as ``[Document<i>]`` and ``DocumentPath=<file>``, numbered from 2: each module
    sheet of ``sheets`` in the order given (change c0037), the PCB document ``pcb`` (change c0035), each
    library (``.SchLib`` and ``.PcbLib`` alike) in the MS-CFB order of the names, and each harness
    definition file of ``harnesses`` in the MS-CFB order of the names. Every schematic document so precedes
    every other document, the top sheet first (``H-A-SCH-HIER-ORDER``); without module sheets the bytes
    are those of changes c0032 to c0035. Each line ends with CR LF, in 7-bit ASCII without a byte-order
    mark. No key names the top sheet or the net scope (``H-A-SCH-HIER-PRJ``, ``H-A-SCH-HIER-COMPILE``).

    Change c0048: with ``sheets`` not empty or with a PCB document, the section of every schematic
    document, the single or top sheet and each module sheet, holds the three lines of ``SHEET_CLASS_KEYS``
    after ``DocumentPath``; with ``net_classes`` true the file ends with an empty line, ``[PrjClassGen]``
    and the seven lines of ``CLASS_GENERATION``. Without module sheets, PCB document and net class the
    bytes do not change.

    Change c0087: the output job ``outjob`` is listed after the PCB document and before the libraries,
    with ``DocumentPath`` alone; without one the bytes do not change.

    Change c0470: with ``channels`` (a sheet written once for several sheet symbols) ``[Design]`` holds the
    three ``CHANNEL_KEYS``, which name the components of a channel ``<designator>_<sheet symbol>``."""
    with_keys = bool(sheets) or pcb is not None
    sheet_keys = [f"{key}={value}" for key, value in SHEET_CLASS_KEYS] if with_keys else []
    lines = ["[Design]", f"Version={VERSION}"]
    if channels:
        lines += [f"{key}={value}" for key, value in CHANNEL_KEYS]
    if harnesses:
        # c0166: use the explicit net labels rather than extra SPI.CS-style
        # names synthesized from harness ports and sheet entries.
        lines += ["AllowPortNetNames=0", "AllowSheetEntryNetNames=0"]
    lines += [
        "",
        "[Document1]",
        f"DocumentPath={_file_name(schematic, 'schematic')}",
        *sheet_keys,
    ]
    schematics = [_file_name(sheet, "sheet") for sheet in sheets]
    documents = [_file_name(pcb, "PCB document")] if pcb is not None else []
    if outjob is not None:
        documents.append(_file_name(outjob, "output job"))
    if draftsman is not None:
        documents.append(_file_name(draftsman, "Draftsman document"))
    documents += [_file_name(library, "library") for library in sorted(libraries, key=name_key)]
    documents += [_file_name(harness, "harness") for harness in sorted(harnesses, key=name_key)]
    for index, document in enumerate([*schematics, *documents], start=2):
        lines += ["", f"[Document{index}]", f"DocumentPath={document}"]
        if index - 2 < len(schematics):
            lines += sheet_keys
    if net_classes:
        lines += ["", f"[{CLASS_SECTION}]", *(f"{key}={value}" for key, value in CLASS_GENERATION)]
    for index, (name, value) in enumerate(parameters, start=1):
        for text in (name, value):
            if text_problem(text) is not None or "\r" in text or "\n" in text:
                raise ValueError("project parameters must be one-line 7-bit text")
        if not name or "=" in name:
            raise ValueError("project parameter names must be non-empty and contain no equals sign")
        lines += ["", f"[Parameter{index}]", f"Name={name}", f"Value={value}"]
    if carried:
        lines = _merged(lines, carried)
    if all(line.isascii() for line in lines):
        return b"".join(line.encode("ascii") + LINE_END for line in lines)
    return UTF8_BOM + b"".join(line.encode("utf-8") + LINE_END for line in lines)


_NOT_CARRIED = re.compile(r"(Generated)?Document[1-9][0-9]*")
"""The sections a written project lists itself: its documents."""


def carried_settings(data: bytes, *, file: str = "") -> str:
    """The settings of the source project ``data`` that a written project carries (change c0479): every
    section in file order but ``Document<n>`` and ``GeneratedDocument<n>``, and ``[Design]`` without
    ``Version``, as INI text with ``\\n`` line ends; ``""`` when nothing is left."""
    lines: list[str] = []
    for section in parse_ini(data, file=file).sections:
        if not section.name or _NOT_CARRIED.fullmatch(section.name):
            continue
        entries = [e for e in section.entries if not (section.name == "Design" and e.key == "Version")]
        if section.name == "Design" and not entries:
            continue
        lines += [f"[{section.name}]", *(f"{e.key}={e.value}" for e in entries)]
    return "".join(f"{line}\n" for line in lines)


_VARIATION = re.compile(r"Variation[1-9][0-9]*")


def retarget_variants(carried: str, paths: Mapping[str, str]) -> str:
    """``carried`` with the ``UniqueId`` of each ``Variation<n>`` of a ``[ProjectVariant<n>]`` set to the
    unique id path that ``paths`` gives its ``Designator``: a rebuilt project gives its components new
    unique ids, which the variant must name (change c0479). A designator ``paths`` lacks keeps its id."""
    out: list[str] = []
    variant = False
    for line in carried.splitlines():
        if line.startswith("[") and line.endswith("]"):
            variant = line[1:-1].rstrip("0123456789") == "ProjectVariant"
        key, sep, value = line.partition("=")
        if variant and sep and _VARIATION.fullmatch(key):
            fields = [field.partition("=") for field in value.split("|")]
            designator = next((v for k, _, v in fields if k == "Designator"), "")
            if designator in paths:
                value = "|".join(f"{k}{s}{paths[designator] if k == 'UniqueId' else v}" for k, s, v in fields)
        out.append(f"{key}{sep}{value}")
    return "".join(f"{line}\n" for line in out)


def _sections(lines: Sequence[str]) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            found.append((line[1:-1], []))
        elif line and found:
            found[-1][1].append(line)
    return found


def _family(section: str) -> str:
    return section.rstrip("0123456789")


def _merged(lines: Sequence[str], carried: str) -> list[str]:
    """The written ``lines`` with the ``carried`` settings (change c0479): a carried ``[Design]`` key replaces
    the written one in place and the others follow it; the carried sections of a family that the file writes
    (``Parameter``, ``PrjClassGen``) take the place of its written ones; the rest come last, in carried
    order."""
    held = _sections(carried.splitlines())
    design: dict[str, str] = {}
    for name, entries in held:
        if name == "Design":
            design.update((key, value) for key, _, value in (entry.partition("=") for entry in entries))
    families: dict[str, list[tuple[str, list[str]]]] = {}
    for name, entries in held:
        if name != "Design":
            families.setdefault(_family(name), []).append((name, entries))
    sections: list[tuple[str, list[str]]] = []
    replaced: set[str] = set()
    for name, entries in _sections(lines):
        if name == "Design":
            keys = [entry.partition("=")[0] for entry in entries]
            entries = [
                f"{key}={design[key]}" if key in design else e for key, e in zip(keys, entries, strict=True)
            ]
            sections.append((name, entries + [f"{k}={v}" for k, v in design.items() if k not in keys]))
        elif _family(name) in families:
            replaced.add(_family(name))
            sections += families.pop(_family(name))  # once, where the family's first written section was
        elif _family(name) not in replaced:
            sections.append((name, entries))
    sections += [section for found in families.values() for section in found]
    out: list[str] = []
    for name, entries in sections:
        out += [*([""] if out else []), f"[{name}]", *entries]
    return out


CARRIED_FOLDER = "altium-carried"
"""The folder of a KiCad or Python output that holds the bytes of the source's documents that Fenolite does
not model, each at its project path (change c0483)."""
STRUCTURE_SUFFIX = ".prjpcbstructure"
_MODELLED = (".schdoc", ".schlib", ".pcblib")


def document_path(path: str) -> str | None:
    """The project path ``path`` (``\\`` or ``/`` between folders) with ``/``, or ``None`` when it would leave
    the project folder: absolute, a drive, an empty, ``.`` or ``..`` part (change c0483)."""
    parts = path.replace("\\", "/").split("/")
    if not path or ":" in path or any(part in ("", ".", "..") for part in parts):
        return None
    return "/".join(parts)


def documents_text(paths: Sequence[str], sheets: Mapping[str, str]) -> str:
    """The source's document list as the root sheet's carrier holds it (change c0483): one line per project
    path in source order, a tab, and the key of the drawn sheet the document is (``sheets``), else ``""``."""
    return "".join(f"{path}\t{sheets.get(path, '')}\n" for path in paths)


def documents_of(text: str) -> list[tuple[str, str]]:
    """``(path, sheet key)`` of each line of ``documents_text``; a path that leaves the folder is left out."""
    found: list[tuple[str, str]] = []
    for line in text.splitlines():
        path, _, key = line.partition("\t")
        if (posix := document_path(path)) is not None:
            found.append((posix, key))
    return found


def carried_kind(paths: Sequence[str]) -> list[str]:
    """The ``paths`` (in order) whose bytes a conversion carries: every document but the schematic sheets,
    the libraries and the first PCB document, which Fenolite writes itself (change c0483)."""
    boards = [p for p in paths if p.lower().endswith(".pcbdoc")]
    return [p for p in paths if not p.lower().endswith(_MODELLED) and p not in boards[:1]]


def laid_out(
    files: Mapping[str, bytes],
    documents: Sequence[tuple[str, str]],
    carried: Mapping[str, bytes],
    *,
    name: str,
) -> dict[str, bytes]:
    """The written ``files`` (bare names) in the source's layout (change c0483): each written document that
    the source lists by its name (without case) moves to the source's path, each carried document the source
    lists is added at its path, the written ``<name>.PcbDoc`` that the source does not name takes the place
    and folder of the source's first PCB document, and ``<name>.PrjPcb`` lists them in the source's order,
    then the written documents the source lacks in written order. A carried ``.PrjPcbStructure`` becomes
    ``<name>.PrjPcbStructure``. Without ``documents`` the files are returned as they are."""
    project = f"{name}.PrjPcb"
    out = dict(files)
    if not documents or project not in out:
        return out
    loose = {file.casefold(): file for file in files if "/" not in file and file != project}
    board = next((path for path, _ in documents if path.lower().endswith(".pcbdoc")), None)
    listed: list[tuple[str, str]] = []  # (source path, written name or "")
    for path, _ in documents:
        folder, _, base = path.rpartition("/")
        if base.lower().endswith(STRUCTURE_SUFFIX):
            if path in carried:
                out[f"{name}.PrjPcbStructure"] = carried[path]
            continue
        written = loose.pop(base.casefold(), None)
        if written is None and path == board:  # the written board in the place of the source's first
            written = loose.pop(f"{name}.PcbDoc".casefold(), None)
            path = f"{folder}/{written}" if folder and written else path
        if written is not None:
            out[path] = out.pop(written)
        elif path in carried and path not in out:
            out[path] = carried[path]
        else:
            continue
        listed.append((path, written or ""))
    out[project] = relisted(out[project], listed)
    return out


def relisted(data: bytes, listed: Sequence[tuple[str, str]]) -> bytes:
    """The project file ``data`` with its ``Document<n>`` sections in the order of ``listed`` (each source
    path with the section of its written name, else ``DocumentPath`` alone), then its other documents,
    renumbered from 1 where the first document section stood (change c0483)."""
    text = data.removeprefix(UTF8_BOM).decode("utf-8")
    sections = _sections(text.split("\r\n"))
    own = {
        next((e.partition("=")[2] for e in entries if e.startswith("DocumentPath=")), ""): entries
        for name, entries in sections
        if _family(name) == "Document"
    }
    ordered: list[list[str]] = []
    for path, written in listed:
        entries = own.pop(written, [])
        rest = [e for e in entries if not e.startswith("DocumentPath=")]
        windows = path.replace("/", "\\")
        ordered.append([f"DocumentPath={windows}", *rest])
    ordered += own.values()
    lines: list[str] = []
    placed = False
    for name, entries in sections:
        if _family(name) == "Document":
            if not placed:
                for index, held in enumerate(ordered, start=1):
                    lines += [*([""] if lines else []), f"[Document{index}]", *held]
                placed = True
            continue
        lines += [*([""] if lines else []), f"[{name}]", *entries]
    if all(line.isascii() for line in lines):
        return b"".join(line.encode("ascii") + LINE_END for line in lines)
    return UTF8_BOM + b"".join(line.encode("utf-8") + LINE_END for line in lines)


__all__ = [
    "CARRIED_FOLDER",
    "CHANNEL_KEYS",
    "CLASS_GENERATION",
    "CLASS_SECTION",
    "SHEET_CLASS_KEYS",
    "VERSION",
    "carried_kind",
    "carried_settings",
    "document_path",
    "documents_of",
    "documents_text",
    "laid_out",
    "relisted",
    "retarget_variants",
    "write_prjpcb",
]
