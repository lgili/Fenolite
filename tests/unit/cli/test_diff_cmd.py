# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite diff`` (capability cli-contract, "Diff command"; change c0066). Hermetic."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import run, without_elapsed
from _projects import authored_project

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
FOOTPRINT = DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
SYMBOLS = DATA / "libs" / "Mini.kicad_sym"
SHEET = DATA / "kicad" / "sheets" / "all_items.kicad_wks"
KEYS = {"view", "equal", "a", "b", "summary", "differences", "total", "truncated"}


def _copy(tmp_path: Path, old: str, new: str, *, name: str = "two_layer.kicad_pcb") -> Path:
    text = TWO_LAYER.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    folder = tmp_path / "copy"
    folder.mkdir(exist_ok=True)
    target = folder / name
    target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return target


def test_a_file_against_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(TWO_LAYER))
    result = env["result"]
    assert code == 0 and env["ok"] is True
    assert (result["view"], result["equal"], result["total"], result["differences"]) == ("model", True, 0, [])
    assert set(result) - {"page"} == KEYS and result["truncated"] is False
    assert result["a"] == result["b"] == {"path": "two_layer.kicad_pcb", "kind": "kicad_pcb"}
    assert env["input"]["path"] == "two_layer.kicad_pcb" and env["input"]["kind"] == "kicad_pcb"
    assert env["evidence"]["hypotheses"] == ["H-K-PCB-READ"]


def test_one_footprint_moved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    moved = _copy(tmp_path, "\t\t(at 20 15 90)\n", "\t\t(at 21 15 90)\n")
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(moved))
    result = env["result"]
    assert code == 0 and result["equal"] is False and result["total"] == 1
    assert result["differences"] == [
        {
            "path": "/footprint/R1/position",
            "change": "changed",
            "a": '{"x":20000000,"y":15000000}',
            "b": '{"x":21000000,"y":15000000}',
        }
    ]
    assert result["summary"] == {"footprint": {"added": 0, "removed": 0, "changed": 1}}


def test_built_model_against_its_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(root), str(root / "board.kicad_pcb"))
    assert code == 0, env
    assert env["result"]["a"] == {"path": root.name, "kind": "fenolite_model"}
    assert env["result"]["b"] == {"path": "board.kicad_pcb", "kind": "kicad_pcb"}
    assert env["evidence"]["level"] == "INFERRED" and env["input"]["sha256"] is None


def test_libraries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    text = FOOTPRINT.read_text(encoding="utf-8")
    folder = tmp_path / "Mini.pretty"
    folder.mkdir()
    wider = folder / FOOTPRINT.name
    assert text.count("(size 0.9 0.95)") == 2
    wider.write_text(text.replace("(size 0.9 0.95)", "(size 1 0.95)", 1), encoding="utf-8", newline="\n")
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(FOOTPRINT), str(wider))
    assert code == 0
    assert [(d["path"], d["change"]) for d in env["result"]["differences"]] == [
        ("/pad/Mini:Mini_R_0603-1/size", "changed")
    ]
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(SYMBOLS), str(SYMBOLS))
    assert code == 0 and env["result"]["equal"] is True and env["result"]["a"]["kind"] == "kicad_sym"


def test_two_families_are_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(FOOTPRINT))
    assert code == 2 and err["code"] == "FEN-2001" and env["ok"] is False
    assert "not of one family" in err["message"]


def test_missing_unread_and_malformed_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(tmp_path / "no.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"
    notes = tmp_path / "notes.txt"
    notes.write_text("x\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(notes), str(TWO_LAYER))
    assert code == 2 and err["code"] == "FEN-2001"
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(unbalanced))
    assert code == 3 and err["code"] == "FEN-3004"


def test_opaque_content_shows_with_ext_and_in_the_tree_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    other = _copy(tmp_path, "\t(embedded_fonts no)\n)\n", ")\n")
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(other))
    assert code == 0 and env["result"]["equal"] is True
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(other), "--ext")
    assert [d["path"] for d in env["result"]["differences"]] == ["/design/ext"]
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(other), "--view", "tree")
    result = env["result"]
    assert code == 0 and result["view"] == "tree" and result["equal"] is False
    assert result["heads"] == {"embedded_fonts": {"a": 1, "b": 0}}
    assert result["first_difference"] == "/kicad_pcb" and result["differences"] == []
    assert env["evidence"]["hypotheses"] == ["H-K-SEXPR-STRICT"]


