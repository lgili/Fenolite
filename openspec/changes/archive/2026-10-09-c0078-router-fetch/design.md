## Context

- **Milestone.** v0.4, the agent track (c0077 to c0081). Written against `origin/dev` at `9aba2dff`.
- **What exists** (at `9aba2dff`).
  - `routing/plugins/specctra/freerouting.py`: the jar is the constructor's path (`--router-path`), else `FENOLITE_FREEROUTING_JAR`. `PINNED_VERSION` is `2.4.1`, and the version is learned from the jar's manifest without running it. `available()` gives the reason "set FENOLITE_FREEROUTING_JAR to the Freerouting 2.4.1 jar (Fenolite never downloads it)" (line 188). The docstring of `tests/_resources.py` (line 111) repeats "Fenolite never downloads the jar".
  - `fenolite route` turns an unavailable router into `FEN-6001` (exit 6) with the registry's hint, "run 'fenolite capabilities' to see what is missing". `capabilities` lists routers with `name`, `description`, `sends_data_offsite` and `builtin`, without their availability; `doctor` has it (`cli-contract`, "Routers in capabilities and doctor", "Freerouting in doctor").
  - ADR-0006, Decision 3: "Fenolite never imports it, vendors it, downloads it or reads its source code for format knowledge." Its consequences: "A user installs Java and the Freerouting jar themselves."
  - `docs/evidence/routing.md` records the jar of the gate: `freerouting-2.4.1.jar` from the release page of the tag `v2.4.1` (S-0223), SHA-256 `251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9`, "equal to the digest the release lists", and its size, `64 076 787 bytes`. The CI `routing` job downloads that address with `curl` and checks that digest with `sha256sum` (the step "Install pinned Freerouting jar" of `.github/workflows/ci.yml`).
  - The mutation protocol: a command returns `PlannedWrite(path, data, kind)` objects and the dispatcher lists them (`--dry-run`), refuses (exit 4) or writes them (`--confirm`). A command therefore produces its bytes before it knows whether it may write. Since c0066 (archived) a receipt also carries `id` and `undo`, and `fenolite restore` reads them; a fetched file gets both like any other write.
  - The error registry ends at `FEN-3005`, `FEN-6002` and `FEN-7003`; every code needs a table in `cli/data/explain.toml` (`tests/unit/cli/test_explain_cmd.py`).
- **The maintainer's decision.** 2026-10-05: Fenolite may download Freerouting when asked with `--confirm`. 2026-10-07, after the review of the v0.4 proposals: confirmed, `fenolite fetch freerouting` is in v0.4. No page on `dev` records it at `9aba2dff`: the row that once did was written on the proposal's branch under a number that `dev` has since given to another decision. Task 1.2 records it as a new row of "Open decisions" in `docs/roadmap.md` (the next free number, 36 at `9aba2dff`), and ADR-0007 cites that row.
- **The second backend.** Nothing here touches a build: no rule kind, no model key, no file kind. `route` works on KiCad boards only, as before.
- **Constraints.** Stdlib only (`urllib.request`, `hashlib`). No request without `--confirm`. No byte of Freerouting in the repository or in the wheel. Nothing is imported from the jar. No design data leaves the machine.

## Goals / Non-Goals

**Goals:**
- One command, safe to run by an agent, takes a machine from "no usable router" to "Freerouting available".
- The bytes installed are the bytes the gate measured: one address, one size, one digest.
- Every message about a missing jar names that command.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A general package manager. The table has one public row; a second tool needs its own decision.

## Decisions

1. **`fenolite fetch NAME [--from FILE] [--dir DIR]`** (`mutates=True`). `NAME` is a row of `cli/data/fetch.toml`.
   - Each row holds `name`, `version`, `file`, `bytes`, `sha256`, `url`, `licence`, `source` (an id of `docs/evidence/sources.md`), `env` (the variable a user may set instead) and `needs` (texts such as `Java 25 or newer`).
   - The one public row is `freerouting`: version `2.4.1`, file `freerouting-2.4.1.jar`, the address and digest of `docs/evidence/routing.md`, licence `GPL-3.0`, source `S-0223`, env `FENOLITE_FREEROUTING_JAR`.
   - The destination is `<tools folder>/<name>/<file>` (Decision 3), or `DIR/<file>` with `--dir`.
   - `result` holds `name`, `version`, `file`, `path`, `bytes`, `sha256`, `url`, `licence`, `origin` (`network` or `file`), `installed` (the destination already holds the pinned bytes), `needs` and `env`. With `--dir`, `env` tells the caller what to set, because the plugin does not look there.
   - A destination that already holds the pinned bytes plans nothing and exits 0.
   - An unknown name exits 2 with the public names in the hint.
   - Rejected: `route --fetch` (a download hidden inside a routing run); a download on the first `route` (a request nobody asked for); `doctor --fix` (`doctor` is read-only).

