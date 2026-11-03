# Bounded private input proposal — review required

## Measured facts

Source is public RoyalBlue54L-Feather at declared library pin97acc80c223d75520c03fc44cab63cd9a3202c42,
with exact source board535dbe212f43a8bab12b23277e176a94ac9694177258af2981c0e7b08e4b7252. The code
already compares native electrical membership and complete derived geometry without a tolerance.

COPY-ONLY probes keep the ordinary cache and strip only the already-qualified pad/via teardrops:

- All425 raw pad pose/size/layer keys match. Thirteen footprint angles -90→270 are independently
  noncausal:289 regions/hash a562fa7965020cc8dfd270a007b7dcf1da04d716c994b7ffeb8a8fb81278ad12
  and every exact region remain unchanged.
- UUID bijections by class change only filled_polygon, never an outline or region count: pad8,
  via9, track10 changed rings; all-class12. Ordinary zone, footprint and non-electrical UUID controls
  are negatives, with all289 regions exact. Native tool and all unchanged input hashes are retained.
- Reversing all943 original track nodes changes one junction outcome despite identical node/UUID
  multisets:289 regions/hash0574dd909d730fa062f9b187537b9011f2be2bc89d8414ca694230f86a7c740a,
  matching the independently observed later source pass. Repeated refill is not an acceptance rule.
- All183 via and943 track object features (including exact net partitions and every non-ID native
  child) are one-to-one equal, and their UUIDs all differ. Pads have428 objects with measured
  pinfunction313/pintype383 losses plus coarse-key multiplicities. These are visible defects or
  unresolved preservation boundaries, not permission to ignore annotations.

Artifacts are external under the overnight-native packet: probe-royal-fp-angle-copy-v2,
probe-royal-uuid-classes, royal-uuid-geometry-diffs, probe-royal-track-order-copy and
royal-identity-feature-audit. Failed setup attempts remain separate from completed measurements.
No third-party board payload enters core.

## Proposed preconditions

This applies only to the existing explicit common-native pad/via derived-cache proof, never pure
comparison or normal build/write/export. Original bytes/digests, unmodified native observations and
all existing model levels remain authoritative records.

Before any private rewrite:

1. Require identical supported class/config/rule context, complete numbered-pad partitions and
   all existing model/electrical/geometry checks. Unsupported or unjudged context cannot become an
   assumed default. Keep literal null distinctions and resource/read-set contracts.
2. Enumerate every pad/via/track/arc, with full parent reference/placement/layer context, exact
   geometry, physical fields and net partition. A coarse location/number match is insufficient.
   Compare all native editable children, including unknown fields and pinfunction/pintype; no
   annotation field may be stripped to obtain a match. Investigate preserving those existing typed
   Pin values in output first, or independently establish a different reviewed contract.
3. Build a complete object bijection/multiset correspondence. Refuse missing/extra objects,
   collisions, changed physical/annotation fields or unresolved duplicate signatures. Never zip a
   set, choose the first candidate or use an original UUID to resolve an otherwise ambiguous match.
   Interchangeable multiplicity may be supported only after a separate authored/native proof that
   every field/reference remains exchangeable, not merely because counts agree.
4. Validate the complete ID-reference closure. Unknown references, one source ID ambiguously
   referencing multiple objects, group membership ambiguity or unsupported links refuse. Original
   duplicate native pad IDs are distinct object-scoped facts, not silently deduplicated objects.

## Proposed private transformation

Derive collision-checked UUIDs from verified semantic object keys (not source UUID/order), then assign
identical UUIDs to the paired electrical objects in both temporary input copies. Rebind only fully
verified known references. Order the matched electrical items identically by those same complete
keys; retain every other object/field/order. Preserve full multiplicities and the exact geometry,
net names, physical fields, project/rules and NORMAL filled_polygon/fill_segments. Do not remove,
seed, repair or import normal fills and do not alter the original files or stored generated outputs.

The native command runs once per prepared side, on the same actual supported tool/config. Compare
every exact outline and filled vertex/multiplicity and all previous checks. If different cache state,
unhandled annotations or any other cause still produces different geometry, report the complete
failure; do not iterate until equal, intersect regions, drop rings, increase a tolerance, relabel the
original raw cache equal or convert an unsupported context into a successful result.

Receipts must state that these are verified-identity private inputs, with original/prepared/output
hashes, a complete correspondence hash, all object counts/references, untouched normal-fill hashes,
actual native version and all findings. This is not a raw-native-byte equivalence claim. Any public
reply delta requires its existing result owner/schema/guide update and root review; no new public
format ID, DSL method, canonical field, dependencies or default writer byte change is intended.

## Required independent controls before runtime

- Original authored matching pad/via/track/junction inputs with deliberately different UUIDs/order;
  actual native before failure and paired identity/order after truth, all pins/partitions/vertices.
- UUID-only versus order-only positives and unaffected zone/fp/graphic negative controls.
- Changed geometry, layer, drill, width, net, pad metadata, netclass/rules, resource input, unknown
  child/reference and missing/extra object negatives. Refuse before a native run/output claim.
