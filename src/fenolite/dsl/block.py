# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Blocks: reusable circuits with ports and recorded parameters (``docs/dsl.md``, "Blocks"; change c0251).

A block is a plain function ``def name(b, *, param=default, ...)`` marked with ``@block``. It runs once per
instance, made by ``design.use(block, name, **params)`` or by ``b.use(...)`` inside another block, with a
fresh ``Block`` (a ``Module``) as ``b``. Nothing is collected behind the script's back: every object joins
the design through an explicit call (``b.part``, ``b.net``, ``b.port``, ``b.use``, ``b.add``).
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, cast, overload

from fenolite.core.partquery import Constraint, PartQuery
from fenolite.dsl.blockschematic import SchematicGroup, declare
from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import I2C, SPI, UART, USB2, DiffPair, Ground, Harness, Interface, Logic, Power
from fenolite.dsl.module import Container, Module
from fenolite.dsl.part import Net, Part, check_name
from fenolite.dsl.portnets import DIRECTIONS, PortHandle
from fenolite.dsl.quantity import Quantity, Range
from fenolite.dsl.record import REQUIRED, Header, ParamMeta, check_header, check_param, check_value
from fenolite.dsl.relative import (
    Edges,
    LiveRequest,
    Pose,
    Reuse,
    Strategy,
    block_root,
    check_frame,
    parse_request,
    set_layout,
)
from fenolite.dsl.units import Length, as_nm, as_udeg
from fenolite.schematic.block_sheets import SheetGroup, sheet_name

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

RESERVED_PORT_NAMES: tuple[str, ...] = (
    "path", "block", "params", "part", "port", "place", "layout", "module",
    "left", "right", "top", "bottom", "center_x", "center_y",
)  # fmt: skip
"""Attributes of ``BlockInstance`` that a port name cannot take."""
PORT_KINDS: Mapping[type, str] = MappingProxyType(
    {
        Power: "power",
        Ground: "ground",
        Logic: "logic",
        DiffPair: "diff_pair",
        I2C: "i2c",
        UART: "uart",
        USB2: "usb2",
        SPI: "spi",
        Harness: "harness",
    }
)
"""Interface class → the kind of a port of that class (``Rail`` is ``Power``; ``Ground``, ``Logic``: c0252).
"""
PORT_MEMBERS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "net": ("net",),
        "power": ("hv", "lv"),
        "ground": ("gnd",),
        "logic": ("io",),
        "diff_pair": ("p", "n"),
        "i2c": ("sda", "scl"),
        "uart": ("tx", "rx"),
        "usb2": ("dp", "dn", "vbus", "gnd"),
        "spi": ("sck", "mosi", "miso", "cs0"),
    }
)
"""The closed member table of port kinds; a ``harness`` port takes ``members=``, an ``spi`` port with more
chip selects ``selects=``."""

_EMPTY = inspect.Parameter.empty
LETTERS = re.compile(r"[A-Z]+")
"""The prefix of a part added with a ref and no name: the leading capital letters of the ref."""


def record(value: object, *, block: str, param: str) -> tuple[str, str]:
    """The ``(type, text)`` that records ``value`` (``BlockParam``); any other value raises ``DslError``."""
    if isinstance(value, bool):
        return ("bool", "true" if value else "false")
    if isinstance(value, int):
        return ("int", str(value))
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, Length):
        return ("length", str(value.nm))
    if isinstance(value, Quantity):
        return ("quantity", value.text())
    if isinstance(value, Range):
        return ("range", value.text())
    if value is None:
        return ("none", "")
    raise DslError(
        f"parameter `{param}` of block `{block}`: a `{type(value).__name__}` cannot be recorded; pass a "
        "recordable value (bool, int, str, Length, Quantity, Range or None) or build the object inside "
        "the block"
    )