def test_tree_view_of_equal_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(SHEET), str(SHEET), "--view", "tree")
    result = env["result"]
    assert code == 0 and result["equal"] is True and result["first_difference"] is None
    assert result["heads"] == {} and result["a"]["kind"] == "kicad_wks"


def test_tree_view_refusals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    board = str(root / "board.kicad_pcb")
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(root), board, "--view", "tree")
    assert code == 2 and err["code"] == "FEN-2001" and "--view model" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", board, str(FOOTPRINT), "--view", "tree")
    assert code == 2 and "not of one kind" in err["message"]
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", board, board, "--view", "tree", "--ext")
    assert code == 2 and err["code"] == "FEN-2001"


def test_output_is_deterministic_and_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    moved = _copy(tmp_path, "\t\t(at 20 15 90)\n", "\t\t(at 21 15 90)\n")
    first = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(moved))[3]
    second = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(moved))[3]
    assert without_elapsed(first) == without_elapsed(second)
    assert str(tmp_path) not in first and str(DATA) not in first


# --- schematics (task 2.2b, after the schematic reader of c0060) ------------------------------------

FLAT = DATA / "kicad" / "schematic" / "flat.kicad_sch"


def _schematic_copy(tmp_path: Path, old: str, new: str) -> Path:
    text = FLAT.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    folder = tmp_path / "copy"
    folder.mkdir(exist_ok=True)
    target = folder / FLAT.name
    target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return target


def test_two_schematics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    moved = _schematic_copy(tmp_path, "\t\t(at 100 50 0)\n\t\t(unit 1)", "\t\t(at 102.54 50 0)\n\t\t(unit 1)")
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(FLAT), str(moved))
    result = env["result"]
    assert code == 0 and result["equal"] is False
    assert [(d["path"], d["change"]) for d in result["differences"]] == [("/symbol/R1#1/position", "changed")]
    assert result["a"] == result["b"] == {"path": "flat.kicad_sch", "kind": "kicad_sch"}
    assert env["input"]["kind"] == "kicad_sch" and "H-K-SCH-READ" in env["evidence"]["hypotheses"]
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(FLAT), str(FLAT))
    assert code == 0 and env["result"]["equal"] is True and env["result"]["total"] == 0


def test_schematic_tree_view_sees_opaque_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire = "\t(wire\n\t\t(pts\n\t\t\t(xy 1 1) (xy 2 1)\n\t\t)\n\t)\n\t(junction\n"
    more = _schematic_copy(tmp_path, "\t(junction\n", wire)
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(FLAT), str(more))
    assert code == 0 and env["result"]["equal"] is True
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(FLAT), str(more), "--ext")
    assert [d["path"] for d in env["result"]["differences"]] == ["/sheet/ext"]
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(FLAT), str(more), "--view", "tree")
    assert code == 0 and env["result"]["equal"] is False
    counts = env["result"]["heads"]["wire"]
    assert counts["b"] == counts["a"] + 1


def test_schematic_against_a_board_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(FLAT), str(TWO_LAYER))
    assert code == 2 and err["code"] == "FEN-2001" and "not of one family" in err["message"]


# --- Altium inputs and the records view (capability cli-contract, "Diff of document inputs and the records
# view"; altium-verification, "Records view of two Altium files"; change c0044) -----------------------------

ALTIUM = DATA / "altium"
BLINK = ALTIUM / "blink"


def test_altium_model_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = str(BLINK / "blink.PcbDoc")
    code, env, _, raw = run(monkeypatch, tmp_path, "diff", board, board)
    result = env["result"]
    assert code == 0 and (result["view"], result["equal"], result["total"]) == ("model", True, 0)
    assert result["a"] == result["b"] == {"path": "blink.PcbDoc", "kind": "altium_pcbdoc"}
    assert env["input"]["kind"] == "altium_pcbdoc" and len(env["input"]["sha256"]) == 64
    assert env["evidence"]["level"] == "INFERRED" and str(DATA) not in raw
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", board, str(ALTIUM / "routed" / "routed.PcbDoc"))
    assert code == 0 and env["result"]["equal"] is False and "track" in env["result"]["summary"]
    sheets = [
        str(ALTIUM / "sample" / "altium_sample.SchDoc"),
        str(ALTIUM / "sample" / "binary" / "altium_sample.SchDoc"),
    ]
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", *sheets)
    assert code == 0 and env["result"]["equal"] is True  # the two forms of one schematic are one model
    assert [env["result"][side]["kind"] for side in "ab"] == ["altium_schdoc_ascii", "altium_schdoc_binary"]
    libraries = [str(BLINK / "blink.PcbLib"), str(ALTIUM / "routed" / "routed.PcbLib")]
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", *libraries)
    assert code == 0 and env["result"]["a"]["kind"] == "altium_pcblib"


