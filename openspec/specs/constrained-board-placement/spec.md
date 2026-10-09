# constrained-board-placement Specification

## Purpose
TBD - created by archiving change c0096-constrained-board-placement. Update Purpose after archive.

## Requirements

### Requirement: Mechanical authoring and coordinate contract
The DSL SHALL record anchor constraints with `MechanicalIntent` (stable key, units, frame, tolerance, source and evidence) on `Part.place(..., locked=True, anchor=...)`, the fixed-anchor primitive, which MUST be respected. Holes and keep-outs are those of `Design.hole` (c0102) and `Design.rule_area` (c0103). Measured, estimated and proposed anchors MUST remain distinguishable; none implies qualified fit.

#### Scenario: Frame roundtrip
- **GIVEN** an authored board has a locked interface with an anchor at stated board-relative coordinates
- **WHEN** the script is converted and canonical model JSON is written and read back
- **THEN** the origin transform is applied once, model coordinates equal the supplied relative coordinates plus one board origin, and the anchor stays in the DSL `placements` output and out of the canonical JSON

### Requirement: Existing drills and reservations
A mechanical reservation SHALL optionally reference a specific existing footprint drill instead of creating another Hole. Duplicate coincident hole intents MUST be detected; electrical pads around a fixing drill MUST keep their assigned net. Assembly reservation volumes and allowed penetrations MUST be explicit user geometry and may not be invented from drill diameter. Each reservation SHALL identify one existing drill, supply its volume geometry and provide nonempty source provenance with measured status; missing source or non-measured status SHALL yield `reservation:<key>:source_measurement` as an unresolved input, never a qualified fit.

#### Scenario: Existing mounting pad
- **GIVEN** a fixing reservation references an authored footprint drill with an electrical pad
- **WHEN** the board is built
- **THEN** one physical drill exists, the pad net is unchanged and only the declared reservation is added

### Requirement: Constrained placement and hard checks
A constrained placement API and --strategy constrained SHALL place selected components deterministically under outline/cutout, keepout, locked anchor, supplied edge/gap and same-layer copper requirements. Opposite faces MUST still respect drilled projections and known body/assembly volumes. Candidate enumeration SHALL start within the intersection of the board bounds and the group-region bounds of that footprint; full polygon containment SHALL still be checked. Candidate placement MUST include all same-footprint findings in its placement assessment and MUST not use force or soft objectives to erase them.

#### Scenario: Fixed interface and both faces
- **GIVEN** an independently authored board contains locked interfaces, drills, body constraints and several movable components
- **WHEN** constrained placement proposes a layout
- **THEN** the anchors remain exact and every accepted candidate respects the supplied hard geometry and inter-component copper constraints

#### Scenario: No feasible placement
- **GIVEN** an authored component fits nowhere under the hard constraints
- **WHEN** placement runs
- **THEN** it remains explicitly unplaced with a reason rather than being hidden, dropped or staged outside the outline

### Requirement: Electrical grouping and proximity objectives
Placement SHALL accept explicit module/group regions, connected-pad proximity targets, declared connected-pad chains represented as explicit pair objectives and optional maximum connection-distance objectives. It MUST report each objective contribution and unmet target; surrogate airwire length MUST not be claimed as routed inductance, EMI, thermal performance or final routing feasibility. No topology, net class or component value may be changed to improve placement.

#### Scenario: Long critical connection
- **GIVEN** an authored layout satisfies hard constraints but one declared pad-to-pad objective exceeds its target
- **WHEN** the result is produced
- **THEN** the long objective is named with its measured surrogate distance and remains pending for layout/routing review

### Requirement: Placement reproducibility and preview
Requests, source hashes, hard rules and deterministic parameters SHALL be recorded with the candidate positions and unresolved constraints. Preview MUST show the board frame, side/view convention, holes, locks and actual pad copper on the displayed layers, including through-hole copper on both faces. A bounding-envelope view MUST state its conservatism and cannot replace a manufacturing view.

#### Scenario: Two-face preview
- **GIVEN** an authored top-side through-hole part and a bottom-side asymmetric part are placed
- **WHEN** both-face preview is rendered from the written/read-back geometry
- **THEN** through-hole pads appear on both copper faces and bottom-side pad mirroring is applied exactly once

### Requirement: Injected checks preserve package layering
The planner SHALL consume hard-check results through an injected checker interface without importing
checks or analysis. Missing checking MUST remain incomplete. Electrical profiles/readiness are out of scope.

#### Scenario: Missing mechanical checker
- **GIVEN** a neutral proposal has no available body projection checker
- **WHEN** the placement assessment is returned
- **THEN** it names the missing check and does not claim mechanical success
