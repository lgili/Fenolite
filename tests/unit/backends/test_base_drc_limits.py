# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``DrcLimits`` and ``LimitedOracle`` of ``fenolite.backends.base`` (capability backend-protocol, "DRC
report limits of an oracle"; change c0141)."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

from fenolite.backends import base
from fenolite.backends.base import DrcLimits, LimitedOracle, Oracle

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "checks"))
from fakes import FakeLimitedOracle, FakeOracle  # noqa: E402


def test_limit_by_type() -> None:
    limits = DrcLimits({"clearance": 499}, others=199)
    assert limits.limit("clearance") == 499
    assert limits.limit("silk_overlap") == 199
    assert limits.limit(base.UNCONNECTED_ITEMS) == 199


@pytest.mark.parametrize(
    ("per_type", "others"),
    [({}, 0), ({}, -1), ({"clearance": 0}, 199), ({"clearance": True}, 199), ({"clearance": 1.5}, 199)],
)
def test_limit_values_are_positive_ints(per_type: dict[str, int], others: int) -> None:
    with pytest.raises(ValueError, match="not a positive int"):
        DrcLimits(per_type, others=others)


def test_limits_are_frozen_and_hashable_free_of_the_callers_mapping() -> None:
    given = {"clearance": 499}
    limits = DrcLimits(given, others=199)
    given["clearance"] = 1
    assert limits.limit("clearance") == 499
    with pytest.raises(dataclasses.FrozenInstanceError):
        limits.others = 5  # type: ignore[misc]
    with pytest.raises(TypeError):
        limits.per_type["clearance"] = 5  # type: ignore[index]
    assert limits == DrcLimits({"clearance": 499}, others=199)


def test_limited_oracle_stands_beside_oracle() -> None:
    plain, limited = FakeOracle(), FakeLimitedOracle()
    assert not isinstance(plain, LimitedOracle)  # an oracle without ``report_limits`` states no limits
    assert isinstance(limited, LimitedOracle)
    assert limited.report_limits().limit("unconnected_items") == 499
    both: Oracle = limited  # the same object still is an ``Oracle``
    assert both.name == "fake"
    assert "report_limits" not in vars(Oracle)  # "Oracle protocol" is unchanged
    assert {"DrcLimits", "LimitedOracle"} <= set(base.__all__)
