# ADR-0002: KiCad file backend: Fenolite's own readers and writers, `kicad-cli` as the oracle

## Status
Accepted (2026-10-01)

## Context
KiCad is the first backend. Its files are text S-expressions with a public, partial description
(S-0001, S-0021) and a date-stamped format version per kind (S-0030). KiCad rejects unknown tokens at
the top level of a board and in its main items (`H-K-TOK-STRICT`), so a reader that drops or invents a
child breaks the file, and a board holds far more than the neutral model represents. KiCad 9.0 and
10.0 differ in their headers, layer numbering and net references (`H-K-TOK-NETNAME`). KiCad's own
programs are GPL software: they may be run, never imported (ADR-0004). `kicad-cli` writes next to the
files it opens (S-0020).

## Decision
1. **Fenolite reads and writes KiCad files with its own code.** No KiCad library is imported and no
   KiCad source code is read; format facts come from public pages and from observed `kicad-cli`
   behaviour (`docs/formats/kicad/`).
2. **Slots, opaque by default.** Every typed node keeps an ordered slot list: a child is modelled
   (re-emitted from the model), projected (an opaque slot whose value is also copied into the model)
   or opaque (kept verbatim with the minimum format version it needs). A field is modelled only when a
   named consumer needs it. A rebuild writes opaque children back in place.
3. **Versions.** Fenolite reads boards and footprints of KiCad 8.0 and newer, and writes for KiCad
   9.0 and 10.0. KiCad 8.0 files are read-only. A file newer than every known version is read but
   cannot be edited. Writing for an older major than the input's (downgrade) is refused (`FEN-7002`).
4. **`kicad-cli` is an oracle, run only as a subprocess through the package runner**
   (`fenolite.backends.kicad.cli.KicadCli`), which copies the inputs to a fresh temporary folder,
   runs with an isolated environment and returns the files it produced. The caller's files are only
   read.
5. **Pad frame.** Footprint instances keep the stored position and rotation on both sides. Pad
   positions are footprint-local and stored as KiCad stores them, so the absolute position is
   `instance.position + R(instance.rotation)·pad.position` with no further mirror; pad rotations are
   relative to the footprint, converted by one function pair in `pcb.py`.

## Alternatives
- **Importing KiCad's Python bindings or a GPL parser**: forbidden by ADR-0004, and the bindings
  are removed in KiCad 11.
- **Driving a live KiCad through its IPC API as the core**: needs a running GUI in 9.0 and 10.0;
  kept for a later optional backend.
- **A complete typed model of every KiCad token**: years of work and constant churn with each KiCad
  release; slots keep what is not modelled without understanding it.
- **Reading in place with `kicad-cli`** (letting it write next to the user's files): races with
  other runs and overwrites the user's local state.

## Consequences
- Same-version read and rebuild are exact (tree-equal), which `CORPUS-VERIFIED` evidence checks over
  public boards.
- What Fenolite does not model can be kept, but not edited; editing a projected value needs its own
  reconciliation rule.
- Every KiCad major needs an update of the version constants and the token inventory.
- Tests that need KiCad run `kicad-cli` 9.0 and 10.0 in pinned containers.

## Evidence
- S-0001, S-0021 (board and common syntax), S-0030 (format versions), S-0020 and S-0022 (observed
  `kicad-cli` behaviour and commands).
- `H-K-TOK-STRICT`, `H-K-TOK-NETNAME`, `H-G-BOTTOM-PLACE`, `H-G-ROT-DIR` (KICAD-VERIFIED);
  `H-K-PCB-READ` (the lossless board read, `docs/hypotheses.md`).
- `docs/formats/kicad/board.md`, `docs/formats/kicad/versions.md`.
