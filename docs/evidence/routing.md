# Routing evidence

The feasibility gate runs KiCadRoutingTools `v0.22.1` against the built blink for target 9 under
`kicad-cli` 9.0.9 and target 10 under `kicad-cli` 10.0.6. Outcomes are recorded here and in a
tag-specific JSON result when the optional CI job runs. `equal` for each route means there are no
unconnected items and no new error-severity DRC types versus the unrouted board. Repeatability is
recorded but does not gate the change.

Tool setup: source tag `v0.22.1`, commit `023d3f79027d5406e4ea8e68291f588c5c135673`; macOS arm64,
CPython 3.13.5. The `grid_router-macos-arm64.so` asset was downloaded from that GitHub release with
`gh release download` and checked against its release API SHA-256
`2c7f22829e0a32f328e6e75e0f587e544cd19316eed6c75580b0abdb027893a5`; it was installed at
`rust_router/grid_router.so` in the checkout outside this repository. `build_router.py --tag v0.22.1`
could not reach GitHub from Python and Rust is not installed here; the direct, digest-checked release
asset runs successfully. The tool states its version in the checkout's `VERSION` file (`0.22.1`).

For target 9, the same checkout's Linux x86_64 release asset (`grid_router-linux-x86_64.so`) was
downloaded into `/tmp/fenolite-c0016-kicadroutingtools-linux/rust_router/grid_router.so`; its SHA-256
`652b67e266c58b1e373e503bcf9b5d0b0d3dd4756e1c306100f23edf3d3f989b` matches the GitHub release API
digest. The gate ran in the pinned `kicad/kicad:9.0.9` Linux x86_64 image with CPython 3.11.2,
KiCad 9.0.9 and pytest 9.1.1. A separate temporary venv held pytest and the tool's dependencies; Fenolite
was imported from the mounted worktree. The pinned image ran under x86_64 emulation on the macOS arm64
host.

| probe | target 9 / KiCad 9.0.9 | target 10 / KiCad 10.0.6 | meaning |
|---|---|---|---|
| `krt-cli` | present | present | command arguments, output board and passed track width |
| `krt-route` | equal | equal | unconnected items and new error types |
| `krt-keep` | equal | equal | equality of all non-copper model content |
| `krt-repeat` | equal | equal | route geometry from two runs |

Verdict: passed. Both target-major route outcomes are equal: no unconnected items and no new DRC error types.

- `krt-cli-t10`: `present` (`v0.22.1`).
- `krt-route-t10`: `equal` (`v0.22.1`).
- `krt-keep-t10`: `equal` (`v0.22.1`).
- `krt-repeat-t10`: `equal` (`v0.22.1`).
- `krt-cli-t9`: `present` (`v0.22.1`).
- `krt-route-t9`: `equal` (`v0.22.1`).
- `krt-keep-t9`: `equal` (`v0.22.1`).
- `krt-repeat-t9`: `equal` (`v0.22.1`).

The integrated router gate and `build` → `place` → `route` → rebuild → `fill` → `check` loop also
passed on both target majors in CI run 37197766881 (KiCad 9.0.9 and 10.0.6).
- `krt-cli-t9`: `present` (`v0.22.1`).
- `krt-keep-t9`: `equal` (`v0.22.1`).
- `krt-repeat-t9`: `equal` (`v0.22.1`).
