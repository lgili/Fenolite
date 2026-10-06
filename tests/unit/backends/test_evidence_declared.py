# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every backend module declares its evidence, and the matrix rows repeat declared constants (capability
backend-protocol, "Backend modules declare their evidence" and "Evidence matrix rows"; change c0067).

``test_live_modules_declare`` is the guard: it fails when a module under ``src/fenolite/backends/`` holds
neither an evidence constant nor a ``# evidence:`` marker, and its message says what to add.
"""

from __future__ import annotations

import importlib
import itertools
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from fenolite.backends import matrix, registry
from fenolite.backends.base import MATRIX_OPERATIONS
from fenolite.backends.matrix import ModuleClaim, module_claims, packages, problems, rows
from fenolite.core.evidence import Evidence, Level

ROOT = Path(__file__).resolve().parents[3]
LIVE = ("fenolite.backends.altium", "fenolite.backends.kicad", "fenolite.backends.specctra")
HEAD = "from fenolite.core.evidence import Evidence, Level\n"
GOOD = HEAD + 'EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))\n'
EMPTY_CLAIMS = "from fenolite.backends.base import MatrixRow\nMATRIX: tuple[MatrixRow, ...] = ()\n"
_COUNTER = itertools.count()

Maker = Callable[..., str]


def fresh() -> str:
    return f"fenolite_c0067_pkg{next(_COUNTER)}"


@pytest.fixture
def make_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Maker]:
    """``make(files, name="", claims=True)`` writes a package of the given files on ``sys.path`` (with a
    ``claims.py`` holding an empty matrix unless given or refused) and returns its dotted name; a name
    with a dot gives a nested package."""
    made: list[str] = []

    def make(files: dict[str, str], name: str = "", claims: bool = True) -> str:
        package = name or fresh()
        base = tmp_path / f"root{next(_COUNTER)}"
        folder = base.joinpath(*package.split("."))
        folder.mkdir(parents=True)
        for parent in [folder, *folder.parents]:
            if parent == base:
                break
            (parent / "__init__.py").write_text("", encoding="utf-8")
        for relative, text in (({"claims.py": EMPTY_CLAIMS} if claims else {}) | files).items():
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        monkeypatch.syspath_prepend(str(base))
        importlib.invalidate_caches()
        made.append(package.split(".")[0])
        return package

    yield make
    for name in [m for m in sys.modules if m.split(".")[0] in made]:
        del sys.modules[name]


# -- "Backend modules declare their evidence"


def test_live_modules_declare() -> None:
    """The guard. A module added under ``src/fenolite/backends/`` without a declaration fails here."""
    found = problems()
    assert not found, matrix.failure_text(found)
    for package in LIVE:
        assert any(claim.constants for claim in module_claims(package)), package


def test_live_packages() -> None:
    assert packages() == LIVE
    for package in LIVE:
        claims = module_claims(package)
        assert [c.module for c in claims] == sorted(c.module for c in claims)
        assert all(isinstance(c, ModuleClaim) and c.package == package for c in claims)
        assert not any(c.module == "claims" for c in claims)
        for claim in claims:
            assert sum(map(bool, (claim.constants, claim.see, claim.none))) == 1, claim.module
            assert [n for n, _ in claim.constants] == sorted(n for n, _ in claim.constants)


def test_forms_the_four_broken_forms_are_named(make_package: Maker) -> None:
    package = make_package(
        {
            "good.py": GOOD,
            "helper.py": "# evidence: see good\n",
            "plain.py": "X = 1\n",
            "both.py": GOOD + "# evidence: see good\n",
            "lost.py": "# evidence: see missing\n",
            "quiet.py": "# evidence: none,\n",
        }
    )
    found = problems([package])
    assert len(found) == 4, found
    assert found == tuple(sorted(found))
    for module in ("plain", "both", "lost", "quiet"):
        assert sum(f"{package}.{module}:" in message for message in found) == 1, module
    assert not any(f"{package}.good" in m or f"{package}.helper" in m for m in found)
    claims = {claim.module: claim for claim in module_claims(package)}
    assert claims["good"].constants == (("EVIDENCE", Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))),)
    assert claims["helper"].see == ("good",) and claims["helper"].none == ""
    assert claims["plain"] == ModuleClaim(package, "plain")


def test_forms_message_for_a_module_without_a_declaration_says_what_to_add(make_package: Maker) -> None:
    """Another change meets this message without having read the rule: it names the module and the three
    forms, and the guard's text adds how to choose and what to regenerate."""
    package = make_package({"schwrite.py": "def write() -> str:\n    return ''\n"})
    (message,) = problems([package])
    assert message.startswith(f"{package}.schwrite: declares no evidence")
    for form in ("EVIDENCE = Evidence(", "# evidence: see <module>", "# evidence: none, <reason>"):
        assert form in message
    text = matrix.failure_text([message])
    assert message in text and "1 problem(s)" in text
    for word in (
        "docs/hypotheses.md",
        "lowest wins",
        "# evidence: see pcb, mod",
        "# evidence: none, error classes only",
        "claims.py",
        "experimental",
        "uv run python tools/gen_evidence_matrix.py",
    ):
        assert word in text, word


