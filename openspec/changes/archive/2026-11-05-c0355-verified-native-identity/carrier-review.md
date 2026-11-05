# Stage2 review: native spelling carrier and authored controls

Root2026-11-03 approved only the narrow criterion: an unchanged imported native project preserves names/assignments/patterns under a complete physical bijection; author controls/private design are allowed before runtime. No preserve_minimums repurposing, convenient public/model/ext field, heuristic rewrite or native/CAD execution was authorized.

## Actual controls

The external authored suite test_authored_native_carrier_boundary.py (external controls, no core fixture) gives1RED/10PASS1.23s. It uses only Fenolite's authored two_sheet board fixture and neutral names/classes. The real API import→reviewedconfirm→freshbuild rawslash case fails at the final native spelling assertion: source /AUTH/P becomes {slash}AUTH{slash}P. The already-stored {slash} source case passes. No Royal coordinate, name, payload or native process is used.

Passing controls cover scalar and list legacy assignments, missing class with an explicit finding and no assumed class, actual changed class retaining explicit update, model-native raw/stored spelling, unchanged model ID under an existing stored extension, stored-name collision refusal, exact raw native physical binding and changed physical membership refusal. The initial test-only assumption that every KiCad10 PCB has a root net table was corrected to the existing native_net helper; its failed setup log remains external and is not called a product RED.

Proof receipt and hashes: controls-receipt.json under the external packet. No task is ticked by this checkpoint.

## Existing carrier inventory

| Existing object | What it actually carries | Boundary |
|---|---|---|
| model.Net.ext[kicad].payload[stored] | Exact stored spelling, already read by pcb.stored_net_name | Sufficient within a validated model; not emitted by current DSL |
| model.Net reader-derived identity | Raw hierarchy name convention | Must not rewrite IDs to manufacture that convention |
| api._native_rules.bindings/raw_bindings | Complete numbered physical terminal partitions and exact native spellings from original PCB bytes | Available while original source is traced, not persisted by emitted DSL |
| importer.Source.design/board_text | Complete original model and PCB bytes | Import-time only |
| importer.emit.design.emit Net(textname) | Logical name string | Raw and stored source spelling collapse to the same constructor |
| dsl.part.Net and dsl.convert._design_model | DSL name/netclass/group and new model net identity/members | No existing native spelling input; generated Net loses original bag |
| declared native/project.kicad_pro | Bound original project bytes, names/assignments/patterns | Does not contain original numbered physical PCB partitions |
| native_rule_context.Binding/certificate | Whole emitted-model/output fingerprints plus source-input digests | Does not carry source spelling/physical rows; Royal's inspected input has no DRU or rules-context certificate anyway |

Conclusion: an existing MODEL carrier is sufficient, but no existing PERSISTENT carrier has been found that can restore it safely after portable emitted-script rebuild under the approved full-bijection criterion. Merely matching logical strings to project assignment keys is not that proof. No source PCB may be discovered ambiently, fetched at build time, guessed from project names, or trusted from a mutable PROVENANCE wrapper.

## Private design, before any runtime approval

The verified in-memory binding would have to be derived while importer.Source still owns both original PCB bytes and the complete source design. Use existing bindings/raw_bindings for the exact physical group identity, reject missing/extra/ambiguous/duplicate groups, retain native spelling literally, and compare complete class values/membership. Restoring a qualified spelling changes only the existing Net.kicad.stored bag in a copy, never any net/component ID, logical name, source bytes, pad membership, class, geometry or canonical schema. Any already-present unknown/conflicting stored entry refuses.

That binding must then survive emitted-script move/rebuild. It is NOT safe to add a private attribute to DSLNet, parse comments, match slash strings heuristically, reuse preserve_minimums, weaken source binding, or smuggle native data through an unrelated opaque/worksheet/rule field. Under the present no-new-carrier restriction the propagation is incomplete and MUST NOT be implemented.

The smallest concrete architecture candidate to return to root, if existing carriers remain insufficient, is a separately approved closed revision of the ALREADY EXISTING private project-context certificate protocol, binding native spelling plus complete physical partitions and source hashes to the exact imported-model fingerprint and native project. This would not add a public DSL/model/ext key, but DOES add private serialized protocol fields and source inputs: it is outside this stage's approval and must be explicitly reviewed before a schema/design/runtime change. No new protocol or file has been created here. If root declines that expansion, retain the current refusal/failure instead of guessing a spelling.

