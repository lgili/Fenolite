# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The licence lists (capability fenolite-library, "Licence allow-list" and "Licence deny reasons"; change
c0279)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fenolite.library.licences import normalised_digest, parse_licences, shipped, shipped_text

ALLOWED = (
    "CC0-1.0 CC-BY-3.0 CC-BY-4.0 CC-BY-SA-2.5 CC-BY-SA-3.0 CC-BY-SA-4.0 CERN-OHL-1.2 CERN-OHL-P-2.0 "
    "CERN-OHL-W-2.0 CERN-OHL-S-2.0 MIT BSD-2-Clause BSD-3-Clause Apache-2.0 SHL-0.5 SHL-0.51 SHL-2.0 SHL-2.1 "
    "GPL-2.0-or-later GPL-3.0-only GPL-3.0-or-later TAPR-OHL-1.0"
).split()
LIBRARY_ENV = "FENOLITE_LIBRARY_CHECKOUT"
"""A local checkout of fenolite-library, compared with the shipped copy when set (CI of a release)."""


def test_allow_list_is_the_spec_list() -> None:
    lists = shipped()
    ids = sorted(spdx for family in lists.families.values() for spdx in family.ids)
    assert ids == sorted(ALLOWED)
    assert lists.family_of("CC-BY-SA-4.0").name == "cc-by-sa"  # type: ignore[union-attr]
    assert lists.family_of("Apache-2.0 WITH SHL-2.1").name == "solderpad"  # type: ignore[union-attr]
    reciprocal = {f.name for f in lists.families.values() if f.reciprocal}
    assert reciprocal == {"cc-by-sa", "cern-ohl-w", "cern-ohl-s", "cern-ohl-1.2", "gpl", "tapr"}
    assert all(family.obligations for family in lists.families.values())


@pytest.mark.parametrize(
    ("spdx", "reason"),
    [
        ("CC-BY-NC-SA-4.0", "non-commercial"),
        ("CC-BY-NC-4.0", "non-commercial"),
        ("CC-BY-ND-4.0", "no-derivatives"),
        ("NOASSERTION", "no-licence"),
        ("NONE", "no-licence"),
        ("", "no-licence"),
        ("LicenseRef-Vendor", "licence-ref"),
        ("Proprietary", "not-allowed"),
        ("CC-BY-4.0", None),
    ],
)
def test_deny_reasons(spdx: str, reason: str | None) -> None:
    assert shipped().deny_reason(spdx) == reason


def test_platform_hosts() -> None:
    lists = shipped()
    assert lists.host_denied("oshwlab.com") and lists.host_denied("u.easyeda.com")
    assert not lists.host_denied("github.com")


def test_normalised_digest_ignores_case_and_spacing() -> None:
    assert normalised_digest(b"The  MIT\nLicence\n") == normalised_digest(b"the mit licence")


def test_shipped_copy_equals_the_library_list() -> None:
    """The library commits the shipped table as licences.toml; with a checkout at hand (the release job
    sets FENOLITE_LIBRARY_CHECKOUT) the two are equal. Without one, the shipped table parses."""
    checkout = os.environ.get(LIBRARY_ENV)
    if not checkout:
        assert parse_licences(shipped_text()).families
        pytest.skip(f"{LIBRARY_ENV} is not set")
    assert (Path(checkout) / "licences.toml").read_text(encoding="utf-8") == shipped_text()
