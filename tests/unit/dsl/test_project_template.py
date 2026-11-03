# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The native project declaration is explicit, portable and records no canonical data (c0351)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design
from fenolite.dsl.errors import DslError


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/project.kicad_pro",
        "../project.kicad_pro",
        "native/../project.kicad_pro",
        "Z:/project.kicad_pro",
        "\\\\server\\project.kicad_pro",
        "file://project.kicad_pro",
        "native//project.kicad_pro",
        "./project.kicad_pro",
        "native/project.json",
        "",
    ],
)
def test_unsafe_or_non_native_declared_paths_refuse(path: str) -> None:
    with pytest.raises(DslError):
        Design("authored").kicad_project(path, sha256="1" * 64)


@pytest.mark.parametrize("digest", ["", "1" * 63, "A" * 64, "g" * 64, None, 1])
def test_digest_is_mandatory_lowercase_sha256(digest) -> None:
    with pytest.raises(DslError):
        Design("authored").kicad_project("native/project.kicad_pro", sha256=digest)


def test_declaration_records_no_file_io_and_is_unique(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    design = Design("authored")
    design.kicad_project("native/project.kicad_pro", sha256="1" * 64)
    assert not list(tmp_path.iterdir())
    with pytest.raises(DslError, match="once"):
        design.kicad_project("other.kicad_pro", sha256="2" * 64)
