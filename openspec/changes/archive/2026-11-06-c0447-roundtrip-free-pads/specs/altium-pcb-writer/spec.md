## ADDED Requirements

### Requirement: Free pads of a converted board
`lower.converted_free_pad(fp, ref)` SHALL say whether a footprint is the form a free pad takes through an
Altium → KiCad conversion (change c0447): no reference, exactly one pad, and a link whose item name (after
its last `:`) starts with `fenolite.core.libnames.FREE_PAD_PREFIX` (`FREE_`). `from_design` MUST write
such a footprint as a free pad with its net, as it writes the import's reading of one, and count it
changed under `footprint` with `lower.FREE_PAD_REASON`. A footprint with a reference MUST be written as a
component whatever its link.

#### Scenario: A converted free pad
- **GIVEN** a design with a footprint `p:FREE_fp_1` holding one pad of net `N` and no component, and a
  footprint `p:FREE_fp_2` of component `R9`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_free_pads.py -n 0 -q` runs `from_design`
- **THEN** the first is one free pad of net `N` and no component, counted changed with `FREE_PAD_REASON`;
  the second is the component `R9`
