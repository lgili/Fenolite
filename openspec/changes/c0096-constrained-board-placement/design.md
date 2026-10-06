## Context

The shared dev implementation has grid/manual placement, BoardFrame, pad-copper projection and a
persistent native layout. This change adds a bounded neutral strategy without changing package
layering or introducing an electrical-readiness API. Its milestone is v0.4.

## Decisions

1. MechanicalIntent records a stable key, written-board frame, integer tolerance, source and input
   status/evidence. Estimated inputs remain proposals until explicitly measured. hole/keepout
   requests apply the board origin once; Part.place with an anchor requires locked=True.
2. MechanicalReservation references an existing footprint/pad drill and explicit board-frame
   volumes. It creates no extra hole and changes no pad net. Detect coincident duplicate drills.
   Physical reservation geometry is supplied independently of drill diameter.
3. PlacementConstraints holds pitch, edge/gap, finite candidate budget, reservations, group regions,
   mechanical geometry inputs and source hashes. PlacementObjective names exact pad ids, a weight
   and optional maximum centre distance; connected objectives require an assigned common net.
   No electrical profile enters this request. First serialized contract: placement-request.v0.
4. The planner imports only core, model, geometry and backends.base. A checker callback supplies a
   PlacementLegality report with hard constraints, missing inputs and intrinsic findings. The
   neutral fallback checks geometry and marks absent copper/mechanical checking explicitly.
   The CLI adapter supplies the existing copper checker and optionally the c0099 body checker.
   A missing optional checker is incomplete, never treated as clearance or mechanical success.
5. Keep outline/cutout, side-specific keepout, drills on both faces, edge/gap and group-region checks.
   Intrinsic findings are preserved separately; they are not numerical exemptions. A known hard
   constraint rejects a candidate. Unknown frame/copper geometry cannot become a feasible candidate.
6. Enumerate a bounded board-frame lattice in deterministic identity/coordinate order, preserving
   locked and unselected components, sides, rotations and topology. Score explicit pad distances;
   report failed searches and unmet objectives. Retain the original position when unplaced.
7. PlacementAssessment reports findings/incomplete/checked for this supplied placement check only.
   It is not c0098 readiness and provides no electrical or manufacturing qualification. Unknown
   assembly geometry and intrinsic findings remain present in the result.
8. CLI --strategy constrained reads an integer JSON request, refuses --force, plans before writing,
   uses --confirm and receipts, and verifies the written/read-back board hash before previews.
   Top/bottom SVGs show actual layer copper, holes, locks and conservative extents. Apply a single
   global bottom-view reflection after board projection; through-hole copper appears on both faces.

## Files and API

| files | API |
|---|---|
| model/board.py; dsl/design.py, part.py, convert.py; lens/build.py | MechanicalIntent, hole, keepout, locked anchor and origin-preserving lowering |
| placement/constraints.py | MechanicalVolume, MechanicalConstraints, reservations, groups, objectives, PlacementRequest |
| placement/constrained_legality.py | neutral finding/report types, checker interface and basic geometry checking |
| placement/constrained.py | bounded propose_placement with injected checker, objective metrics and PlacementAssessment |
| placement/preview.py | both-face copper SVGs tied to readback geometry |
| cli/placement_checks.py, cmd_place.py | check adapter and constrained transaction orchestration |
| tools/gen_schemas.py; schemas/ | additive board fields and placement-request.v0 |
| unit DSL, placement and CLI tests | generic authored requests, finite search, topology, drill/copper and preview proofs |

## Public sources used by this change

| id | URL | use |
|---|---|---|
| S-0010 | https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html | existing rule-area and placement frame conventions |
| S-0019 | https://gitlab.com/kicad/code/kicad/-/blob/9.0.9.1/demos/pic_programmer/pic_programmer.kicad_pcb | existing observed footprint/pad frame transforms on the declared public demo; no new native serialization fact |

The existing facts in docs/formats/kicad/board.md and copper.md and the registered frame hypotheses
are used unchanged. No assembly dimension or application checklist is imported. Test lengths are
invented round integer exercises.

## Hypotheses registered by this change

| id | statement | proof | criterion |
|---|---|---|---|
| H-G-CONSTRAINED-PLACE | bounded proposals preserve fixed geometry and topology while rejecting supplied hard constraints | tests/unit/placement/test_constrained.py, test_constrained_legality.py | deterministic hashes/positions; explicit unplaced reasons; all supplied hard constraints retained |
| H-G-PLACEMENT-PREVIEW | previews use read-back pad copper on both faces with one bottom reflection | tests/unit/placement/test_placement_preview.py and CLI tests | correct layer/pad/drill counts and matching written geometry hash |

## Evidence per behaviour

| behaviour | level | proof |
|---|---|---|
| mechanical authoring/canonical schema | INFERRED; authored canonical proofs | DSL/model and schema tests |
| neutral proposal and supplied-check orchestration | INFERRED | authored fake-frame and injected-checker cases |
| CLI write/readback and previews | INFERRED | authored transaction tests and existing placement/frame oracles |
| body checking supplied by c0099 | checker evidence retained; unknown if absent | optional adapter and injected provider tests |

