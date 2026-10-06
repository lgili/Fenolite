# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The facts a generated schematic is written from, measured on the running ``kicad-cli`` (capability
kicad-oracle, "Schematic naming facts are probed"; hypotheses ``H-K-SCH-PINFRAME``,
``H-K-SCH-UNCONNECTED``, ``H-K-SCH-SLASH``, ``H-K-SCH-POWER`` and ``H-K-SCH-LIBTABLE``; change c0061)."""

from __future__ import annotations

import _gencases as gen
import _probes
import pytest

from fenolite.backends.kicad import netnames, schlayout

pytestmark = pytest.mark.needs_kicad
MIRROR_NAMES = {"": "none", "x": "x", "y": "y"}


def test_pin_frame() -> None:
    """A label at ``schlayout.pin_point`` connects every pin, for every rotation and mirror."""
    assert gen.frame_unconnected(0, "", (90, "")), "the control: labels of another frame leave pins open"
    proved = set()
    for rotation in schlayout.ROTATIONS:
        for mirror in schlayout.MIRRORS:
            outcome = _probes.run(f"sch-pin-frame-{rotation}-{MIRROR_NAMES[mirror]}")
            print(f"sch-pin-frame-{rotation}-{MIRROR_NAMES[mirror]}: {outcome}")
            assert outcome in ("absent", "present")
            if outcome == "absent":
                proved.add((rotation, mirror))
    assert (0, "") in proved
    assert proved == set(schlayout.PROVED_FRAMES), "PROVED_FRAMES must be the pairs this major proves"


def test_unconnected_names() -> None:
    """``sch export netlist`` names a pin on no net as ``netnames.unconnected_name`` does."""
    for kind in ("plain", "unnamed", "units"):
        rows = gen.unconnected_names(kind)
        differing = {key: row for key, row in rows.items() if row[1] != row[2]}
        print(f"sch-unconnected-{kind}: {_probes.run(f'sch-unconnected-{kind}')}; {len(rows)} pins")
        assert _probes.run(f"sch-unconnected-{kind}") == "equal", differing
    units = gen.unconnected_names("units")
    assert units[("U2", "7")][2] == "unconnected-(U2C-GND-Pad7)"
    assert units[("U2", "1")][2] == "unconnected-(U2-Pad1)"
    chars = gen.unconnected_names("chars")
    for (_, number), (name, ours, theirs) in sorted(chars.items(), key=lambda item: int(item[0][1])):
        print(f"  pin {number} {name!r}: {theirs}  ({'equal' if ours == theirs else 'different: ' + ours})")
    outcome = _probes.run("sch-unconnected-chars")
    print(f"sch-unconnected-chars: {outcome}")
    assert outcome in ("equal", "different")
    for name, ours, theirs in chars.values():
        if ours != theirs:
            assert not netnames.proved(name), f"{name!r} is not named as expected and must not be proved"
    equal = {ch for name, ours, theirs in chars.values() if ours == theirs for ch in name}
    differing = {ch for name, ours, theirs in chars.values() if ours != theirs for ch in name}
    assert netnames.PROVED_PIN_CHARS - set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ) <= (equal - (differing - equal)) | set(" /+-_.~{}"), (
        "a character class without a probe is in PROVED_PIN_CHARS"
    )


def test_label_names() -> None:
    """A global label's text is the net name; a slash is stored as ``{slash}``."""
    found = gen.label_nets(gen.LABEL_TEXTS)
    for text, net in found.items():
        print(f"  label {text!r}: net {net!r}")
    assert _probes.run("sch-label-plain") == "equal"
    assert _probes.run("sch-label-chars") == "equal", {t: n for t, n in found.items() if t != n}
    assert gen.label_nets((gen.SLASH_TEXT,)) == {gen.SLASH_TEXT: "mod{slash}LED_A"}
    assert _probes.run("sch-label-slash") == "equal"
    assert _probes.run("sch-parity-slash-stored") == "absent"
    assert _probes.run("sch-parity-slash-raw") == "present"


def test_power() -> None:
    """The authored power flag drives its net; hidden power inputs of one name join, shown ones do not."""
    assert _probes.run("sch-power-flag") == "absent"
    print(f"hidden: {gen.supply_nets(True)}; shown: {gen.supply_nets(False)}")
    assert _probes.run("sch-hidden-power-joined") == "present"
    assert _probes.run("sch-shown-power-separate") == "equal"


def test_library_rows() -> None:
    """ERC reports a symbol without a library, and nothing once the project libraries hold it."""
    assert _probes.run("sch-lib-missing") == "present"
    assert _probes.run("sch-lib-vendored") == "absent"
    assert _probes.run("sch-lib-variant") == "absent"
