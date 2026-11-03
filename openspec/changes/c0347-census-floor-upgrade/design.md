# Capability-aware source lineage

## Non-negotiable boundaries

`READ_FLOOR` and the normal original-byte reader do not change. Classify a floor only from a checked original header's actual kind/version and `VersionStatus.TOO_OLD`; a generic FormatError, malformed input or future version is not a floor. Preserve original row IDs, manifest/input hashes, refusals and native version. No cache input or authored original is modified, and no derived CAD is committed/retained as corpus data.

The original graph is exported by the actual native CLI without asking the core to read unsupported semantics. Copy the complete declared original owner input set, retaining the source tag independent of oracle major. Call the existing c0275 `upgrader`/`KicadCli.upgrade_schematic` only on isolated copies. Each changed file needs tool/version, actual format versions and SHA-256 before/after; validate every output version and digest before reading it. CLI9's missing upgrade capability remains explicit. Companion changes and unresolved dependencies may not be silently omitted.

## Separate comparisons

1. Original bytes still refuse the core reader at its documented floor, with no writes.
2. Native-original9 and native-original10 graphs are linked only for the same checked source/context and exact commit. Compare all physical `REF-PIN` elements, complete partitions and net names, never an intersection. Value-free canonical signatures support cross-job verification.
3. Native-original10 versus native-upgraded10 must agree completely. A tool success alone is insufficient.
4. Only after that bridge, extract/lower the supported upgraded copy and compare its complete own/lowered/native graph and names. Preserve every warning/refusal and distinguish tool output bytes from original manifest bytes in the metadata.

Original status is always retained; `upgraded/equal` qualifies only the successful electrical census probe. It is not an all-level visual/BOM/source-fidelity acceptance. Drift, missing pins/names, changed originals, incomplete upgrade output or any uncompleted comparison prevents qualification.

## Explicit CI contract

Both required existing KiCad jobs remain mandatory on the exact commit. Native9 emits original-negative and native-old graph evidence; it does not claim to read CLI10-upgraded bytes. Native10 runs supplemental upgrade probes for every declared floor candidate, including tag-9 candidates otherwise incompatible with the primary tag-10 census. The primary incompatible records remain unchanged.

Ensure the required schematic/context inputs are fetched, and verify completeness independently of optional pytest resource skips. Preserve both jobs' failure artifacts. An explicit bridge verifier/gate must require the exact code/manifest/input identities and all successful required comparisons before task7.2 can close. This gate never excuses other extraction, context, naming, malformed or standalone-port failures. Missing optional CLI10 on a native9 runner is not fabricated upgrade evidence; the required native10 job supplies that proof.

## Proof order and scope

First author original-floor/refusal controls and independent native copy-upgrade controls, including changed-pin/partition/name and wrong-digest planted negatives. Then measure all five actual declared originals. Use those observations to implement only the reviewed harness/CI evidence path. Do not widen production project reading unless a separate authored reproduction and reviewed task demonstrate its need. Root owns combined fast/full exact-head CI; focused local tests only. No model/DSL/schema/runtime dependency or tolerance changes are expected.

## Workflow contract follow-up

The coordinator fast audit found three stale literal prerequisite controls after
adding the required sch fetch. Update the closed fetch-step marker and ensure
planted missing-library and heavy-exclusion mutations actually change the
current command. Add an explicit required-sch negative. Do not remove any
resource guard, narrow the corpus fetch or waive either native gate.
