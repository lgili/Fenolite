# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private, bounded, portable binding of an unchanged imported native project (c0355)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from fenolite.backends.kicad import netnames, pro
from fenolite.backends.kicad.pcb import stored_net_name
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.core.errors import FormatError
from fenolite.lens.native_rule_context import ENCODING, MAX_BYTES, fingerprint
from fenolite.model.base import ExtBag
from fenolite.model.circuit import Net
from fenolite.model.design import Design

CERTIFICATE = "project.context.json"


def required(design: Design, project: str, *, native_rules: bool = False) -> bool:
    """Keep ordinary imports editable unless their native project/rules need the capsule."""
    settings = pro.read_project_text(project)["net_settings"]
    assignments = settings.get("netclass_assignments")
    if assignments is not None and assignments != {}:
        return True  # Includes malformed shapes: none may silently qualify as ordinary/default.

    # Predicate-only projection of the names emitted by Net(name), never a model/output rewrite.
    # Reader-derived ids and stored bags otherwise make update_project simulate the source reader,
    # rather than the ordinary DSL writer whose assignment/pattern representation we must compare.
    nets: list[Net] = []
    raw_drift = False
    for net in design.circuit.nets:
        ordinary = netnames.stored_name(net.name)
        raw_drift |= stored_net_name(net) != ordinary
        bag = net.ext.get("kicad", ExtBag())
        payload = tuple((key, value) for key, value in bag.payload if key != "stored") + (
            ("stored", ordinary),
        )
        nets.append(
            dataclasses.replace(net, ext={**net.ext, "kicad": dataclasses.replace(bag, payload=payload)})
        )
    projected = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=tuple(nets)))
    common = pro.read_project_text(pro.update_project(project, projected))["net_settings"]
    for key in ("netclass_assignments", "netclass_patterns"):
        # Presence, null, empty arrays and list order remain literal; no equality normalization.
        if (key in settings, settings.get(key)) != (key in common, common.get(key)):
            return True
    return native_rules and raw_drift


@dataclass(frozen=True, slots=True)
class NetRow:
    logical: str
    stored: str
    physical: tuple[tuple[str, str], ...]
    netclass: str | None


@dataclass(frozen=True, slots=True)
class Binding:
    receipt: Path
    target: int
    baseline: str
    project_sha256: str
    nets: tuple[NetRow, ...]


