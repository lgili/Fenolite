# Design

## Existing representations

`Rule` represents an overriding custom rule; it has no hard-floor origin/type. `NetClass` represents class values. KiCad project import clamps effective class values to project floors, but does not preserve independent floor identity in canonical Design. c0351 already declares a native `.kicad_pro` with a digest and includes it in the build/verification read set. Use this declared carrier; never encode hidden Rule name/provenance/ext conventions or invent source rule rows.

## Import

For supported KiCad source projects, emit Default through the existing `design.rules.netclass` API, including exact modeled fields and class membership. Preserve existing supported named-class handling. Preserve hard floors in declared project bytes and do not turn them into unconditional DRU rules. Actual source DRU rules retain their existing selectors, order, severity and minimum/rule DSL path. A source carrying both Pro floors and DRU overrides must retain both, with unchanged measured precedence. Board-only sources and authored minimum() calls keep their current semantics.

## Level6 native context

Path-based API/CLI comparison and verify-source may additionally judge only the existing supported5 floor keys: min_clearance, min_track_width, min_via_diameter, min_through_hole_diameter, min_copper_edge_clearance. Compare supported-version effective values exactly with existing rule-field differences, including a changed floor below every class. Do not erase canonical differences. Missing/ambiguous/malformed native context must not fabricate zero/template success. Explicit Pro selection and unambiguous adjacent project resolution follow c0340. Every read native project file is already bound through source_files and plan dependencies; new consumption must preserve original paths and stale-plan rejection.

Pure Design-vs-Design remains scoped to represented canonical fields; no floor is silently injected. Document this boundary explicitly. No model field, runtime dependency or new public DSL name is added.

## Proofs and limits

Before implementation, census canonical Rules/NetClasses and actual Pro/DRU effective data on original ReadSide, emitted code and rebuilt native project, with exact source/tool hashes. Author native small cases for Default .15/.2 and hardfloor .0762/class .2032; observe actual DRC rows by UUID and include a canary, no exit-code-only judgment. Include source Pro+DRU precedence cases and preserve H-K-PRO-MIN-RULE-2. Plant native floor tampering below all classes and show level6 failure with same/fresh paths; plan stale guards remain required. Existing authored defaults and minimum DSL shapes/bytes must remain exact. Royal may remain a genuine geometry failure; no regeneration loop or relaxed acceptance follows from this change.

## Option B: native netclasses and effective assignments (parent requested review)

The pre-fix census found path ReadSide has ZERO Rules and ZERO NetClasses on both Royal sides: `_with_project_curve` currently projects only curve tolerance. Thus existing path level6 never judged these native classes. Importer Source does apply the project; emitted canonical code has five invented overrides and only USB_DIFF, skipping Default. Record these distinct views explicitly; never claim existing global rule coverage.

Option B adds native-context comparison of the seven existing modeled class length fields and effective class assignments, in addition to the five supported floor keys. Reuse `read_project`/`apply_project` in an ephemeral clone, not new persisted fields. Bind raw PCB net names to canonical nets by exact numbered-pad partitions before applying native patterns/assignments; native escaped spellings and wildcard semantics must be resolved against original raw names, then class membership compared using verified partitions. Same-number same-net stacked pads collapse ONLY in the electrical binding, preserving all physical multiplicities. Conflicting pad nets, repeated references with nonidentical complete electrical signatures and ambiguous bindings refuse. Track-only/unbound memberships refuse instead of guessing identities.

No netclass JSON equality: compare only supported typed fields and effective assignments. Duplicate class names, inexact modeled values, unsupported multiple-class aggregation and malformed relevant assignments must not yield complete native-context equality; expose located refusal/unjudged scope. Unknown unrelated project keys remain outside coverage. Context consumption rechecks traced bytes/digests and supported versions; no ambient undisclosed Pro or stale read set. Differences reuse existing level6 `rule-field`, `netclass-field`, `netclass-members`, `netclass-missing` with native context locations, while all existing canonical differences remain.

