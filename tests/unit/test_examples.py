# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The second example board (capability release-gate, "Second example board"; change c0025) and the
structure of the yardstick board ("Yardstick board"; change c0119)."""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import tokenize
from collections import Counter
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.cli._script import run_design_script
from fenolite.dsl import to_model

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "board_40parts"
SCRIPT = EXAMPLE / "design.py"
MINIMUMS = {"clearance": 150_000, "track_width": 150_000, "via_diameter": 450_000, "via_drill": 200_000}


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_board_40parts_header_and_listing() -> None:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# SPDX-License-Identifier: CC0-1.0"
    assert lines[1].startswith("# Authored for Fenolite")
    assert (EXAMPLE / "fp-lib-table").is_file() and (EXAMPLE / "sym-lib-table").is_file()
    assert "`board_40parts/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_board_40parts_holds_forty_parts() -> None:
    """Scenario "Forty parts": 40 parts, two of them placed and locked, two modules, the script's minimums."""
    design = run_design_script(SCRIPT).design
    parts = list(design.parts.values())
    assert len(parts) == 40
    kinds = Counter(part.lib_id for part in parts)
    assert kinds == {"Mini:Mini_QFP32_IC": 2, "Mini:Mini_R": 20, "Mini:Mini_LED": 18}
    placed = {part.ref: part.request for part in parts if part.request is not None}
    assert sorted(placed) == ["U1", "U2"] and all(request.locked for request in placed.values())
    assert len(design.modules) >= 2
    assert design.size == (100_000_000, 80_000_000)

    model = to_model(design)
    assert [netclass.name for netclass in model.circuit.netclasses if netclass.name != "Default"] == ["PWR"]
    assert len(model.board.zones) == 1 and "B.Cu" in model.board.zones[0].layers
    board_wide = {rule.kind: rule.min for rule in model.rules.rules if rule.priority == 0}
    assert {kind: board_wide[kind] for kind in MINIMUMS} == MINIMUMS


