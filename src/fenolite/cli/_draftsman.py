# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read and bind the optional drawing specification of an Altium build (c0172)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError
from fenolite.exports.drawing_spec import DrawingSpec, read_spec


def drawing_input(
    given: str | None, cwd: Path
) -> tuple[DrawingSpec | None, dict[str, str] | None, Path | None]:
    if given is None:
        return None, None, None
    path = Path(given) if Path(given).is_absolute() else cwd / given
    try:
        data = path.read_bytes()
    except OSError as error:
        raise CliError(
            "FEN-3001", f"cannot read drawing specification: {error.strerror or error}", where=given
        ) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=Path(given).name) from error
    return (
        read_spec(text, file=Path(given).name),
        {"path": given, "sha256": hashlib.sha256(data).hexdigest()},
        path,
    )


__all__ = ["drawing_input"]
