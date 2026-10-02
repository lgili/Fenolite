# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check canary: board injection, rule placement, verdict and stripping (capability kicad-oracle,
"Check canary injection"; change c0013). Hermetic: no ``kicad-cli`` runs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from _boards import board, segment

from fenolite.backends.base import DrcItem, DrcReport, DrcViolation
from fenolite.backends.kicad import canary
from fenolite.backends.kicad.canary import (
    CANARY_NETS,
    CANARY_RULE_NAME,
    CANARY_UUIDS,
    CanaryError,
    append_rule,
    canary_fired,
    canary_rule_text,
    clearance_ignored,
    inject_board,
    insertions,
    strip_canary,
)
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[4]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
PROBES = ROOT / "docs" / "evidence" / "kicad" / "probes"
NET_ROW = re.compile(rb"\(net (\d+) ")


def _remove(injected: bytes, spans: list[tuple[int, bytes]]) -> bytes:
    """``injected`` with each inserted span removed at its shifted offset (checking it is there)."""
    out = bytearray(injected)
    shift = 0
    located: list[tuple[int, int]] = []
    for offset, text in sorted(spans, key=lambda p: p[0]):
        start = offset + shift
        assert bytes(out[start : start + len(text)]) == text
        located.append((start, len(text)))
        shift += len(text)
    for start, length in reversed(located):
        del out[start : start + length]
    return bytes(out)


# -- inject


def test_inject_keeps_user_bytes() -> None:
    data = TWO_LAYER.read_bytes()
    first, second = inject_board(data), inject_board(data)
    assert first == second
    assert _remove(first, insertions(data)) == data

    def table(raw: bytes) -> list[tuple[str, ...]]:
        return [tuple(a.text for a in n.atoms()) for n in parse_bytes(raw).nodes("net")]

    assert table(first)[: len(table(data))] == table(data)  # every net number and name kept


def test_inject_numbered_form_adds_fresh_net_rows() -> None:
    data = TWO_LAYER.read_bytes()
    before = [int(n) for n in NET_ROW.findall(data)]
    injected = inject_board(data)
    design = read_board(injected.decode("utf-8"))
    assert design.board is not None
    names = {n.name for n in design.circuit.nets}
    assert set(CANARY_NETS) <= names
    after = [int(n) for n in NET_ROW.findall(injected)]
    assert max(after) == max(before) + 2
    uuids = {t.id for t in design.board.tracks}
    assert len(design.board.tracks) >= 2 and uuids


def test_inject_named_form() -> None:
    text = board(segment(1, net='(net "A")'), version=20250114, nets=None)
    injected = inject_board(text.encode("utf-8"))
    root = parse_bytes(injected)
    nets = [n for s in root.nodes("segment") for n in s.nodes("net")]
    assert [n.atoms()[0].value for n in nets[-2:]] == list(CANARY_NETS)
    assert not any(c.name == "net" for c in root.nodes())


def test_inject_places_tracks_beyond_the_board() -> None:
    injected = inject_board(TWO_LAYER.read_bytes())
    root = parse_bytes(injected)
    segments = [s for s in root.nodes("segment") if s.find("uuid").atoms()[0].value in CANARY_UUIDS]  # type: ignore[union-attr]
    assert len(segments) == 2
    starts = [s.find("start").atoms() for s in segments]  # type: ignore[union-attr]
    assert {a[1].text for a in starts} == {"0", "1"}
    assert all(float(a[0].text) > 25 for a in starts)
    assert [c.name for c in segments[0].nodes()] == ["start", "end", "width", "layer", "net", "uuid"]


def test_inject_invalid_utf8_raises_format_error() -> None:
    data = TWO_LAYER.read_bytes()
    index = data.index(b'"F.Cu"') + 2
    broken = data[:index] + b"\xff" + data[index:]
    with pytest.raises(FormatError, match="invalid UTF-8"):
        inject_board(broken)


def test_inject_extent_too_large() -> None:
    text = board(segment(1, start="1999000 0", end="1999001 0"))
    with pytest.raises(CanaryError) as info:
        inject_board(text.encode("utf-8"))
    assert info.value.reason == "extent-too-large"


def test_inject_no_front_copper() -> None:
    text = board().replace('"F.Cu"', '"In1.Cu"')
    with pytest.raises(CanaryError) as info:
        inject_board(text.encode("utf-8"))
    assert info.value.reason == "no-front-copper"