def _object(value: object, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(cast(dict[str, object], value)) != keys:
        raise FormatError("native project context has unexpected or missing object keys", locator=where)
    return cast(dict[str, Any], value)


def _digest(value: object, where: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise FormatError("native project context requires a lowercase SHA-256", locator=where)
    return value


def _portable(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 for c in value):
        raise FormatError("native project context source path is not portable")
    if PurePosixPath(value).is_absolute() or any(p in {"", ".", ".."} or ":" in p for p in value.split("/")):
        raise FormatError("native project context source path is not portable")
    return value


def _read(path: Path) -> bytes:
    if path.is_symlink():
        raise FormatError("native project context is a symlink", file=path.name)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError as error:
        raise FormatError("native project context is missing or unreadable", file=path.name) from error
    if len(raw) > MAX_BYTES:
        raise FormatError("native project context exceeds the byte limit", file=path.name)
    return raw


def read_binding(project: Path, project_bytes: bytes) -> Binding | None:
    receipt = project.with_name(CERTIFICATE)
    if not receipt.exists() and not receipt.is_symlink():
        return None

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise FormatError("native project context contains duplicate JSON keys")
            result[key] = value
        return result

    try:
        data = json.loads(_read(receipt), object_pairs_hook=unique)
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise FormatError("native project context is not valid JSON", file=receipt.name) from error
    data = _object(data, {"version", "target", "project", "source_inputs", "baseline", "nets"}, "/")
    if (
        type(data["version"]) is not int
        or data["version"] != 1
        or type(data["target"]) is not int
        or data["target"] not in (9, 10)
    ):
        raise FormatError("unsupported native project context version or target")
    pinned = _object(data["project"], {"path", "sha256"}, "project")
    digest = hashlib.sha256(project_bytes).hexdigest()
    if pinned["path"] != project.name or _digest(pinned["sha256"], "project") != digest:
        raise FormatError("native project context input binding differs")
    baseline = _object(data["baseline"], {"encoding", "sha256"}, "baseline")
    if baseline["encoding"] != ENCODING:
        raise FormatError("unsupported native project context fingerprint encoding")
    inputs = data["source_inputs"]
    if not isinstance(inputs, list) or not inputs:
        raise FormatError("native project context source inputs are missing")
    seen: set[str] = set()
    kinds: set[str] = set()
    project_bound = False
    for value in cast(list[object], inputs):
        row = _object(value, {"path", "sha256", "kind"}, "source_inputs")
        path = _portable(row["path"])
        if path.casefold() in seen or row["kind"] not in (
            "kicad_pcb",
            "kicad_pro",
            "kicad_sch",
            "kicad_dru",
            "kicad_wks",
        ):
            raise FormatError("native project context source inputs collide or have an unknown kind")
        seen.add(path.casefold())
        kinds.add(row["kind"])
        source_sha = _digest(row["sha256"], "source_inputs")
        project_bound |= row["kind"] == "kicad_pro" and source_sha == digest
    if "kicad_pcb" not in kinds or not project_bound:
        raise FormatError("native project context source hashes do not bind its original project and board")
    rows = data["nets"]
    if not isinstance(rows, list) or not rows:
        raise FormatError("native project context nets are missing")
    nets: list[NetRow] = []
    logicals: set[str] = set()
    stored: set[str] = set()
    terminals: set[tuple[str, str]] = set()
    for value in cast(list[object], rows):
        row = _object(value, {"logical", "stored", "physical", "class"}, "nets")
        if any(
            not isinstance(row[key], str) or not row[key] or "\0" in row[key] for key in ("logical", "stored")
        ):
            raise FormatError("native project context net names are invalid")
        physical = row["physical"]
        if not isinstance(physical, list) or not physical:
            raise FormatError("native project context physical partition is invalid")
        pairs: list[tuple[str, str]] = []
        for value in cast(list[object], physical):
            if not isinstance(value, list):
                raise FormatError("native project context terminal identity is invalid")
            if len(cast(list[object], value)) != 2:
                raise FormatError("native project context terminal identity is invalid")
            pair = cast(list[object], value)
            if any(not isinstance(p, str) or not p or "\0" in p for p in pair):
                raise FormatError("native project context terminal identity is invalid")
            pairs.append((cast(str, pair[0]), cast(str, pair[1])))
        partition = tuple(pairs)
        if (
            tuple(sorted(set(partition))) != partition
            or terminals.intersection(partition)
            or row["logical"] in logicals
            or row["stored"] in stored
        ):
            raise FormatError("native project context net names or physical partitions collide")
        if row["class"] is not None and (not isinstance(row["class"], str) or not row["class"]):
            raise FormatError("native project context class is invalid")
        logicals.add(row["logical"])
        stored.add(row["stored"])
        terminals.update(partition)
        nets.append(NetRow(row["logical"], row["stored"], partition, row["class"]))
    return Binding(receipt, data["target"], _digest(baseline["sha256"], "baseline"), digest, tuple(nets))


def _partitions(design: Design) -> dict[str, tuple[tuple[str, str], ...]]:
    # Reuse the existing complete numbered-terminal proof, then retain unambiguous tuple identities.
    from fenolite.backends.kicad.native_net_binding import bindings

    try:
        canonical = bindings(design)
    except ValueError as error:
        raise FormatError(f"native project physical binding is ambiguous: {error}") from error
    if set(canonical) != {net.name for net in design.circuit.nets if net.name} or len(
        set(canonical.values())
    ) != len(canonical):
        raise FormatError("native project requires complete unambiguous physical net coverage")
    refs = {component.id: component.ref for component in design.circuit.components}
    terminals: dict[str, tuple[str, str]] = {}
    for footprint in design.board.footprints if design.board is not None else ():
        reference = refs.get(footprint.component_id)
        for pad in footprint.pads:
            if not pad.number or pad.net_id is None:
                continue
            if not reference:
                raise FormatError("native project physical terminal has no reference")
            key, pair = reference + "-" + pad.number, (reference, pad.number)
            if key in terminals and terminals[key] != pair:
                raise FormatError("native project physical terminal spelling is ambiguous")
            terminals[key] = pair
    try:
        return {
            name: tuple(sorted(terminals[key] for key in physical)) for name, physical in canonical.items()
        }
    except KeyError as error:
        raise FormatError("native project physical terminal is unbound") from error


def _classes(design: Design) -> dict[str, str | None]:
    classes = {cls.id: cls.name for cls in design.circuit.netclasses}
    if any(net.netclass_id is not None and net.netclass_id not in classes for net in design.circuit.nets):
        raise FormatError("native project net names an unknown model class")
    return {
        net.name: classes.get(net.netclass_id) if net.netclass_id is not None else None
        for net in design.circuit.nets
        if net.name
    }


def restore(
    design: Design, binding: Binding, project: str, target: int
) -> tuple[Design, pro.NativeNetContext]:
    if target != binding.target or fingerprint(design) != binding.baseline:
        raise FormatError("native project context requires the unchanged complete imported model and target")
    partitions, classes = _partitions(design), _classes(design)
    if {row.logical: row.physical for row in binding.nets} != partitions or {
        row.logical: row.netclass for row in binding.nets
    } != classes:
        raise FormatError("native project context physical partitions or class membership changed")
    names = {row.logical: row.stored for row in binding.nets}
    nets: list[Net] = []
    for net in design.circuit.nets:
        if not net.name:
            nets.append(net)
            continue
        bag = net.ext.get("kicad", ExtBag())
        kept = [value for key, value in bag.payload if key == "stored"]
        if (
            any(key != "stored" for key, _ in bag.payload)
            or len(kept) > 1
            or (kept and kept[0] != names[net.name])
        ):
            raise FormatError("native project context conflicts with an existing stored net name")
        payload = tuple((key, value) for key, value in bag.payload if key != "stored") + (
            ("stored", names[net.name]),
        )
        nets.append(
            dataclasses.replace(net, ext={**net.ext, "kicad": dataclasses.replace(bag, payload=payload)})
        )
    restored = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=tuple(nets)))
    policy = pro.native_net_context(project, restored, target)
    return restored, policy