def test_forms_other_broken_markers(make_package: Maker) -> None:
    package = make_package(
        {
            "good.py": GOOD,
            "nested/__init__.py": "",
            "nested/deep.py": "# evidence: see good\n",
            "nested/own/__init__.py": GOOD,
            "nested/user.py": "# evidence: see nested.own\n",
            "twice.py": "# evidence: see good\n# evidence: none, twice\n",
            "odd.py": "# evidence: perhaps\n",
            "bare.py": "# evidence: none\n",
            "weak.py": "# evidence: see helper\n",
            "helper.py": "# evidence: none, a table\n",
            "indented.py": "def f() -> None:\n    # evidence: none, not in column 0\n    return None\n",
            "imported.py": "from .good import EVIDENCE\n",
        }
    )
    found = problems([package])
    named = {message.split(":")[0].rsplit(".", 1)[-1] for message in found}
    assert named == {"twice", "odd", "bare", "weak", "indented", "imported"}, found
    assert len(found) == 6
    by_module = {message.split(":")[0].rsplit(".", 1)[-1]: message for message in found}
    assert "2 '# evidence:' markers" in by_module["twice"]
    assert "neither" in by_module["odd"]
    assert "gives no reason" in by_module["bare"]
    assert "declares no constant" in by_module["weak"]
    assert "declares no evidence" in by_module["indented"]
    assert "declares no evidence" in by_module["imported"], "an imported constant is not assigned there"
    modules = [claim.module for claim in module_claims(package)]
    assert "nested.own" in modules and "nested" not in modules and "__init__" not in modules


def test_docstring_marker_does_not_count(make_package: Maker) -> None:
    source = '"""A module.\n\n# evidence: none, only text\n"""\nX = """\n# evidence: see y\n"""\n'
    package = make_package({"texty.py": source})
    (message,) = problems([package])
    assert f"{package}.texty: declares no evidence" in message


def test_inferred_level_without_a_hypothesis(make_package: Maker) -> None:
    package = make_package({"bare.py": HEAD + "EVIDENCE = Evidence(Level.INFERRED)\n"})
    (message,) = problems([package])
    assert all(word in message for word in (f"{package}.bare", "EVIDENCE", "INFERRED"))


def test_constants_of_any_name_are_collected(make_package: Maker) -> None:
    source = HEAD + (
        'EVIDENCE_V3 = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-RD-CFB-CORPUS",))\n'
        "WRITE_EVIDENCE: Evidence = Evidence(Level.UNVERIFIED)\n"
        "NOT_ONE = 3\n"
    )
    package = make_package({"cfb.py": source})
    assert problems([package]) == ()
    (claim,) = module_claims(package)
    assert [name for name, _ in claim.constants] == ["EVIDENCE_V3", "WRITE_EVIDENCE"]


