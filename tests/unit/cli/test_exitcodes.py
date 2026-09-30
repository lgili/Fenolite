# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import pytest

from fenolite.cli.errors import ERROR_CODE, REGISTRY, CliError
from fenolite.cli.exitcodes import ExitCode


def test_exit_code_values_are_frozen() -> None:
    assert [(c.name, int(c)) for c in ExitCode] == [
        ("OK", 0), ("INTERNAL", 1), ("USAGE", 2), ("INPUT", 3),
        ("CONFIRM_REQUIRED", 4), ("FINDINGS", 5), ("TOOL", 6), ("LOSSY", 7),
    ]  # fmt: skip


@pytest.mark.parametrize("code", sorted(REGISTRY))
def test_first_digit_equals_exit_code(code: str) -> None:
    assert ERROR_CODE.match(code)
    assert int(code[4]) == int(REGISTRY[code].exit_code)


def test_every_non_ok_exit_code_has_an_error() -> None:
    covered = {spec.exit_code for spec in REGISTRY.values()}
    assert covered == set(ExitCode) - {ExitCode.OK}


def test_cli_error_defaults_and_overrides() -> None:
    err = CliError("FEN-6001", where="kicad-cli")
    assert err.exit_code is ExitCode.TOOL and err.retryable
    info = CliError("FEN-2002", "unknown field 'nope'", hint="h").info()
    assert (info.code, info.message, info.hint, info.retryable) == (
        "FEN-2002",
        "unknown field 'nope'",
        "h",
        False,
    )


def test_unregistered_code_is_rejected() -> None:
    with pytest.raises(ValueError):
        CliError("FEN-9999")
