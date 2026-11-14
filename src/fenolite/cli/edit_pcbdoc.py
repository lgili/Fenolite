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

The result of a list holds ``edit_plan``, the session's ``fenolite.altium-edit-plan.v0`` (change c0502, D5).
Given such a plan, the command replays it on the board as it is now (``edit.plan.replay``): ``operations``
holds each operation's rebase status, and a conflict or a missing target is an error issue, so no write is
planned. The entries are read by ``edit.plan.queue``.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from fenolite.cli.api import PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level

LIMIT = 1_000_000
"""The largest operations file, in bytes."""


def _fail(index: int, message: str) -> CliError:
    return CliError("FEN-2001", f"--ops-file entry {index}: {message}", where=f"--ops-file:{index}",
                    hint="docs/cli-contract.md, 'edit', lists the operations and the item kinds")  # fmt: skip


def _entries(path: Path) -> list[object] | dict[str, Any]:
    data = path.read_bytes()
    if len(data) > LIMIT:
        raise CliError(
            "FEN-3004", f"the operations file {path.name} is larger than {LIMIT} bytes", where="--ops-file"
        )
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CliError("FEN-3004", f"--ops-file is not JSON: {error}", where="--ops-file") from error
    if isinstance(raw, dict):
        return cast("dict[str, Any]", raw)
    if not isinstance(raw, list):
        raise CliError(
            "FEN-3004", "--ops-file must hold a list of operations or an edit plan", where="--ops-file"
        )
    return cast("list[object]", raw)


def run_pcbdoc(path: Path, ops_file: Path, gates: list[str], cwd: Path) -> Result:
    from fenolite.backends.altium.edit import plan as edit_plan
    from fenolite.backends.altium.edit import session as edit_session

    if not path.is_file():
        raise CliError("FEN-3001", f"{path.name} is not a file", where=path.name)
    unknown = sorted(set(gates) - set(edit_session.GATES))
    if unknown:
        raise CliError("FEN-2001", f"--gate: no gate is named {', '.join(unknown)}", where="--gate",
                       hint=f"the gates: {', '.join(edit_session.OPERATIONS)}")  # fmt: skip
    entries = _entries(ops_file)
    opened_gates = dict.fromkeys(gates, True)
    depends = [path, ops_file]
    planned: Any = None
    if isinstance(entries, dict):
        try:
            planned = edit_plan.EditPlan.of(entries, file=ops_file.name)
            session = edit_plan.replay(planned, path, gates=opened_gates)
        except FormatError as error:
            raise CliError(
                "FEN-3004", f"--ops-file is not an edit plan: {error}", where="--ops-file"
            ) from error
        depends += [
            path.parent / str(o.entry["from_doc"]) for o in planned.operations if "from_doc" in o.entry
        ]
    else:
        session = edit_session.open_document(path, gates=opened_gates)
        for index, entry in enumerate(entries):
            try:
                edit_plan.queue(session, entry, index)
            except edit_plan.EntryError as error:
                raise _fail(error.index, error.message) from None
    old = session.data
    made: dict[str, Any] | None = None
    if planned is None:
        try:
            made = session.plan().data()
        except ValueError:
            made = None  # an operation the board refuses: its issue says why
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
        "operations": [q.label for q in session.queued]
        if planned is None
        else [
            {"label": r.label, "status": r.status}
            | (
                {"fields": [{"field": f, "base": b, "current": c} for f, b, c in r.fields]}
                if r.fields
                else {}
            )
            for r in session.rebased
        ],
        "records": records,
        "stale_pours": list(session.stale_pours),
        "redrawn": dict(session.redrawn),
    }
    if planned is None:
        result["edit_plan"] = made
    else:
        digest = hashlib.sha256(old).hexdigest()
        result |= {"base_sha256": planned.base_sha256, "document_sha256": digest,
                   "rebased": digest != planned.base_sha256}  # fmt: skip
    evidence = edit_session.EVIDENCE
    if gates:
        evidence = Evidence(Level.UNVERIFIED, hypotheses=edit_session.HYPOTHESES)
    writes = (
        (PlannedWrite(path=target, data=data, kind="pcbdoc"),) if data is not None and data != old else ()
    )
    return Result(
        result=result,
        issues=(*opened, *issues) if state is None else (*opened, *session.rebase, *issues),
        evidence=evidence,
        input=InputRef(
            path=path.name, sha256=hashlib.sha256(old).hexdigest(), kind="pcbdoc", format_version=None
        ),
        writes=writes,
        depends=depends_on(cwd, *depends),
    )
