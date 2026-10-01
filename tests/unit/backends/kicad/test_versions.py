# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Format version constants, detection, classification and target policy (capability kicad-version-gating)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import parse
from fenolite.backends.kicad.versions import (
    DEFAULT_TARGET,
    FORMAT_VERSIONS,
    READ_FLOOR,
    READ_MAJORS,
    TARGET_MAJORS,
    DowngradeRefusedError,
    FileKind,
    FormatInfo,
    FutureFormatError,
    UnsupportedFormatError,
    VersionStatus,
    check_target,
    classify,
    detect_version,
    inspect,
    kind_for_suffix,
    kind_of,
    major_for,
    require_editable,
    require_readable,
    version_issues,
)
from fenolite.core.errors import FormatError

B = FileKind.BOARD


def board(version: str) -> str:
    return f'(kicad_pcb (version {version}) (generator "fenolite") (generator_version "10.0"))'


# --- constants ------------------------------------------------------------------------------------


def test_constants() -> None:
    assert FORMAT_VERSIONS[B][10] == 20260206
    assert dict(FORMAT_VERSIONS[FileKind.FOOTPRINT]) == dict(FORMAT_VERSIONS[B])
    assert {FORMAT_VERSIONS[FileKind.WORKSHEET][m] for m in (8, 9, 10)} == {20231118}
    assert FORMAT_VERSIONS[FileKind.SCHEMATIC] == {8: 20231120, 9: 20250114, 10: 20260306}
    assert FORMAT_VERSIONS[FileKind.SYMBOL_LIB] == {8: 20231120, 9: 20241209, 10: 20251024}
    assert FORMAT_VERSIONS[FileKind.RULES] == {9: 1, 10: 1}
    assert READ_MAJORS == (8, 9, 10) and TARGET_MAJORS == (9, 10) and DEFAULT_TARGET == 10
    assert (
        READ_FLOOR[B] == 20240108 and READ_FLOOR[FileKind.WORKSHEET] == 0 and READ_FLOOR[FileKind.RULES] == 1
    )


# --- kind -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (board("20241229"), B),
        ('(footprint "x" (version 20241229))', FileKind.FOOTPRINT),
        ("(kicad_sch (version 20250114))", FileKind.SCHEMATIC),
        ("(kicad_symbol_lib (version 20241209))", FileKind.SYMBOL_LIB),
        ("(kicad_wks (version 20231118))", FileKind.WORKSHEET),
        ("(page_layout (setup (textsize 1.5 1.5)))", FileKind.WORKSHEET),
        ("(drawing_sheet (setup (textsize 1.5 1.5)))", FileKind.WORKSHEET),
        ("(kicad_dru (version 1))", FileKind.RULES),
    ],
)
def test_kind_of(text: str, kind: FileKind) -> None:
    assert kind_of(parse(text)) == kind


def test_pre_6_footprint_refused() -> None:
    with pytest.raises(UnsupportedFormatError) as info:
        kind_of(parse("(module R_0603 (layer F.Cu))"))
    assert info.value.cli_code == "FEN-3003"
    assert "kicad-cli fp upgrade" in info.value.hint


def test_unknown_root_rejected() -> None:
    with pytest.raises(FormatError, match="kicad_frobnicate") as info:
        kind_of(parse("(kicad_frobnicate)"), file="x.kicad_pcb")
    assert info.value.file == "x.kicad_pcb"


def test_kind_for_suffix() -> None:
    assert kind_for_suffix("a/b.kicad_pcb") == B
    assert kind_for_suffix("lib.kicad_mod") == FileKind.FOOTPRINT
    assert kind_for_suffix("fp-lib-table") is None
    assert kind_for_suffix("x.txt") is None


# --- detect ---------------------------------------------------------------------------------------


def test_detect_version() -> None:
    assert detect_version(parse(board("20250513"))) == 20250513


def test_detect_missing_version() -> None:
    with pytest.raises(FormatError, match="format version is missing"):
        detect_version(parse('(kicad_pcb (generator "x"))'))
    with pytest.raises(FormatError):
        detect_version(parse("(kicad_wks (setup))"))


def test_detect_non_integer_version() -> None:
    with pytest.raises(FormatError):
        detect_version(parse('(kicad_pcb (version "abc"))'))
    with pytest.raises(FormatError):
        detect_version(parse("(kicad_pcb (version 2024.1))"))