@dataclass
class Capture:
    name: str
    target: int
    source: Design
    board: bytes
    project: str
    inputs: Sequence[Mapping[str, object]]
    owner: Path | None = None
    binding: Binding | None = None
    count: int = 0

    def certificate(self) -> bytes:
        if self.binding is None or self.count != 1:
            raise FormatError("native project baseline requires exactly one actual lowered model")
        data = {
            "version": 1,
            "target": self.target,
            "project": {"path": "project.kicad_pro", "sha256": self.binding.project_sha256},
            "source_inputs": list(self.inputs),
            "baseline": {"encoding": ENCODING, "sha256": self.binding.baseline},
            "nets": [
                {
                    "logical": row.logical,
                    "stored": row.stored,
                    "physical": [list(pair) for pair in row.physical],
                    "class": row.netclass,
                }
                for row in self.binding.nets
            ],
        }
        raw = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()
        if len(raw) > MAX_BYTES:
            raise FormatError("native project context exceeds the byte limit")
        return raw


@dataclass(frozen=True)
class Scope:
    owner: Path
    name: str
    target: int
    binding: Binding | None
    project: str | None


_CAPTURE: ContextVar[Capture | None] = ContextVar("native_project_import_capture", default=None)
_SCOPE: ContextVar[Scope | None] = ContextVar("native_project_build_scope", default=None)


@contextmanager
def capture_import(
    name: str, target: int, source: Design, board: bytes, project: str, inputs: Sequence[Mapping[str, object]]
) -> Generator[Capture]:
    if _CAPTURE.get() is not None:
        raise FormatError("nested native project baseline capture is refused")
    capture = Capture(name, target, source, board, project, inputs)
    token = _CAPTURE.set(capture)
    try:
        yield capture
        if capture.binding is None or capture.count != 1:
            raise FormatError("native project baseline requires exactly one actual lowered model")
    finally:
        _CAPTURE.reset(token)


@contextmanager
def import_owner(owner: Path) -> Generator[None]:
    capture = _CAPTURE.get()
    if capture is not None:
        if capture.owner is not None:
            raise FormatError("native project baseline owner is already bound")
        capture.owner = owner.resolve()
    yield


@contextmanager
def build_scope(
    owner: Path, name: str, target: int, binding: Binding | None, project: str | None
) -> Generator[None]:
    if _SCOPE.get() is not None:
        raise FormatError("nested native project build scope is refused")
    token = _SCOPE.set(Scope(owner.resolve(), name, target, binding, project))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def before_write(design: Design, name: str, target: int) -> tuple[Design, pro.NativeNetContext | None]:
    scope, capture = _SCOPE.get(), _CAPTURE.get()
    if scope is None:
        if capture is not None:
            raise FormatError("native project capture has no owning build scope")
        return design, None
    if scope.name != name or scope.target != target:
        raise FormatError("native project context project or target differs")
    binding = scope.binding
    project = scope.project
    if capture is not None:
        if (
            capture.owner != scope.owner
            or capture.name != name
            or capture.target != target
            or capture.count
            or binding is not None
            or project != capture.project
        ):
            raise FormatError("native project capture owner/project/target or multiplicity differs")
        from fenolite.backends.kicad.native_net_binding import raw_bindings

        canonical = _partitions(design)
        strings = {part: tuple(sorted(ref + "-" + pad for ref, pad in part)) for part in canonical.values()}
        if len(set(strings.values())) != len(strings):
            raise FormatError("native project physical terminal encoding collides")
        try:
            raw = raw_bindings(parse_bytes(capture.board), frozenset(strings.values()))
        except ValueError as error:
            raise FormatError(f"native project source physical binding differs: {error}") from error
        source_partitions = _partitions(capture.source)
        if frozenset(source_partitions.values()) != frozenset(canonical.values()):
            raise FormatError("native project source complete physical partitions differ")
        source_classes, classes = _classes(capture.source), _classes(design)
        source_by_part = {part: logical for logical, part in source_partitions.items()}
        native_by_strings = {part: native for native, part in raw.items()}
        names = {part: native_by_strings[signature] for part, signature in strings.items()}
        rows: list[NetRow] = []
        for logical, physical in sorted(canonical.items()):
            if classes[logical] != source_classes[source_by_part[physical]]:
                raise FormatError("native project source class membership differs")
            rows.append(NetRow(logical, names[physical], physical, classes[logical]))
        binding = Binding(
            Path(CERTIFICATE),
            target,
            fingerprint(design),
            hashlib.sha256(capture.project.encode()).hexdigest(),
            tuple(rows),
        )
        capture.binding = binding
        capture.count += 1
    if binding is None:
        return design, None
    if project is None or hashlib.sha256(project.encode()).hexdigest() != binding.project_sha256:
        raise FormatError("native project context project bytes differ")
    return restore(design, binding, project, target)
