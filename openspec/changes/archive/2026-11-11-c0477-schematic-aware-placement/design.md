# Design

Proposed 2026-11-10. The engine takes a resolved design and explicit placement intent and returns
candidate poses, partial diagnostics and scoped routing evidence. The first slice optimizes a
selected group or region. KiCad supports staged application. Altium PCB and single-board
project inputs support exploration using native geometry and rules. Application for Altium
uses a reviewed conversion to a separate KiCad copy, staged placement, and a reviewed export
to a new Altium document. Whole-board optimization reuses the same primitives.

## Inputs and identity

- Read the neutral circuit, board frame, stackup, project rules, mechanical volumes, selection,
  effective locks, route decisions and reusable block poses. Distinguish placed, staged,
  intentionally off-board, DNP and board-only items. A DNP footprint still occupies PCB copper
  and cannot supply a fitted decoupling function.
- Match through stable hierarchical paths and resolved model identities. Resolve logical pins
  to physical pad identities, including duplicate pad numbers, multi-unit symbols and repeated
  sheets. Use resolved ports, nets and bus members. A matching label, reference prefix, drawing
  coordinate or wire direction cannot establish connectivity. Imported boards may supply explicit
  intent without a matching schematic. An unresolved selected identity or required relationship
  blocks checked application.
- Respect layout-lens precedence. Script locks, measured anchors, user pins, excluded components
  and protected block members are fixed. A selected part attached to tracks, arcs, vias, protected
  copper or relevant saved fill is fixed in the first slice. Refuse an affected move when attachment
  cannot be checked. Footprint-owned copper travels with the supported backend transformation.
- Support declared mechanical projections, such as a connector overhang, only with an applicable
  geometry and side constraint. Unmodeled projections make the affected move unavailable.

## Schematic graph and intent

Build a bipartite graph of instances and resolved nets with logical and physical terminals on each
incidence. Block instances, approved pin maps and confirmed intent seed functional groups.
A recognizer suggestion carries matched topology, exact endpoints, rule version, provenance,
confidence, alternatives and missing facts. The existing placement is not evidence of which IC
a capacitor serves. Explicit intent takes precedence over confirmed intent and then suggestions.
Conflicting explicit requirements are reported together. Suggestions require confirmation to
become constraints or change the optimization objectives. The [rule catalogue](engineering-rules.md)
defines recognizers and fixture cases.

Use a directed graph only where terminal metadata or declared intent justifies signal or power
direction. Condense strongly connected components for coarse ordering and keep feedback paths
as intra-block objectives. Bidirectional or unresolved ports remain undirected. A shared clock or
rail is a hyperedge. Broad fanout may be downweighted in partitioning. Local supply/return,
isolation and routing width obligations stay in the model.

A declared rigid assembly has one pose and an exact transform for each member. Saved block poses
require current footprint, pad and connectivity bindings. Flexible groups keep independent poses
and shared objectives. A component in several relationships still has one pose.

## Matching electronic patterns

Represent each recognizer as a small typed pattern over the resolved incidence graph. Start
at a discriminating terminal, for example an oscillator terminal or a declared supply bank.
Walk the allowed terminal and device types in a bounded neighborhood. Compare the exact
terminal-to-net relations and collect competing bindings in stable order. Check component
function and variant before adding a match. Reuse confirmed role groups for power relationships
instead of building another independent classifier. Record why a rule stopped at a missing
terminal or ambiguous candidate. Keep categorical evidence and provenance with the suggestion.

For reviewed bypass bindings with several eligible capacitors, use a bounded bipartite
assignment as a seed. Edge costs estimate the best available legal pose relative to both
supply and return terminals. Use one capacity per required bank slot and per fitted capacitor
unless sharing is explicitly allowed. Carry alternate assignments into the local search when
their individual poses can interfere. The assignment cost cannot establish a feasible joint
placement. Check its actual component poses, bank coverage and returns together.

## Candidate generation and search

### Local baseline

1. Build finite domains from board and region bounds, allowed poses, exact pad anchors,
   free-space corners and a coarse-to-fine lattice. Include a legal input pose. Generate positions
   near both endpoints of a decoupling or feedback relationship. Cache footprint-local and rotated
   pad, body and courtyard geometry. Start with each part's current face, quarter turns and any
   supported existing pose. Side changes require explicit per-part permission and later proof.
