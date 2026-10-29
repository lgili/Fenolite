# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where the roles of a board are kept (change c0222; capability net-roles, "Role document";
``docs/roles.md``, "Where roles are kept").

- A project that Fenolite built keeps its roles in ``.fenolite/rules.json`` (``RuleSet.roles``): the
  script's declarations (``declared``) and the roles the user confirmed (``confirmed``).
- A board that Fenolite did not build keeps them in its role document, ``<board stem>.roles.json`` beside
  the board, or in the file that ``--roles FILE`` names. The document is canonical JSON of the schema
  ``fenolite.roles.v0`` and holds one ``RoleSet``. The same document serves a KiCad and an Altium board,
  since roles name nets and pads by name. The board file itself is never written.

Inferred roles that the user has not confirmed are never stored: they are computed again on each run.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.model import canonical
from fenolite.model.rules import PartClass, RoleSet, RuleSet

SCHEMA = "fenolite.roles.v0"
SUFFIX = ".roles.json"


def document_path(board: Path) -> Path:
    """The role document beside ``board``: ``<board stem>.roles.json`` in the board's folder."""
    return board.with_name(board.stem + SUFFIX)


def dumps_document(roles: RoleSet) -> bytes:
    """The canonical bytes of a role document holding ``roles``. ``ValueError`` for a role or a group whose
    source is ``inferred``: an inferred role is stored only once confirmed."""
    for role in roles.nets:
        if role.source == "inferred":
            raise ValueError(f"the role of {role.net} is inferred; confirm it before it is stored")
    for group in (*roles.loops, *roles.kelvins, *roles.gates):
        if group.origin == "inferred":
            raise ValueError(f"the group {group.name} is inferred; confirm it before it is stored")
    data: dict[str, Any] = {"schema": SCHEMA, "roles": canonical.to_data(roles)}
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def loads_document(text: str, *, file: str = "") -> RoleSet:
    """The ``RoleSet`` of a role document; ``FormatError`` naming the file and the JSON pointer for invalid
    JSON, another schema, an unknown key or a refused value."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise FormatError(f"invalid JSON: {error.msg}", file=file, offset=error.pos) from None
    if not isinstance(data, dict):
        raise FormatError("a role document is a JSON object", file=file, locator="/")
    document = cast(dict[str, Any], data)
    if document.get("schema") != SCHEMA:
        raise FormatError(f"the schema must be {SCHEMA!r}", file=file, locator="/schema")
    unknown = sorted(set(document) - {"schema", "roles"})
    if unknown:
        raise FormatError(f"unexpected property {unknown[0]!r}", file=file, locator=f"/{unknown[0]}")
    roles = canonical.decode(RoleSet, document.get("roles", {}), "/roles", file)
    assert isinstance(roles, RoleSet)
    for index, role in enumerate(roles.nets):
        if role.source == "inferred":
            raise FormatError(
                f"the role of {role.net} is inferred; a document stores only confirmed and declared roles",
                file=file,
                locator=f"/roles/nets/{index}/source",
            )
    return roles


def read_document(path: Path) -> RoleSet:
    """The roles of the document at ``path``; ``FormatError`` when it cannot be read or is malformed."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        reason = error.strerror if isinstance(error, OSError) and error.strerror else type(error).__name__
        raise FormatError(f"cannot read the role document: {reason}", file=path.name) from None
    return loads_document(text, file=path.name)


@dataclass(frozen=True, slots=True)
class Stored:
    """The stored roles of a board: ``roles`` (``None`` when nothing is stored), the file they come from
    (``None`` for none), and ``target``, the file a confirmation writes: ``.fenolite/rules.json`` of a built
    project, else the role document."""

    roles: RoleSet | None
    source: Path | None
    target: Path
    built: bool


