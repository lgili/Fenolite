# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""No-connect marks in the KiCad build (capability design-dsl, "No-connect marks in a build"; change
c0036): marks are resolved like net members, kept in ``.fenolite/`` and written to no KiCad file."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _buildhelp import authored, blink, blink_variant, build, codes

import fenolite.cli.main as cli_main
from fenolite.dsl import Design, Net, Part, connect, mm, no_connect
from fenolite.dsl.convert import key_id
from fenolite.lens.build import BUILD_ISSUE_CODES, BuildOutput
from fenolite.model import PinRef, canonical

U1 = key_id("component", "U1")


def marked_blink() -> Design:
    d = blink()
    no_connect(d.parts["U1"][11], d.parts["U1"][12])
    return d


def stored(out: BuildOutput, folder: Path) -> tuple[PinRef, ...]:
    """The marks of the ``.fenolite/`` files of ``out``, loaded back from ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    for path, data in out.files.items():
        if path.startswith(".fenolite/"):
            (folder / Path(path).name).write_bytes(data)
    return canonical.load_dir(folder).circuit.no_connects


def test_marks_resolved_in_the_built_model(tmp_path: Path) -> None:
    out = build(marked_blink())
    assert out.files and not [i for i in out.issues if i.severity == "error"]
    marks = (PinRef(U1, "11"), PinRef(U1, "12"))
    assert out.design.circuit.no_connects == marks == stored(out, tmp_path / "cache")
    assert all(m not in net.members for net in out.design.circuit.nets for m in marks)


def test_written_kicad_files_do_not_change() -> None:
    plain, marked = build(blink()), build(marked_blink())
    outside = sorted(p for p in plain.files if not p.startswith(".fenolite/"))
    assert outside == sorted(p for p in marked.files if not p.startswith(".fenolite/"))
    assert any(p.endswith(".kicad_pcb") for p in outside)
    for path in outside:
        assert marked.files[path] == plain.files[path], path
    assert marked.files[".fenolite/circuit.json"] != plain.files[".fenolite/circuit.json"]
    assert b"no_connects" not in plain.files[".fenolite/circuit.json"]
    board = marked.design.board
    assert board is not None
    pads = {p.number: p.net_id for fp in board.footprints if fp.component_id == U1 for p in fp.pads}
    assert pads["11"] is None and pads["12"] is None, "the pad of a marked pin gets no net"


def test_a_name_marks_every_pin_of_that_name(tmp_path: Path) -> None:
    folder = authored(tmp_path, {"S": [("1", "A"), ("2", "NC"), ("3", "NC")]}, {"F": ["1", "2", "3"]})
    d = Design("t")
    d.board(mm(20), mm(20))
    u1 = Part("U1", "T:S", footprint="T:F")
    d.add(u1)
    u1.place(mm(5), mm(5))
    no_connect(u1["NC"], u1[2])
    out = build(d, project_dir=folder)
    assert out.design.circuit.no_connects == (PinRef(U1, "2"), PinRef(U1, "3"))
    assert "build.unknown-pin" not in codes(out)


def test_a_name_and_a_number_of_one_pin() -> None:
    d = blink()
    u1, gnd = d.parts["U1"], d.nets["GND"]
    del u1.connections["10"]
    connect(gnd, u1["GND"])
    no_connect(u1[10])
    out = build(d)
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.no-connect-on-net"]
    assert found.severity == "error"
    assert "U1" in found.message and "10" in found.message and "GND" in found.message
    assert "model.no-connect-on-net" not in codes(out), "one finding per fault"


def test_unknown_marked_designator() -> None:
    d = blink()
    no_connect(d.parts["R1"]["X"])
    out = build(d)
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.unknown-pin"]
    assert found.severity == "error" and "R1" in found.message and "X" in found.message


def test_a_marked_number_that_is_also_a_name(tmp_path: Path) -> None:
    folder = authored(tmp_path, {"S": [("1", "2"), ("2", "B")]}, {"F": ["1", "2"]})
    d = Design("t")
    d.board(mm(20), mm(20))
    u1 = Part("U1", "T:S", footprint="T:F")
    d.add(u1)
    u1.place(mm(5), mm(5))
    no_connect(u1[2])
    out = build(d, project_dir=folder)
    (found,) = [i for i in out.issues if i.code == "build.pin-ambiguous"]
    assert found.severity == "warning" and out.files
    assert out.design.circuit.no_connects == (PinRef(U1, "2"),), "the number wins"


def test_a_marked_pin_without_a_pad_is_an_unused_pin(tmp_path: Path) -> None:
    folder = authored(tmp_path, {"S": [("1", "A"), ("2", "B"), ("3", "C")]}, {"F": ["1", "2"]})
    d = Design("t")
    d.board(mm(20), mm(20))
    u1 = Part("U1", "T:S", footprint="T:F")
    d.add(u1)
    u1.place(mm(5), mm(5))
    connect(Net("N"), u1[1], u1[2])
    no_connect(u1[3])
    out = build(d, project_dir=folder)
    assert "build.unused-pin-without-pad" in codes(out) and "build.pin-without-pad" not in codes(out)
    assert out.design.circuit.no_connects == (PinRef(U1, "3"),) and out.files


def test_the_new_code_is_an_error() -> None:
    assert BUILD_ISSUE_CODES["build.no-connect-on-net"] == "error"


# --- through the CLI ----------------------------------------------------------------------------------


def run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str) -> tuple[int, dict[str, object]]:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


IMPORT = "from fenolite.dsl import Design, Net, Part, Power, connect, mm"
MARKS = "\nno_connect(u1[11], u1[12])\n"


def test_cli_build_keeps_the_marks_and_the_kicad_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    flags = ("--confirm", "--seed", "7", "--timestamp", "2026-10-03T00:00:00Z")
    plain = blink_variant(tmp_path / "plain", IMPORT, IMPORT + ", no_connect")
    marked = blink_variant(tmp_path / "marked", IMPORT, IMPORT + ", no_connect", append=MARKS)
    receipts: list[dict[str, str]] = []
    for script, out in ((plain, tmp_path / "a"), (marked, tmp_path / "b")):
        code, reply = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), *flags)
        assert code == 0, reply
        written = reply["receipt"]["written"]  # type: ignore[index]
        receipts.append(
            {
                Path(w["path"]).relative_to(out).as_posix(): w["sha256"]
                for w in written
                if ".fenolite" not in Path(w["path"]).parts
            }
        )
    assert receipts[0] and receipts[0] == receipts[1]
    assert canonical.load_dir(tmp_path / "b" / ".fenolite").circuit.no_connects == (
        PinRef(U1, "11"),
        PinRef(U1, "12"),
    )
    assert canonical.load_dir(tmp_path / "a" / ".fenolite").circuit.no_connects == ()


def test_cli_build_refuses_a_marked_pin_on_a_net(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(
        tmp_path / "v",
        "connect(gnd, u1[10], d1[1])",
        'from fenolite.dsl import no_connect\n\nconnect(gnd, u1["GND"], d1[1])',
        append="\nno_connect(u1[10])\n",
    )
    out = tmp_path / "out"
    code, reply = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 5
    found = [i for i in reply["issues"] if i["code"] == "build.no-connect-on-net"]  # type: ignore[union-attr]
    assert len(found) == 1 and all(word in found[0]["message"] for word in ("U1", "10", "GND"))
    assert not out.exists() or not any(out.iterdir())
