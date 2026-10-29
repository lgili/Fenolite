## Why

Package 6 of change c0175 ("Generated copper"), split into a change of its own as c0175's design allows,
on 2026-10-28. A board script draws the same shapes again and again by hand: a power band that runs wide
where there is room and narrows beside a pad, a keep-out ring around a mounting hole, a band that keeps
other nets away from a class of high-voltage copper, a keep-out under a part's body on the other side, the
short track and via that join each SMD pad of a net to its plane, and the vias that tie two pours of one
net. Each is a loop of point arithmetic that an agent writes again for every board, and gets wrong at the
corners. The pieces exist: zones and rule areas of the script, the plane fan-out of `route`
(`backends.kicad.fanout`), the stitch resolver of script copper, and the placed pads of the build.

## What Changes

- Six calls of `fenolite.dsl.Design`: `band`, `keepout_ring`, `barrier`, `body_keepout`, `fanout_zone` and
  `stitch_pieces`. Each checks its arguments at the call and records plain data; `fenolite.dsl.generated`
  returns them, as `copper` returns copper intents.
- `fenolite.backends.kicad.generate.resolve_generated`: after the parts are placed and the script copper
  resolved, the build turns each record into ordinary zones, rule areas, tracks and vias, named by the
  call and its name, so a rebuild replaces them and nothing else; a check and a conversion need nothing
  new.
- Fourteen issue codes `kicad.generate.*`, explained by `fenolite explain`; the hypothesis `H-K-GEN-DRC`.
- `fenolite build` passes the records to the KiCad build; the Altium target refuses them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-dsl`: ADDED "Generated copper calls", "Power band", "Keep-out ring around holes", "Class
  barrier", "Body keep-out", "Fan-out to a zone", "Stitching of zone pieces" and "Generated copper codes".
- `kicad-oracle`: ADDED "Generated copper passes the oracle".

c0175 no longer holds a delta of `design-dsl`: its requirement "Generated copper and keep-outs" is the
eight requirements above (design, decision 1).

## Non-goals

- Stitching vias counted by the current of a net, and a free-area fill that only removes copper when it
  smooths (c0175's additions to package 6): each needs a current model or a polygon difference.
- An exact polygon union: without the `geo` extra the core has none, so a barrier and a body keep-out are
  convex envelopes (design, decision 4).
- Spines with arcs or with segments that are not horizontal or vertical.
- Generated copper on the Altium target: `kicad.generate.altium` refuses it.

## Evidence level required

`INFERRED` (`H-K-GEN-DRC`) for a build. `tests/kicad/dsl/test_generate_fill.py` refills the zones of the
built bench and runs `kicad-cli` DRC on both majors; the row is measured with the local `kicad-cli` 10 and
waits for the `kicad-9` job.

## Impact

- `src/fenolite/dsl/generate.py`, `dsl/design.py`, `dsl/__init__.py`, `backends/kicad/generate.py`,
  `backends/kicad/copper.py` (one public helper), `lens/build.py`, `cli/cmd_build.py`, `cli/explain.py`,
  `cli/data/explain.toml`, `agent/guide.py`, the guide's `board-power` page, tests,
  `docs/copper.md`, `docs/hypotheses.md`, `docs/evidence/matrix.md`, `CHANGELOG.md`, and c0175's
  `proposal.md`, `design.md`, `tasks.md` and `specs/design-dsl/spec.md`.
