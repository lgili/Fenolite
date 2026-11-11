# Evaluation protocol

## Benchmarks and comparability

Use authored fixtures with explicit geometry, net bindings and intended placement decisions.
Start with tiny exhaustive pose domains, an IC with local passives, a buck plus quiet sensing
and a half-bridge with fixed mechanical interfaces. Extend to authored two- and four-layer
boards with repeated channels, congested corridors and about 150 components as a scale target.
Reuse existing authored role, placement and router benches when appropriate. Separate tuning
fixtures from holdout fixtures. Record schematic/board/request hashes, placement and router
versions, seeds, probe subject sets, stackup, limits and checker versions.

For each board, compare the same selected parts and rules with the input/reference placement,
`grid` or `regions`, `constrained`, and the optimizer. For completed legal candidates run the
same fixed-order route job, limits and check profile. Compare with an independent native
post-route DRC and connectivity check on supported pinned KiCad versions. Keep the source
project outside all disposable route outputs. Report incomparable baselines, for example a
grid placement that leaves parts staged, instead of dropping hard cases or computing a
misleading improvement percentage.

## Measures and acceptance

| Measure | Acceptance use |
|---|---|
| Fixed poses, identity, pad mapping and topology | Exact before/after preservation where immutable. Rebuild preserves reviewed layout and respects later edits or locks. |
| Completeness and hard findings | Same selected IDs. Applicable candidates place every required part and introduce no new or worsened hard finding. Preserve pre-existing finding details. |
| Mandatory electronic intent | Report satisfied, violated or unknown for each relationship. An applicable candidate satisfies all required checks and scope. |
| Estimated objective values | Compare weighted pad distances, loop area, crossing/escape proxies and overflow. Record units, source and omissions. |
| Scoped probe outcome | Report found, blocked within search, budget exhausted, unsupported and unattempted. Compare a shared state for the same subjects. Coupled groups are one unit. |
| Held-out routed results | Compare remaining opens, routed subject count, route length, vias and relevant DRC with a fixed routing setup. Report results by family and board. |
| Search cost | Report evaluations, probe expansions, termination reason, wall time, peak memory and failure cases. Set a practical budget from measurements. |

Required counterexamples before adoption:

- A shorter pad-box score blocks dense pad escape or a common routing corridor. The probe must
  expose the regression and select or present the alternative with the better routed outcome.
- A pair of individually feasible routes competes for the only passage. An independent probe
  cannot count both as a joint success.
- An attractive partial assignment omits an awkward part. It remains diagnostic, with the
  omitted subject and reason, regardless of its lower estimated score.
- Equivalent schematics with different symbol and label positions give the same recognized
  intent. Different resolved net, variant or pin bindings change the intent or mark it stale.
- An obstacle, copper attachment, unavailable checker, unsupported pose, shared-rail ambiguity
  and cancelled or exhausted search each has a distinct diagnostic. No case causes an implicit
  write or a claim of infeasibility beyond a proved finite domain.

Run ablations in order: distance-only, electrical goals, per-layer demand, then route feedback.
Record which fixtures improve and which regress. Define numerical performance targets from the
first recorded baseline before inspecting holdout results. Require complete preservation and
hard legality across applicable cases, and a demonstrated routing win on the planted congestion
counterexample. Any regression in required critical checks blocks the candidate or release
claim. Summarize remaining opens and unresolved evidence even when total length improves.

## Evidence and operational checks

Local software tests support INFERRED algorithm and reporting behavior. Native oracle evidence
applies to the geometry and route outcomes it actually checked. Compare deterministic output
from equal inputs with fixed work budgets, excluding wall-clock telemetry. Test stale inputs,
unsupported verification, transaction failure/rollback and readback before closing. Use the
pinned viewer environment for visual references and check user interactions separately.
No benchmark result certifies manufacturing, thermal behavior, EMI or a different project.

## Initial scope audit

The local implementation starts from the neutral resolved circuit and physical footprint identities.
The constrained checker already supplies baseline geometry and copper diagnostics, the layout lens
defines rebuild precedence, and placement readback supports reviewed serialized bytes. The pinned
KiCad 9 and 10 jobs remain the intended native targets. Route adapters are evaluated in phase 2
for exact pad escape, protected copper and shared provisional occupancy. Unavailable capabilities
remain unverified. The initial topology fixture uses u-left/u-right and rail-left/rail-right as
stable authored IDs. The electronic rationale and public source facts are in engineering-rules.md.

### Reviewed placement and Altium conversion (2026-11-10)

