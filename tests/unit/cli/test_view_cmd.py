# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite view`` (capability cli-contract, "View command")."""

from __future__ import annotations

import json
import shutil
import socket
import threading
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli import cmd_view
from fenolite.view.export import embedded
from fenolite.view.findings import GROUPS

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
HIER = ROOT / "tests" / "data" / "altium" / "hier" / "altium_hier.PrjPcb"


def test_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a board"."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD))
    assert code == 0
    result = envelope["result"]
    docs = result["project"]["groups"][0]["documents"]
    assert docs[0]["viewable"] is True and result["document"] == "doc1"
    assert result["summary"]["counts"]["tracks"] == 3
    assert list(tmp_path.iterdir()) == []


def test_altium_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM))
    assert code == 0 and envelope["result"]["summary"]["counts"]["pads"] > 0
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(HIER), "--doc", "altium_hier_flash.Harness")
    assert code == 0 and envelope["result"]["summary"] is None
    assert "no viewer" in envelope["result"]["notes"][0]


def test_schematic_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a sheet" (c0177)."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(HIER), "--doc", "altium_hier.SchDoc")
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "schematic" and summary["counts"]["components"] == 1
    assert summary["counts"]["sheet_symbols"] == 2 and envelope["evidence"]["level"] == "INFERRED"
    assert list(tmp_path.iterdir()) == []
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(HIER), "--export", "view.html", "--confirm")
    assert code == 0
    data = embedded((tmp_path / "view.html").read_text(encoding="utf-8"))
    assert data is not None
    kinds = sorted(scene["kind"] for scene in data["scenes"].values())
    assert kinds == ["library", "schematic", "schematic", "schematic"]


def test_export_follows_the_protocol(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Export follows the protocol"."""
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--export", "view.html")
    assert code == 4 and error["code"] == "FEN-4001" and not (tmp_path / "view.html").exists()
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--export", "view.html", "--confirm"
    )
    assert code == 0
    data = embedded((tmp_path / "view.html").read_text(encoding="utf-8"))
    assert data is not None and list(data["scenes"]) == ["doc1"]
    assert envelope["result"]["export"]["documents"] == ["doc1"]


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--export", "x.html")
    assert code == 2 and error["code"] == "FEN-2001"
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(tmp_path / "missing.kicad_pcb"))
    assert code == 3 and error["code"] == "FEN-3001"
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", "notes.txt")
    assert code == 2 and error["code"] == "FEN-2001"
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--port", "70000")
    assert code == 2


def test_overlay_of_an_analyze_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, out = run(
        monkeypatch, tmp_path, "analyze", str(BOARD), "--kinds", "clearance", "--pair", "GND", "VCC"
    )
    assert code == 0
    (tmp_path / "a.json").write_text(out, encoding="utf-8")
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--overlay", "a.json", "--export", "v.html", "--confirm"
    )
    assert code == 0
    data = embedded((tmp_path / "v.html").read_text(encoding="utf-8"))
    assert data is not None
    overlays = data["scenes"]["doc1"]["overlays"]
    assert overlays and overlays[0]["kind"] == "clearance" and "GND × VCC" in overlays[0]["label"]
    (tmp_path / "bad.json").write_text(json.dumps({"result": {}}), encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--overlay", "bad.json")
    assert code == 3 and error["code"] == "FEN-3004"


def test_serve_until_stopped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()
    monkeypatch.setattr(cmd_view, "SERVE_STOP", stop)
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--no-browser", "--port", "0"
    )
    assert code == 0
    assert envelope["result"]["serve"]["url"].startswith("http://127.0.0.1:")


def test_theme(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A theme file on a KiCad board" (c0178)."""
    theme = tmp_path / "mine.json"
    theme.write_text(json.dumps({"board": {"copper": {"f": "rgb(1, 2, 3)"}}}), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--theme", "mine.json")
    assert code == 0 and envelope["result"]["theme"] == "kicad:mine.json"
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD))
    assert code == 0 and envelope["result"]["theme"] == "kicad"
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM))
    assert code == 0 and envelope["result"]["theme"] == "altium"
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--theme", "no-such-theme-anywhere")
    assert code == 3 and error["code"] == "FEN-3001"
    (tmp_path / "bad.json").write_text("[1]", encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--theme", "bad.json")
    assert code == 3 and error["code"] == "FEN-3004"


def test_kicad_sheet_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sheet = ROOT / "tests" / "data" / "kicad" / "schematic" / "flat.kicad_sch"
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(sheet))
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "schematic" and summary["counts"]["components"] == 5
    assert envelope["result"]["theme"] == "kicad"


