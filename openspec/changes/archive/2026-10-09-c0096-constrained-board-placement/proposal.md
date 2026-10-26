# Propose constrained board placement

## Why

Grid placement cannot preserve declared interfaces, existing drill reservations, group regions and
connected-pad proximity objectives as one reproducible request. A neutral planner needs bounded
search, explicit unplaced results and hard checks supplied through interfaces.

## What Changes

- Author holes, keepouts and locked anchors with integer geometry and source/tolerance metadata.
- Record reservations on existing drills and detect duplicate physical drill intents.
- Add deterministic constrained translation proposals, hard geometry checks and soft objectives.
- Inject copper/mechanical checking without importing checks or analysis in placement.
- Integrate the strategy with the existing CLI transaction and both-face copper previews.

## Capabilities

### New Capabilities

- `constrained-board-placement`: requests, bounded proposals, checks and previews.

### Modified Capabilities

- `design-dsl`: mechanical primitives and anchor metadata.
- `design-model`: additive mechanical intent.
- `cli-contract`: constrained place options and result fields.

## Non-goals

Electrical profiles/readiness, a global optimum, automatic routing, inferred
assembly dimensions or changing default manual/grid behaviour. The planner works through neutral BoardFrame and checker interfaces.

## Milestone

v0.4.

## Evidence level required

INFERRED on authored fixtures and deterministic readback/preview proofs. Existing KiCad frame and
placement oracle tests support the unchanged backend transforms. See S-0010 and S-0019.

## Impact

One signed local commit from origin/dev. Core dependencies and package guards stay unchanged.
The first request schema is fenolite.placement-request.v0. Unknown checks remain explicit.