@pytest.mark.parametrize("target", [9, 10])
def test_board_40parts_builds_without_a_subprocess(
    target: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Builds for both targets without a subprocess"."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a build started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    folder = tmp_path / "bar"
    code = cli_main.main(
        ["build", str(SCRIPT), "--out", str(folder), "--kicad-version", str(target), "--confirm", "--json"]
    )
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert not [issue for issue in envelope["issues"] if issue["severity"] == "error"]
    assert envelope["result"]["components"] == 40
    for suffix in (".kicad_pro", ".kicad_pcb", ".kicad_dru"):
        assert (folder / f"board_40parts{suffix}").is_file()
    board = (folder / "board_40parts.kicad_pcb").read_text(encoding="utf-8")
    assert '"F.Cu"' in board and '"B.Cu"' in board and '"In1.Cu"' not in board


# ---- the yardstick board (capability release-gate, "Yardstick board"; change c0119)

YARDSTICK = ROOT / "examples" / "yardstick" / "design.py"
YARDSTICK_PAGE = ROOT / "docs" / "evidence" / "yardstick.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
STAGE_COPPER = {1: 4, 2: 6, 3: 6, 4: 6, 5: 6}
CHANNELS = 8
PROVENANCE = "chosen for the example"


def _yardstick_stage(script: Path) -> object:
    """The module-level ``STAGE`` of the script, read from its syntax tree."""
    for node in ast.parse(script.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "STAGE" for target in node.targets
        ):
            return node.value.value if isinstance(node.value, ast.Constant) else None
    return None


def yardstick_problems(script: Path) -> list[str]:
    """What is wrong with the structure of a yardstick script, loaded through ``fenolite.dsl`` without a
    build (scenario "Structure without a build")."""
    stage = _yardstick_stage(script)
    if not isinstance(stage, int) or stage not in STAGE_COPPER:
        return [f"STAGE is {stage!r}, not a whole number from 1 to 5"]
    design = run_design_script(script).design
    parts = list(design.parts.values())
    problems: list[str] = []
    if design.copper != STAGE_COPPER[stage]:
        problems.append(f"STAGE = {stage} takes a copper count of {STAGE_COPPER[stage]}, not {design.copper}")
    if len(parts) < 300:
        problems.append(f"{len(parts)} parts, fewer than 300")
    channels = {name: module for name, module in design.modules.items() if re.fullmatch(r"ch[1-8]", name)}
    sizes = {len(module.children) for module in channels.values()}
    if len(channels) != CHANNELS or len(sizes) != 1:
        problems.append(f"{len(channels)} channel modules with the sizes {sorted(sizes)}")
    for path, part in design.parts.items():
        digits = re.search(r"\d+$", part.ref)
        number = int(digits.group()) if digits else -1
        module = path.split("/")[0]
        if module in channels and number // 100 != int(module[2:]):
            problems.append(f"{part.ref} of {module} is not numbered {module[2:]}xx")
        if module not in channels and not 0 < number < 100:
            problems.append(f"{part.ref} is outside the channels and not numbered below 100")
        if part.request is None:
            problems.append(f"{part.ref} is not placed")
        elif part.ref.startswith(("J", "H")) and not part.request.locked:
            problems.append(f"{part.ref} is a connector or a hole and is not locked")
    kinds = Counter(interface.kind for interface in design.interfaces.values())
    if kinds["usb2"] != 1:
        problems.append(f"{kinds['usb2']} USB2 interfaces, not one")
    if not any((part.footprint or "").startswith("Package_DFN_QFN:QFN-48") for part in parts) and not any(
        part.lib_id.startswith("MCU_") for part in parts
    ):
        problems.append("no 48-pin QFN controller")
    holes = ("Mechanical:MountingHole", "Fenolite_Holes:Hole_Pad")  # a library part, or design.hole(pad=…)
    if sum(part.lib_id.startswith(holes) for part in parts) < 4:
        problems.append("fewer than four mounting holes")
    classes = design.rules.netclasses
    high_voltage = {net.name for net in classes["HV"].nets} if "HV" in classes else set()
    if not {"HV_BUS", "HV_RTN"} <= high_voltage or not all(name.startswith("HV_") for name in high_voltage):
        problems.append("the nets of the high-voltage section have no net class of their own")
    return problems


def test_yardstick_structure_without_a_build() -> None:
    """Scenario "Structure without a build"."""
    lines = YARDSTICK.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# SPDX-License-Identifier: CC0-1.0"
    assert lines[1].startswith("# Authored for Fenolite as an example")
    assert yardstick_problems(YARDSTICK) == []
    design = run_design_script(YARDSTICK).design
    sizes = {len(design.modules[f"ch{n}"].children) for n in range(1, CHANNELS + 1)}
    assert sizes == {37} and 360 <= len(design.parts) <= 400
    mcu = [part for part in design.parts.values() if part.lib_id.startswith("MCU_")]
    assert len(mcu) == 1 and mcu[0].ref == "U3"
    usb = next(interface for interface in design.interfaces.values() if interface.kind == "usb2")
    assert (usb.members["dp"].name, usb.members["dn"].name) == ("USB_DP", "USB_DN")  # a pair for KiCad
    readme = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    row = next(line for line in readme.splitlines() if line.startswith("| `yardstick/`"))
    assert f"stage {_yardstick_stage(YARDSTICK)}" in row


def test_yardstick_stage_and_copper_disagree(tmp_path: Path) -> None:
    """Scenario "Stage and copper disagree": a copy at stage 1 with six copper layers."""
    text = YARDSTICK.read_text(encoding="utf-8")
    stage = _yardstick_stage(YARDSTICK)
    assert f"\nSTAGE = {stage} " in text and f"\nCOPPER = {STAGE_COPPER[stage]} " in text
    copy = tmp_path / "design.py"
    at_one = text.replace(f"\nSTAGE = {stage} ", "\nSTAGE = 1 ").replace(
        f"\nCOPPER = {STAGE_COPPER[stage]} ", "\nCOPPER = 6 "
    )
    copy.write_text(at_one, encoding="utf-8")
    problems = yardstick_problems(copy)
    assert len(problems) == 1 and "STAGE = 1" in problems[0] and "copper count of 4, not 6" in problems[0]
    copy.write_text(text.replace(f"\nSTAGE = {stage} ", "\nSTAGE = 7 "), encoding="utf-8")
    assert "STAGE" in yardstick_problems(copy)[0]


def yardstick_value_problems(text: str, source_ids: set[str]) -> list[str]:
    """Every assignment above the first function carries a comment that says where its value comes from:
    ``chosen for the example``, or the id of a registered public source."""
    tree = ast.parse(text)
    first = next(node.lineno for node in tree.body if isinstance(node, ast.FunctionDef))
    comments: dict[int, str] = {}
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            comments[token.start[0]] = token.string
    problems: list[str] = []
    for node in tree.body:
        if node.lineno >= first or not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        last = node.end_lineno or node.lineno
        said = " ".join(comments.get(line, "") for line in range(node.lineno, last + 1))
        cited = set(re.findall(r"S-\d{4}", said))
        if PROVENANCE not in said and not (cited and cited <= source_ids):
            problems.append(
                f"{ast.unparse(target)} (line {node.lineno}) does not say where its value comes from"
            )
    return problems


def test_yardstick_values_say_where_they_come_from() -> None:
    """Scenario "Every value says where it comes from"."""
    text = YARDSTICK.read_text(encoding="utf-8")
    source_ids = set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), re.M))
    assert source_ids and yardstick_value_problems(text, source_ids) == []
    tree = ast.parse(text)
    first = next(node.lineno for node in tree.body if isinstance(node, ast.FunctionDef))
    names = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign) and node.lineno < first
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert {"STAGE", "BOARD", "GAP", "HV_CLEARANCE", "HV_CREEPAGE", "MINIMUMS", "VALUES", "SUPPLY"} <= names
    function = "\n\n\ndef f():\n    pass\n"
    assert yardstick_value_problems("GAP = 8" + function, source_ids) == [
        "GAP (line 1) does not say where its value comes from"
    ]
    assert yardstick_value_problems("GAP = 8  # S-9999" + function, source_ids)
    assert yardstick_value_problems(f"GAP = 8  # {min(source_ids)}" + function, source_ids) == []
    page = YARDSTICK_PAGE.read_text(encoding="utf-8")
    statement = page[page.index("## How to read") : page.index("## Stages")]
    assert "2026-10-07" in statement and "invented for Fenolite" in statement
    assert "mirrors no board" in statement