class BlockDef:
    """A block definition: its name, its function and the keyword parameters with their defaults; a block
    with an id also has its record ``header`` (change c0268), and its name is the id."""

    def __init__(
        self,
        name: str,
        function: Callable[..., object],
        keywords: Mapping[str, object],
        *,
        header: Header | None = None,
        params: Mapping[str, ParamMeta] | None = None,
    ) -> None:
        self.name = name
        self.function = function
        self.keywords: Mapping[str, object] = MappingProxyType(dict(keywords))
        """Keyword parameter → its default, or ``inspect.Parameter.empty`` for a required one."""
        self.header = header
        """The record header of ``@block(id=, version=, ...)``; ``None`` for a project block."""
        self.params: Mapping[str, ParamMeta] = MappingProxyType(
            dict(params) if params is not None else {key: ParamMeta(key) for key in keywords}
        )
        """Keyword parameter → its metadata (``param``), checked at ``use``."""

    @property
    def version(self) -> str:
        """The record's version; empty for a project block."""
        return self.header.version if self.header is not None else ""

    def __call__(self, *args: object, **kwargs: object) -> None:
        raise DslError(
            f"block {self.name} is not called directly; make an instance with "
            f"design.use({self.name}, <instance name>, ...) or b.use(...) inside a block"
        )

    def __repr__(self) -> str:
        return f"BlockDef({self.name!r})"


def _define(function: object, name: str | None, record_keywords: Mapping[str, object]) -> BlockDef:
    if not callable(function):
        raise DslError(f"@block decorates a function, not {function!r}")
    given_id = record_keywords.get("id")
    header: Header | None = None
    if given_id is not None:
        label = str(given_id)
        header = check_header(
            label,
            cast(str, getattr(function, "__module__", "")),
            **record_keywords,  # pyright: ignore[reportArgumentType]
        )
    else:
        label = name if name is not None else cast(str, getattr(function, "__name__", ""))
        label = check_name(label, "block name")
    parameters = list(inspect.signature(function).parameters.values())
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if not parameters or parameters[0].kind not in positional:
        raise DslError(f"block {label}: the first parameter is the builder, such as `def {label}(b, *, ...)`")
    keywords: dict[str, object] = {}
    metas: dict[str, ParamMeta] = {}
    for parameter in parameters[1:]:
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            stars = "*" if parameter.kind is inspect.Parameter.VAR_POSITIONAL else "**"
            raise DslError(
                f"block {label}: {stars}{parameter.name} is refused; every parameter after the builder is a "
                "named keyword-only parameter"
            )
        if parameter.kind is not inspect.Parameter.KEYWORD_ONLY:
            raise DslError(
                f"block {label}: parameter {parameter.name} must be keyword-only; parameters must be "
                f"keyword-only after the builder: def {label}(b, *, {parameter.name}=...)"
            )
        given = REQUIRED if parameter.default is _EMPTY else parameter.default
        meta = check_param(label, parameter.name, given)
        metas[parameter.name] = meta
        keywords[parameter.name] = _EMPTY if meta.required else meta.default
    return BlockDef(label, function, keywords, header=header, params=metas)


RECORD_KEYWORDS: tuple[str, ...] = (
    "id", "version", "summary", "category", "licence", "evidence", "sources", "replaces", "deprecated",
)  # fmt: skip
"""The keywords of ``@block`` that give a block its record (change c0268)."""


@overload
def block(function: Callable[..., None], /) -> BlockDef: ...


@overload
def block(
    *,
    name: str | None = None,
    id: str | None = None,  # noqa: A002 - the record's id
    version: str | None = None,
    summary: str = "",
    category: str = "other",
    licence: str | None = None,
    evidence: str = "INFERRED",
    sources: Sequence[str] = (),
    replaces: str | None = None,
    deprecated: Mapping[str, str] | None = None,
) -> Callable[[Callable[..., None]], BlockDef]: ...


