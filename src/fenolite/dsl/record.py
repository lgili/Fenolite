# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block records: the header of ``@block(id=, version=, ...)``, parameter metadata (``param``), the record
read without a build (``describe``), its canonical JSON with three digests, the version rules of shipped
blocks and the generated page (``docs/blocks.md``; change c0268).

The decorator is the record. ``describe`` reads the header and the parameters from it, and the ports,
parts, nets, nested blocks and requirements by using the block once with its defaults in a detached
design; it reads no file, library or lock and runs no tool. The metadata never reaches the model: the
model keeps c0251's ``BlockParam`` and the new ``Module.block_version`` only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, Any, cast

from fenolite.catalog.devices import EVIDENCE, ID, SHIPPED_NAMESPACE, SOURCE
from fenolite.catalog.records import LICENCE, VERSION
from fenolite.dsl.errors import DslError
from fenolite.dsl.quantity import UNITS, Quantity, Range, decimal_text
from fenolite.dsl.units import Length
from fenolite.model import canonical

if TYPE_CHECKING:
    from fenolite.dsl.block import Block, BlockDef

SCHEMA = "fenolite.block.v0"
"""The schema of a block record's canonical JSON."""
CATEGORIES: tuple[str, ...] = (
    "analog", "power", "protection", "interface", "indicator", "timing", "connector", "other",
)  # fmt: skip
"""The closed set of block categories; ``other`` is the default."""
RESERVED_NAMESPACE = SHIPPED_NAMESPACE
"""The namespace of the blocks shipped under ``fenolite.blocks``."""
SHIPPED_PACKAGE = "fenolite.blocks"
SHIPPED_LICENCE = "Apache-2.0"
DEFAULT_EVIDENCE = "INFERRED"
SUMMARY_LIMIT = 120
DOC_LIMIT = 200
LENGTH = "length"
"""The unit name of a ``Length`` parameter, shown in millimetres in pages."""
VERSIONS_FILE = "VERSIONS.toml"


class _Required:
    """The default of a required parameter: ``param(REQUIRED, ...)`` or ``param(doc=...)``."""

    _instance: _Required | None = None

    def __new__(cls) -> _Required:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "REQUIRED"


REQUIRED: Any = _Required()
"""The default of a required block parameter in ``param``."""


class Param:
    """What ``param(...)`` returns: a default with its metadata, unwrapped by ``@block``."""

    __slots__ = ("choices", "default", "doc", "max", "min", "unit")

    def __init__(
        self, default: object, doc: object, unit: object, low: object, high: object, choices: object
    ) -> None:
        self.default = default
        self.doc = doc
        self.unit = unit
        self.min = low
        self.max = high
        self.choices = choices

    def __repr__(self) -> str:
        return f"param({self.default!r})"


def param(
    default: object = REQUIRED,
    *,
    doc: str = "",
    unit: str | None = None,
    min: object = None,  # noqa: A002 - the keyword names the limit
    max: object = None,  # noqa: A002
    choices: Sequence[object] | None = None,
) -> Any:
    """The default of a block parameter with its metadata: a ``doc`` text (one line, at most 200
    characters), the ``unit`` (a unit name such as ``volt`` or ``ampere``, or ``length``), the limits
    ``min`` and ``max`` and a closed tuple of ``choices``. ``@block`` checks them, and ``use`` checks every
    value against them before the function runs (``docs/dsl.md``, "Blocks")."""
    return Param(default, doc, unit, min, max, choices)


# ------------------------------------------------------------------------------------------- header


@dataclass(frozen=True, slots=True)
class Deprecation:
    """``deprecated``: the id that replaces the block, the version it is deprecated since, and why."""

    by: str
    since: str
    reason: str


@dataclass(frozen=True, slots=True)
class Header:
    """The record header of a block with an id (c0259's header vocabulary)."""

    id: str
    version: str
    summary: str
    category: str = "other"
    licence: str = SHIPPED_LICENCE
    evidence: str = DEFAULT_EVIDENCE
    sources: tuple[str, ...] = ()
    replaces: str | None = None
    deprecated: Deprecation | None = None

    @property
    def namespace(self) -> str:
        return self.id.split(":", 1)[0]

    @property
    def name(self) -> str:
        return self.id.split(":", 1)[1]

    @property
    def pin(self) -> str:
        """``<id>@<version>``: the entry of the lock's ``[blocks]`` section."""
        return f"{self.id}@{self.version}"


