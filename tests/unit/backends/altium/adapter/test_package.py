# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The adapter package (capability altium-import, "Adapter package"; change c0043): what its modules
import, its exports, its evidence, and that an import does not depend on the hash seed."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from fenolite.backends.altium import adapter
from fenolite.backends.altium.adapter import evidence
from fenolite.backends.altium.read import pcb, pcblib, sch
from fenolite.core.evidence import Level, min_level
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "src" / "fenolite" / "backends" / "altium" / "adapter"
WRITERS = (
    "ascii", "binary", "schdoc", "schlib", "altsym", "layout", "project", "prjpcb", "pcbrecords", "pcblib",
    "pcbdoc", "libboard", "docboard", "cfb", "hierarchy", "symbols",
)  # fmt: skip
ALLOWED = ("fenolite.core", "fenolite.model", "fenolite.geometry", "fenolite.backends.base")
FORBIDDEN_STDLIB = {"subprocess", "os", "shutil", "tempfile", "socket", "pathlib.Path"}
EXPORTS = (
    "import_board", "import_circuit", "import_project", "import_footprints", "import_symbols", "netlist",
    "SheetInput", "BoardInput", "ProjectInput", "NetOptions", "Netlist", "NetGroup", "PinKey", "LAYERS",
    "PIN_TYPES", "EXT_KEYS", "IMPORT_ISSUE_CODES", "EVIDENCE",
)  # fmt: skip
SCRIPT = """
import hashlib, sys
from pathlib import Path
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.model import canonical
data = Path(sys.argv[1]).read_bytes()
issues = []
design = import_board(read_pcbdoc(data), file="blink.PcbDoc", sha256=hashlib.sha256(data).hexdigest(),
                      issues=issues)
for part in (design.board, design.circuit, design.rules):
    sys.stdout.write(canonical.dumps(part))
sys.stdout.write(repr(issues))
"""


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative import"
            module = node.module or ""
            names.add(module)
            if module in ("fenolite.backends.altium", "fenolite.backends"):
                names |= {f"{module}.{alias.name}" for alias in node.names}
    return names


def test_imports_name_no_writer_and_no_third_party() -> None:
    modules = sorted(PACKAGE.glob("*.py"))
    assert len(modules) >= 10
    for path in modules:
        for name in _imports(path):
            top = name.split(".")[0]
            if top == "fenolite":
                inside = name == "fenolite" or name.startswith(ALLOWED)
                reader = name.startswith(
                    ("fenolite.backends.altium.read", "fenolite.backends.altium.adapter")
                )
                evidence = name == "fenolite.backends.altium.import_evidence"
                assert inside or reader or evidence or name == "fenolite.backends.altium", (
                    f"{path.name}: {name}"
                )
                assert name not in {f"fenolite.backends.altium.{w}" for w in WRITERS}, f"{path.name}: {name}"
            else:
                assert top == "__future__" or top in sys.stdlib_module_names, f"{path.name}: {name}"
                assert top not in FORBIDDEN_STDLIB and top != "tests", f"{path.name}: {name}"
        text = path.read_text(encoding="utf-8")
        assert "open(" not in text and "read_bytes" not in text and "write_" not in text, path.name


def test_exports() -> None:
    for name in EXPORTS:
        assert hasattr(adapter, name), name
        assert name in adapter.__all__, name


def test_evidence_is_the_lowest_level_of_the_registered_rows() -> None:
    rows = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    registered = tuple(sorted(i for i in rows if i.startswith("H-A-IMP-")))
    named = adapter.EVIDENCE.hypotheses
    assert tuple(sorted(i for i in named if i.startswith("H-A-IMP-"))) == registered
    # the one row of the writer that the import rests on too: the tenting flags of a via (c0112)
    assert tuple(i for i in named if not i.startswith("H-A-IMP-")) == ("H-A-PCB-CU-VIATENT",)
    assert evidence.MAPPING_HYPOTHESES == ("H-A-PCB-CU-VIATENT",) and "H-A-PCB-CU-VIATENT" in rows
    assert set(evidence.LEVELS) == set(registered)
    live = {ident: rows[ident].level for ident in registered if not rows[ident].refuted}
    assert {ident: evidence.LEVELS[ident] for ident in live} == live
    readers = (sch.EVIDENCE.level, pcb.EVIDENCE.level, pcblib.EVIDENCE.level)
    assert evidence.READER_LEVELS == readers
    assert adapter.EVIDENCE.level is min_level(*live.values(), *readers)
    assert adapter.EVIDENCE.level is Level.INFERRED


def test_deterministic_import_whatever_the_hash_seed(tmp_path: Path) -> None:
    script = tmp_path / "run.py"
    script.write_text(SCRIPT, encoding="utf-8")
    document = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"
    outputs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run(
            [sys.executable, str(script), str(document)], capture_output=True, text=True, env=env, check=True
        )
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1] and len(outputs[0]) > 1000