def block(
    function: Callable[..., None] | None = None,
    /,
    *,
    name: str | None = None,
    id: str | None = None,  # noqa: A002 - the record's id
    version: str | None = None,
    summary: str = "",
    category: str = "other",
    licence: str | None = None,
    evidence: str = "INFERRED",
    sources: Sequence[str] = (),
    replaces: str | None = None,
    deprecated: Mapping[str, str] | None = None,
) -> BlockDef | Callable[[Callable[..., None]], BlockDef]:
    """Mark ``def name(b, *, param=default, ...)`` as a block: ``@block`` or ``@block(name="buck")``; or
    give it a record with ``@block(id="Acme:divider", version="1.0.0", summary=..., licence=...)`` and
    ``category``, ``evidence``, ``sources``, ``replaces`` and ``deprecated`` (``docs/dsl.md``, "Block
    records"). A block with an id is named by it, and its version is kept in the design lock.

    The signature is checked here: the builder is the one positional parameter, every other parameter is
    keyword-only with a recordable default, a ``param(...)`` or none, and there is no ``*args`` and no
    ``**kwargs``."""
    if name is not None and not isinstance(name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"@block(name=...) takes a str, not {name!r}")
    if name is not None and id is not None:
        raise DslError("@block: give name or id, not both; a block with an id is named by its id")
    if (id is None) != (version is None):
        raise DslError("@block: id and version go together; give both, or neither for a project block")
    keywords: dict[str, object] = {}
    if id is not None:
        keywords = {
            "id": id, "version": version, "summary": summary, "category": category, "licence": licence,
            "evidence": evidence, "sources": sources, "replaces": replaces, "deprecated": deprecated,
        }  # fmt: skip
    elif (summary, category, licence, evidence, tuple(sources), replaces, deprecated) != (
        "", "other", None, "INFERRED", (), None, None,
    ):  # fmt: skip
        raise DslError("@block: the record keywords need an id and a version")
    if function is None:

        def decorate(found: Callable[..., None]) -> BlockDef:
            return _define(found, name, keywords)

        return decorate
    return _define(function, name, keywords)


