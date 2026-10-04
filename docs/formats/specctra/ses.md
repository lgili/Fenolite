# Specctra session file (`.ses`)

This page states, in Fenolite's own words, what the codec `fenolite.backends.specctra` (change c0023)
relies on to read the session file a router writes. The syntax is the one of `dsn.md`, with the same
rules: facts from S-0224 only, read for facts and never copied (ADR-0006); no reader's or writer's source
code read; **every row `INFERRED`** until the probe named in its last column is recorded in
`docs/evidence/routing.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A session file is one list `session` with an identifier, holding `(base_design <file>)` and then optional sections, among them `placement`, `was_is` and `routes` | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `placement` section of a session has the form of the design file's: `component` lists with `place` lists (reference, position, side, rotation). It records where the components are after the session | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `was_is` section holds one `pins` list of two pin references per pin that changed in a gate, subgate or pin swap | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `routes` section holds, in this order, a `resolution`, a `parser` list, and the output sections, among them `library_out` (padstacks) and `network_out` (nets) | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| In `network_out`, each `net` list is a net name followed by its `wire` and `via` lists, in the forms of the design file's wiring: a wire holds a shape, a via a padstack name and a position | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `resolution` of a session says how its numbers map to lengths: the numbers are database units, and a value `v` under `(resolution <unit> <n>)` is `v / n` of that unit | S-0224 | INFERRED | H-G-DSN-UNITS |
| The frame is the design file's: X then Y, with Y upwards (the inference recorded in `dsn.md`) | S-0224 | INFERRED | H-G-DSN-UNITS |
| A router leaves a wire or a via of type `protect` as it was | S-0224 | INFERRED | H-G-DSN-PROTECT |
| Freerouting writes its result to the file named with `-do` once routing has finished; its exit codes are not documented | S-0221 | INFERRED | H-G-DSN-ACCEPT |
| With one optimiser thread, the default, Freerouting 2.4.1 is meant to give the same result for the same input | S-0223 | INFERRED | H-G-DSN-REPEAT |

## What the reader does with them

- It reads `placement`, `was_is` and `routes` and reports every other list once, by its head, as
  `specctra.unknown-list`.
- It takes the resolution of the `routes` section, converts every number with `fractions.Fraction`, and
  negates Y.
- No source says whether the numbers of a session's `placement` are database units, as in `routes`, or
  the unit itself, as in a design file. Freerouting 2.4.1 writes a placement with its own
  `(resolution um 10)` and database units (probe `dsn-accept`, 2026-10-04,
  `docs/evidence/routing.md`). So the reader takes a placement that declares a resolution as
  database units, one that declares a unit as that unit, and for one that declares neither it accepts either
  reading. A `place` entry is unmoved when it gives the position the writer wrote, with the side `front`
  and the rotation 0.
- It looks a via's padstack up among the names the writer emitted; the padstacks of `library_out` are not
  used to size a via. Freerouting 2.4.1 keeps the writer's via padstack name (same probe).
- No source says whether a session repeats the protected wiring of the design file. Freerouting 2.4.1
  repeats it, unchanged and marked `protect` (probe `dsn-protect`). The reader ignores every wire and via
  equal to protected input.