## Conversion, native output and rebuild policy

`Hole.intent` and `Keepout.intent` are available in `to_model`, and a locked anchor in `placements`.
They are conversion-only input metadata: build and rebuild strip them and do not persist them in
native files or the regenerable `.fenolite/` cache. `FootprintInstance.anchor` remains a neutral
model field for explicit model callers. The build has no duck-typed anchor access.

A KiCad build refuses `design.hole()` as FEN-3004 (exit 3), naming the key and the validated drill
footprint alternative. Altium retains its native lowering of supported holes. A DSL keepout without
layers expands to all copper layers of the board. A native keepout with no layers restricts nothing.
On a KiCad rebuild the board's rule areas win, including when a script area moved or was added.
No merge rule is added. The current build reports no issue for that difference. The recommended
future diagnostic is `layout.keepouts-kept`, at board, analogous to `layout.outline-kept`, explaining
which script areas differ and that native layout was retained; that diagnostic is not implemented
in this change while the coordinator decides c0103's merge policy.

Group search first intersects each applicable group's box with the board's box, shrunk by the
footprint extent, and checks polygon containment on each candidate. Multiple groups intersect.
The bounded greedy search can miss a legal global layout; an exhausted search is explicit.

`estimated` means a supplied estimate regardless of its source; `measured` means the caller
records a measurement with provenance, and `proposed` is an unconfirmed proposal. None qualifies
assembly fit. The general reservation rule links one existing drill, explicit volume geometry and
a nonempty source with measured status. `source_measurement` names missing measurement provenance,
not an application-specific checklist. No volume is inferred from drill diameter.

## Relation to c0103, c0113 and c0102

Checked against proposal, design and spec deltas on `review-roadmap-complex-board`. The names below
are proposals for the coordinator, not compatibility renames or decisions implemented here.
c0100/c0102 modify Board and placements in the DSL; c0103 modifies Identifier derivation; c0113
modifies Place command. The complete MODIFIED requirements in this change must be reconciled with
theirs when integrating; no delta replaces only an excerpt of a living requirement.

| # | c0096 | other proposal / conflict | proposed name to keep and reason |
|---|---|---|---|
| 1 | `hole(key, x, y, drill, plated=...) -> Hole`, `Board.holes`, `hole:<key>` | c0102 `hole(ref, x, y, *, drill, length, rot, pad, courtyard, locked) -> Part`, Fenolite_Holes; **conflict** in signature, representation and KiCad support | c0102's `hole` for native KiCad authoring, because it uses the supported footprint representation; coordinator decides migration of the neutral Hole call |
| 2 | `keepout(key, outline, layers=(), no_*=...) -> Keepout`, any layers, at least one flag, `keepout:<key>`, intent, board areas kept | c0103 `rule_area(name, outline, layers=None, forbid=())`, copper only, empty forbid allowed, `Keepout.name`, `area:<name>`, regenerated; **conflict** in API, ids and rebuild authority | `rule_area` for the common native object; the coordinator must reconcile the existing call and ids rather than adding two synonyms |
| 3 | `place.constraint` at board, footprint/face in message; touching counts | c0113 `place.keepout` at ref, courtyard interiors intersect, separate no-courtyard warning; **conflict** in predicate, location and severity | `place.keepout` for a native placement check, because its proposed predicate is oracle-backed; keep constrained solver reports separate until reconciliation |
| 4 | pad keepout yields `place.constraint` | c0103 `copper.keepout` in copper check; **conflict** in check ownership/code | `copper.keepout` for the shared copper verdict; solver adapter should consume it |
| 5 | `PlacementObjective` by exact pad ids, weighted ceiling distance, optional connectivity/maximum | c0113 `near`, RuleSet.proximity, `placement.too-far`, floor distance, no motion; **conflict** in rounding and inputs, distinct optimization/judging roles | keep `PlacementObjective` for solver cost and `near` for a persistent design rule; coordinator decides conversion and one rounding rule |
| 6 | request `MechanicalVolume` and `MechanicalConstraints` | c0113 Part/Component.height and height_limit in RuleSet; **overlap** in checking bodies, distinct input scopes | keep request `MechanicalConstraints` for explicit 3D geometry and `height_limit` for board rules; neither may be silently substituted |
| 7 | constrained strategy, constraints/budget/previews, placement/preview result, new capability | c0113 grid/manual Place command plus rules/measures and living placement legality; **conflict** in full MODIFIED Place command deltas | keep `constrained` as an explicit strategy alongside grid/manual, composing the result contracts at integration |
| 8 | MechanicalIntent `anchor` on a locked placement | c0113 ProximityRule.anchor and c0111 AnchorRef/Anchor in a part frame; **name/semantic conflict** | keep the existing locked placement `anchor` as metadata for now; coordinator should decide a provenance-specific spelling distinct from a geometric anchor |

No counterpart found for MechanicalIntent, GroupRegion, MechanicalReservation, previews or the
request schema. Every conflicting row awaits the coordinator; this correction renames or removes
none of those APIs to match the proposals.
