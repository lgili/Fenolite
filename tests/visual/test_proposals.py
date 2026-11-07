# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0369 reference capture gate: accept images only from the pinned CI artifact after review."""

from pathlib import Path

import pytest
from _proposal_viewer import proposal_page
from _visual import REFS, job, run

pytestmark = pytest.mark.needs_browser


@pytest.mark.parametrize("bundle", [False, True])
def test_proposal_reference(tmp_path: Path, bundle: bool):
    page = proposal_page(tmp_path, bundle=bundle)
    name = "proposal_bundle" if bundle else "proposal_alternatives"
    (reply,) = run(
        [
            job(
                name,
                page,
                tmp_path,
                ref=REFS / f"{name}.png",
                script=(
                    "sectionEl('proposals').open=true; sectionEl('proposals').scrollIntoView(); return {};"
                ),
            )
        ],
        tmp_path,
    )
    assert reply["errors"] == [], reply
    assert reply["ok"] is True, (
        "Missing/different reference: review the pinned CI viewer-differences artifact; "
        "never promote a local screenshot to the golden",
        reply,
    )
