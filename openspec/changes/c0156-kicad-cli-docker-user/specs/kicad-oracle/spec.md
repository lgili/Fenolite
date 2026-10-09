## MODIFIED Requirements

### Requirement: Reserved state folder
`.fenolite-state` SHALL be a reserved name like `config` (`cli.RESERVED_DIRS`): `KicadCli.run` MUST refuse it as a run file name and never report a file under it as an output, and the copy set of a check MUST skip it as `reserved-name`. The runner MUST NOT change `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME` or `XDG_DATA_DIRS` of a `kicad-cli` it starts on the host; the container of `DockerCli` gets its own `HOME` in this folder ("Docker runs keep the caller's state").

#### Scenario: A library row in the state folder
- **GIVEN** a project whose `fp-lib-table` names `${KIPRJMOD}/.fenolite-state/Z.pretty`
- **WHEN** `project_set` plans the copy set
- **THEN** the row is skipped as `reserved-name` and the folder is not copied

### Requirement: Docker runs keep the caller's state
`DockerCli` SHALL pass no private state to the `docker` client: each container (`--rm`) has its own `/tmp`, and the `docker` client MUST keep the caller's environment, `XDG_RUNTIME_DIR` included. The container MUST run as the user that owns the run folder, so that `kicad-cli` can write a folder of mode 0700 whoever the caller is (c0156): `--user <uid>:<gid>` of the caller under a daemon run by root, `--user 0:0` under a rootless daemon (whose container root is the caller, S-0727), and no `--user` on a host without POSIX ids. Its `-e` entries MUST be `HOME=/w/.fenolite-state/home` (a folder the runner creates in the run folder before the container starts), `KICAD_CONFIG_HOME=/w/config`, `LANG=C` and `LC_ALL=C`, then the run's `env`.

#### Scenario: Docker keeps the caller's runtime folder
- **GIVEN** a fake `docker` and a caller with `XDG_RUNTIME_DIR=/run/user/1000`
- **WHEN** `DockerCli(image).version()` runs
- **THEN** the `docker` client sees `XDG_RUNTIME_DIR=/run/user/1000`, and the command's `-e` entries are `HOME=/w/.fenolite-state/home`, `KICAD_CONFIG_HOME=/w/config`, `LANG=C` and `LC_ALL=C` only

#### Scenario: The container runs as the owner of the run folder
- **GIVEN** a fake `docker` whose `info` lists the security options of a daemon run by root, then of a rootless daemon
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_docker_cli.py -k "owner or rootless or home_folder or docker_user"` runs
- **THEN** the command holds `--user <uid>:<gid>` of the test process before the image, then `--user 0:0` for the rootless daemon, none where `os.getuid` is missing, and `<run folder>/.fenolite-state/home` exists before the container starts

#### Scenario: A root host runs the pinned image
- **GIVEN** a host user root, a daemon run by root and the pinned image `kicad/kicad:10.0.6`
- **WHEN** `DockerCli(image).drc(board)` runs on `tests/data/kicad/board/two_layer.kicad_pcb`
- **THEN** the run exits 0, its stderr holds no "Permission denied", and its `drc.json` report is read
