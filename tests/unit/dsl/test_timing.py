# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored exact conversions for the topology units."""

import pytest

from fenolite.dsl import Delay, DslError, Loss, db, fs, mdb, ns, ps


def test_exact_conversion() -> None:
    assert ps("12.5") == Delay(12_500)
    assert ns("1.2") == Delay(1_200_000)
    assert db("1.5") == Loss(1_500)
    assert fs(0).fs == mdb(0).mdb == 0
    assert ps("0.0010").fs == 1


@pytest.mark.parametrize("value", [1.5, True, -1, "-1", "nan", "1/2", "1e2", ""])
@pytest.mark.parametrize("make", [fs, ps, ns, mdb, db])
def test_refused_numbers(value: object, make: object) -> None:
    with pytest.raises(DslError):
        make(value)  # type: ignore[operator]


@pytest.mark.parametrize("make,value", [(ps, "0.0001"), (fs, "0.1"), (db, "0.0001"), (mdb, "0.5")])
def test_subunit_refused(make: object, value: str) -> None:
    with pytest.raises(DslError):
        make(value)  # type: ignore[operator]
