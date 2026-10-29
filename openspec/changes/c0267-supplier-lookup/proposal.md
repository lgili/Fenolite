## Why

c0254 defines `fenolite pick PATH --propose QUERY --supplier NAME --allow-offsite` and the entry-point
group `fenolite.suppliers`, but ships no plugin. A user who holds an account with a distributor still
copies part numbers by hand. The research (`docs/research/component-library.md`, sections 1 and 4.8)
found that every distributor API allows **one user looking up parts with their own key**, and forbids, in
different words, what a shared library would need: building a database, caching beyond a limit (none at
Farnell, 24 h at Nexar, the session at DigiKey and Mouser), shared keys, and use without attribution. So
supplier data can **propose**, per user, and never become Fenolite data.

## What Changes

- **Optional extra `fenolite[suppliers]`** (adds `keyring` only; HTTP and JSON use the standard library)
  and the package `fenolite.suppliers` with plugins for DigiKey, Mouser, Nexar and Farnell, registered in
  the `fenolite.suppliers` group. A JLC plugin follows once its approved API documentation is read.
- **The user's own credentials**, from environment variables or the system keyring, never from project
  files, never logged, never shipped; no Fenolite key exists.
- **Policy as data in each plugin**: attribution text, terms source, cache scope and age (never above the
  terms), rate limits, what is sent offsite, and which fields may be written to the project.
- **Proposals only.** Answers become `UNVERIFIED` rows under `devices/proposed/` through c0254's plan and
  confirm. A row keeps the identity (manufacturer, MPN, datasheet link) and the provenance with the
  attribution; parameters come from a Fenolite grammar (c0263) when one decodes the MPN, else the user
  fills them from the datasheet. Price, stock and lifecycle are shown in the reply and written nowhere.
- **Never in the build path.** `build`, `check` and every command but `pick --propose` never import the
  package; `--confirm --plan` writes the reviewed bytes without a second request.
- **Offline tests** with fake responses authored for Fenolite after the public API documentation, under
  a patched socket.

## Capabilities

### New Capabilities

- `supplier-lookup`: credentials, source policies, cache, rate limits, the mapping to proposal rows,
  attribution, isolation from the build, and the offline test harness.

### Modified Capabilities

- `cli-contract`: ADDED "Supplier plugins in capabilities", "Supplier errors".
- `package-layering`: MODIFIED "Allowed import edges" (new package `suppliers` → `pick`, `catalog`, `model`).

## Dependencies

c0254 (the proposal hook, `--allow-offsite`, `UNVERIFIED` rows, `pick.row-unverified`). Uses c0263 (decode
an MPN into parameters) when it is present. Independent of c0259–c0266 otherwise.

## Non-goals

- No shared cache, corpus or database from answers; no bulk download; no scraping of any site.
- No ordering, cart or price comparison; no automatic pick of a proposed row.
- No supplier call in CI; no Fenolite-owned API key.

## Evidence level required

- Plugins: `UNVERIFIED` replies (third-party data); every proposed row `UNVERIFIED`.
- Request building, response mapping, cache and rate limiting: `INFERRED`, proven by offline tests over
  authored fake responses (`H-G-SUPPLIER-OFFLINE`).
- Each plugin's policy (endpoints, limits, attribution, cache): recorded in
  `docs/formats/suppliers/<name>.md` from registered public pages, label `INFERRED` or `UNVERIFIED`.

## Impact

- New: `src/fenolite/suppliers/` (`base.py`, `policy.py`, `credentials.py`, `http.py`, `cache.py`,
  `ratelimit.py`, `rows.py`, `digikey.py`, `mouser.py`, `nexar.py`, `farnell.py`), `tests/unit/suppliers/`,
  `tests/fixtures/suppliers/`, `docs/formats/suppliers/`, `docs/suppliers.md`.
- Changed: `pyproject.toml` (extra `suppliers`, entry points), the extras invariant test, the import-graph
  test, `cmd_capabilities.py`, `cli/errors.py` (`FEN-6004`), `explain.toml`, guide pages `parts` and
  `recovery`.
- Size: about 5 design-days.
