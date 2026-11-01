# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The round-trip property of the authored grammars (change c0263, "Round-trip property", scenario "Every
expanded MPN decodes to itself"; hypothesis H-G-FAMILY-ROUNDTRIP in ``docs/hypotheses.md``)."""

from __future__ import annotations

import pytest
from _grammars import authored, authored_files

from fenolite.pick.grammar.decode import decode
from fenolite.pick.grammar.expand import expand
from fenolite.pick.grammar.valuecodes import decode_value, encode_value


@pytest.mark.parametrize("path", authored_files(), ids=lambda path: path.name)
def test_every_expanded_mpn_decodes_to_itself(path) -> None:  # noqa: ANN001
    families = authored()
    family = next(item for item in families if item.file == path.as_posix())
    by_codes = {item.codes: item.mpn for item in expand(family)}
    count = 0
    for candidate in expand(family):
        count += 1
        found = decode(candidate.mpn, families)
        assert len(found.decoded) == 1 and found.issues == (), candidate.mpn
        parsed = found.decoded[0]
        assert parsed.in_matrix and parsed.candidate.suffix == ""
        assert parsed.candidate.codes == candidate.codes and parsed.candidate.value == candidate.value
        assert parsed.candidate.code_texts() == candidate.code_texts()
        assert parsed.candidate.attributes() == candidate.attributes()
        # re-encoding the decoded combination gives the MPN back
        assert by_codes[parsed.candidate.codes] == candidate.mpn
        value_field = family.value_field
        assert value_field is not None
        spelled = dict(candidate.codes)[value_field.name]
        assert encode_value(value_field.scheme, candidate.value, value_field.scale) == spelled
        assert decode_value(value_field.scheme, spelled, value_field.scale) == candidate.value
    assert count > 0
