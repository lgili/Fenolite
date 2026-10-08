# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export`` with the drawing kinds against the fake ``kicad-cli`` (capability cli-contract,
"Drawing options of the export command"; manufacturing-exports, "Drawing kinds in the manifest";
change c0117). Hermetic."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _drawdesign import bench_text
from _fakecli import DRILL, EXPORT_FILES, PDF, calls, drill_report, fake_kicad_cli

from fenolite import templates
from fenolite.backends.kicad import pro, wks
from fenolite.exports import drawings
from fenolite.exports.manifest import design_kind
from fenolite.exports.states import DERIVED

PLATED = {"0.300": 3, "1.000": 3}
UNPLATED = {"3.200": 1}
PAIRS = {("F.Cu", "In1.Cu"): {"0.100": 1, "0.200": 1}}
BOTH = ("--fab-drawing", "--assembly-drawing")
DRAWN = [
    "fab/drawings/drawbench-NPTH-drl_map.pdf",
    "fab/drawings/drawbench-PTH-drl_map.pdf",
    "fab/drawings/drawbench-assembly-bottom.pdf",
    "fab/drawings/drawbench-assembly-top.pdf",
    "fab/drawings/drawbench-drill.rpt",
    "fab/drawings/drawbench-fab.pdf",
]
SPEC = 'schema = "fenolite.drawing-spec.v0"\n'


@pytest.fixture
def board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    path = tmp_path / "project" / "drawbench.kicad_pcb"
    path.parent.mkdir()
    path.write_text(bench_text(10), encoding="utf-8", newline="\n")
    return path


def _fake(tmp_path: Path, report: str | None = None, **options: Any) -> str:
    text = drill_report("drawbench", PLATED, UNPLATED, PAIRS) if report is None else report
    maps = {
        "{stem}-PTH.drl": DRILL,
        "{stem}-NPTH.drl": DRILL,
        "{stem}-PTH-drl_map.pdf": PDF,
        "{stem}-NPTH-drl_map.pdf": PDF,
        "{stem}-drill.rpt": text,
    }
    files = {**EXPORT_FILES, "drill-map": maps}
    return str(fake_kicad_cli(tmp_path / "bin", export_files=files, **options))


