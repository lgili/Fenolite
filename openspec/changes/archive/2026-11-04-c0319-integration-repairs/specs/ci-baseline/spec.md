## ADDED Requirements

### Requirement: Declared CAC closure geometry deferral
The working-branch CI SHALL restore the maintainer-approved geometry exclusion only for pushes
whose ref is `refs/heads/codex/cac-next`. Its source-bound manifest MUST name the 27 known native
c0332 failures and their unchanged test-file digests. They SHALL be explicitly deselected and
reported as deferred, never passed. Every other selected test remains required. Main, dev and
pull-request selection MUST remain unchanged. c0332 remains open and this scoped result MUST NOT
be reported as its complete geometry validation. No runtime acceptance, assertion or budget changes.

#### Scenario: Scoped closure push
- **WHEN** codex/cac-next runs the native10 closure job with the reviewed unchanged test sources
- **THEN** only the 27 declared geometry nodeids are deselected and the summary names their deferral

#### Scenario: Full release or pull-request selection
- **WHEN** the workflow runs on main, dev or a pull request
- **THEN** the closure-only step does not set selection arguments

#### Scenario: Stale exclusion source
- **WHEN** a declared test file differs from its bound digest
- **THEN** scope preparation fails before executing the native suite
