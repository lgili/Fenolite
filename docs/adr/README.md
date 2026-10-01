# Architecture Decision Records

One file per decision: `NNNN-short-slug.md`, numbered in order of creation, never renumbered.
Format (MADR-lite); every ADR MUST contain these six sections, in this order:

```markdown
# ADR-NNNN: <title>

## Status
Proposed | Accepted | Superseded by ADR-XXXX | Deprecated

## Context
What forces are at play; what problem needs a decision.

## Decision
The decision, stated so that it can be checked.

## Alternatives
Each alternative considered, and why it was not chosen.

## Consequences
What becomes easier or harder; follow-up work.

## Evidence
Public sources (ids from `docs/evidence/sources.md`), tests or hypotheses that back the decision.
```

`tests/unit/test_adrs.py` checks the sections and the status vocabulary.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-neutral-model.md) | Neutral model: small now, frozen after the second backend | Accepted |
| [0002](0002-kicad-file-backend.md) | KiCad file backend: Fenolite's own readers and writers, `kicad-cli` as the oracle | Accepted |
| [0003](0003-clean-room-and-provenance.md) | Clean-room development and provenance of format knowledge | Accepted |
| [0004](0004-licence-apache-2.0.md) | Licence: Apache-2.0; copyleft only behind a process boundary | Accepted |
