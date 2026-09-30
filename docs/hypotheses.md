# Hypothesis register

Every claim that is not yet verified is a hypothesis with a test or an acceptance-kit request that
settles it. Ids: `H-K-*` (KiCad backend), `H-A-*` (second backend), `H-G-*` (general/model).

| id | backend | statement | level | test or kit request | criterion | result | date |
|---|---|---|---|---|---|---|---|
| H-K-UNIT | kicad | Board and footprint lengths are written in mm with at most 6 decimals, i.e. exact integer nanometres (S-0001) | INFERRED | read every length of the fetched KiCad demo boards at tags 9.0.x and 10.0.x | 100 % of values parse exactly | pending | 2026-09-30 |
| H-A-UNIT | altium | Binary PCB lengths are integers in 1/10 000 mil (S-0002) | INFERRED | decode positions of public corpus boards and compare with `kicad-cli pcb import altium` output | positions agree within 1.27 nm | pending | 2026-09-30 |
| H-G-ANGLE | general | Rotations used by both targets are exactly representable in integer microdegrees | INFERRED | read all rotations in the corpus; non-representable values are kept in `ext` and counted | 0 non-representable values, or each one recorded | pending | 2026-09-30 |

Change c0001 (repository bootstrap) added no hypothesis. The first rows (`H-K-UNIT`, `H-A-UNIT`,
`H-G-ANGLE`) came with the design model (change c0004) and stay `INFERRED` until corpus files confirm them.

Change c0002 (CLI contract) adds no hypothesis: `capabilities` and `_echo` read no design format; their
evidence label is `UNVERIFIED` because no external oracle applies to them.

Change c0003 (IP hygiene) adds no hypothesis: it is policy and tooling, verified by its own tests.
