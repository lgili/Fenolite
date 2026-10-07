# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The record of a kit run, the archive of its results and the rule of the kit label (capabilities
altium-verification, "Kit run record", and verification-evidence, "Kit label rows";
``docs/altium-kit.md``, "Recording a run").

A record is a small JSON document (schema ``fenolite.altium-kit-run.v0``) that the repository keeps under
``docs/evidence/altium-kit/``: digests, sizes, versions and verdicts, and no path outside the kit, no user
name and no machine name. The archive of ``results/`` is kept outside the repository; the record names it
by digest and size. The archive is a Zip with stored members, sorted names, one fixed date and fixed
attributes, so the same result files give the same bytes on every operating system.

Stdlib and ``fenolite.core`` only.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level
from fenolite.core.io import sha256_bytes
from fenolite.verify.hypotheses import HypothesisRow
from fenolite.verify.kit.manifest import Kit, canonical_json
from fenolite.verify.kit.results import ALTIUM_VERSION, DATE, HOME_FOLDER, KitVerdict, absolute_paths
from fenolite.verify.kit.steps import SAMPLES, Step

RUN_SCHEMA = "fenolite.altium-kit-run.v0"
RECORDS_DIR = "docs/evidence/altium-kit"
"""Where committed run records live, relative to the repository."""
ARCHIVE_FILE = "results.zip"
"""The archive that ``kit record`` writes beside the kit folder."""
RUN_ID = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9a-f]{8}")
KIT_LABEL = re.compile(
    r"ALTIUM-VERIFIED\(kit; (?P<version>AD [0-9]+\.[0-9]+); (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2}); "
    r"(?P<run>[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9a-f]{8})\)"
)
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_ZIP_MODE = 0o100644 << 16
_ZIP_UNIX = 3