class Block(Module):
    """A block instance: a ``Module`` with ports, local nets, local part names and recorded parameters. It is
    the builder ``b`` that the block's function receives."""

    def __init__(self, name: str, definition: BlockDef, params: Mapping[str, object]) -> None:
        super().__init__(check_name(name, "block instance name"))
        self.definition = definition
        self._params: Mapping[str, object] = MappingProxyType(dict(sorted(params.items())))
        self.records: tuple[tuple[str, str, str], ...] = tuple(
            (key, *record(value, block=definition.name, param=key)) for key, value in self._params.items()
        )
        """``(name, type, text)`` of every parameter, by name (``BlockParam``)."""
        self.ports: dict[str, PortHandle] = {}
        self.port_docs: dict[str, str] = {}
        """The ``doc`` of each documented port (change c0268): kept for ``describe``, not in the model."""
        self.local_nets: dict[str, Net] = {}
        self.pose: Pose | LiveRequest | None = None
        """The pose of ``inst.place(...)`` in the parent frame (change c0255), or ``None`` (the identity)."""
        self.body_layout: Strategy | Reuse | None = None
        """The strategy or reuse of ``b.layout(...)`` in the body: the block's default."""
        self.instance_layout: Strategy | Reuse | None = None
        """The strategy or reuse of ``inst.layout(...)``, which wins over the body's."""
        self.query_defaults: dict[str, dict[str, Constraint | None]] = {}
        """``b.defaults()``: the block level of the defaults of part queries (change c0254)."""
        self.schematic_groups: tuple[SheetGroup, ...] | None = None
        """The block-local schematic groups of ``schematic``, resolved; ``None`` before the call (c0269)."""

    @property
    def params(self) -> Mapping[str, object]:
        """The bound parameters, the defaults applied (read-only)."""
        return self._params

    def describe(self) -> str:
        return f"block {self.path} ({self.definition.name})"

    def defaults(self, **kinds: object) -> None:
        """The block-level defaults of part queries, between the design's and the call's: per kind a
        mapping of its constraint keys; ``None`` removes a key (``docs/picking.md``, "Defaults")."""
        from fenolite.dsl.query import set_defaults

        set_defaults(self.query_defaults, kinds, f"{self.describe()}: defaults()")

    def _local_part(self, name: str) -> Part | None:
        return next((c for c in self.children if isinstance(c, Part) and c.key == name), None)

    def part(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        name: str,
        lib_id: str | None = None,
        *,
        footprint: str | None = None,
        value: str | Quantity | Range | None = None,
        ref: str | None = None,
        prefix: str | None = None,
        device: str | PartQuery | None = None,
        properties: Mapping[str, str] | None = None,
        pad_map: Mapping[str, str | Sequence[str]] | None = None,
        height: object = None,
    ) -> Part:
        """Create the part of local name ``name`` (the leaf of its path), add it and return it. Its board
        ref is ``ref`` when given, else the lock's or the allocator's (``docs/dsl.md``, "Blocks"); a
        ``device=`` part takes its symbol, footprint and prefix from the device (change c0248)."""
        from fenolite.dsl.devices import design_records

        check_name(name, "local part name")
        if self._local_part(name) is not None:
            raise DslError(
                f"{self.describe()}: the local part name {name} is used twice ({self.path}/{name})"
            )
        design = self.design
        with design_records(design.device_records if design is not None else {}):
            made = Part(
                ref,
                lib_id,
                footprint,
                value,
                name=name,
                prefix=prefix,
                device=device,
                properties=properties,
                pad_map=pad_map,
                height=height,
            )
        self.add(made)
        return made

    def add(self, *objs: Part | Module | Net | Interface) -> None:
        """As ``Module.add``; a ``Part`` without a name is named by its ref, which becomes its local name, and
        gets its board ref as a part of ``b.part`` does."""
        for obj in objs:
            if not isinstance(obj, Part) or obj.parent is not None:
                continue
            if obj.name is None and obj.explicit_ref is not None:
                local = obj.explicit_ref
                if obj.prefix is None:
                    found = LETTERS.match(local)
                    if found is None:
                        raise DslError(
                            f"{self.describe()}: part {local} becomes the local name {local}, and its board "
                            "ref needs a prefix; give prefix=... or use b.part(...)"
                        )
                    obj.prefix = found.group(0)
                obj.name = local
                obj.explicit_ref = None
            if self._local_part(obj.key) is not None:
                raise DslError(
                    f"{self.describe()}: the local part name {obj.key} is used twice ({self.path}/{obj.key})"
                )
        super().add(*objs)

    def net(self, name: str) -> Net:
        """A local net named ``<block path>/<name>``, added to the block."""
        check_name(name, "local net name")
        self._free(name, "local net")
        made = Net(f"{self.path}/{name}")
        self.local_nets[name] = made
        self.add(made)
        return made

    def _free(self, name: str, what: str) -> None:
        if name in self.ports or name in self.local_nets:
            taken = "port" if name in self.ports else "local net"
            raise DslError(f"{self.describe()}: the {what} name {name} is taken by a {taken} of the block")

    def port(
        self,
        name: str,
        kind: type = Net,
        *,
        direction: str = "inout",
        optional: bool = False,
        members: Sequence[str] | None = None,
        selects: int | None = None,
        requires: Sequence[str] = (),
        reference: object = None,
        share: bool = False,
        doc: str = "",
        **params: object,
    ) -> PortHandle:
        """Declare the port ``name`` of interface type ``kind`` (``Net`` or an ``Interface`` class) and
        ``direction`` (``in``, ``out`` or ``inout``). ``optional`` silences ``build.port-unused``. Change
        c0252: ``params`` are the parameters of the kind's table for that direction (``PARAMETERS``;
        ``current`` needs ``direction="in"`` or ``"out"``), ``reference`` the rail its levels refer to,
        ``share`` lets an out power port share its rail, and ``requires`` its companions."""
        check_name(name, "port name")
        if name in RESERVED_PORT_NAMES:
            raise DslError(
                f"{self.describe()}: the port name {name!r} is an attribute of a block instance "
                f"({', '.join(RESERVED_PORT_NAMES)}); choose another"
            )
        self._free(name, "port")
        if direction not in DIRECTIONS:
            raise DslError(
                f"{self.describe()}: port {name}: direction {direction!r} is not one of "
                f"{', '.join(DIRECTIONS)}"
            )
        if not isinstance(optional, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{self.describe()}: port {name}: optional must be a bool, not {optional!r}")
        kind_name = _kind(kind, f"{self.describe()}: port {name}")
        names = _members(kind_name, members, selects, f"{self.describe()}: port {name}")
        self._sheet_names_free(name, kind_name, names)
        handle = PortHandle(self, name, kind_name, direction, optional, names)
        handle.requires = check_requires(requires, kind_name, direction, f"{self.describe()}: port {name}")
        handle.set(reference=reference, share=share or None, **params)
        if doc:
            self.port_docs[name] = _port_doc(doc, f"{self.describe()}: port {name}: doc")
        elif not isinstance(doc, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{self.describe()}: port {name}: doc is a text")
        self.ports[name] = handle
        return handle

    def _sheet_names_free(self, name: str, kind: str, members: Sequence[str]) -> None:
        """Refuse a port whose sheet name (``<port>`` or ``<port>_<member>``, change c0269) equals one of an
        earlier port of the block."""
        taken = {
            sheet_name(other.name, member, other.kind): other.name
            for other in self.ports.values()
            for member in other.members
        }
        for member in members:
            wanted = sheet_name(name, member, kind)
            if wanted in taken:
                raise DslError(
                    f"{self.describe()}: port {name}: its sheet name {wanted} is the sheet name of the port "
                    f"{taken[wanted]}; KiCad pins and Altium entries would be one; rename one of the ports"
                )

    def schematic(self, *groups: SchematicGroup) -> None:
        """Declare, once, the schematic groups of the block's own parts (``schematic_group``): their order,
        anchors and flow, reused by every instance (``docs/dsl.md``, "Block schematic groups")."""
        self.schematic_groups = declare(self, groups)

    def expect(self, test: object, reason: str) -> None:
        """Record an expectation of this block instance (change c0253): ``within(a, b)``, ``at_least(a, b)``
        or ``at_most(a, b)`` with its reason, judged by the stage ``circuit.rules`` on every check. Its id is
        ``<instance path>/expect#<n>``."""
        from fenolite.dsl.contracts import expect_in

        expect_in(self, test, reason)

    def use(self, definition: BlockDef, name: str, **params: object) -> BlockInstance:
        """A nested instance of ``definition`` named ``name`` inside this block."""
        return instantiate(self, definition, name, params)

    def layout(self, strategy: object = None, *, reuse: object = None, copper: object = False) -> None:
        """The block's default layout (``docs/dsl.md``, "Block layout"): a strategy (``row()``,
        ``column()``, ``grid()``, ``pack()``) for its parts that nothing else places, or ``reuse=PATH``, a
        board laid out for the block alone, relative to the file that defines the block (``copper=True``
        also copies its copper). An instance's ``layout()`` wins over it."""
        root = block_root(self) if reuse is not None else None
        self.body_layout = set_layout(
            self.body_layout, strategy, reuse, copper, what=f"{self.describe()}: layout()", root=root
        )

    def __repr__(self) -> str:
        return f"Block({self.name!r}, {self.definition.name!r})"


def _port_doc(doc: object, what: str) -> str:
    if not isinstance(doc, str) or "\n" in doc or "\r" in doc or len(doc) > 200:
        raise DslError(f"{what} is one line of at most 200 characters")
    return doc


REQUIRES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "chip_select": ("spi",),
        "pullup": ("i2c", "logic"),
        "supply": ("i2c", "logic", "power", "spi", "uart", "usb2"),
    }
)
"""The closed vocabulary of a port's companions (change c0252) → the kinds that take each entry; the same
table as ``fenolite.model.circuit.REQUIRES``."""


