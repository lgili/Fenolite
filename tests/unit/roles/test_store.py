# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role document and the stored roles of a board (change c0222; capability net-roles, "Role document";
scenario "Roles beside a hand-routed board" at the level of the store, the command's own in
``tests/unit/cli/test_roles_cmd.py``)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fenolite.core.errors import FormatError
from fenolite.model import canonical
from fenolite.model.rules import HotLoop, NetRole, RoleLimit, RoleSet, RuleSet
from fenolite.roles import store

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
CONFIRMED = RoleSet(
    nets=(NetRole("SW", "switch_node", "confirmed"), NetRole("VIN", "power", "confirmed", milliamps=2000)),
    loops=(HotLoop("buck", ("C1-1", "Q1-3", "Q1-1", "Q2-3", "Q2-1", "C1-2"), "confirmed"),),
    limits=(RoleLimit("loop_max", 60_000_000_000_000, net="SW"),),
)


def test_document_round_trip() -> None:
    data = store.dumps_document(CONFIRMED)
    assert json.loads(data)["schema"] == "fenolite.roles.v0"
    assert store.loads_document(data.decode("utf-8")) == CONFIRMED
    assert store.dumps_document(store.loads_document(data.decode("utf-8"))) == data
    assert data.endswith(b"\n") and b"\r" not in data


def test_document_path_is_beside_the_board(tmp_path: Path) -> None:
    assert store.document_path(tmp_path / "power.kicad_pcb") == tmp_path / "power.roles.json"
    assert store.document_path(tmp_path / "power.PcbDoc") == tmp_path / "power.roles.json"


def test_roles_beside_a_hand_routed_board(tmp_path: Path) -> None:
    """A board copy with a document beside it: the stored role of ``SW`` is ``confirmed``, the document is
    the source and the target of a confirmation, and the board's bytes do not change."""
    board = tmp_path / BOARD.name
    shutil.copyfile(BOARD, board)
    before = hashlib.sha256(board.read_bytes()).hexdigest()
    store.document_path(board).write_bytes(store.dumps_document(CONFIRMED))
    found = store.stored_roles(board, model_roles=None, built=False, root=tmp_path)
    assert found.roles is not None
    role = found.roles.role_of("SW")
    assert role is not None and role.source == "confirmed"
    assert found.source == found.target == store.document_path(board)
    assert hashlib.sha256(board.read_bytes()).hexdigest() == before


def test_resolution_order(tmp_path: Path) -> None:
    """``--roles FILE`` first, then ``.fenolite/rules.json`` of a built project, then the document beside
    the board; without any, nothing is stored and a confirmation writes the document beside the board."""
    board = tmp_path / "x.kicad_pcb"
    other = tmp_path / "elsewhere.json"
    other.write_bytes(store.dumps_document(CONFIRMED))
    given = store.stored_roles(board, model_roles=None, built=True, root=tmp_path, given=other)
    assert given.roles == CONFIRMED and given.target == other
    built = store.stored_roles(board, model_roles=CONFIRMED, built=True, root=tmp_path)
    assert built.roles == CONFIRMED and built.target == tmp_path / ".fenolite" / "rules.json" and built.built
    none = store.stored_roles(board, model_roles=None, built=False, root=tmp_path)
    assert none.roles is None and none.source is None and none.target == tmp_path / "x.roles.json"


@pytest.mark.parametrize(
    ("text", "pointer"),
    [
        ("{", ""),
        ('{"schema": "fenolite.requirements.v0", "roles": {}}', "/schema"),
        ('{"schema": "fenolite.roles.v0", "extra": 1}', "/extra"),
        ('{"schema": "fenolite.roles.v0", "roles": {"nets": [{"net": "SW", "kind": "motor", "source": '
         '"confirmed"}]}}', "/roles/nets/0/kind"),
        ('{"schema": "fenolite.roles.v0", "roles": {"nets": [{"net": "SW", "kind": "power", "source": '
         '"inferred"}]}}', "/roles/nets/0/source"),
        ('{"schema": "fenolite.roles.v0", "roles": {"limits": [{"key": "loop_max", "value": 1.5}]}}',
         "/roles/limits/0/value"),
        ('{"schema": "fenolite.roles.v0", "roles": {"limits": [{"key": "area", "value": 1}]}}',
         "/roles/limits/0"),
    ],
)  # fmt: skip
def test_malformed_documents(text: str, pointer: str) -> None:
    """A malformed document is a ``FormatError`` (``FEN-3004`` at the command) naming the file and where."""
    with pytest.raises(FormatError) as raised:
        store.loads_document(text, file="b.roles.json")
    assert raised.value.file == "b.roles.json"
    if pointer:
        assert raised.value.locator == pointer


def test_inferred_roles_are_never_stored() -> None:
    with pytest.raises(ValueError, match="confirm it"):
        store.dumps_document(RoleSet(nets=(NetRole("SW", "switch_node", "inferred", "SW-1", "high"),)))
    with pytest.raises(ValueError, match="confirm it"):
        store.dumps_document(RoleSet(loops=(HotLoop("b", ("C1-1", "Q1-3", "Q1-1"), "inferred"),)))


def test_updated_rules_replaces_only_the_roles() -> None:
    rules = RuleSet(id="rst_00000000-0000-4000-8000-000000000001", heights=())
    text = canonical.dumps(rules)
    written = store.updated_rules(text, CONFIRMED)
    loaded = canonical.loads(written.decode("utf-8"), RuleSet)
    assert loaded.roles == CONFIRMED and loaded.id == rules.id
    assert store.updated_rules(written.decode("utf-8"), RoleSet()).decode("utf-8") == text