# -- "Evidence matrix rows"

OWN = HEAD + (
    'READ = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))\n'
    "DRAFT = Evidence(Level.UNVERIFIED)\n"
    "OPEN = Evidence(Level.UNKNOWN)\n"
)


def _with_rows(make_package: Maker, name: str, rows_text: str, head: str = "") -> str:
    """A package whose module ``own`` holds constants and whose ``claims`` holds the rows ``rows_text``."""
    claims = (
        "from fenolite.backends.base import MatrixRow\n"
        "from fenolite.core.evidence import Evidence\n"
        f"from {name} import own\n{head}"
        f"MATRIX: tuple[MatrixRow, ...] = ({rows_text})\n"
    )
    return make_package({"own.py": OWN, "claims.py": claims}, name)


def test_unverified_cell_outside_experimental(make_package: Maker) -> None:
    name = fresh().replace("pkg", "draft")
    package = _with_rows(make_package, name, f'MatrixRow("{name}", "k_draft", write=own.DRAFT),')
    (message,) = problems([package])
    assert "row k_draft" in message and "write is UNVERIFIED" in message and "experimental" in message
    name = fresh().replace("pkg", "draft")
    row = f'MatrixRow("{name}", "k_draft", write=own.DRAFT, experimental=("write",)),'
    assert problems([_with_rows(make_package, name, row)]) == ()


def test_row_rules(make_package: Maker) -> None:
    name = fresh()
    text = (
        f'MatrixRow("{name}", "k_one", read=own.READ),'
        f'MatrixRow("{name}", "k_one", read=own.READ),'
        f'MatrixRow("other", "k_two", read=own.READ),'
        f'MatrixRow("{name}", "k_bare", read=BARE),'
    )
    package = _with_rows(make_package, name, text, head="BARE = Evidence.combine(own.READ, own.OPEN)\n")
    found = problems([package])
    assert len(found) == 2, found
    assert any("k_one" in m and "twice" in m for m in found)
    assert any("k_two" in m and "'other'" in m for m in found)
    assert all(m.startswith(f"{name}.claims: row ") for m in found)


def test_package_without_claims_or_matrix(make_package: Maker) -> None:
    package = make_package({"good.py": GOOD}, claims=False)
    (message,) = problems([package])
    assert "has no 'claims' module" in message and package in message
    package = make_package({"good.py": GOOD, "claims.py": "MATRIX = [1]\n"})
    (message,) = problems([package])
    assert "MATRIX is not a tuple of MatrixRow" in message


def test_literal_level_in_claims_is_refused(make_package: Maker) -> None:
    """A ``kicad`` claims module in which one cell is a literal fails naming ``kicad.claims``."""
    literal = (
        "from fenolite.backends.base import MatrixRow\n"
        "from fenolite.core.evidence import Evidence, Level\n"
        'MATRIX = (MatrixRow("kicad", "kicad_pcb", read=Evidence(Level.KICAD_VERIFIED)),)\n'
    )
    package = make_package({"claims.py": literal}, "fenolite_c0067_literal.kicad")
    found = problems([package])
    assert len(found) == 2 and all(message.startswith("kicad.claims:") for message in found), found
    assert any("names Level" in m for m in found) and any("calls Evidence(...)" in m for m in found)
    default = (
        "from fenolite.backends.base import MatrixRow\n"
        "from fenolite.core.evidence import Evidence\n"
        'MATRIX = (MatrixRow("kicad", "kicad_pcb", read=Evidence()),)\n'
    )
    found = problems([make_package({"claims.py": default}, "fenolite_c0067_default.kicad")])
    assert any("calls Evidence(...)" in m for m in found), "Evidence() is a literal UNVERIFIED"


def test_live_claims_state_no_level() -> None:
    for package in LIVE:
        source = (ROOT / "src" / Path(*package.split(".")) / "claims.py").read_text(encoding="utf-8")
        assert "Level" not in source and "Evidence(" not in source, package