def test_yardstick_states_its_lengths_once() -> None:
    """The lengths of the board are stated at the top: no ``mm()`` call below takes a number."""
    tree = ast.parse(YARDSTICK.read_text(encoding="utf-8"))
    literal = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "mm"
        and any(isinstance(arg, ast.Constant) for arg in node.args)
    ]
    assert literal == []


# ---- the design-lock example (capability design-dsl, "Design lock in a build"; change c0249)

LOCK_EXAMPLE = ROOT / "examples" / "lock"


def test_lock_example_header_and_listing() -> None:
    lines = (LOCK_EXAMPLE / "design.py").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[1].startswith("# Authored for Fenolite")
    assert "`lock/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_lock_example_parts() -> None:
    """Two modules with parts without a ref, one named part, one explicit ref, and the committed lock."""
    from fenolite.dsl.lock import lock_text, read_lock

    design = run_design_script(LOCK_EXAMPLE / "design.py").design
    unnamed = sorted(p.path for p in design.parts.values() if p.explicit_ref is None and p.name is None)
    assert unnamed == ["led/D", "led/R", "reg/C", "reg/U"]
    assert [p.path for p in design.parts.values() if p.name is not None] == ["reg/c_in"]
    assert [p.path for p in design.parts.values() if p.explicit_ref is not None] == ["J1"]
    text = (LOCK_EXAMPLE / "design.lock").read_text(encoding="utf-8")
    lock = read_lock(text, file="design.lock")
    assert lock_text(lock) == text and set(lock.refs) == set(design.parts)
    model = to_model(design, refs=lock.refs)
    assert sorted(c.ref for c in model.circuit.components) == ["C1", "C2", "D1", "J1", "R1", "U1"]


