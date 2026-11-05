# Entry evidence and focused implementation proof

Published source: `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`, run `41421198968`,
KiCad 9 job `125196886139`: 41 failed / 1503 passed / 972 skipped / 1 xfailed,
1117 s. The failures are the 36 VME owner-context rows, orphan row 092 and
tag-9 rows 008/012/013/014. No successful required-job result is claimed.

The read-only probes use the unchanged decoder from `ce3b9992`, evidence head
`2307f683ae3b430b39c407c0f4bc498dc53c36f0`, declared manifest SHA-256
`bdc796c64b61f1e0a0240f2c133e879cc367a1ed256ea006cf883320b2cb4dcc`, and
actual native **9.0.2**. They export selected original owners only: the 130-row
census is not repeated and no lowering/decoder is patched.

## VME structure

The complete owner exports 6811 pins / 1800 groups over 36 reachable sheets.
For all three conflicting IDs, logical-pin, pin-geometry and body-geometry
signature counts are one. Removing only the varying full property nodes also
leaves one exact canonical non-property AST signature per ID:

| Context count | Varying full property nodes | Remaining AST SHA-256 |
|---:|---|---|
| 2 | Description, Val | `eb955606873f15de712bab434ac6ee9359ef926d32b4581ed676cf436a99ccae` |
| 11 | Description, Tolerance, Tolerance_1 | `70963591116012ad809b36ef2ba84c29b744e899b37f041da93dddab4f98ab44` |
| 5 | Description, Part Number | `01fff5290241db8090b9193d8f522221a095537f70dd7b3d1143d45b0b2c2692` |

UUIDs identify the original sheet contexts; they do not account for these
serialized conflicts. These results support scoped preservation, not property
omission or a general claim that every native semantic case is supported.

## Authored CC0 candidates outside the versioned source

The witnesses derive only from Fenolite's owned repeated-child and bus fixtures.
No third-party CAD is committed. Every listed input has an equal complete
own/native pin partition in its own controlled topology on actual 9.0.2.

| Candidate | Pins / groups | Raw name differences | Current vendor behavior |
|---|---|---:|---|
| Split-child identical defaults | 8 / 5 | 0 | accepts |
| Local Description snapshot | 8 / 5 | 0 | refuses; proposed positive case |
| Protected Value default changes | 8 / 5 | 0 | refuses; keep closed in this phase |
| Pin-number mutation | 8 / 5 | 0 | refuses |
| Pin-position mutation | 8 / 7 | 0 | refuses |
| `in_bom` flag mutation | 8 / 5 | 0 | refuses |
| Vector/group/overbar bus controls, each | 40 / 36 | 0 | accepts |
| Parent-only bus naming variants, each | 40 / 40 | 4 | accepts; name issue remains |
| Three scalar/local/hierarchical/global controls, each | 36 / 33 | 0 | accepts |

These are native investigation candidates, not new passing production tests.
Context-aware staging, exact emitted property nodes, effective component/BOM
semantics, stale-input refusal, default bytes and native 10 remain to be proved
after design review. Wrong-context and unknown/repeated-property preservation
negatives are required before any metadata exception is enabled.

## Implemented owned controls, 2026-11-02

Production checkpoints are `80b8e73e` (closed assets/index), `a7998ede`
(fail-closed intermediate inspection), `9ba33716` (scoped lowering/cache) and
`83697dac` (complete reviewed input binding). None changes model/S fields or
CLI envelopes. The native reader floor and name resolver remain unchanged.

Literal CLI proof: 23 passed / 12.72 s. Plan/sync/backend/import compatibility:
126 passed / 43.58 s. Path/import guards: 46 passed / 3.85 s. Backend/default
bytes: 86 passed / 22.66 s. Full source typing: zero errors.

Actual local **9.0.2**: the two new authored native controls pass in 7.34 s.
Four component records, including every field and flag, and four native CSV
BOM rows match. All nine strict fidelity levels are equal, with nonempty copper
coverage. All complete property nodes remain local, and the census adapter
retains four complete snapshots with equal 8-pin / 5-group source, lowered and
native-lowered partitions. The original CAD bytes remain unchanged.

The split fixture's second independent child now records its own generated
`fenolite.path` prefix (`ch1`, two instances), rather than a copied `ch0` prefix
from the formerly shared repeated file. This corrects owned bookkeeping;
electrical data, geometry, UUIDs and the Description snapshot stay intact.
No property is filtered from the native comparison. Historical observations
remain byte-identical.

The [real owner replay](../../../docs/evidence/contextual-symbols.md) on clean
`7584b394` preserves 460 complete contexts and all 6811 pins across 36 sheets.
Native original/written partitions are exactly equal at 1800 groups; the own
resolver still differs at 1700 groups, with all raw warnings/names retained.
The literal owner row fails; the other 35 row parameters were not executed.
Required native 9.0.9/10.0.6 CI, passing VME comparison and the root's exact
combined whole gate remain open. Local 9.0.2 proof does not establish them.

## Remaining names

Six original owners retain exact partitions. The 143 raw differences comprise
25 slash-escape spellings, 117 missing parent-bus member naming candidates and
one still-unreduced scoped election. The scalar controls agree with the current
generic policy, so changing that policy would be an unsupported fit. All raw
differences stay in the census; this packet implements no naming correction.
