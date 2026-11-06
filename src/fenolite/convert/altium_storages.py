# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Storages of an Altium PCB document that no model entity holds, through a conversion to KiCad and back
(change c0450; ``pcb-records.md``, "Storages through KiCad").

A conversion to KiCad copies each carried storage of the source document to a board property
``Fenolite.Altium.<storage>`` with ``backends.kicad.boardcarrier`` (change c0434), whose bytes are the
length of the ``Header`` stream (32-bit), that stream and the ``Data`` stream. KiCad keeps a board property
on a save (S-2092). A conversion back reads them with ``boardcarrier.carried`` and writes each storage again
(``pcbdoc.PcbDocSpec.kept_storages``).

The classes of ``Classes6`` that no net class gives travel as ``Classes6.Kept``: the records of every kind
but ``KIND=0`` that are no super class (change c0461; c0450 carried ``KIND=1`` alone, as
``Classes6.Component``, which a conversion back still reads). So do the ``SignalClasses`` records that are no
super class (``SignalClasses.Kept``), the ``PINPAIR`` keys of ``Board6`` that define the xSignals they name
(``Board6.PinPairs``) and ``DifferentialPairs6``. A conversion back writes them as they were, but a
differential pair whose nets the written document does not hold (``fitted``). Storages that name
primitives by index (``PrimitiveGuids``, the saved violations) are not carried: the round trip renumbers the
primitives. Each one that holds a record is counted lost. Neither is ``BoardRegions`` (change c0459): it
holds the board's layer stack region in the source's frame with the id of the source's stack, which the round
trip moves and writes again; a copy left Altium with a board region beside the board, so the polygons poured
nothing. Nor is ``CustomMaskShapes``, which no public row fills, so whether it holds coordinates is not known.
Each is counted lost when it holds data.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.kicad.boardcarrier import PREFIX
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-STORAGE", "H-A-CONV-BOARD6"))
"""The claim of the carried storages: written back byte for byte, they open in Altium as in the source
(``docs/hypotheses.md``; settled by the kit request of c0450 task 4.2)."""
CARRIED: tuple[str, ...] = ("EmbeddedFonts6", "UnionNames")
"""The storages copied whole."""
FRAME_BOUND_REASON = (
    "the storage holds the source's board regions in its frame and names its layer stack by id, which the "
    "round trip moves and writes again; Altium makes it again"
)
UNKNOWN_FRAME_REASON = (
    "the storage may hold geometry in the source's frame, which the round trip moves, and no public source "
    "shows what it holds; it is not copied"
)
SMART_UNION_REASON = (
    "the storage defines via stitching unions with placements in the source's frame, which the round trip "
    "moves; the stitching vias stay members of their union"
)
FRAME_BOUND: Mapping[str, str] = {
    "BoardRegions": FRAME_BOUND_REASON,
    "CustomMaskShapes": UNKNOWN_FRAME_REASON,
    "SmartUnions": SMART_UNION_REASON,
}
"""The storages that hold, or may hold, the source's geometry in its frame (change c0459), each with the
reason it is counted lost: the round trip moves the origin and writes its own layer stack, so a copy of
``BoardRegions`` placed the board region beside the board, and ``CustomMaskShapes`` holds data in no public
row (S-2181), so a copy would carry bytes nobody checked. ``SmartUnions`` (change c0460) defines via
stitching with ``PLACEHOLDERX`` and ``PLACEHOLDERY`` in the source's frame (S-2190)."""
CLASSES = "Classes6"
KEPT_CLASSES = "Classes6.Kept"
"""The carrier of the classes of ``Classes6`` that are no net class and no super class (change c0461)."""
COMPONENT_CLASSES = "Classes6.Component"
"""The carrier of c0450, its component classes alone: read back as ``KEPT_CLASSES``."""
SIGNAL_CLASSES = "SignalClasses"
KEPT_SIGNAL_CLASSES = "SignalClasses.Kept"
"""The carrier of the xSignal classes of ``SignalClasses`` that are no super class (change c0461)."""
PIN_PAIRS = "Board6.PinPairs"
"""The carrier of the xSignals of ``Board6``: its ``Header`` the count, its ``Data`` the ``PINPAIR`` keys as
``|KEY=value`` text (change c0461)."""
DIFFERENTIAL_PAIRS = "DifferentialPairs6"
"""Carried whole (change c0461): its records name their nets by name."""
SETTINGS = "Board6.Settings"
"""The carrier of the source's ``Board6`` settings (change c0464, ``board_settings``)."""
KEPT_CARRIERS: tuple[str, ...] = (KEPT_CLASSES, KEPT_SIGNAL_CLASSES, PIN_PAIRS, SETTINGS)
"""The carriers that hold part of a storage (change c0461)."""
KIND = "altium-storage"
"""The report kind of a storage."""
INDEX_BOUND_REASON = (
    "the storage names primitives by their index, which the round trip renumbers; Altium makes it again"
)
_INDEX_BOUND = re.compile(r"PrimitiveGuids|WaivedViolations|T[A-Za-z]+Violation")


