# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadCli.import_board`` and ``altium_import`` against the fake ``kicad-cli`` (capability
design-equivalence, "Board import runner"; change c0045)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from _fakecli import calls, fake_kicad_cli
from _projects import tree_snapshot

from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import (
    IMPORT_REPORT,
    IMPORTED_BOARD,
    ImportRun,
    KicadCli,
    KicadCliError,
    KicadCliVersionError,
)
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level

DATA = Path(__file__).resolve().parents[3] / "data"
PCBDOC = DATA / "altium" / "blink" / "blink.PcbDoc"
BOARD = (DATA / "kicad" / "board" / "two_layer.kicad_pcb").read_text(encoding="utf-8")
OUTPUT = (
    "Importing 'blink.PcbDoc' using Altium Designer format...\n"
    "07:06:18 PM: Warning: Layer 'Internal Plane 1' could not be mapped and will be skipped.\n"
    "Error: no time stamp\n"
    "A line that only says Warning somewhere\n"
)


def _imports(fake: Path) -> list[list[str]]:
    return [call["args"] for call in calls(fake) if call["args"][:2] == ["pcb", "import"]]


def test_import_of_a_document(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", imported=BOARD, import_output=OUTPUT, import_warnings=["w"])
    before = tree_snapshot(PCBDOC.parent)
    run = KicadCli(fake).import_board(PCBDOC)
    assert isinstance(run, ImportRun) and run.run.ok
    assert run.board == BOARD.encode("utf-8")
    assert run.report is not None and run.report["source_file"] == "blink.PcbDoc"
    assert run.report["warnings"] == ["w"]
    assert set(run.run.outputs) == {IMPORTED_BOARD, IMPORT_REPORT}
    assert _imports(fake) == [
        ["pcb", "import", "--format", "altium", "--report-format", "json", "--report-file", "import.json",
         "-o", "imported.kicad_pcb", "blink.PcbDoc"]
    ]  # fmt: skip
    assert tree_snapshot(PCBDOC.parent) == before
    KicadCli(fake).import_board(PCBDOC, format="eagle")
    assert _imports(fake)[-1][2:4] == ["--format", "eagle"]


def test_refused_on_9(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", version="9.0.9", imported=BOARD)
    with pytest.raises(
        KicadCliVersionError, match=r"pcb import needs kicad-cli 10\.0 or newer; running 9\.0\.9"
    ):
        KicadCli(fake).import_board(PCBDOC)
    with pytest.raises(KicadCliVersionError, match="10.0"):
        altium_import.import_design(KicadCli(fake), PCBDOC)
    assert _imports(fake) == []


def test_tool_writes_no_board(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin")
    run = KicadCli(fake).import_board(PCBDOC)
    assert run.board is None and run.report is None and run.run.returncode == 0
    with pytest.raises(KicadCliError, match=r"kicad-cli pcb import wrote no board \(exit 0\)") as caught:
        altium_import.import_design(KicadCli(fake), PCBDOC)
    assert not isinstance(caught.value, KicadCliVersionError)


def test_report_that_is_no_json_object(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", writes=[IMPORT_REPORT])
    assert KicadCli(fake).import_board(PCBDOC).report == {}  # ``writes`` gives the text ``{}``
    script = (fake.parent / "fake.py").read_text(encoding="utf-8")
    (fake.parent / "fake.py").write_text(script.replace('.write("{}")', '.write("[1")'), encoding="utf-8")
    assert KicadCli(fake).import_board(PCBDOC).report is None
    (fake.parent / "fake.py").write_text(script.replace('.write("{}")', '.write("[1]")'), encoding="utf-8")
    assert KicadCli(fake).import_board(PCBDOC).report is None


def test_import_design_reads_the_board_and_the_messages(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", imported=BOARD, import_output=OUTPUT, import_warnings=["w", ""])
    found = altium_import.import_design(KicadCli(fake), PCBDOC)
    design = found.read.design
    assert design.board is not None and len(design.board.footprints) == 2
    assert sorted(c.ref for c in design.circuit.components) == ["D1", "R1"]
    assert found.tool_version == "10.0.6"
    assert found.messages == (
        "warning: w",
        "warning: Layer 'Internal Plane 1' could not be mapped and will be skipped.",
        "error: no time stamp",
    )
    assert found.read.evidence == altium_import.IMPORT_EVIDENCE
    assert altium_import.IMPORT_EVIDENCE.level is Level.INFERRED
    assert altium_import.IMPORT_EVIDENCE.oracle == "kicad-cli"
    assert altium_import.IMPORT_EVIDENCE.hypotheses == ("H-K-00", "H-K-PCB-READ")


def test_a_board_the_reader_refuses(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", imported="(kicad_pcb")
    with pytest.raises(FormatError):
        altium_import.import_design(KicadCli(fake), PCBDOC)


def test_messages_hold_no_temporary_folder(tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", imported=BOARD)
    script = (fake.parent / "fake.py").read_text(encoding="utf-8")
    line = (
        'print("Warning: cannot read " + os.path.join(os.getcwd(), "x.PcbDoc"))\ntime.sleep(config["sleep"])'
    )
    assert 'time.sleep(config["sleep"])' in script
    (fake.parent / "fake.py").write_text(
        script.replace('time.sleep(config["sleep"])', line), encoding="utf-8"
    )
    found = altium_import.import_design(KicadCli(fake), PCBDOC)
    (message,) = found.messages
    assert message.startswith("warning: cannot read <tmp>") and message.endswith("x.PcbDoc")
    assert "fenolite-kicad-" not in message


def test_exclusion_data_is_packaged() -> None:
    text = altium_import.exclusions_text()
    data = tomllib.loads(text)
    assert data["schema"] == 1
    assert [p["name"] for p in data["profile"]] == [altium_import.PROFILE] * len(data["profile"])
    assert "10.0" in [p["tool_version"] for p in data["profile"]]
    assert all(p["frame"] == "relative" and p["tool"] == "kicad-cli" for p in data["profile"])
    source = Path(altium_import.__file__).parent / "data" / altium_import.EXCLUSIONS_FILE
    assert source.read_text(encoding="utf-8") == text
