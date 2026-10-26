## Context

The current origin/dev adapter holds source height/standoff, outline and model references,
but rejects malformed heights. Signed mounted-face intervals and explicit unknown projection
preserve component-associated records without widening native writer scope.

## Decisions

1. Add `z_min`, `z_max` (optional integer nm) and `projection_unknown=False` to ComponentBody.
   Known intervals have both ordered bounds, positive away from the mounted face. Legacy bodies
   retain their validation. An explicitly unknown source projection bypasses extent validation
   because preserved heights do not claim a valid extrusion; analysis cannot treat it as known.
2. Keep source height/standoff and references. For malformed lengths use an unknown projection
   and a located bad-length finding; zero placeholders are not claimed as geometry. Unsupported
   projection, model type and reversed bounds produce body-unknown. No raw bytes are duplicated
   in ext: the immutable reader record and source locator retain them. Extensions currently carry the
   existing exact-number metadata, which has the existing adapter contract and bounds.
3. Infer serialized Top=0/Bottom=1 from the public API enumeration and BodyProjection property;
   this mapping remains INFERRED. A mismatch with the mounting face is retained as unknown, since
   bodies can project through the board and that transform needs further evidence.
4. `body_volume` transforms local XY by placement and bottom-face Z by known thickness. Model
   reference envelopes and rounded non-cardinal rotations are conservative. Unknown source
   projection, missing polygon or missing thickness produce unknown, never a clear result.
5. `check_body_volumes` tests intersections and assembly obstacles, board penetration, explicit
   permitted volumes and complete containment in cutouts/drills. Conservative or missing input
   prevents qualified-clear. It changes no circuit or geometry.
6. Preserve package guards and dependencies. Analysis imports only model, geometry and core.
   No compressed library writer or default schematic output is touched.

## Files and public API

| file | API/change |
|---|---|
| model/board.py, model/design.py | ComponentBody fields and interval validation |
| analysis/body_volumes.py | BodyVolume, VolumeProjection, VolumeConstraints, VolumeReport, body_volume, check_body_volumes |
| backends/altium/adapter/bodies.py, board.py, codes.py | retained bodies, mounted-side input and body-unknown issue |
| schemas/fenolite.model.v0/board.json | additive schema |
| docs/design-model.md, docs/analyses.md, docs/altium.md | contracts and native round-trip limitation |
| docs/formats/altium/pcb-bodies.md | public projection facts and retention |
| tests/unit/model/test_body_volumes.py | canonical compatibility and validation |
| tests/unit/backends/altium/test_body_volume_import.py | every ambiguous body remains present |
| tests/unit/analysis/test_body_volumes.py | signed geometry and explicit unknowns |
| tests/corpus/test_altium_import.py | body count, byte identity and adapter retention |

## Sources registered by this change

| id | URL | use |
|---|---|---|
| S-0708 | https://www.altium.com/documentation/altium-designer/pcb/3d-bodies/extruded-spherical-cylindrical | heights, negative standoff and projection behaviour |
| S-0709 | https://www.altium.com/documentation/altium-dxp-developer/pcb-api-types-reference and https://www.altium.com/documentation/altium-dxp-developer/pcb-api-design-objects-interfaces-reference | TBoardSide ordering and BodyProjection type |

Existing S-0303 and S-0160 support model references and native reader retention. No parser code or
private material is used; fixture dimensions are invented numerical exercises.

## Hypotheses registered by this change

| id | statement | proof | criterion |
|---|---|---|---|
| H-A-IMP-BODY-Z | matching inferred mounted/projection sides preserve signed source heights; ambiguous bodies are retained as unknown | test_body_projection_facts.py, test_body_volume_import.py, corpus body retention | authored cases retained and corpus count unchanged |
| H-G-BODY-VOLUME | signed mounted extrusions transform across opposite faces and conservatively report material and obstacle intersections | tests/unit/analysis/test_body_volumes.py | authored exact, conservative and unknown cases agree with supplied geometry |

## Evidence per behaviour

| behaviour | level | proof |
|---|---|---|
| interval/canonical compatibility | mechanical | model tests and schema drift |
| serialized side mapping | INFERRED | public fact plus authored probes; no native acceptance claim |
| body retention | INFERRED; corpus supports count/byte identity | unit import and required corpus body tests |
| extrusion analysis | INFERRED | authored geometry exercises |

## Risks and delivery

Unknown source heights remain inspectable but unusable for mechanical clearance. Polygonal model
envelopes are not full 3D meshes. The existing native writer does not preserve these new projection
fields; document that limitation without widening writer scope. Deliver one signed local commit;
the coordinator runs the complete suite and decides integration. No archive or push here.

## Review scope and compatibility

Milestone: v0.4.

## Non-Goals

The native body writer remains outside this change. Its owner must add support
for z_min, z_max and projection_unknown in a follow-up; height and standoff remain source values.
No raw-record copy is stored in ext; bounded MODELID and MODEL.CHECKSUM keys remain allowed for
c0129. Body ids and read/bodies.py remain unchanged.

Known imported bodies serialize z_min == standoff and z_max == height, including negative
standoff. Malformed lengths use 0 as a retained source placeholder; reversed heights, unsupported
model type or a projection different from the mounted face are retained with a located warning,
projection_unknown and no legacy model.body-height finding. Unassociated bodies remain unmapped.