Controls required before promotion: source Default .15→.2 changes native DRC and native-context level6; planted floor .0762→.08 below both classes fails independently; switching effective class assignment fails; native raw slash escaping and exact partition rename passes only with unchanged class assignment and L2; conflicting or ambiguous bindings, malformed/duplicate/inexact class fields, unsupported version and changed read sets do not pass. Pure Design and ordinary authored default bytes remain unchanged. This option awaits parent review before runtime implementation.

## Approved ownership keyword before runtime

Parent approved `design.kicad_project(path, *, sha256, preserve_minimums: bool = False)` after identifying c0351's explicit managed-wins floor control. Default False preserves existing authored minimum()/lower_minimums planning and output exactly. Import emits True so the five exact native source Pro floors remain owned by the digest-bound carrier while actual DRU rules remain independently represented/emitted and govern as measured. The flag is exact bool, belongs only to DSL request/build context, and adds no canonical field/model inventory row. Every planner branch (copper, generated, roles) and final writer must use the same floor ownership. True requires an explicit declared project input; no ambient source lookup. Native authored control preserves source Pro edge floor0.01 plus real DRU0.7, while defaultFalse keeps the existing test's Pro0.7 output. Guide/surface describe this ONE added optional argument; no user review or sheet approval is inferred.

## Existing derived-cache wire necessary support (separate iteration)

The c0340 producer already emits derived_cache in level7 summary and FidelityProof, but closed descriptors omit it. Declare the exact existing root/config/status/side/crossing fields as closed typed records, with optional fields only for actual partial-failure/final-success branches. Keep producer, acceptance and native calls unchanged.

Only unjudged_project_rule_deltas a/b use CanonicalNativeJson: the exact existing `_json_key` wire canonicalization is null/bool/integer/string or recursive arrays; JSON numbers are rational integer triples and object mappings become arrays of key/value arrays. A dedicated wire marker and explicit SchemaBuilder recursive definition enforce this finite canonical shape without global Any, floats/nonfinite values, objects or unsupported Python objects. This is uninterpreted metadata, never judged geometry/rule equality. Mirror schemas and source-bound producer-shape controls must reject unknown root/side/field/type and verify recursive leaves. Mocked producer-shape controls are explicitly not native evidence.

## Complete electrical signature for repeated physical references

Fresh Tiny source exposes repeated connected STITCH footprints, not merely logos. Parent approved replacing blanket physical-reference uniqueness in the electrical binding with an exact complete terminal signature: each numbered connected (ref,padnumber) has exactly one native net, and every repeated physical footprint of that ref has the SAME complete connected numbered-terminal→net mapping. Different nets or partial/disjoint terminal decompositions refuse. Same-name physical objects without connected numbered terminals do not participate in electrical binding. No physical footprint/pad/UUID/geometry is dropped or rewritten, and existing L3/model comparisons still retain every multiplicity. Authored parallel-copy positive and conflict/decomposition negatives precede runtime; measured public source facts remain in external receipts.

## Explicit null typed-unset correction

Royal source has literal JSON null for USB_DIFF.diff_pair_via_gap. The existing public native parser represents this as None, same as absent. Parent approved accepting only exact null as represented unset and listing null/absent-both fields as unjudged, with no inferred numeric fallback/inheritance value. Null vs represented numeric remains a conservative field difference. Strings, bools, negatives and inexact numeric values still refuse. Authored parser mapping and negative controls precede the isolated guard correction.

## Exact generated project patterns use written PCB names

Complex source/importer/DSL correctly classify /12Vext as power; the generated PCB writes {slash}12Vext while generated Pro uses /12Vext and loses its class. Royal source USB classes show the same downstream mismatch. Use the existing pcb.stored_net_name mapping for generated Pro exact entries and native pattern resolution in apply_project (including planner reads). Preserve canonical names/ids/geometry. Reject collisions in actual stored names before a dict can clobber them. Update removes only writer-owned exact patterns of current logical or stored model names; arbitrary user glob/regex/template entries are not rewritten. Existing unsafe/overmatching pattern refusals remain. No numeric or class-aggregation semantics change, and no DRU selector rewrite is included. Authored red controls and actual source/raw versus generated/escaped class-sensitive DRC on native9/10 precede promotion.
