## MODIFIED Requirements

### Requirement: Supplier extra and plugins
The extra `suppliers` SHALL add only `keyring`, and `fenolite.suppliers` SHALL register the plugins `digikey`, `mouser`, `nexar`, `farnell` and, once the maintainer's approved JLC documentation and terms are recorded in `docs/formats/suppliers/jlc.md` (change c0417), `jlc` under the entry-point group `fenolite.suppliers`, each implementing c0254's `pick.propose.Supplier` with `sends_data_offsite` true. HTTPS and JSON MUST use the standard library, and `import fenolite.suppliers` MUST succeed without the extra.

#### Scenario: Plugins without the extra
- **GIVEN** an environment where `keyring` cannot be imported
- **WHEN** `uv run pytest tests/unit/suppliers/test_registry.py` loads the entry points
- **THEN** the registered plugins load (the four public ones, and `jlc` once registered), and none reads credentials or creates transport until explicitly named and ready; environment lookup works without keyring

#### Scenario: JLC plugin follows its page
- **GIVEN** `docs/formats/suppliers/jlc.md` records the maintainer's approved JLC documentation and terms, each fact with a registered source and an evidence label
- **WHEN** `uv run pytest tests/unit/suppliers/test_jlc.py tests/unit/suppliers/test_policy.py -q` runs with the socket patched
- **THEN** the `jlc` plugin maps the authored fixtures of `tests/fixtures/suppliers/jlc/` into proposal rows, its `SourcePolicy` equals the page, and every right the terms do not grant keeps `ready=false`, `persist=[]` and `cache="none"`

### Requirement: Source readiness is evidence-gated
Production providers SHALL remain unavailable when current terms, persistence rights or response mapping are unverified. Credentials MUST NOT override this gate. JLC MUST remain unregistered until the maintainer's approved documentation and terms are recorded in `docs/formats/suppliers/jlc.md`; once registered it MUST pass the same gate as every other provider. Authored fixtures MUST NOT establish production permission.

#### Scenario: A key cannot enable an unverified source
- **GIVEN** credentials exist for a registered provider whose policy is unavailable
- **WHEN** a proposal explicitly names it
- **THEN** FEN-6001 names the source-review gap before credentials or transport are accessed

#### Scenario: JLC without the maintainer's documents
- **GIVEN** `docs/formats/suppliers/jlc.md` does not exist
- **WHEN** `uv run pytest tests/unit/suppliers/test_registry.py` loads the entry points
- **THEN** no `jlc` entry point, module, policy or fixture exists