Documents written by v0.2.0 with bodies load with defaults and dump to identical bytes. Their
legacy validation remains until source reimport. The v0.2.x reader refuses new body keys.

## Measured proofs

Measured against origin/dev at 1723472755c16666a19d7b716583c9c9061248cc on 2026-10-07:
seven public PCB documents have 446 raw records, 446 associated records and 446 model bodies
before and after. Unknown bodies: 0; raw-record copies in ext: 0. All 446 changed bodies have
z_min == standoff and z_max == height. Body-height errors fall from 68 to 0. No unassociated
body occurs in these documents; the import still counts such records only as unmapped.

Four nonheavy project sets: body-height errors 52 to 0 (02: 32, 03: 7, 04: 9, 05: 4).
CLI exits before: 02/03/04/05 = 5/5/5/5; after: 5/0/5/0. Set 01 not run (heavy).
Both serial document tests passed 5 tests with 1 heavy skip. A v0.2.0-generated fixture
loads and dumps identically with defaults; its legacy negative-standoff finding remains.
The actual tag reader rejects a new key at /footprints/0/bodies/0/z_max.

Source allocation: the ids were first S-0570 (the reserved body page) and S-0605 (the API pair);
on the v0.4 integration branch both ids were already taken (c0121's S-0570, c0138's S-0605), so they
were renumbered to S-0708 (the same documentation page as c0121's S-0570, read for c0099's facts) and
S-0709, the next free ids, on 2026-10-08. Dev's multichannel S-0452 remains unchanged. The separate projection
census/inspection requirement, import cache-equivalence sentence and outward-height census
clause were cut; the outward-height definition remains.

Final rebase base: 6f6227ebf041d58e37a44bd5837e58d9ddf9803e; c0136 milestone renumbering
landed during the first proof run. Its code changes only CLI help text; the body adapter, model
and public-corpus measurements are unchanged from the measured base above.

Integration prerequisites on this base: Altium batch present; c0121 and c0126 proposals only.
Release 0.2.1, c0123, c0134, c0121/c0126 implementations and c0097 are absent; another rebase
is expected. No writer, body-id algorithm or read/bodies.py changes are included.

Review interpretation: an absent MODEL.MODELTYPE key retains the existing extruded-record
convention, needed by authored baseline tests and the proposed c0121 writer. Present unsupported
values become unknown. A missing key is not treated as an unsupported supplied model type.

## Rebase conflicts

- CHANGELOG.md: kept every dev entry and added three bold behaviour lines under Unreleased.
- docs/evidence/sources.md: kept dev's multichannel S-0452 and all its rows; appended S-0708/S-0709 without splitting the table.
- docs/evidence/matrix.md: regenerated from evidence declarations, no manual merge.
- tests/unit/backends/altium/adapter/test_codes.py: retained the closed-table guard and set dev's 36 plus one to 37.
- The second rebase for c0136 conflicted only in CHANGELOG.md, resolved with the same preservation rule.

## Final handover gates

All requested gates passed on the rebased signed commit. Each command's own exit was recorded,
with stdout/stderr in a separate external log. No full make check was run.

| command | exit | result |
|---|---|---|
| `openspec validate --all --strict` | 0 | Totals: 70 passed, 0 failed (70 items) |
| `make check-fast` | 0 | 9384 passed, 17 skipped in 251.05s (0:04:11) |
| `uv run --isolated --python 3.11 --extra dev pytest tests/unit -q -n 4 -p no:cacheprovider` | 0 | 9105 passed, 2 skipped in 425.92s (0:07:05) |
| `uv run pytest tests/corpus/test_manifest.py tests/residue -q` | 0 | 85 passed in 37.50s |
| `uv run python tools/gen_schemas.py --check` | 0 | generated output matches |
| `uv run python tools/gen_evidence_matrix.py --check` | 0 | generated output matches |
| `python3 tools/dco_check.py origin/dev..HEAD` | 0 | one signed commit checked |
| `uv run pytest tests/unit/model tests/unit/analysis/test_body_volumes.py tests/unit/backends/altium/test_body_volume_import.py tests/unit/backends/altium/test_body_projection_facts.py tests/unit/backends/altium/adapter tests/unit/cli/test_explain_cmd.py tests/unit/test_schema_drift.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py -q` | 0 | 590 passed in 23.75s |
| `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus -q -k "bod"` | 0 | 2 passed, 1087 deselected in 9.50s |
| `FENOLITE_REQUIRE=corpus FENOLITE_CENSUS_OUT=<external-file> uv run pytest tests/corpus/test_altium_documents.py -q` | 0 | 5 passed, 1 skipped in 14.91s |

The body-data measurements were repeated by the required final corpus tests: 446 PCB bodies
and one library body retained, stream byte identity preserved. Serial project exits remain
02/03/04/05 = 5/0/5/0; set 01 not run (heavy).

The final amendment adds proof notes and checked tasks only. Source and test subtree ids are
unchanged from the gated commit; OpenSpec, manifest/residue, DCO and documentation guards are
repeated after that amendment. Temporary baseline/tag checkouts are removed; the managed branch
and worktree remain for the coordinator. No push, merge or archive.
- Integration into v04 (2026-10-08): CHANGELOG entries under [Unreleased]/Added; sources renumbered S-0570→S-0708 and S-0605→S-0709 in every c0099 reference; `outward_height` (c0140) now reads `z_max` and skips bodies of unknown projection; v04's other doc and test rows kept beside c0099's.