def test_lock_example_builds_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    args = ["build", str(LOCK_EXAMPLE / "design.py"), "--out", str(tmp_path / "B"), "--frozen", "--dry-run"]
    assert cli_main.main([*args, "--json"]) == 0, err.getvalue()
    assert json.loads(out.getvalue())["result"]["lock"]["changes"] == []


# -- the device example (change c0248)

DEVICES = ROOT / "examples" / "devices"


def test_devices_header_and_listing() -> None:
    for path in (DEVICES / "design.py", DEVICES / "devices" / "example_buck.toml"):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[1].startswith(
            "# Authored for Fenolite"
        )
    assert "`devices/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_devices_parts_come_from_devices() -> None:
    design = run_design_script(DEVICES / "design.py").design
    placed = {path: part.device.id for path, part in design.parts.items() if part.device is not None}
    assert placed["U1"] == "Example:BUCK_6V_2A" and design.parts["U1"].device_origin == "authored"
    assert {placed[ref] for ref in ("R1", "R2", "R3")} == {"Fenolite:R_0603"}
    assert placed["D1"] == "Fenolite:LED_0603" and design.parts["L1"].device is None
    model = to_model(design)
    u1 = next(c for c in model.circuit.components if c.ref == "U1")
    assert u1.properties["MPN"] == "EXB6202" and u1.lib_footprint_ref == "Fenolite:SOT23_6_TI_DBV0006A"


def test_devices_builds_without_a_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a build started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(
        ["build", str(DEVICES / "design.py"), "--out", str(tmp_path / "d"), "--confirm", "--json"]
    )
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert not [issue for issue in envelope["issues"] if issue["severity"] != "info"], envelope["issues"]
    assert [row["id"] for row in envelope["result"]["devices"]][0] == "Example:BUCK_6V_2A"


SYMBOLS = ROOT / "examples" / "symbols"