@dataclass(frozen=True, slots=True)
class Storage:
    """One storage: its ``Header`` and ``Data`` streams."""

    header: bytes
    data: bytes


def packed(storage: Storage) -> bytes:
    """The carried bytes of ``storage``: the length of its ``Header`` stream (32-bit), that stream and its
    ``Data`` stream (``boardcarrier.with_carried`` packs them)."""
    return struct.pack("<I", len(storage.header)) + storage.header + storage.data


def unpacked(packed: bytes) -> Storage | None:
    """The storage of carried bytes, or ``None`` when they are not bytes ``packed`` gives."""
    if len(packed) < 4:
        return None
    (length,) = struct.unpack_from("<I", packed)
    if length > len(packed) - 4:
        return None
    return Storage(packed[4 : 4 + length], packed[4 + length :])


def records(data: bytes) -> list[bytes]:
    """The length-prefixed records of a property storage's ``Data`` stream, each with its 32-bit length."""
    found: list[bytes] = []
    at = 0
    while at + 4 <= len(data):
        (length,) = struct.unpack_from("<I", data, at)
        found.append(data[at : at + 4 + length])
        at += 4 + length
    return found


def fields(record: bytes) -> dict[str, str]:
    """The ``|KEY=value`` fields of one property record (upper-case keys)."""
    text = record[4:].rstrip(b"\x00").decode("latin-1")
    found: dict[str, str] = {}
    for part in text.split("|"):
        key, sep, value = part.partition("=")
        if sep:
            found[key.strip().upper()] = value
    return found


def _super(record: bytes) -> bool:
    return fields(record).get("SUPERCLASS", "FALSE").upper() == "TRUE"


def kept_classes(data: bytes) -> list[bytes]:
    """The records of ``Classes6`` that are no net class (``KIND=0``, which the model holds) and no super
    class (change c0461)."""
    return [record for record in records(data) if fields(record).get("KIND") != "0" and not _super(record)]


def component_classes(data: bytes) -> list[bytes]:
    """The records of ``Classes6`` that are component classes and no super class."""
    return [record for record in kept_classes(data) if fields(record).get("KIND") == "1"]


PIN_PAIR_KEY = re.compile(r"PINPAIR(?:NAME|COLOR|OVERRIDECOLORFORDRAW|PINS)\d+|PINPAIRCOUNT")


def pin_pair_fields(board: bytes) -> list[tuple[str, str]]:
    """The ``PINPAIRCOUNT`` and ``PINPAIR…<k>`` keys of the ``Board6`` stream ``board``, in order (change
    c0461; ``pcb-records.md``, "Storages through KiCad"): the xSignals of the document."""
    text = board[4:].rstrip(b"\x00").decode("latin-1")
    found: list[tuple[str, str]] = []
    for line in text.split("\r"):
        for part in line.split("|"):
            key, sep, value = part.partition("=")
            if sep and PIN_PAIR_KEY.fullmatch(key.strip().upper()):
                found.append((key.strip().upper(), value))
    return found


def pin_pairs(data: bytes) -> list[dict[str, str]]:
    """The xSignals of carried ``Board6.PinPairs`` text, by index: ``NAME``, ``COLOR``,
    ``OVERRIDECOLORFORDRAW`` and ``PINS`` of each, in index order."""
    found: dict[int, dict[str, str]] = {}
    for part in data.decode("latin-1").split("|"):
        key, sep, value = part.partition("=")
        match = re.fullmatch(r"PINPAIR([A-Z]+)(\d+)", key) if sep else None
        if match is not None:
            found.setdefault(int(match.group(2)), {})[match.group(1)] = value
    return [found[index] for index in sorted(found)]


def pin_pair_text(pairs: list[dict[str, str]]) -> bytes:
    """The ``Board6.PinPairs`` text of ``pairs``, numbered from 0: ``PINPAIRCOUNT``, then the four keys of
    each pair."""
    parts = [f"|PINPAIRCOUNT={len(pairs)}"]
    for index, pair in enumerate(pairs):
        parts += [f"|PINPAIR{key}{index}={pair[key]}" for key in _PAIR_KEYS if key in pair]
    return "".join(parts).encode("latin-1")


_PAIR_KEYS = ("NAME", "COLOR", "OVERRIDECOLORFORDRAW", "PINS")
_MECHANICAL_NAME = re.compile(r"LAYER(5[7-9]|6[0-9]|7[0-2])NAME")


