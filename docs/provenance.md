# Provenance rules

How Fenolite proves where its format knowledge comes from (ADR-0003, `LEGAL.md`).

## Source ids

Every public source is a row of `docs/evidence/sources.md` with an id `S-NNNN`. Format pages,
ADRs and proposals cite those ids (or the URL itself).

## `PROVENANCE.md` in every backend package

Each package `src/fenolite/backends/<name>/` contains a `PROVENANCE.md` with this table:

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| `via` node grammar | S-0007 | CC-BY-SA-4.0 (documentation) | 2026-10-02 | facts only |

`how used` is one of `facts only`, `design with attribution` (then the work is also listed in
`NOTICE`) or `oracle` (a tool run as a subprocess to compare outputs).

## Format pages cite sources

Every page under `docs/formats/` (except `README.md`) cites at least one `S-NNNN` id or URL.

## Session log

`LEGAL-ANNEX.md` gets one row per working session on `src/fenolite/backends/` or `docs/formats/`.
CI checks that every ISO week in which a commit touched those paths has at least one row dated in
that week. Content is reviewed by humans.

## Enforcement

`tests/unit/test_provenance.py` checks all three rules.
