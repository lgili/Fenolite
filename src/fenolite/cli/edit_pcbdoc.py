# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite edit PATH.PcbDoc --ops-file FILE [--gate NAME]...``: the operations of a JSON list run on an
Altium edit session (``backends.altium.edit``) under the write protocol (change c0497, design D1;
``docs/cli-contract.md``, "edit").

Each entry is ``{"op": <Session method>, "item": <item>, ...keyword arguments}``. An item is a tagged object,
``{"kind": "via", "at": ["12.5mm", "3mm"], "net": "GND"}``; a length is integer nanometres or text with a
unit. The session's ``apply`` and ``verify`` give the bytes, planned as one write of kind ``pcbdoc``; its
issues keep their codes. ``--gate NAME`` opens one gate for this run, with ``altium.edit.gate-opened`` and the
evidence ``UNVERIFIED``; ``edit.GATES`` stays off.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import types
import typing
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from fenolite.cli.api import PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import parse_length

LIMIT = 1_000_000
"""The largest operations file, in bytes."""
OPS = frozenset({
    "delete", "move", "rotate", "flip", "set_property", "clone", "remap_layer", "set_rule", "set_outline",
    "add_arc", "add_fill", "add_region", "add_polygon", "declare_connectivity", "add_board_cutout",
    "add_polygon_cutout", "set_via_mask", "draw_board_shape",
})  # fmt: skip
"""The ``Session`` methods an entry may name (``add_component`` reads a second document: Python only)."""


def _items() -> dict[str, type]:
    from fenolite.backends.altium.edit import ops

    return {
        "track": ops.Track, "arc": ops.Arc, "fill": ops.Fill, "via": ops.Via, "vias": ops.Vias,
        "component": ops.Component, "polygon": ops.Polygon, "text": ops.Text, "region": ops.Region,
        "designator": ops.Designator, "comment": ops.Comment,
    }  # fmt: skip


def _fail(index: int, message: str) -> CliError:
    return CliError("FEN-2001", f"--ops-file entry {index}: {message}", where=f"--ops-file:{index}",
                    hint="docs/cli-contract.md, 'edit', lists the operations and the item kinds")  # fmt: skip


