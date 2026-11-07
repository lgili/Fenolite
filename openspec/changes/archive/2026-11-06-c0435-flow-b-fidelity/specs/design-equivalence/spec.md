## ADDED Requirements

### Requirement: Footprint names after the library rewrite
Level 3 of `equivalent` SHALL NOT report `footprint-name` for two names that are equal once each is
rewritten by `core.libnames.library_name(name, allow_space=True)`, the rewrite the Altium to KiCad
conversion gives the entries of its derived library (change c0435).

#### Scenario: A slash
- **WHEN** `uv run pytest tests/unit/convert/test_flow_b_fidelity.py -k library_rewrite -q` compares names
- **THEN** `R/0603` and `R_0603` are the same name, and `R_0603` and `R_0805`, or `R/0603` and `R_0603_2`, are not
