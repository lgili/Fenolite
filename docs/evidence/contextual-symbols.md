# Contextual native symbols: focused replay

The [count/hash records](contextual-symbols.json) retain the failed original
replay and the complete current VME owner replay. They contain input IDs/digests,
context/instance hashes, counts, timings, warnings and unmodified partition/name
outcomes. No third-party CAD or raw symbol/property payload is committed.
Historical c0276 artifacts remain unchanged.

| Clean producer | Actual tool | Scope | Outcome |
|---|---|---|---|
| `217387a4` | 9.0.2 | One registered VME owner | 1 failed / 62.65 s: strict adapter KeyError after duplicated relative-module frame |
| `7584b394` | 9.0.2 | Same owner, all 36 reachable sheets | 1 failed / 127.60 s: complete native emission preserved; own resolver partition differs |

The frame witness reproduced the first error with two owned nested pages in
one code module. Encoding the equal child frame as an empty relative module
preserves both complete part paths without a repeated prefix. No pin/path
normalization or report exception was added.

The current replay preserves **460 complete contextual definitions**, 863 drawn
symbols, 743 power symbols and all 6811 native pins. The actual written native
AST checks pass. Native KiCad on the original and written hierarchies agrees
exactly: **1800 groups, zero partition differences and zero name differences**.
This independently proves that the metadata-aware lowering retains the
complete owner, rather than dropping the conflicting snapshots.

The own resolver still differs on both the original and lowered sheets: 1700
groups versus 1800 native groups, with 36 only-own / 136 only-native groups.
All 6811 pins remain present on both sides. The 418 raw name differences and
warnings (2501 unknown bus members, 1079 dangling items, four unconnected-name
warnings) remain visible. No accepted difference, loss flag, baseline update,
pin intersection or name normalization is used.

Only the owner's literal row was executed after the metadata change; the 35
other row parameters selecting the same owner were not executed. Task 2.2
remains open because the strict comparison fails. The existing reader-floor
cases and other owners were not remeasured or reclassified. Required native
9.0.9/10.0.6 CI, c0276 task 7.2 and the exact combined whole gate remain open.

Owned supplemental tests on actual 9.0.2 separately compare every native
component field/flag, four BOM rows, all nine fidelity levels and complete
property nodes; two tests passed in 7.34 s. They do not establish either
required CI job or native Altium application acceptance.

## All native-10 owner contexts — 2026-11-02

On clean signed de6c6f2f, the literal 36 row parameters owned by VME row 106
pass on KiCad 10.0.6: 36 passed in 1130.36 s, with unchanged source and HEAD.
Every report checks its declared source digests and all 73 instances / 36
sheet definitions / 460 contextual definitions. All 6811 pins and 1800 groups
match for extracted code, lowered code and native original/written comparison.
The separately owned orphan row 092 is outside this owner selection.

Own and lowered name election still differs on 486 of 967 compared named
groups. Native original/written names match all 1800 groups. Existing 2501
unknown-bus-member, 1079 dangling and four unconnected-name warnings remain.
The JSON observation retains the exact owner report and digests for every
row report; the complete raw reports and actual command/exit receipt remain
external. Earlier failed observations are preserved, with no new acceptance,
reader-floor waiver, native-9 inference or exact-head CI promotion.