def _work(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return work


def test_plan_then_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    before = hashlib.sha256(board.read_bytes()).hexdigest()
    args = ("export", str(board), "--out", "fab", *BOTH, "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0, env
    assert [p["path"] for p in env["result"]["plan"]] == DRAWN
    assert list(work.iterdir()) == []

    code, env, _, raw = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    written = {w["path"]: w["sha256"] for w in env["receipt"]["written"]}
    assert list(written) == DRAWN
    for path, sha in written.items():
        assert hashlib.sha256((work / path).read_bytes()).hexdigest() == sha
    assert sorted(p.name for p in board.parent.iterdir()) == ["drawbench.kicad_pcb"]
    assert hashlib.sha256(board.read_bytes()).hexdigest() == before
    assert env["result"]["tool_version"] == "10.0.6"
    assert env["result"]["repeat"] == {"fab-drawing": "content", "assembly-drawing": "content"}
    assert {a["kind"] for a in env["result"]["artifacts"]} == set(drawings.DRAWING_KINDS)
    assert {a["layer"] for a in env["result"]["artifacts"]} == {None}
    assert str(tmp_path) not in raw and str(Path.home()) not in raw


def test_the_reply_describes_the_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    args = ("export", str(board), "--out", "fab", "--gerbers", *BOTH, "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, _work(tmp_path), *args, "--dry-run")
    assert code == 0, env
    result = env["result"]
    assert result["kinds"] == ["gerbers", "fab-drawing", "assembly-drawing"]
    pages = result["drawings"]
    assert [(p["kind"], p["path"], p.get("side")) for p in pages] == [
        ("fab-drawing", "drawings/drawbench-fab.pdf", None),
        ("assembly-drawing", "drawings/drawbench-assembly-top.pdf", "top"),
        ("assembly-drawing", "drawings/drawbench-assembly-bottom.pdf", "bottom"),
    ]
    assert {(p["paper"], p["portrait"], p["sheet"]) for p in pages} == {("A3", False, "kicad-default")}
    assert [b["name"] for b in pages[0]["blocks"]] == ["board", "stackup", "drill"]
    for block in pages[0]["blocks"]:
        assert all(isinstance(v, int) for v in (*block["at"], *block["size"]))
    assert "designators_added" not in pages[0]
    assert [p["designators_added"] for p in pages[1:]] == [4, 1]
    evidence = env["evidence"]
    assert evidence["level"] == "KICAD-VERIFIED" and evidence["oracle"] == "kicad-cli 10.0.6"
    assert {"H-K-DRAW-ITEMS", "H-K-DRAW-PAGE", "H-K-DRAW-DRILL", "H-K-EXPORT-FILES"} <= set(
        evidence["hypotheses"]
    )
    codes = [i["code"] for i in env["issues"]]
    assert codes.count("drawing.designators-added") == 2
    assert "drawing.stackup-missing" not in codes  # the board text holds the stack-up of the bench (c0101)
    assert all(i["severity"] == "info" for i in env["issues"])  # an info never changes the exit code


def test_all_does_not_select_a_drawing_kind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    args = ("export", str(board), "--out", "fab", "--all", "--kicad-cli", _fake(tmp_path), "--dry-run")
    code, env, _, _ = run(monkeypatch, _work(tmp_path), *args)
    assert code == 0, env
    assert (
        env["result"]["kinds"] == ["gerbers", "drill", "pos", "ipcd356"] and "drawings" not in env["result"]
    )
    assert not [p for p in env["result"]["plan"] if "/drawings/" in p["path"]]


def test_a_spec_without_a_drawing_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    (work / "d.toml").write_text(SPEC, encoding="utf-8")
    args = ("export", str(board), "--out", "fab", "--gerbers", "--drawing-spec", "d.toml", "--dry-run")
    code, _, err, _ = run(monkeypatch, work, *args, "--kicad-cli", _fake(tmp_path))
    assert code == 2 and err["code"] == "FEN-2001"


def test_an_invalid_spec_runs_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    (work / "d.toml").write_text(SPEC + '[page]\npaper = "B9"\n', encoding="utf-8")
    fake = _fake(tmp_path)
    ran: list[object] = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (ran.append(a), real(*a, **k))[1])
    args = ("export", str(board), "--out", "fab", "--fab-drawing", "--drawing-spec", "d.toml", "--dry-run")
    code, _, err, _ = run(monkeypatch, work, *args, "--kicad-cli", fake)
    assert code == 3 and err["code"] == "FEN-3004" and "page.paper" in err["message"]
    assert ran == [] and calls(Path(fake)) == []
    code, _, err, _ = run(monkeypatch, work, *args[:-3], "--drawing-spec", "none.toml", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001"
    assert ran == []


def test_an_altium_document_is_refused_before_the_spec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    work = _work(tmp_path)
    (work / "board.PcbDoc").write_bytes(b"\xd0\xcf\x11\xe0")
    (work / "d.toml").write_text('schema = "wrong"\n', encoding="utf-8")
    args = (
        "export",
        "board.PcbDoc",
        "--out",
        "fab",
        "--fab-drawing",
        "--drawing-spec",
        "d.toml",
        "--dry-run",
    )
    code, _, err, _ = run(monkeypatch, work, *args)
    assert code == 2 and err["code"] == "FEN-2001"  # not FEN-3004 of the spec, not FEN-6001 of the tool


def test_no_room_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    (work / "d.toml").write_text(SPEC + '[page]\npaper = "A5"\n', encoding="utf-8")
    args = ("export", str(board), "--out", "fab", "--fab-drawing", "--drawing-spec", "d.toml", "--confirm")
    code, env, _, _ = run(monkeypatch, work, *args, "--kicad-cli", _fake(tmp_path))
    assert code == 5, env
    (found,) = [i for i in env["issues"] if i["code"] == "drawing.no-room"]
    assert found["severity"] == "error" and "A5" in found["message"] and "A3" in found["message"]
    assert not (work / "fab").exists() and env["result"]["drawings"] == []


def test_a_count_that_differs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    report = drill_report("drawbench", {**PLATED, "0.300": 4}, UNPLATED, PAIRS)
    args = ("export", str(board), "--out", "fab", "--gerbers", "--fab-drawing", "--confirm")
    code, env, _, _ = run(monkeypatch, work, *args, "--kicad-cli", _fake(tmp_path, report))
    assert code == 5, env
    (found,) = [i for i in env["issues"] if i["code"] == "drawing.drill-mismatch"]
    for word in ("drawbench-PTH.drl", "0.300", "3", "4"):
        assert word in found["message"]
    assert not (work / "fab").exists()  # all or nothing: the Gerbers are not written either


def test_a_drawing_kind_alone_needs_the_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    args = ("export", str(board), "--out", "fab", "--fab-drawing", "--dry-run")
    code, _, err, _ = run(monkeypatch, _work(tmp_path), *args)
    assert code == 6 and err["code"] == "FEN-6001"


def test_a_preset_does_not_reach_a_drawing_kind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    work = _work(tmp_path)
    (work / "p.toml").write_text(
        'schema = "fenolite.export-preset.v0"\n[drill]\nmap = "pdf"\nunits = "in"\n', encoding="utf-8"
    )
    fake = _fake(tmp_path)
    args = ("export", str(board), "--out", "fab", "--fab-drawing", "--preset", "p.toml", "--dry-run")
    code, env, _, _ = run(monkeypatch, work, *args, "--kicad-cli", fake)
    assert code == 0, env
    (drill,) = [c["args"] for c in calls(Path(fake)) if c["args"][:3] == ["pcb", "export", "drill"]]
    assert drill[drill.index("--excellon-units") + 1] == "mm" and "--generate-report" in drill


def test_manifest_lists_the_drawings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    fake = _fake(tmp_path)
    first = (
        "export",
        str(board),
        "--out",
        "fab",
        "--gerbers",
        "--manifest",
        "--confirm",
        "--kicad-cli",
        fake,
    )
    assert run(monkeypatch, work, *first)[0] == 0
    args = ("export", str(board), "--out", "fab", *BOTH, "--manifest", "--confirm", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, work, *args)
    assert code == 0, env
    manifest = json.loads((work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    entries = {e["path"]: e for e in manifest["artifacts"]}
    assert [p for p in entries if p.startswith("gerbers/")]
    drawn = {path: e for path, e in entries.items() if path.startswith("drawings/")}
    assert sorted(f"fab/{path}" for path in drawn) == DRAWN
    sha = hashlib.sha256(board.read_bytes()).hexdigest()
    for path, entry in drawn.items():
        fab = "assembly" not in path
        assert entry["kind"] == ("fab-drawing" if fab else "assembly-drawing")
        assert entry["layer"] is None and entry["from"] == {"board": sha}
        assert entry["state"] == "generated" and entry["tool"] == "kicad-cli 10.0.6"
        assert entry["evidence"] == drawings.EVIDENCE.level.value == "KICAD-VERIFIED"
    assert set(drawings.DRAWING_KINDS) <= DERIVED
    assert all(design_kind(path) == "file" for path in drawn)  # never a drawing kind from a file name


# -- the sheet of the pages


def test_sheet_of_the_spec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    template = templates.example_path("iso5457_generic")
    (work / "frame.sheet.toml").write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    (work / "d.toml").write_text(
        SPEC + '[page]\npaper = "A3"\ndrawing_sheet = "frame.sheet.toml"\n', encoding="utf-8"
    )
    fake = _fake(tmp_path)
    args = ("export", str(board), "--out", "fab", "--fab-drawing", "--drawing-spec", "d.toml", "--dry-run")
    code, env, _, _ = run(monkeypatch, work, *args, "--kicad-cli", fake)
    assert code == 0, env
    (page,) = env["result"]["drawings"]
    assert (page["sheet"], page["paper"]) == ("spec", "A3")
    (plot,) = [c for c in calls(Path(fake)) if c["args"][:3] == ["pcb", "export", "pdf"]]
    assert plot["args"][plot["args"].index("--drawing-sheet") + 1] == drawings.SHEET_FILE
    assert drawings.SHEET_FILE in plot["tree"]
    sheet = templates.build_sheet(templates.load_spec(template))
    margin = sheet.setup.left_margin
    assert all(
        block["at"][0] > margin and block["at"][1] > sheet.setup.top_margin for block in page["blocks"]
    )


def test_sheet_of_the_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    sheet = templates.build_sheet(templates.load_spec(templates.example_path("iso5457_generic")))
    (board.parent / "frame.kicad_wks").write_text(wks.write_drawing_sheet(sheet).text, encoding="utf-8")
    data = pro.template(10)
    data["pcbnew"]["page_layout_descr_file"] = "frame.kicad_wks"
    board.with_suffix(".kicad_pro").write_text(pro.write_project_text(data), encoding="utf-8")
    fake = _fake(tmp_path)
    args = ("export", str(board), "--out", "fab", "--fab-drawing", "--dry-run", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, _work(tmp_path), *args)
    assert code == 0, env
    assert env["result"]["drawings"][0]["sheet"] == "project"
    (plot,) = [c for c in calls(Path(fake)) if c["args"][:3] == ["pcb", "export", "pdf"]]
    assert "--drawing-sheet" not in plot["args"] and "frame.kicad_wks" in plot["tree"]


def test_sheet_that_cannot_be_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    work = _work(tmp_path)
    (work / "d.toml").write_text(SPEC + '[page]\ndrawing_sheet = "missing.kicad_wks"\n', encoding="utf-8")
    fake = _fake(tmp_path)
    args = ("export", str(board), "--out", "fab", *BOTH, "--drawing-spec", "d.toml", "--confirm")
    code, env, _, _ = run(monkeypatch, work, *args, "--kicad-cli", fake)
    assert code == 5, env
    (found,) = [i for i in env["issues"] if i["code"] == "drawing.sheet-unread"]
    assert found["severity"] == "error" and found["where"] == "missing.kicad_wks"
    assert not (work / "fab").exists() and env["result"]["drawings"] == []
    assert not [c for c in calls(Path(fake)) if c["args"][:2] == ["pcb", "export"]]
    (work / "bad.sheet.toml").write_text("[sheet]\n", encoding="utf-8")
    (work / "d.toml").write_text(SPEC + '[page]\ndrawing_sheet = "bad.sheet.toml"\n', encoding="utf-8")
    code, env, _, _ = run(monkeypatch, work, *args, "--kicad-cli", fake)
    assert code == 5 and [i["where"] for i in env["issues"]] == ["bad.sheet.toml"]