def check_requires(requires: object, kind: str, direction: str, what: str) -> tuple[str, ...]:
    """``requires`` as a sorted tuple of entries of ``REQUIRES`` that ``kind`` takes; ``DslError`` naming
    the entry and the kind otherwise. ``supply`` on a ``power`` port needs ``direction="in"``."""
    if isinstance(requires, str) or not isinstance(requires, Sequence):
        raise DslError(
            f"{what}: requires is a list of entries such as ('pullup', 'supply'), not {requires!r}"
        )
    found: set[str] = set()
    for entry in cast(Sequence[object], requires):
        kinds = REQUIRES.get(entry) if isinstance(entry, str) else None
        if kinds is None:
            raise DslError(f"{what}: requires entry {entry!r} is not one of {', '.join(REQUIRES)}")
        if kind not in kinds:
            raise DslError(f"{what}: requires entry {entry!r} is not taken by a {kind} port")
        if entry == "supply" and kind == "power" and direction != "in":
            raise DslError(f"{what}: requires entry 'supply' is taken by an in power port")
        found.add(cast(str, entry))
    return tuple(sorted(found))


def _kind(kind: object, what: str) -> str:
    if kind is Net:
        return "net"
    if isinstance(kind, type) and issubclass(kind, Interface):
        for cls in kind.__mro__:
            found = PORT_KINDS.get(cls)
            if found is not None:
                return found
    raise DslError(f"{what}: kind is Net or an interface class such as I2C, not {kind!r}")