def stored_roles(
    board: Path,
    *,
    model_roles: RoleSet | None,
    built: bool,
    root: Path,
    given: Path | None = None,
) -> Stored:
    """The stored roles of ``board``. ``given`` is the file of ``--roles FILE``; else a built project (one
    whose ``.fenolite/`` model was loaded, ``model_roles`` its ``RuleSet.roles``) keeps them in
    ``.fenolite/rules.json``; else the role document beside the board is read when it exists."""
    if given is not None:
        return Stored(read_document(given) if given.is_file() else None, given, given, False)
    if built:
        rules = root / ".fenolite" / "rules.json"
        return Stored(model_roles, rules if model_roles is not None else None, rules, True)
    beside = document_path(board)
    if beside.is_file():
        return Stored(read_document(beside), beside, beside, False)
    return Stored(None, None, beside, False)


def merged(declared: RoleSet | None, confirmed: RoleSet | None, classes: Sequence[PartClass] = ()) -> RoleSet:
    """The roles of ``rules.json`` of a built project: the script's declarations and the roles the user
    confirmed, a declaration winning on its key (a net, a group's name, a part's reference); the limits are
    the script's, the rejected group names the user's. ``classes`` are classes stated besides."""
    mine = declared or RoleSet()
    other = confirmed or RoleSet()
    names = {role.net for role in mine.nets}

    def groups(own: Sequence[Any], more: Sequence[Any]) -> tuple[Any, ...]:
        taken = {group.name for group in own}
        return (*own, *(group for group in more if group.name not in taken))

    refs = {found.ref for found in mine.classes}
    extra = {found.ref: found for found in (*other.classes, *classes) if found.ref not in refs}
    return RoleSet(
        nets=(
            *mine.nets,
            *(role for role in other.nets if role.net not in names and role.source != "declared"),
        ),
        loops=groups(mine.loops, [g for g in other.loops if g.origin != "declared"]),
        kelvins=groups(mine.kelvins, [g for g in other.kelvins if g.origin != "declared"]),
        gates=groups(mine.gates, [g for g in other.gates if g.origin != "declared"]),
        limits=mine.limits,
        classes=(*mine.classes, *extra.values()),
        rejected=other.rejected,
    )


def kept_confirmed(new_rules: bytes, old_rules: Path) -> bytes:
    """The bytes of a new build's ``.fenolite/rules.json`` with the roles that the user confirmed in the
    previous one (``old_rules``) kept: the build writes the script's declarations, and ``fenolite roles``
    stores the confirmed roles beside them (``docs/roles.md``, "Where roles are kept"). Unchanged when the
    old file is missing, unreadable or holds no confirmed role."""
    try:
        old = canonical.loads(old_rules.read_text(encoding="utf-8"), RuleSet, file=old_rules.name)
    except (OSError, UnicodeDecodeError, FormatError, ValueError):
        return new_rules
    assert isinstance(old, RuleSet)
    roles = old.roles
    confirmed = (
        None
        if roles is None
        else RoleSet(
            nets=tuple(role for role in roles.nets if role.source == "confirmed"),
            loops=tuple(g for g in roles.loops if g.origin == "confirmed"),
            kelvins=tuple(g for g in roles.kelvins if g.origin == "confirmed"),
            gates=tuple(g for g in roles.gates if g.origin == "confirmed"),
            rejected=roles.rejected,
        )
    )
    if not confirmed:
        return new_rules
    text = new_rules.decode("utf-8")
    loaded = canonical.loads(text, RuleSet, file="rules.json")
    assert isinstance(loaded, RuleSet)
    return updated_rules(text, merged(loaded.roles, confirmed, old.roles.classes if old.roles else ()))


def updated_rules(text: str, roles: RoleSet, *, file: str = "rules.json") -> bytes:
    """The bytes of ``.fenolite/rules.json`` (``text``) with its ``roles`` replaced by ``roles``; every other
    key keeps its value."""
    loaded = canonical.loads(text, RuleSet, file=file)
    assert isinstance(loaded, RuleSet)
    return canonical.dumps(replace(loaded, roles=roles or None)).encode("utf-8")


__all__ = [
    "SCHEMA",
    "SUFFIX",
    "Stored",
    "document_path",
    "dumps_document",
    "kept_confirmed",
    "loads_document",
    "merged",
    "read_document",
    "stored_roles",
    "updated_rules",
]