def board_settings(board: bytes) -> list[tuple[str, str]]:
    """The settings of the ``Board6`` stream ``board`` (change c0464): the keys the record holds once and
    ``docboard.OWNED_KEY`` does not name, in order, each run of them opened by ``(docboard.ANCHOR, key)``
    with the key before the run; then the names of mechanical layers 1 to 16 (``LAYER57NAME`` …
    ``LAYER72NAME``). A field ``docboard.format_line`` refuses is left out."""
    from fenolite.backends.altium.docboard import ANCHOR, OWNED_KEY, writable_field

    text = board[4:].rstrip(b"\x00").decode("latin-1")
    order: list[tuple[str, str]] = []
    for line in text.split("\r"):
        for part in line.split("|"):
            key, sep, value = part.partition("=")
            if sep:
                order.append((key.strip().upper(), value))
    counts: dict[str, int] = {}
    for key, _ in order:
        counts[key] = counts.get(key, 0) + 1
    found: list[tuple[str, str]] = []
    names: list[tuple[str, str]] = []
    before: str | None = None
    open_run = False
    for key, value in order:
        kept = counts[key] == 1 and not OWNED_KEY.fullmatch(key) and writable_field(key, value)
        if kept:
            if not open_run and before is not None:
                found.append((ANCHOR, before))
            found.append((key, value))
        elif _MECHANICAL_NAME.fullmatch(key) and counts[key] == 1 and writable_field(key, value):
            names.append((key, value))
        open_run = kept
        before = key
    return found + names


def settings_text(settings: list[tuple[str, str]]) -> bytes:
    """The ``Board6.Settings`` text of ``settings``: ``|KEY=value`` fields."""
    return "".join(f"|{key}={value}" for key, value in settings).encode("latin-1")


def settings_fields(data: bytes) -> list[tuple[str, str]]:
    """The fields of carried ``Board6.Settings`` text, in order."""
    found: list[tuple[str, str]] = []
    for part in data.decode("latin-1").split("|"):
        key, sep, value = part.partition("=")
        if sep:
            found.append((key, value))
    return found


def mechanical_names(settings: list[tuple[str, str]]) -> dict[int, str]:
    """The names of mechanical layers 1 to 16 among carried settings, by Altium layer id (57 … 72)."""
    found: dict[int, str] = {}
    for key, value in settings:
        match = _MECHANICAL_NAME.fullmatch(key)
        if match is not None:
            found[int(match.group(1))] = value
    return found


@dataclass(frozen=True, slots=True)
class Found:
    """The storages of a source document: those carried, by property name, the index-bound ones that hold a
    record, with their record counts, and the frame-bound ones that hold data, with theirs (change c0459)."""

    carried: Mapping[str, Storage]
    index_bound: Mapping[str, int]
    frame_bound: Mapping[str, int] = field(default_factory=lambda: {})


def _count(header: bytes) -> int:
    return struct.unpack_from("<I", header)[0] if len(header) >= 4 else 0


def found_in(path: Path) -> Found:
    """The carried, the index-bound and the frame-bound storages of the PCB document at ``path``."""
    from fenolite.backends.altium.read.cfb import read_compound

    compound = read_compound(path)
    names = set(compound.storages())
    carried: dict[str, Storage] = {}
    bound: dict[str, int] = {}
    framed: dict[str, int] = {}

    def streams(name: str) -> Storage | None:
        if f"{name}/Header" not in compound or f"{name}/Data" not in compound:
            return None
        return Storage(compound.read(f"{name}/Header"), compound.read(f"{name}/Data"))

    for name in sorted(names):
        storage = streams(name)
        if storage is None:
            continue
        if (name in CARRIED or name == DIFFERENTIAL_PAIRS) and storage.data:
            carried[PREFIX + name] = storage
        elif name in FRAME_BOUND and storage.data:
            framed[name] = max(_count(storage.header), 1)
        elif name in (CLASSES, SIGNAL_CLASSES):
            kept = (
                kept_classes(storage.data)
                if name == CLASSES
                else [record for record in records(storage.data) if not _super(record)]
            )
            if kept:
                carrier = KEPT_CLASSES if name == CLASSES else KEPT_SIGNAL_CLASSES
                carried[PREFIX + carrier] = Storage(struct.pack("<I", len(kept)), b"".join(kept))
        elif name == "Board6":
            text = "".join(f"|{key}={value}" for key, value in pin_pair_fields(storage.data))
            pairs = pin_pairs(text.encode("latin-1"))
            if pairs:
                carried[PREFIX + PIN_PAIRS] = Storage(struct.pack("<I", len(pairs)), pin_pair_text(pairs))
            settings = board_settings(storage.data)  # change c0464
            if settings:
                carried[PREFIX + SETTINGS] = Storage(
                    struct.pack("<I", len(settings)), settings_text(settings)
                )
        elif _INDEX_BOUND.fullmatch(name) and _count(storage.header):
            bound[name] = _count(storage.header)
    return Found(carried, bound, framed)