def _line(value: object, what: str, limit: int, *, empty: bool) -> str:
    if not isinstance(value, str):
        raise DslError(f"{what} is a text, not {value!r}")
    if "\n" in value or "\r" in value:
        raise DslError(f"{what} is one line, with no newline")
    if len(value) > limit:
        raise DslError(f"{what} has {len(value)} characters; at most {limit}")
    if not empty and not value.strip():
        raise DslError(f"{what} is a non-empty text")
    return value


def shipped_module(module: str) -> bool:
    """Whether ``module`` is ``fenolite.blocks`` or one of its modules."""
    return module == SHIPPED_PACKAGE or module.startswith(f"{SHIPPED_PACKAGE}.")


def check_header(
    label: str,
    module: str,
    *,
    id: object,  # noqa: A002 - the keyword of @block
    version: object,
    summary: object,
    category: object,
    licence: object,
    evidence: object,
    sources: object,
    replaces: object,
    deprecated: object,
) -> Header:
    """The checked header of the block ``label`` defined in ``module``; ``DslError`` naming the block and
    the keyword otherwise."""
    what = f"@block {label}"
    if not isinstance(id, str) or not ID.fullmatch(id):
        raise DslError(f"{what}: id must be <namespace>:<name>, each part matching [A-Za-z0-9_.+-]+")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise DslError(
            f"{what}: version {version!r} must have the form MAJOR.MINOR.PATCH (decimal, no leading zeros)"
        )
    if version.split(".")[0] != "1":
        raise DslError(
            f"{what}: version: MAJOR stays 1 for the life of an id; an interface change is a new id"
        )
    namespace = id.split(":", 1)[0]
    shipped = namespace == RESERVED_NAMESPACE
    if shipped and not shipped_module(module):
        raise DslError(
            f"{what}: the namespace {RESERVED_NAMESPACE} is reserved for the blocks shipped under "
            f"{SHIPPED_PACKAGE}; give the block an id of your own namespace, such as "
            f"Acme:{id.split(':', 1)[1]}"
        )
    text = _line(summary, f"{what}: summary", SUMMARY_LIMIT, empty=False)
    if category not in CATEGORIES:
        raise DslError(f"{what}: category {category!r} is not one of {', '.join(CATEGORIES)}")
    if licence is None:
        if not shipped:
            raise DslError(f"{what}: licence is required, an SPDX expression such as MIT or Apache-2.0")
        licence = SHIPPED_LICENCE
    if not isinstance(licence, str) or not LICENCE.fullmatch(licence):
        raise DslError(f"{what}: licence {licence!r} is not an SPDX expression")
    if shipped and licence != SHIPPED_LICENCE:
        raise DslError(f"{what}: licence: a {RESERVED_NAMESPACE}: block is {SHIPPED_LICENCE}")
    if not isinstance(evidence, str) or not EVIDENCE.fullmatch(evidence):
        raise DslError(f"{what}: evidence {evidence!r} is not a label of the evidence vocabulary")
    if isinstance(sources, str) or not isinstance(sources, Sequence):
        raise DslError(f"{what}: sources is a tuple of texts, not {sources!r}")
    found = tuple(_line(s, f"{what}: sources", 200, empty=False) for s in cast(Sequence[object], sources))
    if shipped and not found:
        raise DslError(f"{what}: sources: a {RESERVED_NAMESPACE}: block needs at least one source")
    if shipped and not all(SOURCE.fullmatch(s) for s in found):
        raise DslError(f"{what}: sources: each source of a {RESERVED_NAMESPACE}: block is an S- id")
    if replaces is not None and (not isinstance(replaces, str) or not ID.fullmatch(replaces)):
        raise DslError(f"{what}: replaces names a block id <namespace>:<name>, not {replaces!r}")
    gone: Deprecation | None = None
    if deprecated is not None:
        if not isinstance(deprecated, Mapping) or set(cast(Mapping[str, object], deprecated)) != {
            "by",
            "since",
            "reason",
        }:
            raise DslError(f"{what}: deprecated is a mapping of by, since and reason")
        table = cast(Mapping[str, object], deprecated)
        by, since, reason = table["by"], table["since"], table["reason"]
        if not isinstance(by, str) or not ID.fullmatch(by):
            raise DslError(f"{what}: deprecated.by names a block id, not {by!r}")
        if not isinstance(since, str) or not VERSION.fullmatch(since):
            raise DslError(f"{what}: deprecated.since is a MAJOR.MINOR.PATCH version, not {since!r}")
        gone = Deprecation(by, since, _line(reason, f"{what}: deprecated.reason", DOC_LIMIT, empty=False))
    return Header(
        id=id,
        version=version,
        summary=text,
        category=cast(str, category),
        licence=licence,
        evidence=evidence,
        sources=found,
        replaces=replaces,
        deprecated=gone,
    )


