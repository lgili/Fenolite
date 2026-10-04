# ADR-0006: Specctra files from a restricted reference, and Freerouting behind a process boundary

## Status
Proposed

## Context
Plan decision D11 gives v0.1 two routers. The second is Freerouting (S-0220), which reads a Specctra
design file (DSN) and writes a session file (SES). `kicad-cli` 9.0 and 10.0 export no design file and
import no session (S-0022, S-0037); KiCad offers both only in its editor (S-0225). Fenolite therefore
writes the design file and reads the session itself, from the neutral model.

Two things need a decision before any code relies on them.

- **The format's only full description is restricted.** The SPECCTRA Design Language Reference, version
  10.0 of May 2000 (S-0224), is all rights reserved. Its notice forbids copying, modifying, publishing
  and distributing it, allows one printed copy for personal, informational and non-commercial use, and
  calls the information proprietary to its publisher's customers. A copy is published in the Freerouting
  repository. `LEGAL.md` (block A) lets Fenolite learn a fact from public documentation when the fact is
  recorded with its source; it never lets Fenolite copy text, tables, grammar productions or examples.
- **Freerouting is GPL-3.0 and sends usage data by default.** ADR-0004 allows copyleft software only
  behind a process boundary. Its settings page (S-0222) shows analytics enabled unless they are turned
  off, and it offers a hosted API.

## Decision
1. **Facts only, in Fenolite's own words.** Facts about DSN and SES are taken from S-0224 and written in
   Fenolite's own words in `docs/formats/specctra/dsn.md` and `ses.md`, each row with its source, a label
   and a hypothesis. No sentence, table, grammar production or example of the reference is copied into the
   repository. The reference is neither vendored, nor committed, nor linked from the package, and it is
   read on line without keeping a copy.
2. **Each fact is also checked against a tool.** A fact the code relies on stays `INFERRED` until a probe
   confirms it: Freerouting accepts the written file and routes it (`H-G-DSN-ACCEPT`, `H-G-DSN-UNITS`,
   `H-G-DSN-PROTECT`), and KiCad's DRC judges the routed board (`H-G-DSN-ROUTE`). No fact is labelled above
   the probe that proves it.
3. **Freerouting only as a program.** It is run as a subprocess (or in a container) on files in a temporary
   folder. Fenolite never imports it, vendors it, downloads it or reads its source code for format
   knowledge. Its documentation pages (S-0220 to S-0223, S-0226) are read for its arguments and settings.
4. **No data leaves the machine by default.** The plugin always passes the flag that disables analytics,
   and reports `sends_data_offsite: true` until a run with the network disabled is recorded
   (`H-G-DSN-OFFLINE`). There is no cloud mode in v0.1.
5. **Fallback.** If facts may not be taken from S-0224, the codec is rebuilt black-box: the subset is
   learned from design files that KiCad's editor exports for boards authored for Fenolite (recorded as
   observations under S-0020) and from what Freerouting accepts. Every row citing S-0224 is then removed or
   re-sourced, and the code written from it is reviewed against the new rows.

## Alternatives
- **Black-box only, from the start.** Rejected as the default: it costs about three more days, and the
  result is the same subset learned more slowly. It stays as the fallback.
- **Converting through KiCad.** Rejected: `kicad-cli` has no Specctra export or session import (S-0022,
  S-0037), and driving the editor is outside the file backend (ADR-0002).
- **Reading Freerouting's reader or KiCad's exporter for the grammar.** Rejected: both are GPL sources, and
  `LEGAL.md` (P2) forbids transcribing parser code; reading them for format knowledge is excluded here even
  as facts, so that the codec's provenance stays one document and two tools.
- **Importing Freerouting through a Java bridge, or bundling its jar.** Rejected by ADR-0004.
- **The hosted Freerouting API.** Rejected for v0.1: it sends the design off the machine.
- **No second router.** Possible: the change is cuttable (roadmap, Open decisions, row 2). The maintainer
  kept it in v0.1 on 2026-10-03.

## Consequences
- `fenolite.backends.specctra` is a codec package, not a registered backend, with its own `PROVENANCE.md`.
- The fact pages are short and cover only what the writer emits and the reader reads.
- A user installs Java and the Freerouting jar themselves; `doctor` reports both.
- If the publisher of S-0224 objected, the fallback applies and the fact pages change; the code's interface
  does not.
- This ADR becomes `Accepted` only in the maintainer's own commit, with a `LEGAL-ANNEX.md` row; the change
  that writes it (c0023) is not archived before that. The maintainer accepted the decision in the roadmap
  on 2026-10-03 (Open decisions, row 5); the status line here waits for that commit.

## Evidence
S-0220 to S-0223 and S-0226 (Freerouting: licence, arguments, settings, release, image); S-0224 (the
reference and its notice); S-0225 (KiCad's editor exports and imports these files); S-0022 and S-0037
(`kicad-cli` does not); ADR-0003 and ADR-0004; hypotheses `H-G-DSN-ACCEPT`, `H-G-DSN-UNITS`,
`H-G-DSN-PROTECT`, `H-G-DSN-ROUTE`, `H-G-DSN-REPEAT` and `H-G-DSN-OFFLINE`; tests
`tests/unit/backends/specctra/` and `tests/routing/test_freerouting_gate.py`.