- Duplicate physical signatures, duplicate source IDs, shared references and group membership:
  strict ambiguity negatives; no undocumented interchangeable-multiplicity shortcut.
- Counter native cases proving ordinary caches and every untouched editable field remain byte/
  structure exact. A normal-cache-dependent mismatch must remain a mismatch after identity work.
- Existing no-opt-in writer/canonical/CLI bytes and all old explicit negative controls unchanged.
- Fresh production Royal after rule-context fixes, both original and generated source input hashes,
  exact first-run complete native output, plus another public board and authored neighbors.

## Separate unresolved pad preservation diagnosis

pcb.Reader.pins already stores board pinfunction/pintype in existing Component.Pin.name/etype and
keeps unknown pintype text in the existing backend extension. local_footprint deliberately removes
BOARD_PAD_HEADS(net,pinfunction,pintype); current board placement/writing reattaches net but no
pinfunction/pintype writer was found. A possible actual preservation fix is to reattach checked
Component.Pin metadata through the existing pin-pad map at the PCB writer boundary. That needs
independent symbol/PCB conflict, map ambiguity, duplicate pad, unknown type and default byte-impact
proof before approval. It may be a separate spec; no new DSL/model field or opaque carrier is
assumed by this packet, and no preservation implementation is approved here.

## Exact import-only annotation carrier addendum — review requested

Inspection and an authored existing-path probe establish a narrower alternative to Pin reattachment.
The existing native pad slots in FootprintDef retain pinfunction and pintype verbatim, including
absence and explicit empty strings. read_footprint, write_footprint and placed_tree carry these
children without consulting Component.Pin. Board format documentation already classifies them
as retained native children. The importer loses them earlier, when local_footprint removes the
board circuit children before its existing prepare callback. Generic library extraction should
continue to remove circuit annotations as its documented default.

Proposed first implementation is ONLY import vendor preparation. Capture original raw footprint
nodes by their validated Reference, and capture each physical pad's ordered child sequence.
The existing local transform preserves pad order, number, kind, shape and UUID. In its import-only
prepare callback, require equal cardinality and equal complete ordered native pad identity tuples
(including duplicate occurrence positions) before restoring the exact original pinfunction/pintype
children to the corresponding physical pad. This is provenance through a known order-preserving
transform, not matching different boards by first pad number or choosing among duplicate candidates.
Reject missing/extra/reordered/rebound identities before import output; do not repair a mismatch.
Preserve the relative order and multiplicity of annotations, reject malformed annotation shapes
instead of guessing, and retain all absence/empty-string distinctions. Do not restore net children.

Run the restored node through the existing library_footprint preparation and existing full native
variant signature. Different annotation values or presence must create distinct explicit footprint
definitions/variants; ordinary identical definitions remain shared. Existing footprint_definition
selection already binds that exact native definition to the generated component. No new DSL/API
argument, model field, schema, fallback Pin metadata, writer behavior or generic derive_library
default is required. Native pad slots are reused for their existing documented purpose, with no
new arbitrary extension carrier. Existing normal builds without such imported annotations retain
their bytes. Imported outputs with actual annotations intentionally change and require exact
source/output proof; ordinary import fixtures must not be blindly re-goldened.

Required first focused iteration: independent authored pads with duplicate numbers and different
annotations, explicit empty versus absent, explicit passive versus absent, unknown pintype text,
two same-geometry physical pads, bottom/rotated placement and variant-sharing boundaries; before
proof shows current loss. After proof compares every physical pad annotation/presence and all
physical/net fields. Planted changed order/cardinality/identity/malformed children refuse rather
than selecting a candidate. Actual native9/10 board loads and native10 save preserve the complete
values where supported. A fresh Royal import must prove all428 physical pads' exact annotation
sequences, while its unresolved L7 result remains visible. Identity/order implementation still
needs its own0.2 review and independent controls after this preservation iteration.

## Numeric-netcode diagnostic addendum (no production normalization)

After the common-ID COPY remained unequal, coordinator approved a separate authored structural/native investigation. Numeric declaration and reference roles must be recognized by structural occurrence, never interned Atom identity. Explicit NO_NET0 remains0. Numeric code bijection must use complete physical electrical partitions, not name spelling (Royal raw source slash names and generated stored escapes differ). Names/classes/rules are never renamed. Missing/duplicate/conflicting declaration, unresolved reference, ambiguous partition or affected unknown/outside/JSON reference refuses. Coordinates/enums/pad numbers can only be exempted through explicit known nonreference structural roles with authored proof; do not globally exempt equal integers. Start with complete authored code/reference controls and native baseline, table-order-only and renumber-only cases. Return measured results to coordinator BEFORE a Royal COPY transformation. Original35/0ordinary caches, editable state and opaque content stay intact. No normalizer, equality waiver or production qualification is authorized.


### Bounded numeric-role inventory (test-only)

The coordinator-approved inventory is not an eligibility certificate. Full structural paths, closed field shapes/types and independent format/native facts are required per descriptor. Numeric heads in the layer table use a separate declared namespace; unknown object fields are never admitted by a familiar child name. Every project key is inventoried, including zero/false, with literal-key/array-index distinctions. Unknown reference/configuration paths block any future renumbering.

