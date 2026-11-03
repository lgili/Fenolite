# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native declared input bytes are checked before the build can stage them (c0351)."""

from __future__ import annotations

import hashlib
import json

import pytest

from fenolite.core.errors import FormatError
from fenolite.lens.project_template import read_project_template, validate_project_template


def given(tmp_path, data=b"{}"):
    script = tmp_path / "design.py"
    script.write_text("# original authored fixture\n")
    folder = tmp_path / "native"
    folder.mkdir()
    template = folder / "project.kicad_pro"
    template.write_bytes(data)
    request = ("native/project.kicad_pro", hashlib.sha256(data).hexdigest())
    return script, template, request


def test_checked_input_is_returned_without_writes(tmp_path) -> None:
    data = (
        b'{"meta":{"version":3},"net_settings":{"meta":{"version":5}},'
        b'"authored":{"value":1.2500,"text":"/plain/not-a-path-field"}}\n'
    )
    script, template, request = given(tmp_path, data)
    result = read_project_template(script, request)
    assert result.text.encode() == data and result.path == template
    assert result.sha256 == request[1] and template.read_bytes() == data


@pytest.mark.parametrize(
    "data",
    [
        b"[]",
        b"{}",
        b'{"meta":{"version":3},"net_settings":{"meta":{"version":3}}}',
        b"{bad}",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"meta":{"version":true}}',
        b'{"meta":{"version":999}}',
        b'{"net_settings":{"meta":{"version":999}}}',
        b"\xff",
    ],
)
def test_invalid_or_future_declared_json_is_not_synthesized(data, tmp_path) -> None:
    script, template, request = given(tmp_path, data)
    with pytest.raises(FormatError):
        read_project_template(script, request)
    assert template.read_bytes() == data


def test_missing_or_changed_declared_input_refuses(tmp_path) -> None:
    script, template, request = given(tmp_path)
    template.write_bytes(b'{"changed":true}')
    with pytest.raises(FormatError, match="digest"):
        read_project_template(script, request)
    template.unlink()
    with pytest.raises(FormatError):
        read_project_template(script, request)


def test_symlink_cannot_escape_the_script_folder(tmp_path) -> None:
    script, template, request = given(tmp_path)
    outside = tmp_path.parent / "authored-outside-project.kicad_pro"
    outside.write_bytes(b"{}")
    template.unlink()
    template.symlink_to(outside)
    with pytest.raises(FormatError, match="folder"):
        read_project_template(script, request)


@pytest.mark.parametrize(
    "reference",
    [
        "/outside/frame.kicad_wks",
        "../frame.kicad_wks",
        "Z:/frame.kicad_wks",
        "\\\\server\\frame.kicad_wks",
        "${UNKNOWN}/frame.kicad_wks",
    ],
)
def test_known_unsafe_native_resource_is_not_followed(reference) -> None:
    data = json.dumps(
        {
            "meta": {"version": 3},
            "net_settings": {"meta": {"version": 5}},
            "schematic": {"page_layout_descr_file": reference},
        }
    )
    with pytest.raises(FormatError):
        validate_project_template(data, file="native/project.kicad_pro", managed_frame=True)


def test_known_portable_resource_requires_an_explicit_managed_frame() -> None:
    data = (
        '{"meta":{"version":3},"net_settings":{"meta":{"version":5}},'
        '"schematic":{"page_layout_descr_file":"${KIPRJMOD}/frame.kicad_wks"}}'
    )
    with pytest.raises(FormatError, match="sheet"):
        validate_project_template(data, file="native/project.kicad_pro")
    validate_project_template(data, file="native/project.kicad_pro", managed_frame=True)


def test_code_owned_minimum_governs_planning_and_output_with_fresh_root_ids(monkeypatch) -> None:
    import _drawn
    from _buildhelp import build

    from fenolite.backends.kicad import pro
    from fenolite.backends.kicad.sexpr import parse
    from fenolite.dsl import copper, mm
    from fenolite.lens import build as build_module

    design = _drawn.design("full")
    design.rules.minimum(edge_clearance=mm("0.7"))
    design.track(
        "template_managed_floor",
        (mm(35), mm(25)),
        (mm(37), mm(25)),
        width=mm("0.25"),
        net=next(iter(design.nets.values())),
    )
    data = json.loads(pro.write_project_text(pro.template(10)))
    data["board"]["design_settings"]["rules"]["min_copper_edge_clearance"] = 0.01
    data["board"]["design_settings"]["rules"]["min_via_annular_width"] = 0.19
    data["meta"]["filename"] = "stale-input-name.kicad_pro"
    data["sheets"] = [["11111111-1111-5111-8111-111111111111", "STALE"]]
    seen = []
    actual = build_module.resolve_copper

    def capture(*args, **kwargs):
        seen.append(kwargs["edge_floor"])
        return actual(*args, **kwargs)

    monkeypatch.setattr(build_module, "resolve_copper", capture)
    output = build(
        design,
        10,
        project_dir=_drawn.folder("full"),
        drawn=_drawn.drawn("full"),
        drawn_file="schematic.toml",
        copper_intents=copper(design),
        project_template=json.dumps(data),
    )
    assert output.files and not [issue for issue in output.issues if issue.severity == "error"]
    assert seen == [700_000]
    project_name = next(name for name in output.files if name.endswith(".kicad_pro"))
    final = json.loads(output.files[project_name])
    assert final["board"]["design_settings"]["rules"]["min_copper_edge_clearance"] == 0.7
    assert final["board"]["design_settings"]["rules"]["min_via_annular_width"] == 0.19
    assert final["meta"]["filename"] == project_name
    root_name = _drawn.root_name(output)
    root_uuid = parse(output.files[root_name].decode()).find("uuid").atoms()[0].value
    assert final["sheets"][0][0] == root_uuid and all(row[1] != "STALE" for row in final["sheets"])
    assert final["schematic"]["top_level_sheets"][0]["filename"] == root_name