# ---------------------------------------------------------------------------------------- parameters


@dataclass(frozen=True, slots=True)
class ParamMeta:
    """One parameter of a block as its record holds it: the default (``REQUIRED`` for none), the doc,
    the unit, the limits and the choices."""

    name: str
    default: object = REQUIRED
    doc: str = ""
    unit: str | None = None
    min: object = None
    max: object = None
    choices: tuple[object, ...] | None = None

    @property
    def required(self) -> bool:
        return self.default is REQUIRED

    @property
    def type(self) -> str:
        """The recorded type (c0251's ``BlockParam.type``), or ``any`` for a required parameter of no unit
        and no choices."""
        from fenolite.dsl.block import record

        if not self.required:
            return record(self.default, block="", param=self.name)[0]
        if self.choices:
            return record(self.choices[0], block="", param=self.name)[0]
        if self.unit == LENGTH:
            return LENGTH
        if self.unit is not None:
            return "quantity"
        return "any"


def unit_of(value: object) -> str | None:
    """The unit name of ``value``: a ``Quantity`` or ``Range`` unit, ``length``, or ``None``."""
    if isinstance(value, (Quantity, Range)):
        return value.unit
    if isinstance(value, Length):
        return LENGTH
    return None


def _number(value: object) -> Fraction | None:
    """The comparable number of a limit or a value: an int, nanometres or a quantity's value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Length):
        return Fraction(value.nm)
    if isinstance(value, Quantity):
        return value.value
    return None


def shown(value: object) -> str:
    """The text of ``value`` in messages and pages: a length in millimetres, any other value as c0251
    records it."""
    from fenolite.dsl.block import record

    if isinstance(value, Length):
        sign = "-" if value.nm < 0 else ""
        return f"{sign}{decimal_text(Fraction(abs(value.nm), 1_000_000), 'a length')}mm"
    if value is REQUIRED:
        return "required"
    return record(value, block="", param="")[1]


def allowed_text(meta: ParamMeta) -> str:
    """``1uA to 10mA``, ``at least 1uA``, ``at most 10mA`` or ``E24, E96``; empty without limits."""
    if meta.choices:
        return ", ".join(shown(choice) for choice in meta.choices)
    if meta.min is not None and meta.max is not None:
        return f"{shown(meta.min)} to {shown(meta.max)}"
    if meta.min is not None:
        return f"at least {shown(meta.min)}"
    if meta.max is not None:
        return f"at most {shown(meta.max)}"
    return ""


def _limit_kind(value: object) -> tuple[str, str | None] | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return ("int", None)
    if isinstance(value, Length):
        return (LENGTH, None)
    if isinstance(value, Quantity):
        return ("quantity", value.unit)
    return None


def _ends(value: object) -> tuple[Fraction | None, Fraction | None] | None:
    """The two ends of ``value`` for a limit check; ``None`` for a value that has no number."""
    if isinstance(value, Range):
        return value.low, value.high
    number = _number(value)
    return None if number is None else (number, number)


def _within(meta: ParamMeta, value: object) -> bool:
    ends = _ends(value)
    if ends is None:
        return True
    low, high = ends
    lo, hi = _number(meta.min), _number(meta.max)
    if lo is not None and (low is None or low < lo):
        return False
    return not (hi is not None and (high is None or high > hi))


def _is_choice(meta: ParamMeta, value: object) -> bool:
    from fenolite.dsl.block import record

    wanted = record(value, block="", param=meta.name)
    return any(record(choice, block="", param=meta.name) == wanted for choice in meta.choices or ())


def check_param(block: str, name: str, given: object) -> ParamMeta:
    """The metadata of the parameter ``name`` of ``block`` from its signature default ``given`` (a
    ``Param`` or a plain default), checked; ``DslError`` naming the block and the parameter otherwise."""
    from fenolite.dsl.block import record

    if not isinstance(given, Param):
        if given is not REQUIRED:
            record(given, block=block, param=name)
        return ParamMeta(name, given)
    what = f"block {block}: parameter `{name}`"
    default = given.default
    if default is not REQUIRED:
        record(default, block=block, param=name)
    doc = _line(given.doc, f"{what}: doc", DOC_LIMIT, empty=True)
    unit = given.unit
    if unit is not None and (not isinstance(unit, str) or (unit != LENGTH and unit not in UNITS)):
        raise DslError(f"{what}: unit {unit!r} is not one of {', '.join((*UNITS, LENGTH))}")
    has = unit_of(default) if default is not REQUIRED else None
    if unit is not None and default is not REQUIRED and has != unit:
        raise DslError(f"{what}: unit {unit} differs from the unit of the default ({has or 'none'})")
    if unit is None:
        unit = has
    low, high = given.min, given.max
    for side, limit in (("min", low), ("max", high)):
        if limit is None:
            continue
        kind = _limit_kind(limit)
        if kind is None:
            raise DslError(f"{what}: {side} is a Quantity, a Length or an int, not {limit!r}")
        if unit is not None and (kind[1] or (LENGTH if kind[0] == LENGTH else None)) != unit:
            raise DslError(f"{what}: {side} {shown(limit)} is not in the unit {unit}")
        if unit is None and default is not REQUIRED and _limit_kind(default) != kind:
            raise DslError(f"{what}: {side} {shown(limit)} is not of the type of the default")
    if low is not None and high is not None:
        if _limit_kind(low) != _limit_kind(high):
            raise DslError(f"{what}: min and max are of one type")
        if cast(Fraction, _number(low)) > cast(Fraction, _number(high)):
            raise DslError(f"{what}: min {shown(low)} is above max {shown(high)}")
    choices: tuple[object, ...] | None = None
    raw: object = given.choices
    if raw is not None:
        if isinstance(raw, str) or not isinstance(raw, Sequence):
            raise DslError(f"{what}: choices is a tuple of values")
        choices = tuple(cast(Sequence[object], raw))
        recorded = [record(choice, block=block, param=name) for choice in choices]
        if len(choices) < 2 or len(set(recorded)) != len(recorded):
            raise DslError(f"{what}: choices holds at least two distinct values")
        if len({kind for kind, _ in recorded}) != 1:
            raise DslError(f"{what}: choices are values of one type")
    meta = ParamMeta(name, default, doc, unit, low, high, choices)
    if default is not REQUIRED:
        if not _within(meta, default):
            raise DslError(f"{what}: the default {shown(default)} is outside {allowed_text(meta)}")
        if choices is not None and not _is_choice(meta, default):
            raise DslError(
                f"{what}: the default {shown(default)} is not one of the choices {allowed_text(meta)}"
            )
    return meta


def check_value(block: str, meta: ParamMeta, value: object) -> None:
    """Refuse ``value`` for the parameter ``meta`` of ``block`` before the function runs: another unit,
    outside the limits or not a choice (``DslError`` naming the parameter, the value and what is
    allowed)."""
    what = f"block {block}: parameter `{meta.name}`"
    if meta.unit is not None:
        has = unit_of(value)
        if has != meta.unit:
            given = f"a value in {has}" if has is not None else f"a {type(value).__name__}"
            raise DslError(f"{what}: {given} is given; the unit is {meta.unit}")
    if not _within(meta, value):
        raise DslError(f"{what}: {shown(value)} is outside the range {allowed_text(meta)}")
    if meta.choices is not None and not _is_choice(meta, value):
        raise DslError(f"{what}: {shown(value)} is not one of the choices {allowed_text(meta)}")


# ------------------------------------------------------------------------------------------- record


@dataclass(frozen=True, slots=True)
class PortRecord:
    """A port as the record lists it."""

    name: str
    kind: str
    direction: str
    optional: bool
    members: tuple[str, ...]
    doc: str = ""


@dataclass(frozen=True, slots=True)
class Requires:
    """What a block needs from the catalog: device ids, lib ids of parts without a device, query texts."""

    devices: tuple[str, ...] = ()
    lib_ids: tuple[str, ...] = ()
    queries: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BlockRecord:
    """The record of a block (``describe``). ``header`` is ``None`` for a project block. ``ports``,
    ``parts``, ``nets``, ``blocks`` and ``requires`` are ``None`` when the block cannot be elaborated with
    its defaults, and ``elaboration`` then says why (``reason`` or ``error``)."""

    name: str
    header: Header | None
    params: tuple[ParamMeta, ...]
    ports: tuple[PortRecord, ...] | None = None
    parts: tuple[str, ...] | None = None
    nets: tuple[str, ...] | None = None
    blocks: tuple[tuple[str, str], ...] | None = None
    requires: Requires | None = None
    elaboration: Mapping[str, str] | None = field(default=None)

    @property
    def id(self) -> str:
        """The id of a block with a record, else its block name."""
        return self.header.id if self.header is not None else self.name


def _local(path: str, root: str) -> str:
    return path[len(root) + 1 :]


def _elaborate(definition: BlockDef) -> dict[str, object]:
    """The fields read by using ``definition`` once with its defaults in a detached design."""
    from fenolite.dsl.block import Block
    from fenolite.dsl.design import Design
    from fenolite.dsl.part import Part

    design = Design("describe")
    defaults = dict(definition.keywords)
    instance = design.use(definition, "x", **defaults)
    top: Block = instance.module
    root = top.path
    nested = sorted(
        (m for path, m in design.modules.items() if isinstance(m, Block) and path.startswith(f"{root}/")),
        key=lambda m: m.path,
    )
    ports = tuple(
        PortRecord(
            handle.name,
            handle.kind,
            handle.direction,
            handle.optional,
            tuple(handle.members),
            top.port_docs.get(name, ""),
        )
        for name, handle in sorted(top.ports.items())
    )
    parts: dict[str, Part] = {
        _local(path, root): part for path, part in design.parts.items() if path.startswith(f"{root}/")
    }
    nets = sorted(
        {name for name in top.local_nets}
        | {f"{_local(m.path, root)}/{name}" for m in nested for name in m.local_nets}
    )
    devices: set[str] = set()
    lib_ids: set[str] = set()
    queries: set[str] = set()
    for part in parts.values():
        query = part.query
        if query is not None:
            queries.add(query.text())
        elif part.device is not None:
            devices.add(part.device.id)
        else:
            lib_ids.add(part.lib_id)
    return {
        "ports": ports,
        "parts": tuple(sorted(parts)),
        "nets": tuple(nets),
        "blocks": tuple((_local(m.path, root), m.definition.name) for m in nested),
        "requires": Requires(tuple(sorted(devices)), tuple(sorted(lib_ids)), tuple(sorted(queries))),
    }


def describe(definition: object) -> BlockRecord:
    """The record of the block ``definition`` (``fenolite.dsl.describe``): the header and parameters from
    the decorator; the ports, parts, nets, nested blocks and requirements from one use with the defaults
    in a detached design. Pure: no file, library or lock is read, no tool runs, and the design is never
    converted to a model. A required parameter or an exception of the function is given back in
    ``elaboration`` instead of raised."""
    from fenolite.dsl.block import BlockDef

    if not isinstance(definition, BlockDef):
        raise DslError(f"describe() takes a block made with @block, not {definition!r}")
    params = tuple(definition.params[name] for name in sorted(definition.params))
    required = [meta.name for meta in params if meta.required]
    if required:
        return BlockRecord(
            definition.name,
            definition.header,
            params,
            elaboration={"reason": f"required parameter {required[0]}"},
        )
    try:
        found = _elaborate(definition)
    except Exception as error:  # noqa: BLE001 - reported in the record, never raised
        return BlockRecord(
            definition.name,
            definition.header,
            params,
            elaboration={"error": f"{type(error).__name__}: {error}"},
        )
    return BlockRecord(definition.name, definition.header, params, **found)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------- canonical form


def _value(value: object) -> str | None:
    """A default, limit or choice as c0251's canonical text; ``None`` for no value."""
    from fenolite.dsl.block import record

    if value is None or value is REQUIRED:
        return None
    return record(value, block="", param="")[1]