2. Choose the variable with fewest viable poses, breaking ties by stable ID. Check constraints
   as endpoints become available. Propagate region and pair restrictions to the remaining
   domains. A pending endpoint remains pending. An empty sampled domain reports blocking
   geometry and the sampling budget.
3. Keep a bounded beam of partial assignments. Deduplicate canonical poses and retain distinct
   region or orientation alternatives. Compare partial states at compatible coverage. Prefer
   remaining feasible domains and reserved pad exits over lower costs caused by missing parts.
4. Refine complete candidates with legal translations, allowed rotations, compatible swaps
   and rigid-block moves. Around a congested window, freeze the rest and jointly reassign a
   small group. Use stable neighbor order and a fixed evaluation budget. Keep the incumbent
   and the current board pose as comparison points when legal.

Use boxes and a per-face spatial index to find nearby objects. Exact polygon checks decide
containment and overlap, including a cut-out wholly enclosed by a courtyard. Drills and permitted
assembly volumes have cross-face checks. Check affected copper, including objects beyond the
boundary of a scoped move. Retain unchanged baseline findings outside the affected scope and
recheck them for new or worsened effects. Reuse the existing placement checker adapter and run
final checks on serialized board readback.

### Whole-board floorplan and solver experiments

Coarsen the hypergraph into declared blocks and compatible, reviewed clusters. Respect domain
boundaries, fixed anchors, footprints and side-specific packing capacity. Compare a deterministic
multilevel partition with the hierarchy-only seed on flat designs. Propose region maps using
weighted net cuts, capacity and connections to fixed ports. Place large or constrained blocks
first. Expand them with the local solver. Revisit region boundaries where groups compete for the
same free space. Check the assembled board with the same hard checker. The [multilevel hypergraph
paper](https://doi.org/10.1109/92.748202) provides coarsening ideas, and [NS-Place](https://arxiv.org/abs/2210.14259)
provides a seed, refine and legalize reference.

A tiny difficult window can use exact finite-domain branch-and-bound with pose conflicts and
forward checking. Exhausting its domain proves infeasibility only on that enumerated domain.
Use it as a benchmark oracle for small instances. Compare seeded simulated annealing or a global
analytical seed after measuring the local baseline. Any optional solver uses the same neutral
inputs, pose checks and budgets. Keep runtime dependencies out of the core.

## Scoring and routing evidence

Compare complete candidates on the same active footprints, constraints and routing subjects.
Hard violations and missing mandatory checks make a candidate unavailable for application.
Partial states remain diagnostic. Report soft objectives in original units and by priority.

- **Electrical intent.** Measure exact pad distances, estimated path lengths, projected loop
  area over an ordered path, quiet/switching separation and declared channel symmetry. A loop
  without a known return or a self-intersecting sketch is unknown until a suitable probe. These
  quantities are geometric proxies.
- **Routing demand.** Keep pad HPWL as a baseline. Estimate demand from connection trees or
  coarse path sketches using width, clearance and eligible layers. Estimate directional capacity
  per layer from traversable lanes after obstacles and reservations. Use common lane units for
  demand and capacity, and count each connection once per resource. Charge the full required
  width of a pair or group. Handle zero capacity as unserved demand. Report peak and sum of
  squared overflow and incomplete capacity inputs. An unfilled zone does not supply verified
  connectivity or reference coverage. See [RUDY](https://doi.org/10.1109/DATE.2007.364463) and
  [Cypress](https://www.csl.cornell.edu/~zhiruz/pdfs/cypress-ispd2025.pdf).
- **Selection.** Rank declared critical goals before ordinary wiring and optional movement cost.
  Keep useful nondominated alternatives, with stable canonical ties. Any aggregate uses explicit
  normalization and profile weights. Keep distinct nm, nm², vias and counts in the report.

### Demand estimator and work accounting

Use a coarse adjacency graph whose edges cross a tile boundary in a direction on a specific
copper layer. Model legal layer changes as explicit edges. At each boundary, measure free
intervals after geometry, copper and keep-outs, using conservative sampled cross-sections.
A wide route must fit in one interval. The sum of fragments cannot stand in for one continuous
lane. Use an interval projection for quick screening and retain exact copper checks for finalists.

For each measured connection, choose a bounded coarse path sketch using allowed layers and
clearances. Charge the route's required cross-section, including the coupled width and gap when
relevant, against each traversed boundary. Compare demand and capacity in the same fixed-point
units. For a resource with known capacity C and demand D, overflow is max(0, D - C). Report
demand over zero capacity separately. Track peak overflow and sum of squared overflow, with
distinct flags for unmodeled resources and connections with no known sketch. Share occupancy
across sketches so many narrow signals and a wide bus compete for the same space. A congestion
proxy omits unsupported subjects with a visible reason and preserves their mandatory status.

During a tentative move, recompute only incident nets, touched resources and affected
neighborhood checks. After refinement, recompute whole-candidate metrics from scratch before
reporting. Charge candidate generation and pruning, evaluations and probe expansions to
explicit bounded counters. Limit both the retained state count and the work spent before a
state is retained. Tune beam size, grid schedules and neighborhood sizes on the authored
training fixtures under the published work budget.

Probe top distinct candidates with the same declared subject set, stackup and budgets. Check dense
package exits, critical loops and returns, supported coupled groups and competing corridor
connections. Use a shared provisional copper state to test coexistence. Independent escape probes
may eliminate a candidate but cannot establish coexistence. Record found paths, tested paths that
hit limits or were blocked, unsupported subjects, unattempted subjects, lengths, vias, clearance
findings and checked scope. The result states whether a group was checked as a unit. A failed
bounded search does not establish physical impossibility.

Feed failed escapes and congested corridors back into a bounded neighborhood refinement.
Use identical subjects to compare final evidence. Run probes in memory or in disposable
copies without mutating source files or route decisions. Confirming placement applies only
poses. Production routing and its checks are subsequent operations.

## Interfaces and file ownership

- Add `src/fenolite/placement/intent.py` for provenance and policy, `topology.py` for resolved
  incidences and suggestions, `optimize.py` for bounded search, `routability.py` for demand and the
  neutral probe interface, and `floorplan.py` for whole-board work. Reuse `constraints.py`,
  `constrained_legality.py`, placement measures and existing transforms.
- The scoped beam and refinement accept a neutral judge callback. The block APIs in
  `placement.floorplan` bind saved layouts, plan regions and expand them with the same
  solver. The CLI coordinates the CAD frame, geometry and router and returns a
  `PlacementOptimization` with candidates, diagnostics and fingerprints. The viewer reads
  those results and uses a fixed served request for refinement.
- Add `schemas/fenolite.placement-optimization.v0.json` and a result schema. The request carries
  selection, allowed poses, intent with provenance, hard constraints, budgets and probe subjects.
  Persist confirmed intent in the request, and keep existing constrained request files compatible.
  The read-only CLI publishes the request and result schemas in the schema catalogue.
  The review/write task adds its staged dependency binding separately.
- Extend `src/fenolite/cli/cmd_place.py` via a placement adapter. Proposed syntax
  `fenolite place BOARD --strategy optimize --constraints REQUEST --dry-run --json` lists
  alternatives. The caller can save the reply and use `--proposal FILE --candidate ID` to
  dry-run a selected complete move set. The unselected reply has no confirmable plan.
  Review treats saved JSON as untrusted: validate schema and limits, recompute the pose ID
  and dependencies, then repeat mandatory checks and any required probe for that exact pose.
  Do not accept supplied evidence fields as proof. Review cannot search for a substitute.
  The existing `--confirm --plan ID` writes its reviewed bytes.
- Fingerprint all consumed inputs, including board, schematic variant, library definitions,
  rules, intent, decisions and solver/probe versions and options. Candidate IDs include canonical
  poses and input fingerprint. Exclude elapsed time and display labels from identity.
  Reject stale inputs at review and confirm. Confirmation consumes staged bytes. Use the existing
  rollback, receipt and layout-lens mechanisms.
- Extend `src/fenolite/view/` and `viewer/src/` with read-only candidate overlays and served plan
  review. Show base/proposed poses, anchors, blockers, pad links, layer demand and probe status.
  Cross-probe by instance and pad IDs. Region refinement starts from an explicit selection and
  current board snapshot. Static pages expose inspection only.

## Limits and adoption

Budget candidate evaluations, legal moves and probe expansions. Record work separately from
elapsed time. Cancellation leaves the input intact and may return a complete previously checked
alternative only as a result, with the run marked incomplete. Stable ordering, fixed budgets
and fixed seeds make the non-time-limited search reproducible for a given version and inputs.

Ship the local baseline with auditable rule sources and authored fixtures. Enable larger scopes,
side changes and additional footprint families after their respective proofs. Keep algorithmic
claims INFERRED and associate native evidence with the exact geometry, routed scope and version
checked. See [evaluation](evaluation.md).
