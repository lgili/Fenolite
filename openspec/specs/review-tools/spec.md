# review-tools Specification

## Purpose
The viewer's review tools: edge-to-edge measurement, links that reopen a view, review marks a person leaves for a colleague or an agent (`fenolite.review.v0`), and SVG and print of the view (change c0189).

## Requirements

### Requirement: Edge measurement
The page SHALL measure the shortest distance between the edges of two clicked objects and show the two closest points, and the distance SHALL equal the clearance `analyze` reports for the same pair within 1 µm.

#### Scenario: Two pads
- **GIVEN** the scene of an authored board with two rectangular pads 0.2 mm apart
- **WHEN** `uv run pytest tests/unit/view/test_edge_measure.py` measures between them under Node
- **THEN** the distance reads 0.200 mm
