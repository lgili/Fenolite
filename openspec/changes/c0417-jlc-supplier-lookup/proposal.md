# c0417: JLC supplier lookup (follow-up of c0267)

## Why

c0267 added supplier lookup for four public suppliers (DigiKey, Mouser, Nexar, Farnell). On 2026-11-04 the
maintainer cut JLC from that change: a JLC plugin needs the maintainer's own approved API access,
documentation and terms, which no agent session can supply or infer. c0267's design ("Found on 2026-11-04")
proposed this follow-up; the coordinator assigned it the id c0417 on 2026-11-05.

**This change is blocked.** No task after 0.1 may start until the maintainer supplies the approved JLC API
documentation and terms. Until then JLC stays unregistered, as c0267's spec and the four supplier pages say.

## What

After the maintainer's documents are recorded:

- `docs/formats/suppliers/jlc.md`: endpoints, parameters, response keys, limits, cache rule and attribution,
  each with its source (registered in `docs/evidence/sources.md`) and an evidence label.
- `fenolite.suppliers.jlc` on the existing c0267 machinery (credentials, bounded stdlib HTTP, policy,
  proposal rows), with its `SourcePolicy`, authored fake responses under `tests/fixtures/suppliers/jlc/`
  and the entry point `jlc` in the group `fenolite.suppliers`.
- Gated exactly like the four public suppliers: `ready=false`, `persist=[]` and `cache="none"` until the
  recorded terms establish each right; a key never enables it.
- The four supplier pages and the agent guide's `supplier-lookup` page stop saying "JLC remains
  unregistered" and name the gate instead.

## Impact

- Code: none in this proposal. When unblocked: one module, one entry point, fixtures and tests; no new
  runtime dependency (the `suppliers` extra still adds only `keyring`).
- No change to the build path, the CLI contract or the `supplier.*` codes.
- Source ids are taken from the coordinator's range when task 0.2 starts.
