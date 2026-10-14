# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Write graduation requires independent evidence and current kit provenance."""

from dataclasses import dataclass, replace

import pytest

from fenolite.backends.base import GraduationRun, MatrixRow, graduated
from fenolite.core.evidence import Evidence, Level
from fenolite.verify.evidence import RELEASE_VERIFIED


@dataclass(frozen=True)
class Hypothesis:
    level: Level
    level_text: str = ""
    refuted: bool = False


RUN = "2026-10-13-12345678"
TEST = "tests/unit/backends/altium/test_readback.py::test_committed_files_read_back"
ROW = MatrixRow(
    "altium",
    "altium_schlib",
    write=Evidence(Level.INFERRED, hypotheses=("kit", "oracle")),
    experimental=("write",),
)
REGISTER = {
    "kit": Hypothesis(Level.ALTIUM_VERIFIED_KIT, f"ALTIUM-VERIFIED(kit; AD 26.5; 2026-10-13; {RUN})"),
    "oracle": Hypothesis(Level.ORACLE_VERIFIED),
}
RECORD = GraduationRun(RUN, frozenset({"kit"}), frozenset(), True)


def verdict(
    row: MatrixRow = ROW,
    register: dict[str, Hypothesis] | None = None,
    runs: tuple[GraduationRun, ...] = (RECORD,),
) -> tuple[bool, tuple[str, ...]]:
    return graduated(
        row,
        REGISTER if register is None else register,
        runs,
        own_readback=TEST,
        suite_tests=(TEST,),
    )


def test_current_committed_run_graduates() -> None:
    assert verdict() == (True, ())


@pytest.mark.parametrize("level", list(Level))
def test_release_levels_agree_with_verifier(level: Level) -> None:
    register = {**REGISTER, "oracle": Hypothesis(level)}
    passed, reasons = verdict(register=register)
    assert passed == (level in RELEASE_VERIFIED and level is not Level.ALTIUM_VERIFIED_KIT)
    if level not in RELEASE_VERIFIED:
        assert "oracle is not release-verified" in reasons


def test_missing_and_refuted_rows_never_support_graduation() -> None:
    assert "oracle is not registered" in verdict(register={"kit": REGISTER["kit"]})[1]
    assert (
        "oracle is not release-verified"
        in verdict(register={**REGISTER, "oracle": replace(REGISTER["oracle"], refuted=True)})[1]
    )


@pytest.mark.parametrize(
    "run",
    [
        replace(RECORD, committed=False),
        replace(RECORD, passed_hypotheses=frozenset()),
        replace(RECORD, stale_hypotheses=None),
        replace(RECORD, stale_hypotheses=frozenset({"kit"})),
    ],
)
def test_uncommitted_failed_unknown_or_stale_run_blocks(run: GraduationRun) -> None:
    passed, reasons = verdict(runs=(run,))
    assert not passed
    assert any(RUN in reason for reason in reasons)


def test_missing_run_is_named() -> None:
    assert any(RUN in reason for reason in verdict(runs=())[1])


def test_readback_metadata_is_required() -> None:
    assert not graduated(ROW, REGISTER, (RECORD,))[0]
    assert not graduated(ROW, REGISTER, (RECORD,), own_readback=TEST, suite_tests=())[0]


@pytest.mark.parametrize(
    "kind, dependency",
    [
        ("altium_pcbdoc", "H-A-VER-RTA3"),
        ("altium_prjpcb", "H-A-VER-RTA3-PRJ"),
        ("altium_schdoc_ascii", "H-A-VER-RTA3-PRJ"),
        ("altium_schdoc_binary", "H-A-VER-RTA3-PRJ"),
    ],
)
def test_model_kinds_need_corpus_roundtrip(kind: str, dependency: str) -> None:
    row = replace(ROW, kind=kind)
    assert dependency + " is not registered" in verdict(row=row)[1]
    assert verdict(row=row, register={**REGISTER, dependency: Hypothesis(Level.CORPUS_VERIFIED)}) == (
        True,
        (),
    )


def test_kicad_requires_its_own_oracle() -> None:
    row = MatrixRow("kicad", "kicad_pcb", write=Evidence(Level.KICAD_VERIFIED, hypotheses=("oracle",)))
    assert not verdict(row=row, register={"oracle": Hypothesis(Level.CORPUS_VERIFIED)}, runs=())[0]
    assert verdict(row=row, register={"oracle": Hypothesis(Level.KICAD_VERIFIED)}, runs=()) == (True, ())


def test_no_write_and_unknown_backend_fail_closed() -> None:
    assert not verdict(row=MatrixRow("altium", "reader"))[0]
    assert not verdict(row=replace(ROW, backend="future"))[0]


def test_matrix_altium_writes_still_experimental() -> None:
    from pathlib import Path

    from fenolite.backends.matrix import rows
    from fenolite.verify.hypotheses import load_register

    register = {entry.id: entry for entry in load_register(Path("docs/hypotheses.md"))}
    for row in rows():
        if row.backend == "altium" and row.write is not None:
            passed, reasons = graduated(row, register, ())
            assert not passed and reasons
            assert "write" in row.experimental
