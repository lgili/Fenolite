# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Building records from frames and lines, checking their values, rebuilding their bytes, linking owners.

Private to the schematic reader; ``document`` and ``schlib`` share it.
"""

# evidence: see read.sch

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fenolite.backends.altium.read.sch.issues import IssueLog
from fenolite.backends.altium.read.sch.pins import decode_fields, encode_fields
from fenolite.backends.altium.read.sch.props import UTF8_PREFIX, PropertyList, decode_value, parse, parse_int
from fenolite.backends.altium.read.sch.records import (
    COUNT_CHECKS,
    NUMERIC,
    QUARTER,
    REAL,
    RECORD_TYPES,
    Component,
    Pin,
    PropertyRecord,
    RecordRef,
    SchRecord,
    UnknownRecord,
)
from fenolite.backends.altium.read.sch.units import parse_udeg

NUL = b"\0"


@dataclass
class Context:
    """What one reading carries: the code page, the UTF-8 flag of an ASCII file, the findings and the unknown
    record ids met so far (id → count and the locator of the first)."""

    codepage: str
    log: IssueLog
    utf8: bool = False
    unknown_ids: dict[str, tuple[int, str]] = field(default_factory=dict[str, tuple[int, str]])

    def unknown(self, label: str, where: str) -> None:
        count, first = self.unknown_ids.get(label, (0, where))
        self.unknown_ids[label] = (count + 1, first)

    def report_unknown(self) -> None:
        """One ``unknown-record`` info per distinct unknown id, with its count, in order of first meeting."""
        for label, (count, where) in self.unknown_ids.items():
            self.log.add(
                "altium.sch.unknown-record",
                f"record id {label} has no class; {count} record(s) kept whole",
                where,
            )
        self.unknown_ids.clear()


def settle(record: SchRecord, **values: object) -> None:
    """Set fields of a record that is still being built and that no caller has seen yet. Records are frozen
    for their users; while a stream is read, its owner links and findings are filled in place, because a copy
    per record would make a long stream slow."""
    for name, value in values.items():
        object.__setattr__(record, name, value)


# --- value checks -----------------------------------------------------------------------------------------


def _numbers(props: PropertyList, pattern: str) -> int:
    compiled = re.compile(f"^{pattern}$")
    return len({m.group(1) for key in props.keys() if (m := compiled.match(key))})


def check_values(record: SchRecord, ctx: Context, where: str) -> SchRecord:
    """Report modelled keys whose value does not parse (``bad-value``), counts that disagree with the keys
    present, and undecodable text (``text-undecodable``, once per record). Returns the record with
    ``bad_keys`` set."""
    props = record.props
    if props is None:
        return record
    bad: list[str] = []
    typed = not isinstance(record, (UnknownRecord, PropertyRecord))
    if typed:
        for key in props.keys():
            spec = record.spec_for(key)
            if spec is None:
                continue
            raw = props.raw(key)
            if raw is None:
                continue
            ok = True
            if spec.kind in NUMERIC:
                value = parse_int(raw)
                ok = value is not None and (spec.kind != QUARTER or 0 <= value <= 3)
            elif spec.kind == REAL:
                ok = parse_udeg(raw.decode("latin-1")) is not None
            if not ok:
                bad.append(key)
                ctx.log.add(
                    "altium.sch.bad-value",
                    f"{type(record).__name__} key {key} holds a value that is not a {spec.kind}",
                    where,
                )
        for count_key, pattern in COUNT_CHECKS.items():
            if not props.has(count_key) or record.spec_for(count_key) is None or count_key in bad:
                continue
            stated = parse_int(props.raw(count_key))
            if stated is None:
                continue
            present = _numbers(props, pattern)
            if not 0 <= stated <= len(record.payload):
                ctx.log.add(
                    "altium.sch.bad-value",
                    f"{type(record).__name__} key {count_key} is {stated}, more than the record can hold; "
                    f"the {present} item(s) present are read",
                    where,
                )
            elif present > stated:
                ctx.log.add(
                    "altium.sch.bad-value",
                    f"{type(record).__name__} key {count_key} is {stated} but {present} item(s) are present; "
                    "the items present are read",
                    where,
                )
    undecodable = False
    for item in props.items:
        if item.raw is None or item.raw.isascii():
            continue
        folded = item.folded
        if folded.startswith(UTF8_PREFIX):
            undecodable |= not decode_value(item.raw, ctx.codepage, utf8=True)[1]
        elif props.has(UTF8_PREFIX + folded):
            continue
        else:
            undecodable |= not decode_value(item.raw, ctx.codepage, utf8=props.utf8)[1]
    if undecodable:
        ctx.log.add(
            "altium.sch.text-undecodable",
            f"a value holds a byte that {('utf-8' if props.utf8 else ctx.codepage)} does not define; "
            "the text view shows U+FFFD and the bytes are kept",
            where,
        )
    if bad:
        settle(record, bad_keys=tuple(bad))
    return record


def _check_pin_text(record: SchRecord, ctx: Context, where: str) -> None:
    fields = record.pin_fields
    if fields is None:
        return
    strings = (fields.description, fields.name, fields.designator, fields.swap_group)
    strings += (fields.part_and_sequence, fields.default_value)
    if any(not decode_value(value, ctx.codepage)[1] for value in strings):
        ctx.log.add(
            "altium.sch.text-undecodable",
            f"a pin string holds a byte that {ctx.codepage} does not define; the bytes are kept",
            where,
        )


# --- records from frames and lines ------------------------------------------------------------------------


def typed_record(
    props: PropertyList,
    *,
    ref: RecordRef,
    kind: int,
    payload: bytes,
    offset: int,
    segments: tuple[tuple[int, bytes], ...],
    ctx: Context,
    where: str,
) -> SchRecord:
    """The record of a property list: its class from ``RECORD``, or an ``UnknownRecord``."""
    record_id = parse_int(props.raw("RECORD"))
    cls = RECORD_TYPES.get(record_id) if record_id is not None else None
    if record_id is None:
        ctx.log.add("altium.sch.malformed-record", "the record has no integer RECORD key; kept whole", where)
        cls = UnknownRecord
    elif cls is None:
        ctx.unknown(str(record_id), where)
        cls = UnknownRecord
    record = cls(ref, kind, payload, offset, props, segments)
    return check_values(record, ctx, where)


def frame_record(
    kind: int, payload: bytes, *, ref: RecordRef, offset: int, ctx: Context, where: str
) -> SchRecord:
    """The record of one binary frame."""
    if kind != 0:
        fields = decode_fields(payload, codepage=ctx.codepage)
        if fields == "malformed":
            ctx.log.add(
                "altium.sch.malformed-record", "a binary pin record is cut inside a field; kept whole", where
            )
            return UnknownRecord(ref, kind, payload, offset, None)
        if fields == "not-pin":
            label = f"binary {int.from_bytes(payload[:4], 'little', signed=True)}"
            ctx.unknown(label, where)
            return UnknownRecord(ref, kind, payload, offset, None)
        record = Pin(ref, kind, payload, offset, None, pin_fields=fields)
        _check_pin_text(record, ctx, where)
        return record
    if not payload.endswith(NUL):
        ctx.log.add(
            "altium.sch.malformed-record",
            "the property list does not end with its NUL; kept whole",
            where,
        )
        return UnknownRecord(ref, kind, payload, offset, None)
    text = payload[:-1]
    props = parse(text, codepage=ctx.codepage)
    return typed_record(
        props,
        ref=ref,
        kind=kind,
        payload=payload,
        offset=offset,
        segments=((len(text), NUL),),
        ctx=ctx,
        where=where,
    )


def header_record(
    props: PropertyList,
    *,
    ref: RecordRef,
    kind: int,
    payload: bytes,
    offset: int,
    segments: tuple[tuple[int, bytes], ...],
) -> PropertyRecord:
    return PropertyRecord(ref, kind, payload, offset, props, segments)


def record_bytes(record: SchRecord) -> bytes:
    """The payload of ``record``, rebuilt from its parts: the property list's bytes laid out by
    ``segments``, a binary pin's fields, or the kept bytes of a record without either."""
    if record.pin_fields is not None:
        return encode_fields(record.pin_fields)
    if record.props is None:
        return record.payload
    text = record.props.to_bytes()
    out = bytearray()
    position = 0
    for length, after in record.segments:
        out += text[position : position + length]
        out += after
        position += length
    out += text[position:]
    return bytes(out)