def test_symbols_example_builds_both_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Change c0261: the script generates both symbols and their variants, and the build writes them into
    one library, base before variant, as ``write_symbol_library`` gives them."""
    from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
    from fenolite.catalog.generate.symbol import generate_symbol
    from fenolite.catalog.pins import read_pins

    lines = (SYMBOLS / "design.py").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[1].startswith("# Authored for Fenolite")
    assert "`symbols/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    design = run_design_script(SYMBOLS / "design.py").design
    assert sorted(design.symbols) == [
        "Example:EXB6202",
        "Example:EXB6202DR",
        "Example:EXM120",
        "Example:EXM120-T",
    ]
    expected: list[object] = []
    for name, footprint in (("EXB6202", "Fenolite:SOIC_8"), ("EXM120", "")):
        table = read_pins(SYMBOLS / "pins" / f"{name}.toml")
        base, derived, _ = generate_symbol(table, library="Example", footprint=footprint)
        expected += [base, *derived]
        assert design.symbols[f"Example:{name}"].definition == base  # type: ignore[attr-defined]
    monkeypatch.chdir(tmp_path)
    code = cli_main.main([
        "build", str(SYMBOLS / "design.py"), "--out", "out", "--kicad-version", "10", "--confirm", "--json"
    ])  # fmt: skip
    assert code == 0
    text = (tmp_path / "out" / "lib" / "Example.kicad_sym").read_text(encoding="utf-8")
    assert text == write_symbol_library(expected, target=10)  # type: ignore[arg-type]
    units = {s.name: s.unit_count for s in read_symbol_library(text, library="Example") if not s.extends}
    assert units == {"EXB6202": 1, "EXM120": 3}


def test_import_python_is_a_fresh_import(tmp_path: Path) -> None:
    """The authored import example is the code a fresh import writes (change c0275)."""
    from _importexample import EXAMPLE, KEPT, fresh, unversioned

    files = fresh(tmp_path)
    committed = {
        p.relative_to(EXAMPLE).as_posix(): p.read_bytes()
        for p in EXAMPLE.rglob("*")
        if p.is_file() and p.name not in KEPT
    }
    assert sorted(committed) == sorted(files)
    for name, data in files.items():
        assert unversioned(committed[name]) == unversioned(data), name
    assert "`import_python/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_import_python_builds(tmp_path: Path) -> None:
    """The authored import example builds on its vendored library alone."""
    from fenolite.api import run

    folder = ROOT / "examples" / "import_python"
    reply = run(
        "build", str(folder / "design.py"), "--out", str(tmp_path / "built"), "--dry-run", cwd=tmp_path
    )
    assert reply.exit_code == 0, reply.error
    assert set(reply.result["libraries"].values()) == {"project"}
    lines = (folder / "design.py").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[4].startswith("# Authored for Fenolite")


# -- the parametric-pick example (change c0254)

PICKS = ROOT / "examples" / "picks"


def test_picks_header_and_listing() -> None:
    for path in sorted(PICKS.rglob("*.py")) + sorted((PICKS / "devices").glob("*.toml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[1].startswith(
            "# Authored for Fenolite"
        ), path
    assert "`picks/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_picks_locks_round_trip() -> None:
    from fenolite.dsl.lock import lock_text, read_lock

    for name in ("design", "divider"):
        text = (PICKS / f"{name}.lock").read_text(encoding="utf-8")
        lock = read_lock(text, file=f"{name}.lock")
        assert lock_text(lock) == text and lock.sections["picks"]


@pytest.mark.parametrize("script", ["design.py", "divider.py"])
def test_picks_build_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: str) -> None:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    args = ["build", str(PICKS / script), "--out", str(tmp_path / "B"), "--frozen", "--dry-run", "--json"]
    assert cli_main.main(args) == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert envelope["result"]["lock"]["changes"] == [] and envelope["result"]["generators"]


# -- the grammar-family example (change c0263)

FAMILIES = ROOT / "examples" / "families"


def test_families_header_and_listing() -> None:
    for path in [FAMILIES / "design.py", *sorted((FAMILIES / "devices").glob("*.toml"))]:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[1].startswith(
            "# Authored for Fenolite"
        ), path
    assert "`families/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_families_pick_of_an_exact_mpn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A pick of an exact MPN": with an empty lock the build picks EX03R104KAT for C_in, gives
    pick.new, and the planned parts name the manufacturer and the MPN."""
    import shutil

    work = tmp_path / "families"
    shutil.copytree(FAMILIES, work)
    (work / "design.lock").unlink()
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    args = ["build", str(work / "design.py"), "--out", str(tmp_path / "B"), "--dry-run", "--json"]
    assert cli_main.main(args) == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    picks = {pick["path"]: pick for pick in envelope["result"]["picks"]}
    assert picks["C_in"]["device"] == "Example:EX_MLCC@EX03R104KAT" and picks["C_in"]["state"] == "new"
    assert "pick.new" in {issue["code"] for issue in envelope["issues"]}
    design = run_design_script(work / "design.py").design
    from fenolite.cli._lock import plan_lock
    from fenolite.cli._picks import picking

    with picking(work / "design.py"):
        plan_lock(
            design, script=work / "design.py", given="design.lock", path=work / "design.lock", frozen=False
        )
    properties = design.parts["C_in"].properties
    assert properties["MPN"] == "EX03R104KAT" and properties["Manufacturer"] == "Example Passive"


def test_families_build_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    args = [
        "build",
        str(FAMILIES / "design.py"),
        "--out",
        str(tmp_path / "B"),
        "--frozen",
        "--dry-run",
        "--json",
    ]
    assert cli_main.main(args) == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert envelope["result"]["lock"]["changes"] == []
    assert {pick["device"] for pick in envelope["result"]["picks"]} == {
        "Example:EX_MLCC@EX03R104KAT", "Example:EX_CHIP_R@EXR06F1002T", "Example:EX_MF_R@EXM-4K7J"
    }  # fmt: skip
