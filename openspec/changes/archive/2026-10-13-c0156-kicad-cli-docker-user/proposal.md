## Why

On 2026-10-09 two agents running Fenolite as root with `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6@…` got no report from any `kicad-cli` command: the tool printed "Directory '/w/config' couldn't be created (error 13: Permission denied)" and `pcb drc` exited 3. `KicadCli.run` makes its run folder with `tempfile.mkdtemp` (mode 0700, owned by the caller) and `DockerCli` mounts it at `/w`, but the pinned images run as their own user `kicad` (uid 1000), who cannot write a folder of mode 0700 owned by another user. The runner worked only where the caller's uid was 1000 or where the folder's ownership is virtualised (Docker Desktop). c0153 and c0015 did not cover it: no CI job runs `DockerCli` against a real daemon (the KiCad jobs run inside the image).

## Outcome in one paragraph

**A `docker:<image>` run works for any host user.** `DockerCli` runs the container as the user that owns the run folder: `--user <uid>:<gid>` of the caller under a daemon run by root, `--user 0:0` under a rootless daemon, where container root is the caller (S-0727), and no `--user` on Windows. The container's `HOME` is `/w/.fenolite-state/home`, a folder the runner makes in the reserved state folder, because a user the image does not know gets `HOME=/`, which it cannot write. Nothing else in the command line changes, and the CI jobs, which run inside the image and use `KicadCli`, are not touched.

## What Changes

- **`backends/kicad/cli.py`**: `DOCKER_HOME`, `docker_rootless()` (one `docker info` per runner), `docker_user(rootless)`, `DockerCli.user`; `DockerCli._command` adds `--user` and `HOME` and makes the home folder.
- **Tests**: `tests/unit/backends/kicad/test_docker_cli.py` (the command line through a fake `docker`, no daemon needed).
- **Pages**: `docs/formats/kicad/cli.md` (the command row and two rows of facts, one measured locally on both pinned images), `docs/evidence/sources.md` (S-0727).

Size: 0.25 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-oracle`: MODIFIED "Docker runs keep the caller's state" (the container's user and `HOME`) and "Reserved state folder" (the host's `HOME` is still never changed; the container's is in the state folder).

## Non-goals

- No change to `KicadCli`, to the CI jobs, or to the Freerouting image runner (it already passes `HOME=/work` and runs as the image's user; not reported failing).
- No `docker:` support in the `version` probes of `capabilities` and `doctor`.
- No rootless daemon is run here; that branch rests on S-0727.

## Evidence level required

- The failure and the fix on a daemon run by root: `KICAD-VERIFIED (9.0.x, 10.0.x)`, measured locally on 2026-10-09 with both pinned images (`docs/formats/kicad/cli.md`, "Per-run state").
- The rootless branch: `INFERRED` from S-0727.

## Impact

- Changed: `src/fenolite/backends/kicad/cli.py`, `tests/unit/backends/kicad/test_docker_cli.py`, the pages above, `CHANGELOG.md`, `openspec/README.md`.
- Behaviour: a `docker:` run starts one `docker info` per runner and passes `--user` and `HOME`; what `kicad-cli` writes into the home folder stays in the reserved state folder and is never an output.