# --- owners -----------------------------------------------------------------------------------------------

Resolver = Callable[[SchRecord], tuple[RecordRef | None, str]]
"""Gives a record's owner, or ``None`` and a reason (empty when the record simply has no owner)."""


def link(
    groups: Sequence[Sequence[SchRecord]],
    resolve: Resolver,
    ctx: Context,
    where: Callable[[SchRecord], str],
    *,
    warn: bool = True,
) -> list[list[SchRecord]]:
    """Set ``owner`` and ``children`` of every record of ``groups`` (index spaces in order). A record whose
    owner is not valid stays at the root, with an ``orphan-record`` warning when ``warn``."""
    owners: dict[RecordRef, RecordRef | None] = {}
    children: dict[RecordRef, list[RecordRef]] = {}
    for group in groups:
        for record in group:
            owner, reason = resolve(record)
            if owner is None and reason and warn:
                ctx.log.add("altium.sch.orphan-record", reason, where(record))
            owners[record.ref] = owner
            if owner is not None:
                children.setdefault(owner, []).append(record.ref)
    out: list[list[SchRecord]] = []
    for group in groups:
        linked: list[SchRecord] = []
        for record in group:
            kids = tuple(children.get(record.ref, ()))
            owner = owners[record.ref]
            if owner is not None or kids:
                settle(record, owner=owner, children=kids)
            linked.append(record)
        out.append(linked)
    return out


def check_parts(
    components: Sequence[SchRecord],
    get: Callable[[RecordRef], SchRecord],
    ctx: Context,
    where: Callable[[SchRecord], str],
) -> None:
    """One ``part-out-of-range`` warning per component that has a child outside its part or mode counts."""
    for component in components:
        if not isinstance(component, Component):
            continue
        parts, modes = component.part_count, component.display_mode_count
        outside: Counter[str] = Counter()
        for ref in component.children:
            child = get(ref)
            if child.owner_part > parts or child.owner_part < -1:
                outside["part"] += 1
            if child.owner_part != -1 and not 0 <= child.owner_display_mode < max(modes, 1):
                outside["display mode"] += 1
        if outside:
            detail = ", ".join(
                f"{count} child(ren) outside its {what} count" for what, count in sorted(outside.items())
            )
            ctx.log.add(
                "altium.sch.part-out-of-range",
                f"component {component.ref.stream} {component.ref.index} ({parts} part(s), {modes} display "
                f"mode(s)): {detail}",
                where(component),
            )


__all__ = [
    "Context",
    "Resolver",
    "check_parts",
    "check_values",
    "frame_record",
    "header_record",
    "link",
    "record_bytes",
    "typed_record",
]