def _param_json(meta: ParamMeta) -> dict[str, object]:
    return {
        "name": meta.name,
        "type": meta.type,
        "unit": meta.unit,
        "required": meta.required,
        "default": _value(meta.default),
        "min": _value(meta.min),
        "max": _value(meta.max),
        "choices": None if meta.choices is None else [_value(choice) for choice in meta.choices],
        "doc": meta.doc,
    }


def _port_json(port: PortRecord) -> dict[str, object]:
    return {
        "name": port.name,
        "kind": port.kind,
        "direction": port.direction,
        "optional": port.optional,
        "members": list(port.members),
        "doc": port.doc,
    }


def _header_json(header: Header | None) -> dict[str, object]:
    if header is None:
        names = ("id", "version", "summary", "category", "licence", "evidence", "replaces", "deprecated")
        return {**dict.fromkeys(names), "sources": []}
    gone = header.deprecated
    return {
        "id": header.id,
        "version": header.version,
        "summary": header.summary,
        "category": header.category,
        "licence": header.licence,
        "evidence": header.evidence,
        "sources": list(header.sources),
        "replaces": header.replaces,
        "deprecated": None if gone is None else {"by": gone.by, "since": gone.since, "reason": gone.reason},
    }


def _body(record: BlockRecord) -> dict[str, object]:
    """The record as plain JSON values, without ``digests``."""
    requires = record.requires
    return {
        "schema": SCHEMA,
        "name": record.name,
        **_header_json(record.header),
        "params": [_param_json(meta) for meta in record.params],
        "ports": None if record.ports is None else [_port_json(port) for port in record.ports],
        "parts": None if record.parts is None else list(record.parts),
        "nets": None if record.nets is None else list(record.nets),
        "blocks": None
        if record.blocks is None
        else [{"name": name, "block": block} for name, block in record.blocks],
        "requires": None
        if requires is None
        else {
            "devices": list(requires.devices),
            "lib_ids": list(requires.lib_ids),
            "queries": list(requires.queries),
        },
        "elaboration": None if record.elaboration is None else dict(record.elaboration),
    }


