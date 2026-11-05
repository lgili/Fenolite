# c0417 design

## Context

c0267 (archived 2026-11-05) built the supplier-lookup machinery: per-user credentials from
`FENOLITE_<SOURCE>_<NAME>` and the keyring, a bounded standard-library HTTPS client, a `SourcePolicy` per
plugin equal to its documentation page, process-only caching, proposal rows and the readiness gate that
keeps a provider unavailable while its terms, persistence rights or response mapping are unverified. JLC
was cut from it by the maintainer on 2026-11-04 because it needs the maintainer's own approved API access.
Its spec states "JLC MUST remain unregistered until approved maintainer documentation and terms are
recorded".

## Blocker

Every fact the plugin needs (base URL, authentication, endpoints, parameters, response keys, rate limits,
cache and storage rights, attribution) must come from documentation and terms that the maintainer has
approved and supplied. Clean-room rules forbid guessing them, reading other clients' code or probing the
service. Task 0.1 is the maintainer's; nothing else starts before it is done.

## Decisions (when unblocked)

1. **Same machinery, no special case.** `jlc.py` reuses `credentials`, `http`, `policy`, `rows`, `cache`
   and `ratelimit` as the four public plugins do; no JLC branch is added to shared code. If the documented
   API needs something the machinery lacks (an auth flow, a paging shape), that is recorded in this design
   before code and kept generic.
2. **Policy from the page.** `SourcePolicy` values equal `docs/formats/suppliers/jlc.md`, checked by
   `test_policy.py` like the others. A right the terms do not grant stays at its closed value
   (`ready=false`, `persist=[]`, `cache="none"`).
3. **Authored fixtures.** Fake responses follow the documented shape with fictional parts, prices and
   `example.invalid` links, each with a sidecar naming its source and the authored line; never a captured
   live response.
4. **Credentials.** Named in the page from the documentation (`FENOLITE_JLC_<NAME>`), read only from the
   environment and the keyring service `fenolite.suppliers.jlc`, redacted everywhere as in c0267.

## Risks

- The approved access may never be supplied; the change then stays proposed and is not archived.
- The terms may forbid any persistence or automated lookup; the plugin is then registered with
  `ready=false` and the page records why, or the change is withdrawn by the maintainer.
