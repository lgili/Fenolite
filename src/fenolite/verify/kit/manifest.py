# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of the Altium verification kit and its manifest ``kit.json`` (capability
altium-verification, "Verification kit contents"; ``docs/altium-kit.md``).

A kit is a folder with ``kit.json``, ``STEPS.md``, the kit script, one folder per sample and ``results/``
with the blank form. Every byte is computed here from the built samples, the steps and the two build
inputs, so two builds with the same seed and timestamp are equal on every operating system: paths use
``/``, text is UTF-8 with LF line ends (the script, which Altium reads, has CR LF), and the manifest is
JSON with sorted keys.

``package-layering`` lets ``verify`` import ``model``, ``geometry`` and ``backends`` only, and building a
sample needs the DSL and the lens. The built samples are therefore an argument (``KitSources``):
``fenolite.cli._kit.kit_sources`` builds them from the scripts under ``examples/kit/``.

Stdlib and ``fenolite.core`` only (``tests/unit/verify/test_levels.py``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.core.io import sha256_bytes
from fenolite.verify.kit.script import LOG, PROCEDURE, SCRIPT_CALLS, SCRIPT_NAME, script_text
from fenolite.verify.kit.steps import KIT_SAMPLE, RESULTS, SAMPLES, STEPS, Step, steps_markdown

KIT_SCHEMA = "fenolite.altium-kit.v0"
FORM_SCHEMA = "fenolite.altium-kit-form.v0"
KIT_VERSION = 1
"""Raised when the layout of a kit changes; a change of a sample's bytes changes its digest instead."""
KIT_FILE = "kit.json"
STEPS_FILE = "STEPS.md"
FORM_FILE = f"{RESULTS}/form.json"
EXPECTED_FILE = "expected.txt"
"""``results/<sample>/expected.txt``: the result files of that folder, so that every folder exists."""
DEFAULT_SEED = 0
DEFAULT_TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)
"""The build inputs of the kit that the tree builds when none is given: everyone builds the same kit."""


@dataclass(frozen=True, slots=True)
class SampleFiles:
    """One built sample: its files by path below the sample's folder, and the digest of its script."""

    name: str
    script_sha256: str
    files: Mapping[str, bytes]


@dataclass(frozen=True, slots=True)
class KitSources:
    """What a kit is made of besides the steps: the built samples, and the files that belong to no sample
    (the sheet template of group K8) by path below the kit."""

    samples: tuple[SampleFiles, ...]
    extras: Mapping[str, bytes] = field(default_factory=lambda: MappingProxyType({}))
    fenolite_version: str = ""
    """The version of the Fenolite that built the samples (``verify`` does not import the root package)."""


@dataclass(frozen=True, slots=True)
class Kit:
    """A kit as its manifest describes it. ``files`` maps every file of the kit but ``kit.json`` and the
    form to its SHA-256; ``samples`` maps a sample to its digest; ``digest`` is ``kit_digest`` of the
    manifest's bytes."""

    digest: str
    data: Mapping[str, Any]
    files: Mapping[str, str]
    samples: Mapping[str, str]
    steps: tuple[Step, ...]
    script_sha256: str