def items(found: Found) -> dict[str, bytes]:
    """The carried storages of ``found`` as ``boardcarrier.with_carried`` items, by property name."""
    return {name: packed(storage) for name, storage in found.carried.items()}


def from_carried(carried: Mapping[str, bytes]) -> dict[str, Storage]:
    """The storages among a board's carried properties (``boardcarrier.carried``), by storage name
    (``Classes6.Kept`` for the classes, c0450's ``Classes6.Component`` among them). Only the names a
    conversion carries count, so the rule records of ``Rules6`` (change c0434) are not a storage; bytes that
    do not unpack are left out."""
    names = {PREFIX + name for name in (*CARRIED, DIFFERENTIAL_PAIRS, COMPONENT_CLASSES, *KEPT_CARRIERS)}
    found: dict[str, Storage] = {}
    for name, data in sorted(carried.items()):
        storage = unpacked(data) if name in names else None
        if storage is None:
            continue
        key = name.removeprefix(PREFIX)
        if key == COMPONENT_CLASSES:  # c0450's carrier
            if KEPT_CLASSES in found:
                continue
            key = KEPT_CLASSES
        found[key] = storage
    return found


# --- what a conversion back writes (change c0461) --------------------------------------------------------

PAIR_REASON = "the differential pair names a net the written document does not hold"
XSIGNAL_REASON = "the xSignal holds a character that a line of the board record cannot hold"


@dataclass(frozen=True, slots=True)
class Fitted:
    """The carried storages a conversion back writes, by storage name, and what it left out: per reason,
    the ids ``<storage>:<name>``."""

    storages: Mapping[str, Storage]
    dropped: Mapping[str, tuple[str, ...]]


def fitted(storages: Mapping[str, Storage], nets: set[str]) -> Fitted:
    """``storages`` (``from_carried``) as the written document can hold them (change c0461): a differential
    pair whose two nets are among ``nets``, and an xSignal of ``Board6.PinPairs`` that a line of the board
    record can hold. Classes keep their members as the source held them: the conversion keeps every
    designator and net name of the board, and an Altium-saved document holds members that name nothing
    (``pcb-records.md``, "Storages through KiCad")."""
    out = dict(storages)
    dropped: dict[str, list[str]] = {}
    if DIFFERENTIAL_PAIRS in out:
        kept: list[bytes] = []
        for record in records(out[DIFFERENTIAL_PAIRS].data):
            f = fields(record)
            if f.get("POSITIVENETNAME") in nets and f.get("NEGATIVENETNAME") in nets:
                kept.append(record)
            else:
                dropped.setdefault(PAIR_REASON, []).append(f"{DIFFERENTIAL_PAIRS}:{f.get('NAME', '')}")
        out[DIFFERENTIAL_PAIRS] = Storage(struct.pack("<I", len(kept)), b"".join(kept))
    if PIN_PAIRS in out:
        held: list[dict[str, str]] = []
        for pair in pin_pairs(out[PIN_PAIRS].data):
            if _writable("".join(pair.values())):
                held.append(pair)
            else:
                dropped.setdefault(XSIGNAL_REASON, []).append(f"Board6:{pair.get('NAME', '')}")
        if held:
            out[PIN_PAIRS] = Storage(struct.pack("<I", len(held)), pin_pair_text(held))
        else:
            del out[PIN_PAIRS]
    return Fitted(out, {reason: tuple(ids) for reason, ids in dropped.items()})


def _writable(text: str) -> bool:
    """Whether ``text`` can stand in a line of the ``Board6`` record (``docboard.format_line``)."""
    return "|" not in text and all(0x20 <= ord(ch) <= 0x7E for ch in text)


__all__ = [
    "CARRIED",
    "FRAME_BOUND",
    "FRAME_BOUND_REASON",
    "UNKNOWN_FRAME_REASON",
    "COMPONENT_CLASSES",
    "DIFFERENTIAL_PAIRS",
    "EVIDENCE",
    "INDEX_BOUND_REASON",
    "KEPT_CLASSES",
    "KEPT_CARRIERS",
    "SETTINGS",
    "board_settings",
    "mechanical_names",
    "settings_fields",
    "settings_text",
    "KEPT_SIGNAL_CLASSES",
    "SMART_UNION_REASON",
    "KIND",
    "PAIR_REASON",
    "PIN_PAIRS",
    "PREFIX",
    "XSIGNAL_REASON",
    "Fitted",
    "Found",
    "Storage",
    "component_classes",
    "fields",
    "fitted",
    "found_in",
    "from_carried",
    "items",
    "kept_classes",
    "packed",
    "pin_pair_fields",
    "pin_pair_text",
    "pin_pairs",
    "records",
    "unpacked",
]