The S-1299 measured silkscreen cache descriptor applies only to direct gr_text on F/B.SilkS with an explicit font face and one cache whose text/angle match its owner, and only ordered polygon→pts→xy pairs with at least three vertices per polygon. Vertices remain exact rational values in their original order: there is no ring repair, sort or geometry mutation. This is not a copper-cache exemption or proof of typography. Direct footprint zone_connect admits only unique wire integers0..3; the authored SMD control makes no general through-hole behavior claim. These descriptors and all reference helpers live exclusively under tests. Production comparison and acceptance are unchanged.

The separate S-1299 erc.pin_map descriptor is exactly12×12 wire integer cells0..2 under the documented project ERC key. It is a pin-TYPE conflict matrix, not a board numeric-netcode map. Enum3, malformed arrays, bool/string/null/fraction cells and all unclassified sibling keys remain blockers. The native witness links this key to the passive/passive pair only; it does not qualify every matrix relationship.


### Proposed single-variable project-pattern diagnostic (review pending)

The complete read-only project comparison found only an absent/null class field, two added exact class patterns and schematic sheet identity metadata; every numeric/boolean and all board settings stayed exact. Task0.5 proposes one external source-original PCB case changing only the netclass_patterns JSON value. Compute the candidate project in memory first, pin its hash and the exact unchanged prefix/suffix, and retain the whole original PCB byte-for-byte, including35ordinary and263derived cache regions. The original source baseline has289fresh native regions; that observation is a comparison reference, not an expected result imposed on the candidate. Use the same native version, basename and original declared companion set; one case only after coordinator approval. The exact public third-party pattern strings and diff stay external, not core. No runtime normalizer, cache manipulation, renumbering or acceptance change is proposed.


## Approved private native-project context correction

Coordinator review on 2026-11-03 approves the concrete private sibling architecture in
`carrier-review.md`. A closed version-1 `native/project.context.json` binds its exact project bytes,
original declared source digests, target, complete numbered physical net partitions, native spellings,
class values/membership and the whole version-neutral lowered model BEFORE restoring native spelling.
Only an existing `Net.ext["kicad"]` stored payload is restored on a copy. IDs, logical names and all
other model fields remain unchanged. The c0359 guard/capture observes that same restored model.

The carrier is issued only when an unchanged native project would otherwise lose its exact native
name/assignment/pattern representation; ordinary imports with identical representation keep their
existing editable path. It is never selected by preserve_minimums. A required but unqualified context
refuses. There is no new public DSL/model/ext/FEN surface. The original project is read-only; the
private artifact and its literal stdlib digest guard travel with emitted Python. The consumer reads
only the fixed sibling of the explicitly declared project, includes it in the reviewed read-set,
and never opens/fetches/discovers source PCB inputs from the provenance rows.

Closed decoding reuses the existing 16 MiB context bound, portable paths and supported targets,
rejects unknown/duplicate/missing keys, malformed types, collisions and incomplete partitions.
Model/name/class/physical changes or stale project/target refuse rather than silently retaining an
immutable native representation. Scoped immutable target/owner state has no global cache and refuses
nested capture/build scopes. Qualified backend policy verifies exact project digest and complete
class values/membership before retaining original assignments/patterns. Ordinary synthesis and
unqualified writers retain their existing path. No comparator, tolerance, native cache eligibility,
source geometry or acceptance baseline is changed. The coordinator owns subsequent native review,
combined fast, exact-head CI and shared CHANGELOG integration.

The coordinator additionally approved relocating the existing native physical binding helpers into
`backends/kicad/native_net_binding.py` with unchanged API reexports, after independent authored parity
controls. This avoids a forbidden lens→API/checks dependency. The backend traversal retains exactly the
old empty NO_NET label, missing-component reference `""`, duplicate/conflicting terminals and duplicate
net-name behavior; the carrier's stricter completeness check is separate. No comparator or proof gate
is weakened by this refactor.


### Approved activation repair after fast14

The two authored shared-sheet rebuild failures arose because raw Default/unclassed names alone
activated an immutable capsule although the source assignments(null) and exact GND/VIN Power
patterns matched the ordinary DSL projection. The existing rebuild merges native readback
metadata/outline representation and legitimately changes286canonical fields. No fingerprint field
may be ignored/normalized, no guard moved and no baseline refreshed to accept those changes.

Coordinator approved the narrower predicate before production: compare exact assignment/pattern
presence and values against the existing writer using ordinary DSL stored spellings in a local
model copy, with unchanged IDs/names/classes/members and no source mutation. Nonempty or malformed
legacy assignment shapes always require the capsule; any literal array/order/presence change
requires it too. Missing/null/empty forms are not normalized. Preserved native-only rules plus raw
name drift remain mandatory via a private source fact, with the same bounded c0359 selector profile.
An ordinary raw Default name with no affected native project/rule context stays on the established
editable path. Genuine context restore/model/output/target/class/member/stale guards remain exact.
No immutable-rebuild lifecycle extension is claimed; a genuinely changed final model still refuses.
