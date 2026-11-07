# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net roles on the board in Chromium (change c0305): the Net roles panel of the `bad` buck of
``examples/roles``, its overlays and their toggles, and Confirm roles offered to a served page.

The reference ``refs/roles_bad_buck.png`` is no fixture of ``tools/update_view_refs.py``: after an intended
change, delete it, run ``test_overlays`` (it fails without a reference), review the screenshot it wrote and
copy it to ``tests/visual/refs/``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _visual import REFS, export, job, run

pytestmark = pytest.mark.needs_browser

HELP = """
const settle = (ms = 60) => new Promise(ok => setTimeout(ok, ms));
await settle(150);
const sample = (x, y) => {
  const [X, Y] = w2s(x, y), g = cv.getContext("2d"), d = window.devicePixelRatio || 1;
  const box = g.getImageData(Math.round(X * d) - 20, Math.round(Y * d) - 20, 40, 40);
  return Array.from(box.data).join(",");
};
const hot = () => S.roles.groups.find(g => g.type === "hot");
const centre = g => g.points.reduce((a, p) => [a[0] + p[0] / g.points.length, a[1] + p[1] / g.points.length],
  [0, 0]);
const $q = s => document.querySelector(s);
"""


@pytest.fixture(scope="module")
def roles_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from _roles import reference_board
    from _visual import browser_missing

    if browser_missing():
        pytest.skip("the browser is missing")
    folder = tmp_path_factory.mktemp("roles")
    board = reference_board("buck_shunt", "bad", folder / "out")
    return export(board.parent, folder / "roles.html", "--roles", "run", "--no-models", "--no-review")


def _act(page: Path, tmp_path: Path, script: str, **extra: Any) -> dict[str, Any]:
    (reply,) = run([job("roles", page, tmp_path, script=HELP + script, shot="", **extra)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    return reply


def test_panel(roles_page: Path, tmp_path: Path) -> None:
    """Scenario "The panel of the bad buck": the legend counts the reply's kinds, `SW` reads `switch_node`,
    a net row opens its Role section and a group row frames its pads."""
    script = """
    const legend = [...document.querySelectorAll("#roleList .rleg")]
      .map(b => [b.dataset.kind, +b.querySelector(".rlegN").textContent]);
    const kind = $q('#roleNets .rrow[data-net="SW"]').querySelector(".rkind").textContent;
    $q('#roleNets .rrow[data-net="GH"]').click(); await settle();
    const sections = [...$("info").querySelectorAll(".isect > summary")].map(s => s.textContent);
    const confirmOffer = !!document.getElementById("inspConfirmRole");
    $q('#roleGroups .rrow[data-group="hot_SW"]').click(); await settle();
    const r = cv.getBoundingClientRect();
    const inside = hot().points.every(p => { const [X, Y] = w2s(p[0], p[1]);
      return X >= 0 && Y >= 0 && X <= r.width && Y <= r.height; });
    const head = sectionEl("roles");
    return {legend, kinds: S.roles.kinds, kind, sections, confirmOffer, inside,
      title: $("inspTitle").textContent, hidden: head.hidden,
      count: head.querySelector(".count").textContent};
    """
    found = _act(roles_page, tmp_path, script)["result"]
    assert found["legend"] == [[k, n] for k, n in found["kinds"].items()]
    assert found["kind"].startswith("switch node") and found["hidden"] is False
    assert found["sections"] == ["Net", "Role"]
    assert found["confirmOffer"] is False  # an exported page writes nothing
    assert found["inside"] and found["title"] == "hot_SW" and int(found["count"]) == 12


def test_overlays(roles_page: Path, tmp_path: Path) -> None:
    """Scenario "Overlays drawn and hidden": the screenshot matches its reference, and each toggle of the
    Roles group of the Layers panel removes its overlay and brings it back."""
    script = """
    const [x, y] = centre(hot()), pad = S.pads.find(p => p.net === "VOUT");
    const at = { loops: () => sample(x, y), colors: () => sample(pad.x, pad.y) };
    const on = {}, off = {}, back = {};
    for (const k in at) on[k] = at[k]();
    for (const k in at) { setRoleView(k, false); await settle(); off[k] = at[k](); }
    const rows = [...document.querySelectorAll("#roleLayers .rlrow")]
      .map(r => [r.dataset.overlay, r.classList.contains("off")]);
    for (const k in at) setRoleView(k, true);
    await settle();
    for (const k in at) back[k] = at[k]();
    return { changed: { loops: on.loops !== off.loops, colors: on.colors !== off.colors },
      back: back.loops === on.loops && back.colors === on.colors, rows };
    """
    shot = job("roles_bad_buck", roles_page, tmp_path, ref=REFS / "roles_bad_buck.png")
    (picture,) = run([shot], tmp_path)
    assert picture["errors"] == [] and picture["ok"] is True, picture
    found = _act(roles_page, tmp_path, script)["result"]
    assert found["changed"] == {"loops": True, "colors": True} and found["back"] is True
    assert ["loops", True] in found["rows"] and ["colors", True] in found["rows"]


def test_confirm_roles_offered_to_a_served_page(roles_page: Path, tmp_path: Path) -> None:
    """Requirement "Roles from a served page", the page side: with the actions of a served page the panel
    offers Confirm for the inferred rows, and the inspector Confirm role for an inferred net; both plan the
    action `roles` with those names."""
    script = """
    const asked = []; ACTS.enabled = true;
    ACTS.offer = { roles: { available: true, title: "Confirm roles", options: {} } };
    window.FenoliteActions.plan = (action, options) => { asked.push([action, options]); };
    buildRoles(); await settle();
    document.getElementById("rolesConfirm").click();
    $q('#roleNets .rrow[data-net="GH"]').click(); await settle();
    document.getElementById("inspConfirmRole").click();
    return { asked, inferred: S.roles.roles.filter(r => r.state === "inferred").map(r => r.net),
      groups: S.roles.groups.filter(g => g.origin === "inferred").map(g => g.name) };
    """
    found = _act(roles_page, tmp_path, script)["result"]
    (action, everything), single = found["asked"]
    assert action == "roles" and everything == {"nets": found["inferred"], "groups": found["groups"]}
    assert single == ["roles", {"nets": ["GH"], "groups": []}]