2. **Deferred writes.** `PlannedWrite` gains `source: Callable[[], bytes] | None`, `size: int | None` and `sha256: str | None`.
   - A write with a `source` declares its size and digest and carries no data. The plan lists the declared values.
   - With `--confirm` the dispatcher calls `source()` once, before it writes any file of the command, and compares length and digest with the declared ones. A mismatch is `FEN-3006` and nothing is written.
   - Without `--confirm` the dispatcher never calls `source()`. This is what lets `--dry-run` and the refusal of exit 4 run without a request.
   - **Order with c0120.** c0120 (v0.4, the complex board) modifies "Mutation protocol" and adds "Staged plans" and "All-or-nothing writes" in the same dispatcher. This change lands first, as the design of c0120 already says; c0120 then regenerates its deltas from the living text and resolves a deferred write inside its staged plan.
   - Rejected: letting the command read `args.confirm` and download itself. The rule "commands never write and never decide whether to write" would have an exception that the consistency suite cannot see.

3. **The tools folder.** `fenolite.core.tools.tools_dir()` returns, in this order:
   - `FENOLITE_TOOLS_DIR` when it is set (an absolute path; a relative one is refused);
   - `$XDG_CACHE_HOME/fenolite/tools` when that variable is set;
   - `~/Library/Caches/fenolite/tools` on macOS, `%LOCALAPPDATA%\fenolite\tools` on Windows, `~/.cache/fenolite/tools` elsewhere.
   - It creates nothing. `fetch --confirm` is the only writer.
   - A downloaded tool can be downloaded again, so it is a cache entry and not user data.
   - Rejected: a folder inside the project (one copy of the jar per board, and a GPL file beside the user's sources); the folder of the package (not writable in many installs).

4. **Where the plugin looks.** The jar is the constructor's path, else `FENOLITE_FREEROUTING_JAR`, else `tools_dir()/freerouting/freerouting-<PINNED_VERSION>.jar` when that file exists. The environment and the folder are read when the router is used.
   - The plugin does not hash the file on each run: `fetch` checked it, and the manifest check of the version stays.
   - `doctor` adds `source` to the entry: `argument`, `env`, `fetched`, or `null` without a jar.

5. **The request.** `cli/fetch.py::download(row)`:
   - `urllib.request.urlopen` on the row's `https` address, with the header `User-Agent: fenolite/<version>` and no other, a timeout of 60 s, and the proxies of the environment as `urllib` reads them.
   - A redirect is followed only to an `https` address.
   - It reads at most `bytes + 1` bytes and fails as soon as the size differs.
   - It sends no parameter, no identifier and no design data, and it runs no retry: `FEN-6003` is retryable and the caller decides.
   - `--from FILE` reads that file instead. The same size and digest checks apply, so a wrong file is refused.

6. **A hidden row for the suites.** The row `_selftest` names `cli/data/fetch-selftest.txt`, a text file of a few lines packaged with Fenolite, through the address `package:`. It is not listed in hints or documentation.
   - The consistency suite needs a mutating command to plan and write in an empty folder without a network (`mutation_example_args = ("_selftest", "--dir", "tools")`). The hidden command `_echo` is the precedent.
   - Unit tests of the real row replace `download` or pass `--from`.

7. **Messages.**
   - The plugin's reason without a jar: "no Freerouting jar: run 'fenolite fetch freerouting --confirm', or set FENOLITE_FREEROUTING_JAR".
   - `fenolite route` gives the hint "run 'fenolite fetch freerouting --confirm'" with `FEN-6001` when the Freerouting jar is missing, and keeps the registry's hint otherwise.
   - A missing Java keeps its own reason, which names Java 25: `fetch` does not install it, and `result.needs` says so before the download.

8. **Two error codes.**
   - `FEN-6003`, exit 6, `retryable: true`: "download failed". The message holds the address and the cause; the hint names `--from FILE`.
   - `FEN-3006`, exit 3: "fetched file does not match the pinned size or SHA-256". The message holds both digests; nothing is written.
   - Each gets a table in `cli/data/explain.toml` (`meaning`, `fix`, `see`), so `fenolite explain FEN-6003` answers.

9. **ADR-0007, "Fetching external tools on request".** Status `Accepted`, with the two dates of the maintainer's decision and the number of its row in `docs/roadmap.md` (task 1.2 comes first, so the record claims no more than `dev` shows).
   - Decision: Fenolite downloads an external tool only inside `fenolite fetch`, only with `--confirm`, only from the address of a table row whose source is registered, and only when size and digest match the row. It bundles nothing, imports nothing from the tool and makes no other request. A tool under a copyleft licence stays a separate program (ADR-0004).
   - ADR-0006 gets one dated line under Decision 3: "amended by ADR-0007: the jar may be downloaded by `fenolite fetch`".
   - `LEGAL-ANNEX.md` gets a row for the command and the ADR.

10. **CI.** The `routing` job replaces its `curl` and `sha256sum` step with `uv run fenolite fetch freerouting --dir /tmp/freerouting --confirm --json`, and keeps `FENOLITE_FREEROUTING_JAR`. Every run of that job then proves the address, the size and the digest (`H-G-FETCH-PIN`).

11. **Order with the other proposals of v0.4.**
    - "Freerouting plugin" (`routing`) is modified by c0078, c0109 and c0110, in that order. The delta of this change is the living text at `9aba2dff` with the tools folder, the reason text, the download sentence, the messages and three scenarios added; c0109 and c0110 each regenerate theirs from the living text that the change before left.
    - c0120 after this change (Decision 2).
    - c0079 and c0080 name `fetch` in the guide when this change is archived first. When c0080 is archived first, its coverage rule (every public command in a tested block, every `FEN-` code on the page `recovery`) binds this change: task 3.3.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/core/tools.py` (new) | `TOOLS_ENV`; `tools_dir() -> Path`; `tool_path(name, file) -> Path` |
| `src/fenolite/cli/fetch.py`, `cli/data/fetch.toml`, `cli/data/fetch-selftest.txt` (new) | `FetchRow`; `rows() -> Mapping[str, FetchRow]`; `public_names() -> tuple[str, ...]`; `download(row) -> bytes`; `read_file(row, path) -> bytes`; `matches(row, data) -> bool` |
| `src/fenolite/cli/cmd_fetch.py` (new) | `COMMAND` |
| `src/fenolite/cli/api.py`, `cli/main.py` (extended) | `PlannedWrite.source`, `PlannedWrite.size`, `PlannedWrite.sha256`; the dispatcher resolves deferred writes |
| `src/fenolite/cli/errors.py`, `cli/data/explain.toml` (extended) | `FEN-6003`, `FEN-3006` and their tables |
| `src/fenolite/cli/cmd__echo.py` (extended) | the hidden options `--defer` and `--defer-bad` |
| `src/fenolite/routing/plugins/specctra/freerouting.py` (extended) | the third location; `jar_source`; the new reason |
| `src/fenolite/cli/cmd_route.py`, `cmd_doctor.py` (extended) | the hint; `source` in the `freerouting` entry |
| `docs/adr/0007-fetching-external-tools.md` (new); `docs/adr/0006-…md`, `docs/adr/README.md`, `LEGAL-ANNEX.md` (extended) | the decision record |
| `docs/routing.md`, `docs/cli-contract.md` (extended) | "Install" rewritten around `fetch`; the section `fetch`; the two codes |
| `.github/workflows/ci.yml`, `tests/unit/test_ci_workflow.py` (changed) | the `routing` job installs the jar with `fetch` |
| `tests/unit/core/test_tools.py`, `tests/unit/cli/test_fetch_cmd.py` (new); `tests/unit/routing/test_freerouting.py`, `tests/unit/cli/test_doctor_cmd.py`, `tests/unit/cli/test_route_cmd.py` (extended); `tests/_resources.py` (one docstring) | hermetic |
| `docs/roadmap.md` (extended) | the row of the maintainer's decision |

## Names introduced by this change

Hypothesis `H-G-FETCH-PIN`. Error codes `FEN-3006` and `FEN-6003`. Command `fetch` with the flags `--from` and `--dir`; hidden `_echo` options `--defer` and `--defer-bad`. Environment variable `FENOLITE_TOOLS_DIR`. Result keys of `fetch`: `name`, `version`, `file`, `path`, `bytes`, `sha256`, `url`, `licence`, `origin`, `installed`, `needs`, `env`; `source` in the `freerouting` entry of `doctor`'s `result.routers`. API: `PlannedWrite.source`, `PlannedWrite.size`, `PlannedWrite.sha256`, `fenolite.core.tools` (`TOOLS_ENV`, `tools_dir`, `tool_path`), `FreeroutingRouter.jar_source`. Decision record ADR-0007. No issue code, no model field, no source id. None of these names is in the tree at `9aba2dff`.

## Sources registered by this change

None new. S-0223 (the release page of the tag `v2.4.1`) already records the asset, and `docs/evidence/routing.md` already holds its size in bytes beside its digest; a test keeps the table row equal to both (task 3.1).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-FETCH-PIN | The release asset `freerouting-2.4.1.jar` at the pinned address has the pinned size and SHA-256, and the jar that `fenolite fetch freerouting` installs is reported by the plugin as version `2.4.1` | the CI `routing` job, whose install step is `fenolite fetch freerouting --confirm`, followed by `tests/routing/test_freerouting_gate.py` | the step exits 0 and the gate passes on both targets |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| No request without `--confirm` | mechanical | `test_fetch_cmd.py`, with `urllib.request.urlopen` patched to raise |
| Size and digest checked before any write | mechanical | `test_fetch_cmd.py` |
| Tools folder per platform | mechanical | `test_tools.py` |
| The plugin finds a fetched jar | mechanical | `test_freerouting.py -k fetched` |
| The pinned asset is what the publisher serves | `H-G-FETCH-PIN`, by the `routing` job | CI |
| A route with the fetched jar | unchanged: `UNVERIFIED` until `check` | the existing gate |

## Budget (4 days)

| work | days |
|---|---|
| entry check, register, the decision row | 0.25 |
| tools folder | 0.25 |
| deferred writes in the dispatcher | 0.5 |
| the table, the request, the command | 1.0 |
| plugin location, messages, `doctor` | 0.5 |
| ADR-0007, ADR-0006 note, `LEGAL-ANNEX.md`, docs | 0.5 |
| CI job and its workflow test | 0.5 |
| closing | 0.5 |
| **total** | **4.0** |

Cut order: (1) `--dir`; (2) `source` in `doctor`. Not optional: no request without `--confirm`, the size and digest check, the tools folder as the plugin's third location, the messages, ADR-0007.

## Risks / Trade-offs

- [The publisher moves or removes the asset] → `FEN-6003` names `--from FILE`; the user downloads it another way and the digest still decides.
- [A proxy or a firewall] → `urllib` reads the usual proxy variables; `--from` covers a machine without a network.
- [A tampered download] → refused by size and digest before any write; TLS verification is the default of `urllib` and is not turned off.
- [An agent downloads GPL software the user did not want] → the command needs `--confirm`, the plan names the licence and the address, and nothing else in Fenolite downloads.
- [A hidden folder outside the project] → written only by this command, shown in the plan, reported by `doctor`, and moved with `FENOLITE_TOOLS_DIR`.
- [The cache folder is not writable] → the write fails as any write does; `--dir` names another place.

## Migration Plan

- Additive: one command, one core module, two error codes, three optional fields of `PlannedWrite`. No key of the design model and no file of a built project changes.
- A user who set `FENOLITE_FREEROUTING_JAR` or passes `--router-path` sees no change: both win over the tools folder.
- The reason text of a missing jar changes; `tests/unit/routing/test_freerouting.py` and `tests/unit/cli/test_doctor_cmd.py` follow.
- Rollback: remove the command and the third location; a fetched jar stays usable through the environment variable.

## Open Questions

- **Should the plugin hash a fetched jar on every run?** Default: no. It costs a read of the whole file per route, and the user owns the folder.
- **Should `capabilities` list what can be fetched?** Default: no; the messages and the agent guide (c0079, c0080) name the command.
- **KiCadRoutingTools through `fetch`?** Default: no; it is a checkout, a build step and an interpreter.