## Exact function path for an approved future propagation

1. importer.source.read_kicad and importer.emit.design.emit: inspect the existing Source and retain exact source binding during emission/self-check; ordinary Net(name) output remains unchanged unless an explicitly approved private carrier can recover its native spelling.
2. cli.cmd_import._build/_native_rule_context and lens.native_rule_context.capture_import/certificate: bind the source physical/name rows at the actual imported-model capture, if root approves extending that private protocol. Do not write a certificate when any source/class/physical check fails.
3. lens.project_template.read_project_template and lens.native_rule_context.read_binding: validate exact declared digest/read-set/target and closed carrier/version; no ambient sibling discovery. Royal currently has only project.kicad_pro, so existing rules-only assumptions cannot silently qualify it.
4. lens.build.build_design path before native PCB/project output and native_rule_context.before_write: after whole-model/bijection checks, apply only the existing Net.kicad.stored payload to a model copy; preserve original IDs and every other field. Missing/changed membership or classes invalidates the preservation path.
5. backends.kicad.pro.update_project/_net_class_names/_exact_entries: preserve the source native assignments/patterns representation ONLY through an approved qualified binding, never based on preserve_minimums or arbitrary equality of logical names. A real class/net change retains existing explicit update/refusal. pcb.stored_net_name and synthesized new-project behavior remain existing controls.
6. cmd_verify_source._compare and _derived_cache.prove remain UNCHANGED acceptance controls. Raw teardrop-count difference is already removed only after exact complete native regenerated geometry proves equal; no new comparator change is needed.

No default writer/synthesis/public surface byte change is authorized. Future schema or result-owner impact needs root review. No native authored case or Royal rerun may precede carrier review; the earlier pattern-only native receipt demonstrates causal sensitivity, not a complete pair fix.


## Concrete private carrier option for root review (NOT implemented)

No new public API is necessary. Reinspection of component/module emitters found source native IDs used
only in import-time owner dictionaries for emitted groups/verbatim references; they do not persist a
complete net spelling/physical partition map. Existing rules-context fingerprints validate an emitted
model, not the source names, and Royal has no such rules sidecar. Therefore neither can be silently
repurposed as the missing carrier.

The smallest explicit candidate is one PRIVATE import-owned sibling of the ALREADY DECLARED native
project: `native/project.context.json`. This is a proposed new private artifact, not a field in the
canonical model or a new DSL argument. It must be separately approved before creation/runtime work.
Do not add a fake `.kicad_dru` or overload the rules-only certificate for a rules-free project.

Proposed closed version1 data (bounded, reject unknown/duplicate keys):

```text
version: 1
target: 9 or10
project: {path: "project.kicad_pro", sha256: original_project_sha}
source_inputs: existing {path,sha256,kind} source rows
baseline: {encoding: existing version-neutral model fingerprint encoding, sha256: imported_model_sha}
nets: [
  {logical: logical_name, stored: EXACT_original_native_name,
   physical: [[ref, numbered_pad], ...], class: exact_class_name_or_null}
]
```

Rows come ONLY from the original source PCB and its checked model through existing complete physical
bindings. Require unique native/logical names, unique physical rows, exact coverage and a true bijection;
no net name/slash/UUID heuristic. Class parameters remain in the pinned original project plus the whole
model fingerprint; their values and complete memberships must agree before preservation. A board with
unbound/ambiguous/unknown electrical terminals is not eligible; do not silently discard them to fit rows.
The bounds should reuse existing16MiB private-context input limit and current source cardinality
limits, not add a larger resource allowance.

Producer→consumer path:

1. `importer.emit.design.emit` retains Source/design/PCB binding during actual import self-check.
   A private import capture analogous to c0359 observes the emitted model BEFORE the native writer.
   The spelling map is verified there and applied only to existing `Net.ext['kicad'].payload['stored']`
   on a copied model; no IDs or canonical logical names change. No class/context proof is issued if
   any physical/model/supported-rule check is unresolved.