The authored tests exercised exact candidate replay, tampered poses, stale rules before
confirmation and during review, an injected write failure with retry, and rebuild with a script
lock. KiCad to Altium export retained the relative component displacement within 3 nm when
reread. The blink PCB and project produced native read-only proposals. The full blink
Altium to KiCad to reviewed placement to Altium workflow preserved the source tree bytes.
These are local checks using Fenolite readers.

### Altium native save and reopen (2026-11-11)

Altium Designer 24.5.2.23 opened the authored blink board produced by the reviewed
placement export from `f2c60c97d`. It saved a new PCB document, closed it, and reopened
the saved file. The source SHA-256 stayed
`61dc1291265f286d5f04d69f459c58397e1548b653f2e1fa594b025f55b2c1d1`.
The saved SHA-256 was `ddaf44bc5386c2efe76438435dff6ad66258a6b76f155492fc7fbf16d0c33766`.
The saved file preserved all component positions, rotations and sides exactly.
The maximum relative position difference from the approved KiCad candidate was
1 nm per axis.

| Reference | X (nm) | Y (nm) | Rotation (µdeg) | Side |
|---|---:|---:|---:|---|
| D1 | 63,400,000 | -35,400,000 | 0 | bottom |
| R1 | 50,399,998 | -40,400,000 | 0 | top |
| U1 | 39,400,000 | -40,400,000 | 0 | top |

The native DRC report SHA-256 was
`feaacee6adb397c4116b0a0ac2d75b5b4e604e19abb98726222662f10bef07f0`.
It recorded 3 unrouted connections, 28 minimum solder-mask sliver findings and 10
silk-to-solder-mask clearance findings, with zero waivers, short circuits or
copper clearance findings under the selected rules. The control verifies the
converted-copy workflow with Altium 24.5 and reports its electrical findings.
Direct native edits remain gated separately by the existing Part J phase B evidence.

### Scoped connection probes (2026-11-10)

With identical limits the authored connection routes on an open board and reports no room
with a wall across the board. A second connection that routes in isolation is refused when
the first connection occupies its corridor. A coupled leg returns unsupported. The CLI
repeats a required escape probe at candidate review, rejects an exhausted probe budget and
writes only poses at confirmation.

### Board-derived channel estimate and seeded placement (2026-11-10)

A known-width single net consumes 600,000 nm of lane width at a fully blocked cross-section.
The authored pair consumes a single 1,300,000 nm lane including its gap and clearance, which
does not fit in either free interval around the obstacle. Absent dimensions or layers are
reported as missing. In the placement CLI a 1.5 mm reviewed pad distance has valid samples
beside a fixed part on a 5 mm lattice. The corresponding 1 nm request has no proposal.

### Local native KiCad check and placement view (2026-11-10)

The authored blink conversion opens in KiCad 10.0.6 both before and after the placement.
`fenolite check --kicad-cli …` reported the same 37 findings by code, severity and message.
Both runs exited 5 with the three existing unconnected-item errors. The board remains
unrouted. This comparison does not cover the other native targets or the routed benchmarks.

The standalone placement view binds the saved reply to the source board SHA-256. It shows
the component moves, exact pad links and before/after distances, plus per-layer overflow,
probe outcomes and missing inputs in each candidate group. The stale-source control
suppresses those overlays. The static scene has no placement write action.

### Local bypass and gate-loop oracles (2026-11-10)

Both authored fixtures passed on KiCad 10.0.6. They plan and apply the reviewed exact poses,
route the two open connections and pass native check. The switching fixture retains its
existing sense track. The board-file readback compares copper by physical records and
identity, ignoring file provenance which changes when reading staged bytes. In the crossing
negative control, the failed return prevents acceptance of the gate drive alone.

### Region planning and scale (2026-11-10)

The repeated-channel control has two signal edges and one broad supply edge. Coarsening keeps
each channel together and cuts only the supply edge (weight 85). A separate feedback case retains
the directed external port ordering. Exact local expansion rejects a footprint crossing a region
boundary and uses a neighboring allowed region. If every allowed region is full, no board candidate
is produced.

On the local KiCad 10.0.6 oracle, the two-layer baseline and four-layer holdout each had 150
components in 15 captured blocks, 150 placement evaluations and 75 routed connections.
The placement stage took 0.83 s and 0.66 s; placement, routing and native check took
5.43 s and 4.70 s respectively. These cases use one reviewed origin per block, 360 total
placement evaluations allowed, and the same built-in octilinear router. They measure
block binding, expansion and final geometry. They leave broader domain scaling unmeasured.

On two six-part finite-site controls with one footprint per site, beam and seeded annealing
both used 234 evaluations. The measured objective sums were 38 and 44 nm respectively
for both solvers, equal to the exhaustive results. The annealer stays a comparison test.
