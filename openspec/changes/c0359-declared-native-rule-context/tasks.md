## 1. Resolve the contract before runtime
- [x] 1.1 Root reviews exact ownership, closed receipt, full-model and actual-output binding, explicit metadata exception, two-build bootstrap and bounded original-to-first-output qualification before implementation.
- [x] 1.2 Authored RED reproduces the missing native-only rule/order/comments; the same reproduction passes after the fix.

## 2. Focused preservation and independent controls
- [x] 2.1 Preserve native-only programs/read-sets; reject unsupported contexts and changes before staging, without changing public API/model or the import layer table. Fully modelled programs remain editable.
- [x] 2.2 Authored positive/negative, actual native9/10 canary, generated-input deletion and stale-plan controls pass. Whole-model/default-state controls, tool-version/native-byte stability, complete75 build maps and no-DRU import byte maps pass. Real import_python freshness and its three specific byte pins pass without regenerating snapshots.

## 3. Public candidate and final gate
- [x] 3.1 Run the final exact implementation against the immutable author six-input OpenAir source: strict supported1–8/S equal with no accepts; preserve exact DRU bytes and all notices/unjudged scope, source and authoritative item unchanged. Do not claim original cache equality or native DRC result equivalence.
- [ ] 3.2 Required full CI on the exact final integration commit passes before archival. Library item/catalog audit/review/publication remain separately owned gates.

Local proof2026-11-03: RED1failure; capsule/all-field controls22pass; bounded profile/partition controls30pass; import/rule/context neighbours39pass; original Altium/project/rule/guide neighbours114pass; context neighbours73pass; layer/evidence guards87pass. Native9.0.9 and10.0.6 authored source/generated file-loading canaries pass, plus the actual public17-rule file loads on small authored benches on both tools. The external v7 working-tree public run passed allnine supported levels with zero differences/accepts while retaining27 routing notices and L6 unjudged custom rules. Its raw DRU4546bytes SHAfc6858c9efdc5ae0e12e01e4475e4c186a7f7b6c4fe99698d4379ec2808985ea is unchanged. Final exact-checkpoint replay and CI remain pending; no authoritative library payload was replaced.

Exact checkpoint proof2026-11-03: source938f9c1bbf272eb9ece86c439a7688c227cc005e, immutable six-input author bundle, actual10.0.6 strictallnine supported levels equal, zero differences/accepts. RawDRU and allsource/iteminputhashes unchanged;27notices and L6unjudged retained. Receipt bound in public-source-proof.json. Task3.2CI and librarypublication gates remain open.

CI follow-up2026-11-03: Windows job125888606275 reached both successful builds but the test searched an absolute plan path using a POSIX-only separator. Compare native path components instead and require all three native payload types before hash equality; metadata must still change. Focused module proof: 11passed in5.84s on the local candidate; Windows CI is still required and task3.2 remains open.
