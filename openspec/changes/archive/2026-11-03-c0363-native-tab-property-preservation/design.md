# Exact bounded native value ownership

Existing c0358 ownership retains LF-native values in FootprintDef properties and formatting slots while omitting them from printable Part.properties. Extend only the native-value validation predicate to permit the exact U+0009 codepoint in addition to U+000A after actual authored native proof. Do not replace tabs by spaces, change values/names, normalize geometry/formatting or add carrier fields. The underlying model already stores strings.

Validate a printable nonempty trimmed unreserved unique name, exact property shape and every other existing constraint. TAB in a name, CR/NUL/other controls, duplicate or malformed properties, unsupported fonts/layers/size/anchors and unknown forms remain failures. Mixed LF+TAB is allowed only after measured proof; public Part.properties continues refusing both controls. Distinct native values retain distinct variants; identical native payloads may share only through existing signatures. Value tampering must be detected by an independent exact raw/native value assertion; pose tampering must remain visible to the existing strict pose operators.

Before implementation, build Fenolite-authored source originals with explicit TAB values, both9/10, hidden/visible styles and sides. Compare exact native field values and every existing strict modeled operator through the native model writer; independently export official native SVG and compare all geometry/attributes, retaining metadata differences separately. Run actual production dry import to establish RED/no writes. The model-writer probe is representation evidence only, not a working importer. After approval, require complete import→reviewed confirmation→fresh build→strict1–8/S native proofs, flags/style mapping, all refusal controls, variants and unchanged75complete default plans. No GUI or user configuration changes.

## Measured representation proof, not importer success

S-1301 records16authored TAB+LF cases across9/10, both sides, hidden/visible and style/rotation mappings. The native model writer preserves all16PCBs byte-exact, full typed field dataclasses and derived FootprintDef values exact. Four actual native9.0.9/10.0.6 comparisons pass fullL8/S and independently preserve all SVG XML except root filename/date title metadata, which remains in raw artifacts. Production import still refuses all16before a plan and2authored retention regression tests remain RED.

Existing L1–7 does not compare Component.properties values. Exact independent native-value/rawproperty assertions are therefore mandatory for positive and TAB→space tamper controls, in addition to existing operators; no comparer changes or false L7 value-detection claim. The model-writer representation probe does not replace required full production import/build/native proof after runtime approval. No native GUI-save or quality claim is made.

The existing LF-native vendor helper does not itself validate every presentation constraint. Preserve that LF behavior. For TAB-bearing source values, the actual emission orchestrator explicitly runs the existing complete measured field-request validation before vendorization (discarding generated requests); no TAB request or nonprintable Part.properties declaration is emitted. The native vendor helper remains an internal retention helper, not a standalone all-context acceptance claim.

The supported native TAB context is explicitly KiCad input; another source backend with a TAB-bearing property refuses rather than inheriting an unmeasured conversion claim.

## Implemented local proof

The bounded path is implemented and full production/native controls now pass separately in implementation-proof.json. Historical native-proposal-proof.json remains unchanged as pre-implementation evidence. Only the prior native TAB refusal is reclassified; existing LF and all other control/public-DSL refusals remain. Required complete CI on the exact final commit is still pending.

## Native proof collection correction

Complete import/build levels8/S proofs require an actual KiCad executable. Move the existing eight authored mirror/TAB proof cases to `tests/kicad/board/test_import_native_properties.py`, marked `needs_kicad`; leave pure controls in unit. Both native jobs collect all eight. The four writer10 parameters use the existing `kicad_min_major(10)` capability marker: native9 executes four writer9 cases and reports four unsupported writer10 skips, while native10 executes all eight. Do not count those skips as passes. Assertions, source targets, exact values, native operators and all validation/CI requirements remain unchanged. Shared authored source helpers are reused; no public API, runtime or baseline change.
