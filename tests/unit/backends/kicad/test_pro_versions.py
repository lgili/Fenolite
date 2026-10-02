# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project file versions (capability kicad-version-gating, "Project file versions"; change c0010)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.pro import (
    NET_SETTINGS_READ_MAX,
    PROJECT_READ_MAX,
    PROJECT_VERSIONS,
    classify_project,
    project_major,
)
from fenolite.backends.kicad.versions import TARGET_MAJORS, VersionStatus


def test_pairs_per_target() -> None:
    assert PROJECT_VERSIONS[9] == (3, 4) and PROJECT_VERSIONS[10] == (3, 5)
    assert tuple(PROJECT_VERSIONS) == TARGET_MAJORS
    assert (PROJECT_READ_MAX, NET_SETTINGS_READ_MAX) == (3, 5)


@pytest.mark.parametrize(
    ("pair", "status"),
    [
        ((3, 4), VersionStatus.SUPPORTED),
        ((3, 5), VersionStatus.SUPPORTED),
        ((None, None), VersionStatus.SUPPORTED),
        ((1, 3), VersionStatus.SUPPORTED),
        ((2, None), VersionStatus.SUPPORTED),
        ((4, 4), VersionStatus.FUTURE),
        ((3, 6), VersionStatus.FUTURE),
        ((None, 6), VersionStatus.FUTURE),
    ],
)
def test_classify(pair: tuple[int | None, int | None], status: VersionStatus) -> None:
    assert classify_project(*pair) is status


@pytest.mark.parametrize(
    ("pair", "major"), [((3, 4), 9), ((3, 5), 10), ((None, None), None), ((2, 4), None), ((3, None), None)]
)
def test_project_major(pair: tuple[int | None, int | None], major: int | None) -> None:
    assert project_major(*pair) == major
