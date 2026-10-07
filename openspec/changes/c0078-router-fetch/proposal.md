## Why

A machine with Fenolite and KiCad has no router that closes a real board. The built-in `direct` router joins two pads with a straight track and avoids nothing. Freerouting needs a jar that the user must download by hand, and ADR-0006 says that Fenolite never downloads it.

Measured on 2026-10-05, on `dev` at `1882644`, from a folder outside the repository: `fenolite route … --router freerouting` exits 6 with "set FENOLITE_FREEROUTING_JAR to the Freerouting 2.4.1 jar (Fenolite never downloads it)". The hint says to run `capabilities`, which lists the router and does not say that it is unavailable. Neither message says where the jar comes from. `--router direct` then routed the three nets of a three-part board with four shorts. Both texts are still in the tree at `9aba2dff` (`routing/plugins/specctra/freerouting.py`, line 188; `cli/errors.py`, line 73), and no `fetch` command exists there.

An agent cannot open a release page, check a digest and set an environment variable that survives its next command.

**The maintainer's decision.** On 2026-10-05 the maintainer decided that Fenolite may download the jar when it is asked to, with `--confirm`. On 2026-10-07, after the review of the v0.4 proposals, he confirmed it: `fenolite fetch freerouting` is in v0.4. No page on `dev` records either date yet; task 1.2 records the decision as a row of "Open decisions" in `docs/roadmap.md` before ADR-0007 is written.

## What Changes

- **`fenolite fetch NAME`**, a mutating command. `fenolite fetch freerouting --confirm` downloads the pinned release asset of Freerouting 2.4.1 from its publisher, checks its size and its SHA-256 against the values recorded in `docs/evidence/routing.md`, and writes it to the user's tools folder. `--dry-run` shows the file, its size, its digest, its address and its licence, and makes no request. `--from FILE` installs a copy the user already has; `--dir DIR` chooses another folder.
- **The tools folder.** `fenolite.core.tools.tools_dir()`: `FENOLITE_TOOLS_DIR`, else the platform's user cache folder. The Freerouting plugin looks there after the `--router-path` argument and `FENOLITE_FREEROUTING_JAR`.
- **Messages that say what to do.** The plugin's reason for a missing jar and the hint of the exit-6 error name `fenolite fetch freerouting --confirm`. `doctor` reports where the jar came from.
- **Two error codes.** `FEN-6003` (exit 6, retryable): the download failed. `FEN-3006` (exit 3): the bytes do not have the pinned size or digest; nothing is written. Each gets its table in `explain.toml`.
- **ADR-0007** records the decision and amends one sentence of ADR-0006. The CI `routing` job installs the jar with this command.

Milestone: v0.4 (the agent track). Size: 4 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `cli-contract`: ADDED "Fetch command", "Deferred writes", "Fetch error codes".
- `routing`: MODIFIED "Freerouting plugin" (the jar's third location; downloading only through `fetch`); ADDED "Tools folder", "Fetched tools decision record".

The MODIFIED delta is the living text of `routing` at `9aba2dff` with only this change applied. No open change on `dev` holds a delta of "Freerouting plugin". Two other proposals of v0.4 modify it, c0109 and c0110: the order is c0078, c0109, c0110, and each later one regenerates its delta from the living text that the one before left.

## Non-goals

- No implicit download. `route`, `doctor`, `capabilities` and `build` never make a request.
- No Java: the user installs a Java 25 runtime.
- No KiCadRoutingTools: it is a checkout with a compiled part and its own interpreter.
- No container image: `--router-path docker:<image>` stays as it is, and Fenolite pulls nothing.
- No bundling: the wheel and the repository hold no byte of Freerouting.
- No update check, no "latest" version, no mirror list.
- No hosted routing service.
- No MCP server: it stays in v0.5b.

## Evidence level required

- The pinned address, size and digest: the release page (S-0223) and `docs/evidence/routing.md`, which already holds both values; `H-G-FETCH-PIN` is settled by the CI `routing` job, which installs the jar with `fenolite fetch` on every run.
- The command, the tools folder and the error codes: mechanical, proved by hermetic tests with a file source.
- The router's own evidence does not change: a route stays `UNVERIFIED` until `check` judges it.

## Prerequisites

- `0.3.0` is released from `dev` first.
- The maintainer's decision is recorded on `dev` (task 1.2) before ADR-0007 is written with the status `Accepted`.
- Nothing of c0096, c0097 or c0099, and nothing of the other proposals of v0.4. c0066, whose receipt fields this command inherits, is archived.
- This change lands before c0120 (staged plans and all-or-nothing writes in the same dispatcher; its design orders c0078 first) and before c0109 and c0110 (the same requirement, see above).
- c0079 and c0080 name `fetch` in the agent guide only when this change is archived before them. When c0080 is archived first, task 3.3 adds the tested guide line that its coverage rule asks for.

## Impact

- New: `src/fenolite/core/tools.py`, `src/fenolite/cli/fetch.py`, `src/fenolite/cli/data/fetch.toml`, `src/fenolite/cli/data/fetch-selftest.txt`, `src/fenolite/cli/cmd_fetch.py`, `docs/adr/0007-fetching-external-tools.md`.
- Changed: `src/fenolite/cli/api.py` and `cli/main.py` (deferred writes), `cli/errors.py`, `cli/data/explain.toml` (two tables), `cli/cmd__echo.py` (two hidden options), `routing/plugins/specctra/freerouting.py`, `cli/cmd_route.py`, `cli/cmd_doctor.py`, `tests/_resources.py` (its docstring says "Fenolite never downloads the jar"), `docs/routing.md`, `docs/cli-contract.md`, `docs/roadmap.md` (the decision row), `docs/adr/0006-specctra-and-freerouting.md` (one dated note), `LEGAL-ANNEX.md`, `.github/workflows/ci.yml`.
- One network request, to the publisher's release address, and only inside `fenolite fetch … --confirm` without `--from`. No design data is sent, so `sends_data_offsite` stays `false`.
- No model key, no rule kind and no file kind: nothing changes for the KiCad or the Altium build, and 0.2.x projects are untouched.