def _sha(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical.dumps(value).encode("utf-8")).hexdigest()


def digests(record: BlockRecord) -> dict[str, str]:
    """The three digests: ``interface`` (ports without docs; parameter names, types, units, required),
    ``definition`` (also defaults, limits, choices, parts, nets, nested blocks and requires) and
    ``record`` (the whole record but its digests)."""
    body = _body(record)
    ports = body["ports"]
    interface = {
        "ports": None
        if ports is None
        else [{k: v for k, v in port.items() if k != "doc"} for port in cast(list[dict[str, object]], ports)],
        "params": [
            {key: entry[key] for key in ("name", "type", "unit", "required")}
            for entry in cast(list[dict[str, object]], body["params"])
        ],
    }
    definition = {
        **interface,
        "params": [
            {k: v for k, v in entry.items() if k != "doc"}
            for entry in cast(list[dict[str, object]], body["params"])
        ],
        **{key: body[key] for key in ("parts", "nets", "blocks", "requires")},
    }
    return {"definition": _sha(definition), "interface": _sha(interface), "record": _sha(body)}


def record_data(record: BlockRecord) -> dict[str, object]:
    """The ``fenolite.block.v0`` record as plain JSON values, with its ``digests``."""
    return {**_body(record), "digests": digests(record)}


