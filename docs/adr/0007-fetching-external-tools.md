# ADR-0007: Fetching external tools on request

## Status
Accepted (2026-10-05; confirmed on 2026-10-07)

## Context
Fenolite runs some tools it does not contain. The first is Freerouting (S-0220), a GPL-3.0 autorouter that
ADR-0006 keeps behind a process boundary. Decision 3 of ADR-0006 also said that Fenolite never downloads
it, so a user had to open the release page (S-0223), download a 64 MB jar, check its digest and set an
environment variable before the first route.

An agent cannot do that. Measured on 2026-10-05 from a folder outside the repository, `fenolite route
--router freerouting` exited 6 with a message that named the variable and not the place the jar comes
from, and the built-in `direct` router then closed three nets with four shorts. A machine with Fenolite
and KiCad had no router that closes a real board.

The forces:

- A download nobody asked for is a request to a third party, and it may install software under a licence
  the user did not choose.
- Bytes from the network must be the bytes that were measured: `docs/evidence/routing.md` records the size
  and the SHA-256 of the jar of the gate.
- ADR-0004 allows copyleft software only as a separate program.
- The mutation protocol already asks for `--confirm` before any write.

The maintainer decided on 2026-10-05 that Fenolite may download the jar when it is asked to, with
`--confirm`, and confirmed it on 2026-10-07 after the review of the v0.4 proposals. The decision is held
by `docs/roadmap.md`, Open decisions, row 36.

## Decision
1. **One command downloads.** Fenolite downloads an external tool only inside `fenolite fetch NAME`. No
   other command opens a network connection for a tool: not `route`, not `doctor`, not `capabilities`,
   not `build`.
2. **Only with `--confirm`.** `--dry-run`, and a run with neither flag, show the plan (the file, its size,
   its SHA-256, its address and its licence) and make no request.
3. **Only a table row.** The address is that of a row of `src/fenolite/cli/data/fetch.toml`. A public row
   names a source registered in `docs/evidence/sources.md` and an `https` address, and holds the size and
   the SHA-256 recorded on an evidence page. A new row needs a decision of its own.
4. **Only matching bytes are written.** What was obtained, from the network or from `--from FILE`, is
   compared with the row's size and SHA-256 before any file is written. A difference is `FEN-3006`, and
   nothing is written.
5. **Nothing is bundled and nothing is imported.** The wheel and the repository hold no byte of a fetched
   tool, and Fenolite imports nothing from one. A tool under a copyleft licence stays a separate program,
   run as a subprocess (ADR-0004).
6. **Nothing is sent.** The request carries the address and one `User-Agent` header with Fenolite's
   version: no parameter, no identifier and no design data. A redirect is followed only to an `https`
   address, TLS verification stays on, and there is no retry and no update check.
7. **The file goes to the user's tools folder** (`fenolite.core.tools`): `FENOLITE_TOOLS_DIR`, else the
   cache folder of the platform. It is outside the project, shown in the plan and reported by `doctor`.

## Alternatives
- **Bundling the jar in the wheel.** Rejected: it would distribute GPL-3.0 software with an Apache-2.0
  package (ADR-0004), and add 64 MB to every install, also for users who never route.
- **A download on the first `route`.** Rejected: it is a request nobody asked for, hidden inside a routing
  run, and it would install GPL software without the user having seen its licence. `route --fetch` and
  `doctor --fix` were rejected for the same reason; `doctor` is read-only.
- **Leaving the install manual.** Rejected: it was the state before this record. An agent cannot open a
  release page or set a variable that survives its next command, so the only router that closes a real
  board stayed out of reach. The manual way remains: `FENOLITE_FREEROUTING_JAR`, `--router-path`, and
  `fetch --from FILE`.
- **Letting the command download by itself when it sees `--confirm`.** Rejected: commands never write and
  never decide whether to write. The dispatcher calls the source of a deferred write, so the consistency
  suite covers `fetch` like any other mutating command.

## Consequences
- `fenolite fetch freerouting --confirm` takes a machine with Java 25 from "no usable router" to
  "Freerouting available"; every message about a missing jar names that command.
- The plugin looks in the tools folder after `--router-path` and `FENOLITE_FREEROUTING_JAR`, and does not
  hash the file on each run: `fetch` checked it, and the user owns the folder.
- The command installs no Java; `result.needs` says so before anything is downloaded.
- The CI `routing` job installs the jar with this command, so each run proves the address, the size and the
  digest (`H-G-FETCH-PIN`).
- If the publisher moves or removes the asset, the command fails with `FEN-6003` and names `--from FILE`;
  the digest still decides.
- ADR-0006 keeps its text and gains one dated line under its Decision 3.
- A second tool in the table needs its own decision and its own evidence row.

## Evidence
S-0223 (the release page of the tag `v2.4.1`, which lists the asset and its digest); S-0220 (the licence);
`docs/evidence/routing.md` (the size and the SHA-256 of the jar of the gate); ADR-0004 and ADR-0006;
hypothesis `H-G-FETCH-PIN`; tests `tests/unit/cli/test_fetch_cmd.py` (no request without `--confirm`, size
and digest checked before any write, the table against the evidence page), `tests/unit/core/test_tools.py`
and `tests/unit/routing/test_freerouting.py`.