def test_library_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a footprint library" (c0179)."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM), "--doc", "blink.PcbLib")
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "library" and summary["lib"] == "pcb" and summary["counts"]["items"] == 3
    assert envelope["result"]["theme"] == "altium"
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(ROOT / "tests" / "data" / "libs" / "Mini_v9.kicad_sym")
    )
    assert code == 0 and envelope["result"]["summary"]["lib"] == "schematic"
    assert envelope["result"]["theme"] == "kicad"


def test_drawing_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a drawing" (c0180)."""
    from _draftsman import DOCUMENT, stored

    path = tmp_path / "authored.PCBDwf"
    path.write_bytes(stored(DOCUMENT))
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(path), "--json")
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "drawing" and summary["counts"]["sheets"] == 1
    assert summary["counts"]["BoardAssemblyViewData"] == 1 and not summary["panel"]


CACHE_BOARD = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"


def test_second_open_reads_the_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "blink.PcbDoc"
    shutil.copy(CACHE_BOARD, board)
    folder = tmp_path / "cache"
    monkeypatch.setenv("FENOLITE_CACHE_DIR", str(folder))
    code, first, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--json")
    assert code == 0 and first["result"]["cache"] == {"where": "user", "hits": 0, "misses": 1}
    code, second, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--json")
    assert (
        second["result"]["cache"]["hits"] == 1 and second["result"]["summary"] == first["result"]["summary"]
    )
    data = bytearray(board.read_bytes())
    data[-1] ^= 0xFF  # one byte of the file changes, so its digest does
    board.write_bytes(bytes(data))
    code, third, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--json")
    assert third["result"]["cache"]["misses"] == 1
    assert len(list((folder / "view").glob("*.json.gz"))) == 2


def test_off_and_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "blink.PcbDoc"
    shutil.copy(CACHE_BOARD, board)
    code, reply, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--cache", "off", "--json")
    assert code == 0 and reply["result"]["cache"] == {"where": "off", "hits": 0, "misses": 0}
    run(monkeypatch, tmp_path, "view", str(board), "--cache", "project", "--json")
    assert list((tmp_path / ".fenolite" / "view-cache").glob("*.json.gz"))


def test_export_docs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Export of one document" (c0182)."""
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(ALTIUM),
        "--export",
        str(tmp_path / "p.html"),
        "--docs",
        "blink.PcbDoc",
        "--json",
    )
    assert code in (0, 4)
    documents = envelope["result"]["export"]["documents"]
    assert len(documents) == 1
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(ALTIUM), "--export", "x.html", "--docs", "nope", "--json"
    )
    assert code == 2


def test_compare(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Compare counts" (c0184): a board against its copy with one part moved."""
    old = tmp_path / "old.kicad_pcb"
    shutil.copy(BOARD, old)
    text = BOARD.read_text(encoding="utf-8")
    start = text.index("(footprint ")
    at = text.index("(at ", start)
    end = text.index(")", at)
    x, y, *rest = text[at + 4 : end].split()
    new = tmp_path / "new.kicad_pcb"
    new.write_text(text[: at + 4] + " ".join([str(float(x) + 1), y, *rest]) + text[end:], encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(new), "--compare", str(old), "--json")
    assert code == 0 and envelope["result"]["compare"]["moved"] == 1
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(new), "--compare", str(ALTIUM_SHEET), "--json"
    )
    assert code == 2


ALTIUM_SHEET = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"


def test_variant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Unknown variant" (c0186), and the counts of a known one."""
    from _variants import variant_text

    folder = tmp_path / "blink"
    shutil.copytree(ALTIUM.parent, folder)
    sheet = cmd_view.scene_of(folder / "blink.SchDoc")
    uid = next(c["uid"] for c in sheet["comps"] if c["ref"] == "R1")
    project = folder / "blink.PrjPcb"
    project.write_bytes(project.read_bytes() + b"\r\n" + variant_text(uid).encode())
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(project), "--doc", "blink.SchDoc", "--variant", "Lite", "--json"
    )
    assert code == 0 and envelope["result"]["variant"] == {"name": "Lite", "fitted": 2, "not_fitted": 1}
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(project), "--variant", "Nope", "--json")
    assert code == 2