def test_inject_names_taken() -> None:
    text = board(nets=("", "FENOLITE_CANARY_A"))
    with pytest.raises(CanaryError) as info:
        inject_board(text.encode("utf-8"))
    assert info.value.reason == "names-taken"


# -- rule


def test_rule_text_and_user_bytes() -> None:
    text = canary_rule_text(10)
    assert text is not None and CANARY_RULE_NAME in text and CANARY_NETS[0] in text
    user = b'(version 1)\n(rule "mine"\n\t(constraint clearance (min 0.2mm)))'
    out = append_rule(user, text, major=10)
    assert out.startswith(user)
    assert out.rstrip().endswith(text.encode("utf-8").rstrip())


def test_rule_whitespace_only_file() -> None:
    text = canary_rule_text(9)
    assert text is not None
    assert append_rule(b"\n  \n", text, major=9) == b"\n  \n(version 1)\n" + text.encode("utf-8") + b"\n"


def test_rule_unparsable_bytes_appended_at_the_end() -> None:
    text = canary_rule_text(10)
    assert text is not None
    user = b"(version 1)\n(rule 'quoted'\n"
    assert append_rule(user, text, major=10) == user + text.encode("utf-8") + b"\n"


def test_rule_names_taken() -> None:
    with pytest.raises(CanaryError) as info:
        append_rule(f'(rule "{CANARY_RULE_NAME}")'.encode(), "(rule x)", major=10)
    assert info.value.reason == "names-taken"


def test_rule_none_without_net_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "SELECTOR_SUPPORT", {"net": frozenset({10})})
    assert canary_rule_text(9) is None
    assert canary_rule_text(10) is not None


# -- strip and verdict


def _item(uid: str) -> DrcItem:
    return DrcItem(uid, "track", Point(0, 0))


def _report(*violations: DrcViolation, unconnected: tuple[DrcViolation, ...] = ()) -> DrcReport:
    return DrcReport("b.kicad_pcb", "", "10.0.6", "mm", violations=violations, unconnected_items=unconnected)


CANARY_PAIR = DrcViolation("clearance", "canary", "error", (_item(CANARY_UUIDS[0]), _item(CANARY_UUIDS[1])))
USER = DrcViolation("clearance", "user", "error", (_item("u1"), _item("u2")))
DANGLING = DrcViolation("track_dangling", "end", "warning", (_item(CANARY_UUIDS[1]),))


def test_strip_canary() -> None:
    report = _report(CANARY_PAIR, USER, DANGLING, unconnected=(DANGLING,))
    stripped, removed = strip_canary(report)
    assert stripped.violations == (USER,)
    assert stripped.unconnected_items == ()
    assert removed == 3
    assert canary_fired(report) and not canary_fired(stripped)


def test_strip_fired_needs_exactly_the_pair() -> None:
    half = DrcViolation("clearance", "half", "error", (_item(CANARY_UUIDS[0]), _item("u1")))
    assert not canary_fired(_report(half, USER))
    other = DrcViolation("hole_clearance", "x", "error", CANARY_PAIR.items)
    assert not canary_fired(_report(other))


# -- ignored


def test_ignored_clearance_severity() -> None:
    ignored = {"board": {"design_settings": {"rule_severities": {"clearance": "ignore"}}}}
    assert clearance_ignored(json.dumps(ignored))
    ignored["board"]["design_settings"]["rule_severities"]["clearance"] = "error"
    assert not clearance_ignored(json.dumps(ignored))
    assert not clearance_ignored("{}")
    assert not clearance_ignored("{not json")


# -- support


def _recorded(probe: str, outcome: str) -> frozenset[int]:
    majors: set[int] = set()
    for path in sorted(PROBES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["probes"].get(probe) == outcome:
            majors.add(int(data["version"].split(".")[0]))
    return frozenset(majors)


def test_support_follows_the_probe_files() -> None:
    assert canary.CANARY_SUPPORT == _recorded("check-canary-fired", "present") & _recorded(
        "check-canary-broken", "absent"
    )
    # Every probed major is two-run: the authored projects record ``equal``, but the canary changes the
    # reports of large demo boards on 9.0.9 and 10.0.6 (H-K-CHECK-CANARY, refuted; H-K-CHECK-CANARY-2).
    assert canary.CANARY_TWO_RUN >= _recorded("check-canary-neutral", "different")
    assert canary.CANARY_TWO_RUN == canary.CANARY_SUPPORT == frozenset({9, 10})
