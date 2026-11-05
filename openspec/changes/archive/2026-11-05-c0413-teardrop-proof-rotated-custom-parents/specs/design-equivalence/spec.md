## ADDED Requirements

### Requirement: Rotated and custom teardrop parents
Qualification of native-derived padvia caches SHALL accept a parent footprint or pad at any
whole-microdegree angle and SHALL refuse a finer angle. A non-quarter pose SHALL be judged with the
fixed-point cosine and sine and an explicit error bound: a containment or contact test SHALL hold only
when it holds for the parent bodies shrunk by the bound, SHALL fail only when it fails for them grown by
the bound, and SHALL refuse qualification otherwise. A custom pad SHALL qualify with `(clearance outline)`
or `(clearance convexhull)`; its body SHALL be its anchor plus only primitive copper known from inside:
a line of positive width as its round-capped stroke, a filled circle as its disc and, for an exact
quarter-turn parent, a filled polygon or rectangle as its interior. Arcs, unfilled or unknown primitives
and the primitives of bottom-side footprints SHALL add no body. Native regeneration SHALL remain the only
source of derived-cache equality.

#### Scenario: Turned custom antenna and primitive-attached cache
- **GIVEN** the public demo board `kicad-demo-9-0-9-1-pcb-01` with a custom pad at 20°, a custom pad with
  `(clearance convexhull)` and a cache attached only to a custom pad's line primitive
- **WHEN** `verify-source` runs its strict round trip with KiCad 10.0.6
- **THEN** the derived-cache proof qualifies both sides, regenerates six caches on each with equal exact
  geometry, and no teardrop `opaque-count` remains

#### Scenario: Native contact agrees with the turned body
- **GIVEN** authored pads: a 4 × 0.4 mm rectangle at 30°, a custom pad at 30° and 90° with a 1 mm wide
  line primitive, and a custom pad with `(clearance convexhull)`
- **WHEN** a probe track of another net ends inside the turned body but outside the unturned one, in a
  line's round cap, past that cap, or inside the convex-hull anchor
- **THEN** KiCad 9.0.9 and 10.0.6 report `shorting_items` exactly where the parent body predicts contact

#### Scenario: Unsettled contact refuses
- **WHEN** a non-quarter parent's contact test differs between its shrunk and grown bodies, or a
  coordinate lies beyond the bounded board frame
- **THEN** the board does not qualify and no derived-cache equality is claimed