2. `cli.cmd_import` writes the closed artifact only after the import self-check validates that exact
   candidate. Emitted Python keeps `Net(name)` public statements and adds only a leading-private
   stdlib digest guard, as c0359 already emits a private Path guard for required native files:
   read this exact relative context file and require its SHA256 equal a generated literal.
   It does NOT assign private attributes to DSLNet, parse comments or import a new public DSL helper.
   Path/hash failures must be mapped/tested through the existing authored-input failure contract.
3. `lens.project_template.read_project_template` recognizes only that one exact sibling of the
   explicitly declared native project, returns a PRIVATE optional binding and includes it in the
   existing reviewed input read-set. This fixed private sibling lookup follows the existing rules
   context pattern, not arbitrary ambient PCB discovery. The embedded project SHA and emitted
   digest guard bind it to the declared project and script. No source fetch or source PCB discovery.
4. A private build scope/before-write hook receives that binding. It first compares the existing
   version-neutral whole imported-model fingerprint AND a fresh complete physical/class bijection.
   On success only existing Net.kicad.stored payload values are populated. On a changed model,
   name/class/membership, missing/extra row, collision, unknown key or stale digest, REFUSE the
   preservation path with existing FEN-3004; confirmation read-set changes remain FEN-4002.
   Do not silently fall back to new names while retaining an immutable native context.
5. `pro.update_project` gets the qualified PRIVATE context policy, separate from preserve_minimums.
   For that exact unchanged imported context preserve original assignments/patterns representation
   literally; all ordinary synthesis and unqualified edited-model paths keep existing behavior.
   No blind skip_exact_entries, no source project overwrite, no known/unknown field stripping.
6. Native rules and this spelling binding must compose: keep c0359's complete model/output guards.
   A carrier that needs an altered native rule program, writer option or unsupported rule context
   refuses instead of inventing a default. The comparator/cache eligibility/global certificates stay
   exactly as today. The derived-count difference remains conditional on exact native geometry.

Exact code impact if root approves this new PRIVATE artifact:

| File | Bounded role |
| --- | --- |
| importer.emit.design / cli.cmd_import | source graph→verified rows, capture source binding, emit required private digest guard and artifact |
| new private lens/native_project_context.py (or existing project_template module if small enough) | closed decoder, bounded rows, collision/completeness/class checks, immutable private build scope; reuse fingerprint and bindings rather than a second format/model |
| lens/project_template.py | optional private binding and explicit read-set, no public DSL change |
| cli/cmd_build.py / lens/build.py | thread private context through existing build scope; restore existing model Net.kicad.stored only after all guards and before PCB/project writes |
| backends/kicad/pro.py | qualified private preserve policy, ordinary patterns/defaults unchanged |
| dsl.part.Net / dsl.convert | NO new public constructor argument, exported name, model field or convenience extension; remain unchanged if after-conversion private hook suffices |
| docs/cli-contract.md, docs/import.md, agent/skill/references/equivalent-s.md and its existing import reference | document that imported private context files travel with code and edits require reviewed re-import; teach no new command/DSL/FEN code |
| tests/unit/importer + project_template/native_context controls | actual moved-folder import/rebuild raw/stored spellings, scalar/list assignments, missing classes, model edits, physical rows, missing/symlink/tampered/oversize/duplicate/unknown context, stale confirmation, target changes, custom-rules composition |
| existing test_pro_native_names/pro_synth and complete default guards | preserve all ordinary authored/generated behavior and defaults; do not refresh baselines to accommodate unexpected effects |

The PRIVATE optional binding and serialized rows above are NEW implementation details requiring root
approval; this review does not pretend they already exist. If root requires absolutely no new private
artifact or protocol fields, this option is not allowed and no currently identified existing carrier
can satisfy the criterion. That is an architecture decision, not a reason to weaken preservation.

No native authored case, Royal replay or runtime change was executed during stage2. Future first native
case must be authored and reviewed, then one original Royal proof per side without iterative reruns.

Fingerprint/order invariant for a future approved implementation: compare the new spelling binding's
unchanged DSL-model baseline BEFORE populating stored-name bags; then perform the qualified model copy.
The existing rules-context capture and its later guard must observe the same restored complete model
on both original capture and portable rebuild, so no metadata restoration is exempted from c0359.
Use project/owner/target-scoped immutable state with the existing no-nested-capture policy, never a
process-global map or cache. Changing any source context/target/canonical field refuses until reviewed.
