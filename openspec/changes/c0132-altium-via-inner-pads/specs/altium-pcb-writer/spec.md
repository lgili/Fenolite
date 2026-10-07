## ADDED Requirements

### Requirement: Removed pad shapes are counted, not written
`lower.write_design` SHALL write a via whose `altium` bag holds the pair `pad_removed` as the ordinary via record of 321 bytes, with a pad on every layer of its span, and SHALL count it (change c0132).
- Every such via that is written MUST be listed in `AltiumInputs.not_lowered` under the kind `via-pad-shape`, with the reason that the layers without a pad shape are not written. The kind MUST be in `MORE_KINDS` and MUST NOT be in `LOSS_KINDS`: the via is written, and a write is not refused for it.
- The via MUST stay in the comparison of RT-A3 (`altium-verification`, "Round-trip level RT-A3"): the kind names no model entity that the write left out.
- No byte of the table at 209 and no further byte of the 330-byte form MUST be written: no fact says what the nine further bytes of that form are (`docs/formats/altium/pcb-copper.md`, "Via").
- A via without the pair MUST be written and counted as before.

#### Scenario: A via with removed pad shapes in a rewrite
- **GIVEN** the reading of `tests/data/altium/routed/routed.PcbDoc` with the pair `("pad_removed", "2,4,5")` added to the bag of its first via
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k pad_shape` writes it without `allow_lossy`
- **THEN** the write is not refused, every via is written as a record of 321 bytes whose table at 209 is zero, the files are the bytes of the write without the pair, `not_lowered["via-pad-shape"]` holds the id of the first via alone, and the write has one `altium.not-lowered` information for the kind