def test_check_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Not a check reply" (c0188), and the counts of a check reply drawn on the board."""
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "check", str(BOARD), "--stages", "model.validate,copper.clearance", "--json"
    )
    reply = tmp_path / "check.json"
    reply.write_text(json.dumps(envelope), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--check", str(reply), "--json")
    assert code == 0
    found = envelope["result"]["check"]
    assert found["total"] == len(json.loads(reply.read_text(encoding="utf-8"))["issues"]) > 0
    analyze = tmp_path / "analyze.json"
    analyze.write_text(json.dumps({"command": "analyze", "result": {"distances": []}, "issues": []}))
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--check", str(analyze), "--json")
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--check", "missing.json", "--json")
    assert code == 3 and err["code"] == "FEN-3001"


def test_check_run_on_altium(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`--check run` checks the project in the same process and writes nothing (c0188)."""
    folder = tmp_path / "blink"
    shutil.copytree(ALTIUM.parent, folder)
    before = sorted(p.name for p in folder.iterdir())
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(folder / "blink.PrjPcb"),
        "--doc",
        "blink.PcbDoc",
        "--check",
        "run",
        "--json",
    )
    assert code == 0 and set(envelope["result"]["check"]) == {"error", "warning", "info", "total", "placed"}
    assert sorted(p.name for p in folder.iterdir()) == before


def test_marks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Marks for an agent" (c0189): `result.marks` lists the marks of an authored review file."""
    review = tmp_path / "review.json"
    marks = [
        {
            "id": "m1",
            "doc": BOARD.name,
            "x_nm": 12_500_000,
            "y_nm": 3_250_000,
            "note": "gap too small",
            "select": "R1",
        },
        {"id": "m2", "doc": "other.kicad_sch", "x_nm": 0, "y_nm": 0, "note": "label?"},
    ]
    review.write_text(json.dumps({"schema": "fenolite.review.v0", "marks": marks}), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--marks", str(review), "--json")
    assert code == 0
    first, second = envelope["result"]["marks"]
    assert (first["doc"], first["x_mm"], first["y_mm"], first["note"]) == (
        BOARD.name,
        12.5,
        3.25,
        "gap too small",
    )
    assert second["note"] == "label?"
    review.write_text(json.dumps({"schema": "fenolite.review.v0", "marks": [{"id": "m1"}]}), encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--marks", str(review), "--json")
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--marks", "none.json", "--json")
    assert code == 3 and err["code"] == "FEN-3001"


def test_select(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`--select` opens the page at a part or net (c0189): the reply says whether the document holds it, and
    an exported page carries it."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--select", "R1", "--json")
    assert code == 0 and envelope["result"]["select"] == {"name": "R1", "found": True}
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--select", "net:GND", "--json")
    assert envelope["result"]["select"]["found"] is True
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--select", "U99", "--json")
    assert envelope["result"]["select"]["found"] is False and "U99" in envelope["result"]["notes"][-1]
    out = tmp_path / "view.html"
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--select",
        "R1",
        "--export",
        str(out),
        "--dry-run",
        "--json",
    )
    plan = envelope["result"]["plan_id"]
    code, _, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--select",
        "R1",
        "--export",
        str(out),
        "--confirm",
        "--plan",
        plan,
    )
    data = embedded(out.read_text(encoding="utf-8"))
    assert code == 0 and data is not None and data["select"] == "R1" and data["marks"] == []


def test_review_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Findings in the summary" (change c0193)."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD))
    assert code == 0
    summary = envelope["result"]["summary"]
    assert set(summary["findings"]) == {*GROUPS, "open_ground", "open_net"} and summary["models"] is None
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--no-review")
    assert code == 0 and envelope["result"]["summary"]["findings"] == {}
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--silk-gap", "-1")
    assert code == 2 and error["code"] == "FEN-2001"