def record_json(record: BlockRecord) -> str:
    """The canonical JSON text of ``record`` (keys sorted, LF, no float): equal records give equal bytes."""
    return canonical.dumps(record_data(record))


# ---------------------------------------------------------------------------------------------- page


def _cell(text: str) -> str:
    return text.replace("|", "\\|") if text else ""


def page(record: BlockRecord, *, titles: Mapping[str, str] | None = None) -> str:
    """The Markdown page of ``record``: LF line ends, no date; equal records give equal pages. ``titles``
    maps a source id to its title (``tools/gen_block_docs.py`` reads them; the core never does)."""
    header = record.header
    title = record.id if header is None else f"{header.id} {header.version}"
    lines = [f"# {title}", ""]
    if header is not None:
        lines += [header.summary, "", "| category | licence | evidence |", "|---|---|---|"]
        lines += [f"| {header.category} | {header.licence} | {header.evidence} |", ""]
        if header.deprecated is not None:
            gone = header.deprecated
            lines += [f"Deprecated since {gone.since}: use {gone.by} ({gone.reason}).", ""]
        if header.replaces is not None:
            lines += [f"Replaces {header.replaces}.", ""]
    lines += ["## Parameters", ""]
    if record.params:
        lines += ["| name | type | unit | default | allowed | doc |", "|---|---|---|---|---|---|"]
        for meta in record.params:
            cells = (meta.name, meta.type, meta.unit or "", shown(meta.default), allowed_text(meta), meta.doc)
            lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    else:
        lines.append("None.")
    lines += ["", "## Ports", ""]
    if record.elaboration is not None:
        why = record.elaboration.get("reason") or record.elaboration.get("error", "")
        lines.append(f"Not elaborated: {why}.")
    elif record.ports:
        lines.append("The ports are those of the default parameters.")
        lines += ["", "| name | kind | direction | optional | doc |", "|---|---|---|---|---|"]
        for port in record.ports:
            optional = "yes" if port.optional else "no"
            lines.append(f"| {port.name} | {port.kind} | {port.direction} | {optional} | {_cell(port.doc)} |")
    else:
        lines.append("None.")
    lines += ["", "## Requires", ""]
    requires = record.requires
    wanted = (
        []
        if requires is None
        else [
            *(f"- device `{item}`" for item in requires.devices),
            *(f"- symbol `{item}`" for item in requires.lib_ids),
            *(f"- query `{item}`" for item in requires.queries),
        ]
    )
    lines += wanted or ["None."]
    lines += ["", "## Sources", ""]
    sources = header.sources if header is not None else ()
    named = titles or {}
    lines += [f"- {s}: {named[s]}" if s in named else f"- {s}" for s in sources] or ["None."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------- versions


@dataclass(frozen=True, slots=True)
class VersionRow:
    """One table of ``VERSIONS.toml``: a shipped id with its version and digests, or a removed id."""

    id: str
    version: str = ""
    record: str = ""
    definition: str = ""
    interface: str = ""
    removed: bool = False


def version_row(record: BlockRecord) -> VersionRow:
    found = digests(record)
    header = cast(Header, record.header)
    return VersionRow(header.id, header.version, found["record"], found["definition"], found["interface"])


def _toml_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def versions_text(rows: Sequence[VersionRow]) -> str:
    """The canonical text of ``VERSIONS.toml``: a comment, then one table per id in code-point order."""
    lines = [
        '# The version and digests of every shipped block (docs/blocks.md, "Version rules").',
        "# Written by tools/blocks/versions.py --update; tests/unit/blocks/test_versions.py checks it.",
    ]
    for row in sorted(rows, key=lambda r: r.id):
        lines += ["", f"[{_toml_string(row.id)}]"]
        if row.removed:
            lines.append("removed = true")
            continue
        lines += [
            f"{key} = {_toml_string(getattr(row, key))}"
            for key in ("version", "record", "definition", "interface")
        ]
    return "\n".join(lines) + "\n"


def read_versions(text: str) -> tuple[VersionRow, ...]:
    import tomllib

    data = tomllib.loads(text)
    rows: list[VersionRow] = []
    for key, raw in sorted(data.items()):
        if not isinstance(raw, dict):
            raise DslError(f"{VERSIONS_FILE}: {key} must be a table")
        table = cast(dict[str, object], raw)
        if table.get("removed") is True:
            rows.append(VersionRow(key, removed=True))
            continue
        values = {name: table.get(name) for name in ("version", "record", "definition", "interface")}
        if not all(isinstance(value, str) for value in values.values()):
            raise DslError(f"{VERSIONS_FILE}: {key} needs version, record, definition and interface")
        texts = cast(dict[str, str], values)
        rows.append(
            VersionRow(key, texts["version"], texts["record"], texts["definition"], texts["interface"])
        )
    return tuple(rows)


def _parts(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


UPDATE_HINT = "run `uv run python tools/blocks/versions.py --update` after the review"


def version_problems(records: Sequence[BlockRecord], rows: Sequence[VersionRow]) -> list[str]:
    """How the shipped ``records`` break the version rules against the committed ``rows``: an interface
    changed under an id, a changed definition without a MINOR step, a changed record without a PATCH step,
    a reused removed id, a missing or stale row, and a ``replaces`` whose block does not name the record in
    ``deprecated.by``."""
    problems: list[str] = []
    known = {row.id: row for row in rows}
    present: set[str] = set()
    headers = {record.id: record.header for record in records}
    for record in records:
        header = record.header
        if header is None:
            problems.append(f"{record.name}: a shipped block has an id and a version")
            continue
        current = version_row(record)
        present.add(current.id)
        old = known.get(current.id)
        if old is None:
            problems.append(f"{current.id}: not in {VERSIONS_FILE}; {UPDATE_HINT}")
        elif old.removed:
            problems.append(f"{current.id}: the id was removed and must not be used again; choose a new id")
        elif old != current:
            if old.interface != current.interface:
                problems.append(
                    f"{current.id}: its interface changed; an interface change needs a new id with replaces, "
                    "and a deprecation of this one"
                )
            elif old.definition != current.definition and not (
                _parts(current.version)[:1] == _parts(old.version)[:1]
                and _parts(current.version)[1] > _parts(old.version)[1]
            ):
                problems.append(
                    f"{current.id}: its definition changed; give it a MINOR version above {old.version}"
                )
            elif old.record != current.record and _parts(current.version) <= _parts(old.version):
                problems.append(
                    f"{current.id}: the record changed; give it a PATCH version above {old.version}"
                )
            else:
                problems.append(f"{current.id}: {VERSIONS_FILE} is stale; {UPDATE_HINT}")
        problems += replacement_problems(header, headers)
    for row in rows:
        if not row.removed and row.id not in present:
            problems.append(f"{row.id}: in {VERSIONS_FILE} but not shipped; mark it removed = true")
    return problems


def replacement_problems(header: Header | None, headers: Mapping[str, Header | None]) -> list[str]:
    """Why ``header``'s ``replaces`` is refused: the replaced block, in the same catalog (``headers``: id →
    header), does not name the record in ``deprecated.by``."""
    if header is None or header.replaces is None:
        return []
    old = headers.get(header.replaces)
    if old is None:
        return []
    if old.deprecated is not None and old.deprecated.by == header.id:
        return []
    return [
        f"{header.id} replaces {header.replaces}, but {header.replaces} does not name {header.id} in "
        "deprecated.by"
    ]


__all__ = [
    "CATEGORIES",
    "LENGTH",
    "REQUIRED",
    "SCHEMA",
    "BlockRecord",
    "Deprecation",
    "Header",
    "Param",
    "ParamMeta",
    "PortRecord",
    "Requires",
    "VersionRow",
    "allowed_text",
    "check_header",
    "check_param",
    "check_value",
    "describe",
    "digests",
    "page",
    "param",
    "read_versions",
    "record_data",
    "record_json",
    "replacement_problems",
    "shipped_module",
    "shown",
    "unit_of",
    "version_problems",
    "version_row",
    "versions_text",
]