def _length(value: object, index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise _fail(index, f"{value!r} is not a length: give nanometres or text with a unit")
    if isinstance(value, int):
        return value
    try:
        return parse_length(value.strip())
    except ValueError as error:
        raise _fail(index, f"{value!r}: {error}") from None


def _convert(value: object, hint: object, index: int) -> object:
    """``value`` read as the type ``hint``: lengths as nanometres, points as tuples, items from objects."""
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin in (typing.Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        if isinstance(value, dict):
            return _item(cast("dict[str, Any]", value), index)
        kept = [a for a in args if a is not type(None)]
        return _convert(value, kept[0], index) if len(kept) == 1 or int in kept else value
    if hint is int:
        return _length(value, index)
    if hint is float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise _fail(index, f"{value!r} is not a number")
        return float(value)
    if hint is bool:
        if not isinstance(value, bool):
            raise _fail(index, f"{value!r} is not true or false")
        return value
    if origin is tuple:
        if not isinstance(value, list) or len(cast("list[object]", value)) != len(args):
            raise _fail(index, f"{value!r} is not a point [x, y]")
        return tuple(_convert(v, a, index) for v, a in zip(cast("list[object]", value), args, strict=True))
    if origin in (list, Sequence) or (
        isinstance(origin, type) and issubclass(origin, Sequence) and origin is not str
    ):
        if not isinstance(value, list):
            raise _fail(index, f"{value!r} is not a list")
        return [_convert(v, args[0], index) for v in cast("list[object]", value)]
    if isinstance(hint, type) and hint in _items().values():
        if not isinstance(value, dict):
            raise _fail(index, f"{value!r} is not an item object")
        return _item(cast("dict[str, Any]", value), index)
    return value


def _item(value: dict[str, Any], index: int) -> object:
    kinds = _items()
    kind = value.get("kind")
    if kind not in kinds:
        raise _fail(index, f"the item kind {kind!r} is not one of {', '.join(sorted(kinds))}")
    cls = kinds[str(kind)]
    hints = typing.get_type_hints(cls)
    fields = {k: v for k, v in value.items() if k != "kind"}
    unknown = set(fields) - set(hints)
    if unknown:
        raise _fail(index, f"the item {kind} has no field {', '.join(sorted(unknown))}")
    try:
        return cls(**{k: _convert(v, hints[k], index) for k, v in fields.items()})
    except TypeError as error:
        raise _fail(index, f"the item {kind}: {error}") from None


def _queue(session: Any, entry: object, index: int) -> None:
    if not isinstance(entry, dict):
        raise _fail(index, 'an entry is an object {"op": ..., ...}')
    given = dict(cast("dict[str, Any]", entry))
    op = given.pop("op", None)
    if op not in OPS:
        raise _fail(index, f"the op {op!r} is not one of {', '.join(sorted(OPS))}")
    method = getattr(session, str(op))
    hints = typing.get_type_hints(method)
    parameters = list(inspect.signature(method).parameters.values())
    if "item" in given and parameters and parameters[0].name in ("item", "selector"):
        given[parameters[0].name] = given.pop("item")
    names = {p.name for p in parameters}
    unknown = set(given) - names
    if unknown:
        raise _fail(index, f"{op} takes no argument {', '.join(sorted(unknown))}")
    args: list[object] = []
    kwargs: dict[str, object] = {}
    for parameter in parameters:
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            args += list(cast("list[object]", given.get("nets", [])))
            continue
        if parameter.name not in given:
            if parameter.default is inspect.Parameter.empty:
                raise _fail(index, f"{op} needs the argument {parameter.name}")
            continue
        kwargs[parameter.name] = _convert(given[parameter.name], hints.get(parameter.name), index)
    try:
        method(*args, **kwargs)
    except TypeError as error:
        raise _fail(index, f"{op}: {error}") from None


def _entries(path: Path) -> list[object]:
    data = path.read_bytes()
    if len(data) > LIMIT:
        raise CliError(
            "FEN-3004", f"the operations file {path.name} is larger than {LIMIT} bytes", where="--ops-file"
        )
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CliError("FEN-3004", f"--ops-file is not JSON: {error}", where="--ops-file") from error
    if not isinstance(raw, list):
        raise CliError("FEN-3004", "--ops-file must hold a list of operations", where="--ops-file")
    return cast("list[object]", raw)


def run_pcbdoc(path: Path, ops_file: Path, gates: list[str], cwd: Path) -> Result:
    from fenolite.backends.altium.edit import session as edit_session

    if not path.is_file():
        raise CliError("FEN-3001", f"{path.name} is not a file", where=path.name)
    unknown = sorted(set(gates) - set(edit_session.GATES))
    if unknown:
        raise CliError("FEN-2001", f"--gate: no gate is named {', '.join(unknown)}", where="--gate",
                       hint=f"the gates: {', '.join(edit_session.OPERATIONS)}")  # fmt: skip
    entries = _entries(ops_file)
    session = edit_session.open_document(path, gates=dict.fromkeys(gates, True))
    for index, entry in enumerate(entries):
        _queue(session, entry, index)
    old = session.data
    state, issues = session.apply()
    data: bytes | None = None
    records: list[dict[str, Any]] = []
    if state is not None:
        data, issues = edit_session.verify(old, state, declared_nets=session.declared_nets, file=path.name)
        removed = Counter(storage for (storage, _), n in state.removed.items() for _ in range(n))
        added = Counter(storage for (storage, _), n in state.added.items() for _ in range(n))
        records = [
            {"storage": name, "removed": removed[name], "added": added[name]}
            for name in sorted(set(removed) | set(added))
        ]
    opened = [
        Issue("altium.edit.gate-opened", "warning",
              f"the gate of {gate} is open for this run; rows {', '.join(edit_session.ROWS[gate])} are not "
              "confirmed by the kit", "--gate", "the written records are UNVERIFIED until Part J confirms")
        for gate in sorted(set(gates))
    ]  # fmt: skip
    from fenolite.cli.cmd_edit import _shown  # pyright: ignore[reportPrivateUsage]

    target = _shown(path, cwd)
    result: dict[str, Any] = {
        "path": target,
        "kind": "pcbdoc",
        "changed": data is not None and data != old,
        "operations": [q.label for q in session.queued],
        "records": records,
        "stale_pours": list(session.stale_pours),
        "redrawn": dict(session.redrawn),
    }
    evidence = edit_session.EVIDENCE
    if gates:
        evidence = Evidence(Level.UNVERIFIED, hypotheses=edit_session.HYPOTHESES)
    writes = (
        (PlannedWrite(path=target, data=data, kind="pcbdoc"),) if data is not None and data != old else ()
    )
    return Result(
        result=result,
        issues=(*opened, *issues),
        evidence=evidence,
        input=InputRef(
            path=path.name, sha256=hashlib.sha256(old).hexdigest(), kind="pcbdoc", format_version=None
        ),
        writes=writes,
        depends=depends_on(cwd, path, ops_file),
    )