def _row(backend: str, kind: str):  # type: ignore[no-untyped-def]
    return next(row for row in rows() if (row.backend, row.kind) == (backend, kind))


def test_board_row_follows_its_constants() -> None:
    from fenolite.backends.kicad import pcb
    from fenolite.backends.kicad.backend import KicadBackend

    row = _row("kicad", "kicad_pcb")
    assert row.read is pcb.EVIDENCE and row.write is pcb.WRITE_EVIDENCE
    assert row.roundtrip_exact is pcb.EVIDENCE
    assert row.roundtrip_modified == KicadBackend().capabilities().evidence
    assert row.roundtrip_modified == Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)
    assert row.experimental == ()


def test_report_kinds_agree_with_the_matrix() -> None:
    backends = registry.all_backends()
    assert {backend.name for backend in backends} >= {"altium", "kicad"}
    for backend in backends:
        report = backend.capabilities()
        mine = {row.kind: row for row in rows() if row.backend == backend.name}
        for kind in report.read_kinds:
            assert mine[kind].detect is not None and mine[kind].read is not None, (backend.name, kind)
        stable = sorted(k for k, row in mine.items() if row.write and "write" not in row.experimental)
        assert stable == sorted(report.write_kinds), backend.name


def test_report_kinds_disagreement_is_a_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    from fenolite.backends.kicad import backend as kicad_backend

    report = kicad_backend.CAPABILITIES
    changed = dataclasses.replace(
        report, read_kinds=(*report.read_kinds, "kicad_new"), write_kinds=report.write_kinds[1:]
    )
    monkeypatch.setattr(kicad_backend, "CAPABILITIES", changed)
    found = problems(["fenolite.backends.kicad"])
    assert len(found) == 2, found
    assert any("reads kicad_new" in m and "detect and read" in m for m in found)
    assert any("write_kinds" in m and "both must agree" in m for m in found)


def test_experimental_writers_and_the_codec_have_rows() -> None:
    from fenolite.lens.altium import PCB_WRITE_KINDS, WRITE_KINDS

    for kind in (*WRITE_KINDS, *PCB_WRITE_KINDS):
        row = _row("altium", kind)
        assert row.write is not None and "write" in row.experimental, kind
    dsn, ses = _row("specctra", "specctra_dsn"), _row("specctra", "specctra_ses")
    assert dsn.write is not None and dsn.read is None and ses.read is not None and ses.write is None


def test_cells_are_constants_of_their_package() -> None:
    """Every id of a cell is named by a constant of the row's package, and no cell is stronger than every
    constant that shares an id with it: a cell repeats declarations and adds none."""
    for package in LIVE:
        constants = [evidence for claim in module_claims(package) for _, evidence in claim.constants]
        declared = {ident for evidence in constants for ident in evidence.hypotheses}
        for row in rows():
            if row.backend != package.rsplit(".", 1)[-1]:
                continue
            for operation, cell in row.cells():
                assert set(cell.hypotheses) <= declared, (row.kind, operation)
                parts = [c for c in constants if set(c.hypotheses) <= set(cell.hypotheses)]
                assert any(cell.level is c.level for c in parts), (row.kind, operation)
            assert set(row.experimental) <= set(MATRIX_OPERATIONS)


def test_rows_are_sorted_and_need_no_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("rows() must run no external tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    first, second = rows(), rows()
    assert first == second
    assert [(r.backend, r.kind) for r in first] == sorted((r.backend, r.kind) for r in first)
    assert {r.backend for r in first} == {"altium", "kicad", "specctra"}
    assert len({(r.backend, r.kind) for r in first}) == len(first)


def test_importing_the_collector_stays_light() -> None:
    code = (
        "import sys, fenolite.backends.matrix; print(sorted(m for m in sys.modules if m.startswith("
        "('fenolite.backends.altium', 'fenolite.backends.kicad', 'fenolite.backends.specctra'))))"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
