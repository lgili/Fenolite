## Why

Package 1 of change c0175 ("Router input fidelity"), split into a change of its own as c0175's design allows
and as the maintainer chose on 2026-10-26: the first package of the board engineering tools, because it is a
defect that every routed board pays for. c0175 records the failure: an autorouter closed one connection in six
because of two defects of the Specctra design file that `write_dsn` writes.

- **A board-wide width rule with a preferred value** (`track_width`, selector `all`, with `opt`) becomes the
  width of every class. Such a rule is a limit with a preference, not a wish for every net: written into every
  class, it routed every net at that width, and little fitted.
- **A one-sided clearance rule** (`clearance`, one side a class, the other `all` or absent) raises the class's
  own clearance, so the class keeps that distance from its own nets too; dense regions of the class that
  KiCad's DRC accepts could not be routed.

And one limit of `fenolite route`: `--order` takes one glob per tier, so a tier of several name patterns needs
a single glob that matches them all.

## What Changes

- `track_width`, `all`, with `opt`: `opt` becomes the width of each class that holds no width of its own (and
  of the nets without a class); a class width inside `[min, max]` is kept and one outside is clamped into it,
  with one `specctra.rule-widened` (info) naming the rule and the classes it left unchanged. A width rule that
  names classes keeps today's behaviour.
- `clearance`, one side classes, the other `all` or absent: one `class_class` pair per class of that side and
  per other written class; the class's own clearance is not raised. A class's clearance against itself comes
  only from rules that name it on both sides, the later rule of the board winning, as KiCad resolves it.
  Nets without a class keep the default clearance against the class, with one `specctra.rule-not-sent` (info)
  that says so.
- `fenolite route --order` takes comma-separated globs per tier (`--order "GATE_*,SENSE_*" --order "*"`); one
  glob per tier stays valid; an empty glob exits 2 with `FEN-2001`.
- A bench routes an authored dense board with Freerouting before and after, and records the share routed and
  the DRC findings; two hypotheses are registered.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `specctra-dsn`: MODIFIED "Routing rules in design files".
- `cli-contract`: MODIFIED "Route command budget and tiers".

## Non-goals

The other eleven packages of c0175, which stay there.

## Evidence level required

`INFERRED` for the file; the bench of task 1.4 measures the routed share and the DRC findings before and after
with Freerouting and `kicad-cli`, and registers the two hypotheses in `docs/hypotheses.md`.

## Impact

- `src/fenolite/backends/specctra/dsn.py`, `src/fenolite/cli/cmd_route.py`, their tests, a bench under
  `tests/kicad/routing/`, `docs/formats/specctra/dsn.md`, `docs/cli-contract.md`, `docs/evidence/routing.md`,
  `docs/hypotheses.md`, `CHANGELOG.md`.
- Size: about 2 design-days (c0175's estimate for the package).
