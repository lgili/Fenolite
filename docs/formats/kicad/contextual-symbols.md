# Local symbol cache metadata

Sources: S-0367, the schematic format's library-symbol section; S-0058, the
declared demo schematic/project inputs; S-0020, native
`kicad-cli` through a subprocess. No third-party CAD, parser code or library
payload is committed. The accepted implementation contract is
[c0327](../../../openspec/changes/c0327-contextual-symbol-definitions/design.md);
the permanent file contract is [symbol-contexts](../../symbol-contexts.md).

| Observation | Source | Scope |
|---|---|---|
| VME's same native IDs have distinct full property nodes in 2, 11 and 5 sheets; all other native AST nodes match after removing only those varying property nodes | S-0058 | INFERRED contextual rule; source/hash-bound structural observation |
| Native 9.0.2 loads/exports the real owner with 36 reachable sheets, 6811 pins and 1800 net groups | S-0058, S-0020 | ORACLE-VERIFIED(kicad-cli), actual 9.0.2 load/export only |
| The original authored split-child witness keeps native IDs and equal partitions while the old global table refuses | S-0020 | Historical local 9.0.2 witness |
| Current owned controls preserve four full contextual definitions, equal 8-pin/5-group source/lowered/native partitions, all component fields/flags, four native BOM rows and all nine fidelity levels | S-0020 | Supplemental actual 9.0.2 proof; required 9.0.9/10.0.6 CI remains open |

Legacy `(power)` means global (S-0043), while target 10 also uses `(power global)`
(S-0049; see `libraries.md`). The standalone library reader projects the former
into the latter; the schematic reader retains its literal embedded node.
Context assets use the schematic reader to preserve the full original AST.
Only comparison against a resolved library projection accepts these two global
spellings; local power and every other non-property difference still refuse.
Written-cache checks include the original node. This does not rewrite caches
or establish a new native application claim.

The source differences are complete property nodes, not corrupt electrical or
body data. Values, presentation and unknown fields must remain local. Neither
projected property equality nor unchanged connectivity justifies dropping a
snapshot. Core-default, pin, body, flag and wrong-binding negatives remain part
of the implemented closed boundary. A required hash-bound context now preserves
property-only snapshots; all material/default guards remain closed.

Exact L10 `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`, run `41421198968`,
KiCad 9 job `125196886139`, reports 41 failures: 36 owner-context definition
refusals and five reader-floor refusals. This change addresses only the first
group's metadata-preserving support. It does not change the floor, suppress
findings or establish a passing exact-head CI job.

Naming remains independent: the six owners have equal partitions with 25 raw
slash spellings, 117 missing parent-bus name candidates and one unresolved
local/hierarchical election. Authored vector/group/overbar controls reproduce
the parent-bus naming issue. All raw differences stay recorded; no guessed
election or comparison normalization is implemented here.