def _members(kind: str, members: Sequence[str] | None, selects: int | None, what: str) -> tuple[str, ...]:
    if kind == "harness":
        if members is None or isinstance(members, str) or not members:
            raise DslError(f"{what}: a harness port takes members=(...), its entry names")
        names = tuple(check_name(m, "harness member") for m in members)
        if len(set(names)) != len(names):
            raise DslError(f"{what}: a harness member is named twice")
        if selects is not None:
            raise DslError(f"{what}: selects belongs to an SPI port")
        return names
    if members is not None:
        raise DslError(f"{what}: members belongs to a harness port")
    if kind == "spi" and selects is not None:
        if isinstance(selects, bool) or not isinstance(selects, int) or selects < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{what}: selects is a count of chip selects, not {selects!r}")
        return ("sck", "mosi", "miso", *(f"cs{index}" for index in range(selects)))
    if selects is not None:
        raise DslError(f"{what}: selects belongs to an SPI port")
    return PORT_MEMBERS[kind]


class BlockInstance(Edges):
    """What ``use`` returns: the ports of the instance as attributes (``inst.VIN``) and through
    ``port(name)``, and ``path``, ``block``, ``params`` and ``part(local_name)``; ``place(...)`` and
    ``layout(...)`` set its pose and its layout, and its edges are placement references of its box
    (change c0255)."""

    __slots__ = ("_block",)

    def __init__(self, block: Block) -> None:
        self._block = block

    @property
    def path(self) -> str:
        return self._block.path

    @property
    def block(self) -> BlockDef:
        return self._block.definition

    @property
    def params(self) -> Mapping[str, object]:
        return self._block.params

    @property
    def module(self) -> Block:
        """The instance's ``Block``, a module of the design."""
        return self._block

    def part(self, local_name: str) -> Part:
        """The part of the instance whose local name is ``local_name``."""
        found = self._block._local_part(local_name)  # pyright: ignore[reportPrivateUsage]
        if found is None:
            raise DslError(f"{self._block.describe()} has no part named {local_name}")
        return found

    def place(
        self,
        x: object = None,
        y: object = None,
        rot: int | str | float = 0,
        locked: bool = False,
        *,
        right_of: object = None,
        left_of: object = None,
        above: object = None,
        below: object = None,
        gap: object = None,
        align: str | None = None,
        left: object = None,
        right: object = None,
        top: object = None,
        bottom: object = None,
        center_x: object = None,
        center_y: object = None,
    ) -> None:
        """The pose of the instance in its parent frame: ``(x, y)`` and ``rot``, or a relation or edge keys
        measured on the block's box, as ``Part.place`` takes them. The placements of the block's parts are
        in the block's frame and move with it as one rigid group (``docs/dsl.md``, "Block layout")."""
        block = self._block
        what = block.describe()
        if block.pose is not None:
            raise DslError(f"{what} is already placed")
        keys = {
            "right_of": right_of, "left_of": left_of, "above": above, "below": below, "left": left,
            "right": right, "top": top, "bottom": bottom, "center_x": center_x, "center_y": center_y,
        }  # fmt: skip
        live = parse_request(
            what, x=x, y=y, rot=rot, side="top", locked=locked, keys=keys, gap=gap, align=align
        )
        if live is not None:
            check_frame(block, what, live)
            block.pose = live
            return
        if x is None or y is None:
            raise DslError(f"{what}: place() needs x and y, or a relation or edge keys")
        if not isinstance(locked, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{what}: locked must be a bool")
        block.pose = Pose(as_nm(x, name="x"), as_nm(y, name="y"), as_udeg(rot, name="rot"), locked)

    def layout(self, strategy: object = None, *, reuse: object = None, copper: object = False) -> None:
        """The layout of this instance, which wins over the body's ``b.layout(...)``: a strategy, or
        ``reuse=PATH`` relative to the script (``docs/dsl.md``, "Block layout")."""
        block = self._block
        block.instance_layout = set_layout(
            block.instance_layout, strategy, reuse, copper, what=f"{block.describe()}: layout()", root=None
        )

    def port(self, name: str) -> PortHandle:
        found = self._block.ports.get(name)
        if found is None:
            known = ", ".join(sorted(self._block.ports)) or "none"
            raise DslError(f"{self._block.describe()} has no port {name}; its ports: {known}")
        return found

    def __getattr__(self, name: str) -> PortHandle:
        if name.startswith("_"):
            raise AttributeError(name)
        found = self._block.ports.get(name)
        if found is None:
            known = ", ".join(sorted(self._block.ports)) or "none"
            raise AttributeError(f"{self._block.describe()} has no port {name}; its ports: {known}")
        return found

    def __repr__(self) -> str:
        return f"BlockInstance({self.path!r}, {self.block.name!r})"


def _bind(definition: BlockDef, params: Mapping[str, object]) -> dict[str, object]:
    """The keyword arguments of one instance, the defaults applied; refused before the function runs."""
    for given in params:
        if given not in definition.keywords:
            taken = ", ".join(definition.keywords) or "no parameter"
            raise DslError(f"block {definition.name}: unknown parameter {given!r}; it takes {taken}")
    values: dict[str, object] = {}
    for key, default in definition.keywords.items():
        if key in params:
            value = params[key]
        elif default is _EMPTY:
            raise DslError(f"block {definition.name}: parameter {key!r} is missing; it has no default")
        else:
            value = default
        record(value, block=definition.name, param=key)
        check_value(definition.name, definition.params[key], value)
        values[key] = value
    return values


def instantiate(
    parent: Container, definition: object, name: str, params: Mapping[str, object]
) -> BlockInstance:
    """Create the block instance ``name`` of ``definition`` in ``parent`` (``design.use`` and ``b.use``):
    bind the parameters, add the block, run the function with it, and return the instance."""
    if not isinstance(definition, BlockDef):
        raise DslError(f"use() takes a block made with @block, not {definition!r}")
    design: Design | None = parent.design
    if design is None:
        raise DslError(f"use(): {parent.describe()} is not in a design yet; add it first")
    known = design.block_defs.get(definition.name)
    if known is not None and known is not definition:
        raise DslError(
            f"use(): two different functions are named as the block {definition.name}; "
            "rename one, or give it @block(name=...)"
        )
    values = _bind(definition, params)
    made = Block(name, definition, values)
    parent.add(made)
    design.block_defs[definition.name] = definition
    result = definition.function(made, **values)
    if result is not None:
        raise DslError(
            f"block {definition.name} returned {type(result).__name__}; a block returns None, and use() "
            "gives the instance"
        )
    return BlockInstance(made)


def blocks(design: Design) -> tuple[Block, ...]:
    """The block instances of ``design``, in path order."""
    return tuple(m for _, m in sorted(design.modules.items()) if isinstance(m, Block))


__all__ = [
    "PORT_KINDS",
    "PORT_MEMBERS",
    "RECORD_KEYWORDS",
    "REQUIRES",
    "RESERVED_PORT_NAMES",
    "Block",
    "BlockDef",
    "BlockInstance",
    "PortHandle",
    "block",
    "blocks",
    "check_requires",
    "instantiate",
    "record",
]
