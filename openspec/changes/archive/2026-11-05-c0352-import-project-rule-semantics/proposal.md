# c0352: preserve imported project floors and Default class semantics

## Why

The importer skips every native `Default` netclass and synthesizes unconditional custom rules from native project hard floors. Native classes and project floors have different precedence from a custom rule. On KiCad 9.0.9/10.0.6 the measured H-K-PRO-MIN-RULE-2 contract says custom overrides may govern below floors. Thus importing a source with Default clearance 0.15 mm, floor 0.0762 mm, and a 0.2032 mm named class can change the effective native clearance, even when canonical comparisons overlook the source of the setting.

## What

Use the existing explicit, portable, digest-bound KiCad project template carrier (c0351) for native hard floors. Emit the existing netclass DSL for the actual Default class. Emit DSL custom minimum/rule calls only for actual native DRU rules. Add narrow native-context level6 comparison for the existing five supported project floor keys with traced inputs, supported version guards and exact numeric values. Preserve existing authored DSL minimum semantics and every existing comparison/difference.

Pure Design-vs-Design has no canonical hard-floor property and does not gain or claim one. No model/schema persisted field is proposed. Royal is a diagnostic source, not a success criterion waived by this proposal: all its regenerated fill geometry must still compare exactly before success is claimed.