def test_a_kicad_board_against_an_altium_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(BLINK / "blink.PcbDoc"))
    result = env["result"]
    assert code == 0 and result["equal"] is False
    assert (result["a"]["kind"], result["b"]["kind"]) == ("kicad_pcb", "altium_pcbdoc")
    assert env["evidence"]["level"] == "INFERRED"
    code, _, err, _ = run(
        monkeypatch, tmp_path, "diff", str(BLINK / "blink.PcbDoc"), str(BLINK / "blink.PcbLib")
    )
    assert code == 2 and err["code"] == "FEN-2001" and "not of one family" in err["message"]


def test_altium_project_folder_as_an_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(BLINK), str(BLINK / "blink.PrjPcb"))
    result = env["result"]
    assert code == 0 and result["equal"] is True
    assert result["a"] == result["b"] == {"path": "blink.PrjPcb", "kind": "altium_prjpcb"}
    cut = tmp_path / "blink.PcbDoc"
    cut.write_bytes((BLINK / "blink.PcbDoc").read_bytes()[:100])
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(cut), str(BLINK / "blink.PcbDoc"))
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(tmp_path / "gone.PcbDoc"), str(cut))
    assert code == 3 and err["code"] == "FEN-3001"


def test_records_view_of_a_file_against_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sheet = str(BLINK / "blink.SchDoc")
    code, env, _, raw = run(monkeypatch, tmp_path, "diff", sheet, sheet, "--view", "records")
    result = env["result"]
    assert code == 0 and set(result) - {"page"} == KEYS
    assert (result["view"], result["equal"], result["total"], result["differences"]) == (
        "records",
        True,
        0,
        [],
    )
    assert result["a"] == result["b"] == {"path": "blink.SchDoc", "kind": "altium_schdoc_binary"}
    assert env["issues"] == [] and env["input"]["kind"] == "altium_schdoc_binary" and str(DATA) not in raw
    assert env["evidence"]["hypotheses"] and all(
        h.startswith("H-A-RD-SCH-") for h in env["evidence"]["hypotheses"]
    )


def test_records_view_lists_and_pages_the_records(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pair = [str(BLINK / "blink.PcbDoc"), str(ALTIUM / "routed" / "routed.PcbDoc")]
    code, env, _, first = run(monkeypatch, tmp_path, "diff", *pair, "--view", "records")
    result = env["result"]
    assert code == 0 and result["equal"] is False and result["truncated"] is False
    assert result["summary"]["Nets6/Data"] == {"added": 0, "removed": 0, "changed": 4}
    assert (
        result["total"]
        == len(result["differences"])
        == sum(sum(c.values()) for c in result["summary"].values())
    )
    assert env["evidence"]["level"] == "CORPUS-VERIFIED"
    second = run(monkeypatch, tmp_path, "diff", *pair, "--view", "records")[3]
    assert without_elapsed(first) == without_elapsed(second)
    code, env, _, _ = run(monkeypatch, tmp_path, "diff", *pair, "--view", "records", "--limit", "2")
    paged = env["result"]
    assert len(paged["differences"]) == 2 and paged["truncated"] is True and paged["total"] == result["total"]
    assert paged["differences"] == result["differences"][:2] and paged["page"]["next"] is not None


def test_records_view_refusals_of_kinds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Records view refused for KiCad files" and "Different kinds refused"."""
    board = str(TWO_LAYER)
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", board, board, "--view", "records")
    assert code == 2 and err["code"] == "FEN-2001" and "--view model" in err["hint"]
    sheet, document = str(BLINK / "blink.SchDoc"), str(BLINK / "blink.PcbDoc")
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", sheet, document, "--view", "records")
    assert code == 2 and err["code"] == "FEN-2001" and "not of one kind" in err["message"]
    ascii_sheet = str(ALTIUM / "sample" / "altium_sample.SchDoc")
    binary_sheet = str(ALTIUM / "sample" / "binary" / "altium_sample.SchDoc")
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", ascii_sheet, binary_sheet, "--view", "records")
    assert code == 2 and "not of one kind" in err["message"]  # the records view does not convert a form
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(BLINK), sheet, "--view", "records")
    assert code == 2 and err["code"] == "FEN-2001" and "--view model" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", sheet, sheet, "--view", "records", "--ext")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", sheet, sheet, "--view", "tree")
    assert code == 2 and err["code"] == "FEN-2001" and "--view model" in err["hint"]