def stamp(timestamp: datetime) -> str:
    """``timestamp`` in UTC as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(data: object) -> bytes:
    """``data`` as JSON with sorted keys, two spaces of indentation, UTF-8 and one final LF."""
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def kit_digest(manifest: bytes) -> str:
    """The digest that identifies a kit: the SHA-256 of the bytes of its ``kit.json``."""
    return sha256_bytes(manifest)


def sample_digest(files: Mapping[str, str]) -> str:
    """The digest of one sample: the SHA-256 over its ``<sha256>  <path>`` lines in path order."""
    lines = "".join(f"{digest}  {path}\n" for path, digest in sorted(files.items()))
    return sha256_bytes(lines.encode("utf-8"))


def blank_form(steps: Sequence[Step] = STEPS) -> dict[str, object]:
    """The form a run fills: the tool, the system and one value per ``form`` step, all empty."""
    return {
        "schema": FORM_SCHEMA,
        "altium_version": "",
        "os_family": "",
        "date": "",
        "synthetic": False,
        "values": {step.result: None for step in steps if step.kind == "form"},
    }


def _checked(path: str) -> str:
    pure = PurePosixPath(path)
    if not path or pure.is_absolute() or ".." in pure.parts or "\\" in path or ":" in path:
        raise ValueError(f"{path!r} is not a path inside the kit")
    return pure.as_posix()


def _expected_files(steps: Sequence[Step]) -> dict[str, bytes]:
    folders: dict[str, list[str]] = {name: [] for name in SAMPLES}
    for step in steps:
        if step.kind == "file":
            folder, _, name = step.result.partition("/")
            folders.setdefault(folder, []).append(f"{name}  ({step.id})")
    return {
        f"{RESULTS}/{folder}/{EXPECTED_FILE}": (
            "The files that a run leaves in this folder, with the step of each:\n"
            + "".join(f"{line}\n" for line in names)
        ).encode("utf-8")
        for folder, names in sorted(folders.items())
    }


def _entries(files: Mapping[str, bytes]) -> list[dict[str, object]]:
    return [
        {"path": path, "sha256": sha256_bytes(data), "size": len(data)}
        for path, data in sorted(files.items())
    ]


def kit_files(
    sources: KitSources,
    *,
    seed: int = DEFAULT_SEED,
    timestamp: datetime = DEFAULT_TIMESTAMP,
    steps: Sequence[Step] = STEPS,
) -> dict[str, bytes]:
    """Every file of the kit by its path below the kit's folder, ``kit.json`` included.

    ``ValueError`` when ``sources`` does not hold exactly the samples of ``steps.SAMPLES``, when a path
    leaves the kit, when two files share a path, or when a step opens a document that the kit lacks."""
    names = [sample.name for sample in sources.samples]
    if sorted(names) != sorted(SAMPLES):
        raise ValueError(f"a kit holds the samples {', '.join(SAMPLES)}; got {', '.join(names) or 'none'}")
    files: dict[str, bytes] = {}

    def add(path: str, data: bytes) -> None:
        path = _checked(path)
        if path in files or path in (KIT_FILE, FORM_FILE):
            raise ValueError(f"two files of the kit share the path {path}")
        files[path] = data

    samples: list[dict[str, object]] = []
    for sample in sorted(sources.samples, key=lambda s: SAMPLES.index(s.name)):
        own = {f"{sample.name}/{_checked(path)}": data for path, data in sample.files.items()}
        for path, data in own.items():
            add(path, data)
        entries = _entries(own)
        samples.append(
            {
                "name": sample.name,
                "script": f"examples/kit/{sample.name}/design.py",
                "script_sha256": sample.script_sha256,
                "digest": sample_digest({str(e["path"]): str(e["sha256"]) for e in entries}),
                "files": entries,
            }
        )
    other: dict[str, bytes] = {}
    for path, data in sources.extras.items():
        other[_checked(path)] = data
    script = script_text(steps).encode("ascii")
    other[SCRIPT_NAME] = script
    other[STEPS_FILE] = steps_markdown(steps).encode("utf-8")
    other.update(_expected_files(steps))
    for path, data in other.items():
        add(path, data)
    for step in steps:
        if step.document and step.document not in files:
            raise ValueError(f"{step.id} opens {step.document}, which the kit does not hold")
        if step.sample != KIT_SAMPLE and step.document and not step.document.startswith(step.sample + "/"):
            raise ValueError(f"{step.id} opens {step.document}, which is not a file of its sample")
    form = canonical_json(blank_form(steps))
    manifest: dict[str, object] = {
        "schema": KIT_SCHEMA,
        "kit_version": KIT_VERSION,
        "fenolite_version": sources.fenolite_version,
        "seed": seed,
        "timestamp": stamp(timestamp),
        "samples": samples,
        "files": _entries(other),
        "form": {"path": FORM_FILE, "schema": FORM_SCHEMA, "sha256": sha256_bytes(form), "size": len(form)},
        "script": {
            "path": SCRIPT_NAME,
            "sha256": sha256_bytes(script),
            "procedure": PROCEDURE,
            "log": LOG,
            "calls": dict(sorted(SCRIPT_CALLS.items())),
        },
        "steps": [step.to_json() for step in steps],
    }
    return {KIT_FILE: canonical_json(manifest), FORM_FILE: form, **files}


def _step(data: Mapping[str, Any]) -> Step:
    return Step(
        id=data["id"],
        sample=data["sample"],
        instruction=data["instruction"],
        kind=data["kind"],
        result=data["result"],
        hypotheses=tuple(data["hypotheses"]),
        document=data["document"],
        checks=tuple(data["checks"]),
        pending=MappingProxyType(dict(data["pending"])),
        value_type=data["value_type"],
        expected=data["expected"],
        scripted=data["scripted"],
    )


def read_kit(manifest: bytes, *, file: str = KIT_FILE) -> Kit:
    """The kit that the bytes of a ``kit.json`` describe. ``FormatError`` for bytes that are not such a
    manifest."""
    try:
        data: object = json.loads(manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FormatError(f"{file} is not JSON: {exc}", file=file) from exc
    if not isinstance(data, dict) or cast(dict[str, object], data).get("schema") != KIT_SCHEMA:
        raise FormatError(f"{file} is not a kit manifest of the schema {KIT_SCHEMA}", file=file)
    body = cast(dict[str, Any], data)
    try:
        files = {str(entry["path"]): str(entry["sha256"]) for entry in body["files"]}
        samples: dict[str, str] = {}
        for sample in body["samples"]:
            samples[str(sample["name"])] = str(sample["digest"])
            files.update({str(entry["path"]): str(entry["sha256"]) for entry in sample["files"]})
        steps = tuple(_step(entry) for entry in body["steps"])
        script = str(body["script"]["sha256"])
    except (KeyError, TypeError) as exc:
        raise FormatError(f"{file} lacks a field of the schema {KIT_SCHEMA}: {exc}", file=file) from exc
    return Kit(
        digest=kit_digest(manifest),
        data=MappingProxyType(body),
        files=MappingProxyType(files),
        samples=MappingProxyType(samples),
        steps=steps,
        script_sha256=script,
    )


def load_kit(folder: Path) -> Kit:
    """The kit in ``folder``. ``FormatError`` when the folder holds no readable ``kit.json``."""
    path = Path(folder) / KIT_FILE
    if not path.is_file():
        raise FormatError(f"{Path(folder).name} holds no {KIT_FILE}: it is not a kit", file=KIT_FILE)
    return read_kit(path.read_bytes())


def build_kit(
    out: Path,
    *,
    seed: int = DEFAULT_SEED,
    timestamp: datetime = DEFAULT_TIMESTAMP,
    sources: KitSources,
) -> Kit:
    """Write the kit of ``sources`` under ``out`` and return it. The folder is created; a file it already
    holds under a kit path is replaced, and no other file is touched."""
    files = kit_files(sources, seed=seed, timestamp=timestamp)
    root = Path(out)
    for path, data in files.items():
        target = root.joinpath(*PurePosixPath(path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return read_kit(files[KIT_FILE])


__all__ = [
    "DEFAULT_SEED",
    "DEFAULT_TIMESTAMP",
    "EXPECTED_FILE",
    "FORM_FILE",
    "FORM_SCHEMA",
    "KIT_FILE",
    "KIT_SCHEMA",
    "KIT_VERSION",
    "STEPS_FILE",
    "Kit",
    "KitSources",
    "SampleFiles",
    "blank_form",
    "build_kit",
    "canonical_json",
    "kit_digest",
    "kit_files",
    "load_kit",
    "read_kit",
    "sample_digest",
    "stamp",
]