def archive_bytes(folder: Path, verdict: KitVerdict) -> bytes:
    """The archive of the result files of ``verdict``, read from the kit folder ``folder``. ``ValueError``
    when a file changed since the verdict was made."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for entry in sorted(verdict.results, key=lambda e: e.path):
            data = Path(folder).joinpath(*entry.path.split("/")).read_bytes()
            if sha256_bytes(data) != entry.sha256:
                raise ValueError(f"{entry.path} changed since the results were checked")
            info = zipfile.ZipInfo(entry.path, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = _ZIP_UNIX
            info.external_attr = _ZIP_MODE
            archive.writestr(info, data)
    return buffer.getvalue()


def step_source(kit: Kit, step: Step) -> str:
    """The digest of what a step used: its sample's digest, or the digest of the kit file it opens when it
    belongs to no sample."""
    if step.sample in kit.samples:
        return kit.samples[step.sample]
    return kit.files.get(step.document, "")


def refusal(verdict: KitVerdict) -> str:
    """Why ``verdict`` gives no record, or ``""``: a synthetic run, a kit whose own files differ from
    its manifest, or a form without a sound tool version, system and date."""
    if verdict.synthetic:
        return "the run is synthetic: no tool saved its files, and no label can come from it"
    if verdict.kit_problems:
        return f"the kit's own files differ from kit.json ({verdict.kit_problems[0]})"
    if verdict.form_problems:
        return f"the form is not sound ({verdict.form_problems[0]})"
    return ""


def run_id(date: str, archive_sha256: str) -> str:
    return f"{date}-{archive_sha256[:8]}"


def run_record(verdict: KitVerdict, *, archive: bytes, fenolite_version: str = "") -> dict[str, Any]:
    """The run record of ``verdict`` and of the archive of its results. ``fenolite_version`` is the version
    that checked the results (the kit's own when none is given). ``ValueError`` for a verdict that
    ``refusal`` names: a synthetic verdict gives no record."""
    reason = refusal(verdict)
    if reason:
        raise ValueError(reason)
    kit = verdict.kit
    digest = sha256_bytes(archive)
    ident = run_id(verdict.date, digest)
    steps = {step.id: step for step in kit.steps}
    return {
        "schema": RUN_SCHEMA,
        "run_id": ident,
        "date": verdict.date,
        "synthetic": False,
        "kit_sha256": kit.digest,
        "kit_version": kit.data["kit_version"],
        "kit_fenolite_version": kit.data["fenolite_version"],
        "fenolite_version": fenolite_version or kit.data["fenolite_version"],
        "altium_version": verdict.altium_version,
        "os_family": verdict.os_family,
        "samples": {name: kit.samples[name] for name in SAMPLES if name in kit.samples},
        "script_sha256": kit.script_sha256,
        "steps": [
            {
                "id": found.id,
                "kind": found.kind,
                "outcome": found.outcome,
                "scripted": found.scripted,
                "pending": sorted(steps[found.id].pending),
                "source": step_source(kit, steps[found.id]),
            }
            for found in verdict.steps
        ],
        "hypotheses": [
            {"id": found.id, "outcome": found.outcome, "form": found.form} for found in verdict.hypotheses
        ],
        "results": [{"path": f.path, "sha256": f.sha256, "size": f.size} for f in verdict.results],
        "privacy_findings": len(verdict.privacy),
        "kit_resaved": list(verdict.resaved),
        "archive": {"name": f"altium-kit-{ident}.zip", "sha256": digest, "size": len(archive)},
    }


def record_bytes(record: Mapping[str, Any]) -> bytes:
    return canonical_json(dict(record))


_FIELDS = (
    "schema", "run_id", "date", "synthetic", "kit_sha256", "kit_version", "kit_fenolite_version",
    "fenolite_version", "altium_version", "os_family", "samples", "script_sha256", "steps", "hypotheses",
    "results", "privacy_findings", "kit_resaved", "archive",
)  # fmt: skip


def record_problems(record: object) -> list[str]:
    """What is wrong with a run record: its schema and fields, a path that leaves the kit, a string that
    looks like a home folder or another absolute path, a run id that does not follow from its date and
    archive."""
    if not isinstance(record, dict):
        return ["the record is not a JSON object"]
    body = cast(dict[str, Any], record)
    if body.get("schema") != RUN_SCHEMA:
        return [f"the record's schema is not {RUN_SCHEMA}"]
    found = [f"the field {name} is missing" for name in _FIELDS if name not in body]
    found += [f"unknown field {name}" for name in sorted(set(body) - set(_FIELDS))]
    if found:
        return found
    if body["synthetic"] is not False:
        found.append("a record of a synthetic run supports nothing")
    if not isinstance(body["date"], str) or DATE.fullmatch(body["date"]) is None:
        found.append("date is not YYYY-MM-DD")
    if (
        not isinstance(body["altium_version"], str)
        or ALTIUM_VERSION.fullmatch(body["altium_version"]) is None
    ):
        found.append("altium_version is not 'AD <major>.<minor>'")
    archive = body["archive"]
    if not isinstance(archive, dict) or not isinstance(cast(dict[str, Any], archive).get("sha256"), str):
        found.append("archive holds no sha256")
    elif body["run_id"] != run_id(str(body["date"]), str(cast(dict[str, Any], archive)["sha256"])):
        found.append("run_id is not <date>-<first 8 hex digits of the archive digest>")
    for entry in cast(list[Any], body["results"]) if isinstance(body["results"], list) else []:
        path = str(cast(dict[str, Any], entry).get("path", ""))
        if not path.startswith("results/") or ".." in path.split("/") or "\\" in path or ":" in path:
            found.append(f"the result path {path!r} leaves the kit")
    text = json.dumps(body, ensure_ascii=False)
    if HOME_FOLDER.search(text) or HOME_FOLDER.search(text.replace("\\\\", "\\")):
        found.append("the record holds a string that looks like a home folder")
    elif absolute_paths(text):
        found.append("the record holds a string that looks like an absolute path of a machine")
    return found


def load_records(repository: Path) -> tuple[dict[str, Any], ...]:
    """The committed run records of ``repository``, by run id. ``FormatError`` for a file that is not a
    sound record or whose name is not its run id."""
    folder = Path(repository).joinpath(*RECORDS_DIR.split("/"))
    records: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data: object = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FormatError(f"not JSON: {exc}", file=path.name) from exc
        problems = record_problems(data)
        body = cast(dict[str, Any], data)
        if not problems and path.name != f"{body['run_id']}.json":
            problems = [f"the file name is not {body['run_id']}.json"]
        if problems:
            raise FormatError("; ".join(problems), file=path.name)
        records.append(body)
    return tuple(sorted(records, key=lambda r: str(r["run_id"])))


def kit_label(record: Mapping[str, Any]) -> str:
    """The level text that a row settled by ``record`` carries."""
    return f"ALTIUM-VERIFIED(kit; {record['altium_version']}; {record['date']}; {record['run_id']})"


def candidate_rows(record: Mapping[str, Any]) -> list[dict[str, object]]:
    """The register rows whose label may change after ``record``: one entry per hypothesis that passed,
    with the label and the text its result cell must hold."""
    archive = cast(Mapping[str, Any], record["archive"])
    rows: list[dict[str, object]] = []
    for found in cast(Sequence[Mapping[str, Any]], record["hypotheses"]):
        if found["outcome"] != "pass":
            continue
        typed = "; the verdict rests on a typed value (form)" if found["form"] else ""
        rows.append(
            {
                "id": found["id"],
                "label": kit_label(record),
                "form": bool(found["form"]),
                "result": f"confirmed by the kit run {record['run_id']} (archive SHA-256 "
                f"{archive['sha256']}){typed}",
            }
        )
    return rows


def _outcome(record: Mapping[str, Any], ident: str) -> Mapping[str, Any] | None:
    for found in cast(Sequence[Mapping[str, Any]], record["hypotheses"]):
        if found["id"] == ident:
            return found
    return None


def _labelled(rows: Sequence[HypothesisRow]) -> list[tuple[HypothesisRow, re.Match[str] | None]]:
    return [
        (row, KIT_LABEL.fullmatch(row.level_text)) for row in rows if row.level is Level.ALTIUM_VERIFIED_KIT
    ]


def stale_rows(
    register: Sequence[HypothesisRow], records: Sequence[Mapping[str, Any]], kit: Kit
) -> tuple[str, ...]:
    """The ids of the register rows whose kit label names a run that is stale: for a step of the current
    kit that names the row, the run used another sample (or kit file) than the one the tree builds now, or
    did not hold that step."""
    by_run = {str(record["run_id"]): record for record in records}
    stale: list[str] = []
    for row, label in _labelled(register):
        record = by_run.get(label.group("run")) if label is not None else None
        if record is None:
            continue
        used = {
            str(s["id"]): str(s.get("source", "")) for s in cast(Sequence[Mapping[str, Any]], record["steps"])
        }
        steps = [step for step in kit.steps if row.id in step.hypotheses]
        if not steps or any(used.get(step.id) != step_source(kit, step) for step in steps):
            stale.append(row.id)
    return tuple(stale)


def label_problems(
    register: Sequence[HypothesisRow], records: Sequence[Mapping[str, Any]], kit: Kit | None
) -> list[str]:
    """One message per register row that carries a kit label it may not carry (capability
    verification-evidence, "Kit label rows"): a label of another form, no record of the run, a synthetic
    record, no passing verdict for the row, a version or date that is not the record's, a result text
    without the archive digest or without the word ``form`` for a typed verdict, and a stale run. ``kit``
    is the kit the tree builds; ``None`` skips the stale check."""
    by_run = {str(record["run_id"]): record for record in records}
    found: list[str] = []
    for row, label in _labelled(register):
        if label is None:
            found.append(
                f"{row.id}: a kit label is ALTIUM-VERIFIED(kit; AD <major>.<minor>; <date>; <run id>)"
            )
            continue
        record = by_run.get(label.group("run"))
        if record is None:
            found.append(f"{row.id}: no run record {label.group('run')}.json under {RECORDS_DIR}")
            continue
        if record.get("synthetic") is not False:
            found.append(f"{row.id}: the record {record['run_id']} is synthetic")
            continue
        verdict = _outcome(record, row.id)
        if verdict is None or verdict["outcome"] != "pass":
            found.append(f"{row.id}: the run {record['run_id']} holds no passing verdict for the row")
            continue
        if kit_label(record) != row.level_text:
            found.append(f"{row.id}: the label is not {kit_label(record)}, the label of its run")
        archive = str(cast(Mapping[str, Any], record["archive"])["sha256"])
        if archive not in row.result:
            found.append(f"{row.id}: the result text does not name the archive digest {archive}")
        if verdict["form"] and "form" not in row.result:
            found.append(
                f"{row.id}: the verdict rests on a typed value, and the result text does not say 'form'"
            )
    if kit is not None:
        found += [
            f"{ident}: its kit run is stale (a sample changed since the run): record a new run, or set "
            "the row back to its level before the run and name the stale run in its result"
            for ident in stale_rows(register, records, kit)
        ]
    return found


__all__ = [
    "ARCHIVE_FILE",
    "KIT_LABEL",
    "RECORDS_DIR",
    "RUN_ID",
    "RUN_SCHEMA",
    "archive_bytes",
    "candidate_rows",
    "kit_label",
    "label_problems",
    "load_records",
    "record_bytes",
    "record_problems",
    "refusal",
    "run_id",
    "run_record",
    "stale_rows",
    "step_source",
]