def test_detect_legacy_worksheet() -> None:
    assert detect_version(parse("(page_layout (setup))")) == 0


# --- major ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "version", "major"),
    [
        (B, 20250513, 10),
        (B, 20241030, 9),
        (B, 20260207, None),
        (B, 20221018, None),
        (B, 20240108, 8),
        (B, 20241229, 9),
        (B, 20260206, 10),
        (FileKind.RULES, 1, 9),
        (FileKind.RULES, 2, None),
        (FileKind.WORKSHEET, 0, 8),
        (FileKind.SYMBOL_LIB, 20250101, 10),
    ],
)
def test_major_for(kind: FileKind, version: int, major: int | None) -> None:
    assert major_for(kind, version) == major


# --- classification and policy --------------------------------------------------------------------


def test_classify() -> None:
    assert classify(B, 20221018) == VersionStatus.TOO_OLD
    assert classify(B, 20990101) == VersionStatus.FUTURE
    assert classify(B, 20241229) == VersionStatus.SUPPORTED
    assert classify(FileKind.RULES, 2) == VersionStatus.FUTURE
    assert classify(FileKind.WORKSHEET, 0) == VersionStatus.SUPPORTED


def test_inspect() -> None:
    info = inspect(parse(board("20241229")))
    assert info == FormatInfo(B, 20241229, 9, VersionStatus.SUPPORTED, "fenolite", "10.0")


def test_policy_kicad_7_board_refused() -> None:
    info = inspect(parse(board("20221018")))
    with pytest.raises(UnsupportedFormatError) as error:
        require_readable(info)
    assert "20221018" in str(error.value) and "20240108" in str(error.value)
    assert "kicad-cli pcb upgrade" in error.value.hint and "10.0" in error.value.hint


@pytest.mark.parametrize(
    ("kind", "command"),
    [
        (FileKind.FOOTPRINT, "fp upgrade"),
        (FileKind.SCHEMATIC, "sch upgrade"),
        (FileKind.SYMBOL_LIB, "sym upgrade"),
    ],
)
def test_policy_hint_names_the_upgrade_command(kind: FileKind, command: str) -> None:
    with pytest.raises(UnsupportedFormatError) as error:
        require_readable(FormatInfo(kind, 20200101, None, VersionStatus.TOO_OLD))
    assert command in error.value.hint


def test_policy_future_board_readable_but_not_editable() -> None:
    info = inspect(parse(board("20990101")))
    require_readable(info)
    codes = [i.code for i in version_issues(info)]
    assert codes == ["kicad.version.future"]
    with pytest.raises(FutureFormatError) as error:
        require_editable(info)
    assert error.value.cli_code == "FEN-3002" and error.value.hint


def test_dev_version_reported() -> None:
    issues = version_issues(inspect(parse(board("20250907"))))
    assert [(i.code, i.severity) for i in issues] == [("kicad.version.dev", "info")]


def test_dev_not_reported_for_released_or_legacy() -> None:
    assert version_issues(inspect(parse(board("20241229")))) == ()
    assert version_issues(inspect(parse("(page_layout (setup))"))) == ()
    assert version_issues(inspect(parse(board("20240108")))) == ()


# --- targets --------------------------------------------------------------------------------------


def test_target_same_major() -> None:
    assert check_target(inspect(parse(board("20241229"))), 9) == 20241229


def test_target_upgrade_allowed() -> None:
    assert check_target(inspect(parse(board("20241229"))), 10) == 20260206


def test_downgrade_refused() -> None:
    with pytest.raises(DowngradeRefusedError) as error:
        check_target(inspect(parse(board("20250513"))), 9)
    assert (error.value.source_major, error.value.target_major, error.value.cli_code) == (10, 9, "FEN-7002")
    assert "10" in error.value.hint


def test_target_too_old_input_refused() -> None:
    with pytest.raises(UnsupportedFormatError):
        check_target(inspect(parse(board("20221018"))), 10)


def test_target_future_input_refused() -> None:
    with pytest.raises(FutureFormatError):
        check_target(inspect(parse(board("20990101"))), 10)


def test_unsupported_target() -> None:
    with pytest.raises(ValueError, match=r"\(9, 10\)"):
        check_target(inspect(parse(board("20241229"))), 8)


def test_rules_target() -> None:
    info = inspect(parse("(kicad_dru (version 1))"))
    assert check_target(info, 9) == 1 and check_target(info, 10) == 1
