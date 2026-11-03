# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed immutable native-rule input binding and isolated import capture (c0359)."""

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

from fenolite import __version__
from fenolite.backends.kicad import dru
from fenolite.core.errors import FormatError
from fenolite.model import canonical
from fenolite.model.design import Design

ENCODING = "canonical-design-v1-tool-version-neutral"
CERTIFICATE = "project.rules-context.json"
MAX_BYTES = 16 * 1024 * 1024


def fingerprint(design: Design) -> str:
    """Bind the whole model, except the explicitly neutral tool-version metadata value."""
    copy = dataclasses.replace(design, header=dataclasses.replace(design.header, fenolite_version=""))
    return hashlib.sha256(canonical.dumps(copy).encode("utf-8")).hexdigest()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def certificate(
    project: bytes,
    rules: bytes,
    design: Design,
    target: int,
    inputs: Sequence[Mapping[str, object]],
    *,
    emitted_pcb: bytes,
    emitted_project: bytes,
) -> bytes:
    data = {
        "version": 1,
        "target": target,
        "project": {"path": "project.kicad_pro", "sha256": _sha(project)},
        "rules": {"path": "project.kicad_dru", "sha256": _sha(rules)},
        "source_inputs": list(inputs),
        "baseline": {
            "encoding": ENCODING,
            "sha256": fingerprint(design),
            "producer_tool_version": __version__,
            "emitted_pcb_sha256": _sha(emitted_pcb),
            "emitted_project_sha256": _sha(emitted_project),
        },
    }
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _object(value: object, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormatError("native rule context is not an object", locator=where)
    row = cast(dict[str, Any], value)
    if set(row) != keys:
        raise FormatError("native rule context has unexpected or missing keys", locator=where)
    return row


def _digest(value: object, where: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise FormatError("native rule context requires a lowercase SHA-256", locator=where)
    return value


def _portable(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 for c in value):
        raise FormatError("native rule context input path is not portable")
    parts = value.split("/")
    if PurePosixPath(value).is_absolute() or any(p in {"", ".", ".."} or ":" in p for p in parts):
        raise FormatError("native rule context input path is not portable")
    return value


@dataclass(frozen=True, slots=True)
class Binding:
    project: Path
    rules: Path
    receipt: Path
    raw: bytes
    target: int
    baseline: str
    emitted_pcb: str
    emitted_project: str


def _read(path: Path) -> bytes:
    if path.is_symlink():
        raise FormatError("native rule input is a symlink", file=path.name)
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError as error:
        raise FormatError("native rule input is missing or unreadable", file=path.name) from error
    if len(data) > MAX_BYTES:
        raise FormatError("native rule input exceeds the byte limit", file=path.name)
    return data


def read_binding(project: Path, project_bytes: bytes) -> Binding | None:
    """An explicitly declared project's exact sibling inputs; absent siblings preserve defaults."""
    rules = project.with_suffix(".kicad_dru")
    receipt = project.with_name(CERTIFICATE)
    if not rules.exists() and not rules.is_symlink() and not receipt.exists() and not receipt.is_symlink():
        return None
    raw = _read(rules)
    if not receipt.exists() and not receipt.is_symlink():
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FormatError("native rules are not UTF-8", file=rules.name) from error
        document = dru.parse_rules(text, file=rules.name)
        lifted = dru.read_rules(text, file=rules.name)
        if document.version == dru.RULES_VERSION and sum(
            isinstance(item, dru.RuleItem) for item in document.items
        ) == len(lifted.rules):
            return None  # Existing pro-only ownership of fully modelled sibling programs.

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise FormatError("native rule context contains duplicate JSON keys", file=receipt.name)
            result[key] = value
        return result

    try:
        data = json.loads(_read(receipt).decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise FormatError("native rule context is not valid JSON", file=receipt.name) from error
    data = _object(data, {"version", "target", "project", "rules", "source_inputs", "baseline"}, "/")
    if (
        type(data["version"]) is not int
        or data["version"] != 1
        or type(data["target"]) is not int
        or data["target"] not in (9, 10)
    ):
        raise FormatError("unsupported native rule context version or target")
    for key, expected, content in (("project", project.name, project_bytes), ("rules", rules.name, raw)):
        row = _object(data[key], {"path", "sha256"}, key)
        if row["path"] != expected or _digest(row["sha256"], key) != _sha(content):
            raise FormatError("native rule context input binding differs", locator=key)
    baseline = _object(
        data["baseline"],
        {"encoding", "sha256", "producer_tool_version", "emitted_pcb_sha256", "emitted_project_sha256"},
        "baseline",
    )
    if (
        baseline["encoding"] != ENCODING
        or not isinstance(baseline["producer_tool_version"], str)
        or not baseline["producer_tool_version"]
    ):
        raise FormatError("unsupported native rule context fingerprint encoding")
    digest = _digest(baseline["sha256"], "baseline")
    rows = data["source_inputs"]
    if not isinstance(rows, list) or not rows:
        raise FormatError("native rule context source inputs are missing")
    seen: set[str] = set()
    for value in cast(list[object], rows):
        row = _object(value, {"path", "sha256", "kind"}, "source_inputs")
        path = _portable(row["path"])
        if (
            path.casefold() in seen
            or not isinstance(row["kind"], str)
            or row["kind"]
            not in {
                "kicad_pcb",
                "kicad_pro",
                "kicad_sch",
                "kicad_dru",
                "kicad_wks",
            }
        ):
            raise FormatError("native rule context source inputs collide or have an unsupported kind")
        seen.add(path.casefold())
        _digest(row["sha256"], "source_inputs")
    typed_rows = cast(list[dict[str, Any]], rows)
    if not any(row["kind"] == "kicad_pcb" for row in typed_rows) or any(
        not any(row["kind"] == kind and row["sha256"] == digest for row in typed_rows)
        for kind, digest in (("kicad_pro", _sha(project_bytes)), ("kicad_dru", _sha(raw)))
    ):
        raise FormatError("native rule context source hashes do not bind its original project and rules")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError("native rules are not UTF-8", file=rules.name) from error
    from fenolite.backends.kicad.native_rule_profile import validate_profile

    validate_profile(text)
    # Existing full-dialect target gates/self-checks; preserve the original bytes, not their rewrite.
    dru.write_rules(dru.read_rules(text, file=rules.name), target=data["target"])
    return Binding(
        project,
        rules,
        receipt,
        raw,
        data["target"],
        digest,
        _digest(baseline["emitted_pcb_sha256"], "emitted_pcb"),
        _digest(baseline["emitted_project_sha256"], "emitted_project"),
    )


@dataclass
class Capture:
    name: str
    target: int
    owner: Path | None = None
    design: Design | None = None
    count: int = 0
    output_count: int = 0
    emitted_pcb: bytes | None = None
    emitted_project: bytes | None = None


@dataclass(frozen=True)
class Scope:
    owner: Path
    name: str
    target: int
    binding: Binding | None


_CAPTURE: ContextVar[Capture | None] = ContextVar("native_rule_import_capture", default=None)
_SCOPE: ContextVar[Scope | None] = ContextVar("native_rule_build_scope", default=None)


@contextmanager
def capture_import(name: str, target: int) -> Generator[Capture]:
    if _CAPTURE.get() is not None:
        raise FormatError("nested native rule baseline capture is refused")
    capture = Capture(name, target)
    token = _CAPTURE.set(capture)
    try:
        yield capture
        if (
            capture.count != 1
            or capture.design is None
            or capture.output_count != 1
            or capture.emitted_pcb is None
            or capture.emitted_project is None
        ):
            raise FormatError("native rule baseline requires exactly one actual lowered model capture")
    finally:
        _CAPTURE.reset(token)


@contextmanager
def import_owner(owner: Path) -> Generator[None]:
    capture = _CAPTURE.get()
    if capture is not None:
        if capture.owner is not None:
            raise FormatError("native rule baseline owner is already bound")
        capture.owner = owner.resolve()
    yield


@contextmanager
def build_scope(owner: Path, name: str, target: int, binding: Binding | None) -> Generator[None]:
    if _SCOPE.get() is not None:
        raise FormatError("nested native rule build scope is refused")
    token = _SCOPE.set(Scope(owner.resolve(), name, target, binding))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def before_write(design: Design, name: str, target: int) -> bytes | None:
    """Validate first, then optionally observe exactly this actual lowered model."""
    scope = _SCOPE.get()
    capture = _CAPTURE.get()
    if scope is None:
        if capture is not None:
            raise FormatError("native rule baseline has no owning build scope")
        return None
    if scope.name != name or scope.target != target:
        raise FormatError("native rule baseline project or target differs")
    binding = scope.binding
    if binding is not None and (target != binding.target or fingerprint(design) != binding.baseline):
        raise FormatError(
            "declared native rules require the unchanged complete imported model; "
            "review the native rule context before editing"
        )
    if capture is not None:
        if capture.owner != scope.owner or capture.name != name or capture.target != target or capture.count:
            raise FormatError("native rule baseline capture owner/project/target or multiplicity differs")
        capture.design = design
        capture.count += 1
    return binding.raw if binding is not None else None


def after_write(pcb_bytes: bytes, project_bytes: bytes, name: str, target: int) -> None:
    """Bind the complete actual emitted native bytes, including writer options/library effects."""
    scope = _SCOPE.get()
    capture = _CAPTURE.get()
    if scope is None:
        if capture is not None:
            raise FormatError("native rule output has no owning build scope")
        return
    if scope.name != name or scope.target != target:
        raise FormatError("native rule output project or target differs")
    binding = scope.binding
    if binding is not None and (
        _sha(pcb_bytes) != binding.emitted_pcb or _sha(project_bytes) != binding.emitted_project
    ):
        raise FormatError(
            "declared native rules require unchanged emitted PCB/project context; "
            "review resolved libraries and writer options"
        )
    if capture is not None:
        if capture.owner != scope.owner or capture.count != 1 or capture.output_count:
            raise FormatError("native rule output capture owner or multiplicity differs")
        capture.emitted_pcb = pcb_bytes
        capture.emitted_project = project_bytes
        capture.output_count += 1