def test_port_in_use(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Port in use" (change c0193)."""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    try:
        port = str(holder.getsockname()[1])
        code, _, error, _ = run(
            monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--no-browser", "--port", port
        )
    finally:
        holder.close()
    assert code == 2 and error["code"] == "FEN-2001" and "--port 0" in error["hint"]


def test_findings_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A findings file is drawn" (change c0193)."""
    findings = {
        "schema": "fenolite.view_overlay.v0",
        "groups": [{"id": "insulation", "title": "Insulation report", "note": "pairs below their minimum"}],
        "items": [
            {
                "group": "insulation",
                "kind": "line",
                "points_nm": [[1_000_000, 2_000_000], [3_000_000, 2_000_000]],
                "label": "A × B",
            }
        ],
    }
    (tmp_path / "f.json").write_text(json.dumps(findings), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--overlay", "f.json")
    assert code == 0 and envelope["result"]["summary"]["findings"]["insulation"] == 1
    findings["items"][0]["kind"] = "circle"
    (tmp_path / "f.json").write_text(json.dumps(findings), encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--overlay", "f.json")
    assert code == 3 and error["code"] == "FEN-3004"


def test_check_findings_carry_their_explanations() -> None:
    """Change c0245, M11: the Messages panel shows each code's `fenolite explain` text from the page."""
    reply = {
        "command": "check",
        "result": {"stages": {}},
        "issues": [
            {"code": "roles.width-current", "severity": "error", "message": "m", "where": "VOUT"},
            {"code": "no.such-code", "severity": "info", "message": "m", "where": ""},
        ],
    }
    tree = cmd_view.load_tree(BOARD)
    scene = cmd_view._with_check(reply, tree, BOARD, cmd_view.scene_of(BOARD))
    explain = scene["check"]["explain"]
    assert set(explain) == {"roles.width-current"}
    assert set(explain["roles.width-current"]) == {"meaning", "fix", "see"}


def test_keymap_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Change c0245: `--keymap NAME|FILE` reaches the page; a bad file is FEN-3004, a missing one FEN-3001."""
    page = tmp_path / "view.html"
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--keymap",
        "altium",
        "--export",
        str(page),
        "--confirm",
        "--json",
    )
    assert code == 0
    data = embedded(page.read_text(encoding="utf-8"))
    assert data is not None and data["settings"]["keymap"]["base"] == "altium"
    keys = tmp_path / "keys.json"
    keys.write_text(
        json.dumps({"schema": "fenolite.view_keymap.v0", "base": "kicad", "bindings": {"view.fit": ["F5"]}})
    )
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--keymap", str(keys), "--json")
    assert code == 3 and err["code"] == "FEN-3004" and "browser" in err["message"]
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--keymap", "emacs", "--json")
    assert code == 3 and err["code"] == "FEN-3001"


def test_workspace_roles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Roles summary for an agent" and "Edit needs the server" (c0245)."""
    script = ROOT / "examples" / "roles" / "buck_shunt" / "bad.py"
    code, _, _, _ = run(
        monkeypatch, tmp_path, "build", str(script), "--out", str(tmp_path / "b"), "--confirm"
    )
    assert code == 0
    before = sorted(p.name for p in (tmp_path / "b").rglob("*"))
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(tmp_path / "b" / "buck_shunt_bad.kicad_pro"),
        "--workspace",
        "roles",
    )
    assert code == 0
    roles = envelope["result"]["roles"]
    assert roles["counts"] == {"confirmed": 0, "declared": 4, "inferred": 8} and roles["groups"] == 4
    assert envelope["evidence"]["level"] == "INFERRED"
    assert sorted(p.name for p in (tmp_path / "b").rglob("*")) == before  # nothing written
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--edit")
    assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--edit"
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM_SHEET), "--workspace", "roles")
    assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--workspace"


def test_layout_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Change c0245: `--layout FILE` reaches the page; a bad file is FEN-3004, a missing one FEN-3001."""
    good = tmp_path / "layout.json"
    good.write_text(
        json.dumps(
            {
                "schema": "fenolite.view_layout.v0",
                "workspace": "board",
                "docks": {"left": {"size": 300, "groups": [{"panels": ["projects", "messages"]}]}},
                "closed": [],
            }
        ),
        encoding="utf-8",
    )
    page = tmp_path / "view.html"
    code, _, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--layout", str(good), "--export", str(page), "--confirm"
    )
    assert code == 0
    data = embedded(page.read_text(encoding="utf-8"))
    assert data is not None and data["settings"]["layout"]["docks"]["left"]["size"] == 300
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "fenolite.view_layout.v0", "workspace": "kitchen", "docks": {}}))
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--layout", str(bad))
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--layout", "missing.json")
    assert code == 3 and err["code"] == "FEN-3001"


def test_window_requires_serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--window")
    assert code == 2 and error["code"] == "FEN-2001" and "--serve" in error["message"]


def test_window_missing_extra(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original = cmd_view.importlib.import_module

    def without_window(name: str):
        if name == "webview":
            raise ImportError("not installed")
        return original(name)

    monkeypatch.setattr(cmd_view.importlib, "import_module", without_window)
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--window")
    assert code == 6 and error["code"] == "FEN-6001" and "fenolite[view-app]" in error["hint"]
    # Ordinary summaries never import the native host.
    code, _, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD))
    assert code == 0


def test_window_serves_and_closes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from types import SimpleNamespace
    from urllib.request import urlopen

    shown = []

    def create_window(title: str, url: str, **kwargs: int) -> None:
        shown.append((title, url))
        with urlopen(url, timeout=5) as response:
            assert response.status == 200 and b"<html" in response.read()

    native = SimpleNamespace(create_window=create_window, start=lambda: None)
    monkeypatch.setattr(cmd_view, "_window_module", lambda: native)
    monkeypatch.setattr(cmd_view.webbrowser, "open", lambda url: pytest.fail("opened a browser"))
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--window", "--port", "0"
    )
    assert code == 0 and len(shown) == 1
    assert shown[0][0] == BOARD.name + " · Fenolite"
    url = envelope["result"]["serve"]["url"]
    with pytest.raises(OSError):
        urlopen(url, timeout=1)
