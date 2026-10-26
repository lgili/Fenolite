# review-panels Specification

## Purpose
The board view gives the review panels of an Altium user: a filter query, Find similar, highlight modes, the Components and Nets lists with routed lengths, and every parameter of a part (change c0187).

## Requirements

### Requirement: Filter query
The page SHALL select the board primitives that a filter query matches: `key:value` terms on net, ref, footprint, value, layer and side, with wildcards, `|` for or and a leading `-` for not.

#### Scenario: Parts of a footprint on the bottom
- **GIVEN** the scene of an authored board with three 0402 parts, one on the bottom
- **WHEN** `uv run pytest tests/unit/view/test_filter.py` runs the query `footprint:*0402* side:bottom` under Node
- **THEN** one part is selected
