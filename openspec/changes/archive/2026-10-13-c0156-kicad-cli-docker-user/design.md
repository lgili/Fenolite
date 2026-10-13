## Outcome in one paragraph

**Run the container as the owner of the run folder, with a writable `HOME`.** `DockerCli._command` adds `--user` (from `docker_user`, worked out once per runner) and `-e HOME=/w/.fenolite-state/home`, and makes that folder in the run folder before the container starts.

## Context

- `KicadCli.run` makes the run folder with `tempfile.mkdtemp` (mode 0700, owned by the caller), copies the inputs, and for `DockerCli` mounts it at `/w`. `DockerCli._state` passes no private state (c0153): the folders `private_state` makes are not created for a container run.
- The pinned images run as `kicad` (uid 1000, gid 1000), with `HOME=/home/kicad` (mode 0700). Measured on 2026-10-09 (host user root, Docker 29.8.2, a daemon run by root): without `--user`, `pcb drc` on 10.0.6 prints "Directory '/w/config' couldn't be created (error 13: Permission denied)" and exits 3 with no report; with `--user 1234:1234` on a folder of that owner and no `HOME`, both majors print "Directory '/.cache' couldn't be created" and "Directory '/.local' couldn't be created" but write their report; with `HOME` in the run folder they print nothing.
- Under a rootless daemon, container uid 0 is the host user and any other container uid is a subordinate uid (S-0727): the image's `kicad` user cannot write the caller's folder there either.

## Decisions

1. **The caller's ids, not a wider mode.** Opening the run folder to everyone (0777) would make the copied project readable by every local user; the container's user follows the folder instead.
2. **Rootless.** `docker_rootless` reads `docker info --format '{{json .SecurityOptions}}'` once per runner and looks for `rootless` (S-0727; a daemon run by root prints `["name=seccomp,profile=builtin"]` here). Rootless gives `--user 0:0`; a client that cannot answer counts as a daemon run by root.
3. **No POSIX ids.** Where `os.getuid` does not exist (Windows), no `--user` is passed: Docker Desktop's mounts are not owned by a host uid.
4. **`HOME` in the state folder.** `.fenolite-state/home` is under a reserved name, so what `kicad-cli` keeps there (`.cache/kicad`, `.local/share/kicad/<major>`) is never an output and goes with the run folder. `KICAD_CONFIG_HOME` stays `/w/config`.
5. **CI unchanged.** The `kicad-9`, `kicad-10` and `yardstick` jobs run inside the image with `KicadCli`; they never call `DockerCli`.

## Tests

- `tests/unit/backends/kicad/test_docker_cli.py`, through a fake `docker`: the `-e` entries; `--user <uid>:<gid>` before the image under a daemon run by root; `--user 0:0` under a rootless one; `docker_user` without `os.getuid`; `docker_rootless` without a client; the home folder exists after `_command`.
- Local, not in CI: `DockerCli("kicad/kicad:10.0.6@…").drc(two_layer.kicad_pcb)` as root exits 0 with a report and no "Permission denied", and the same on 9.0.9.

## Released output

`backends/kicad/cli.py` changes; no written file changes.

## Size (design-days)

| group | dd |
|---|---|
| runner, tests, pages | 0.25 |

Total: 0.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `kicad-oracle`: MODIFIED "Docker runs keep the caller's state" and "Reserved state folder", both added by c0153 (archived), so this change can be archived at any time.
