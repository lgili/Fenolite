# Offline library device example

Authored for Fenolite under CC0-1.0. The names, dimensions and mappings are illustrative, not a real
component. LICENSE files are original fixture declarations with explicit fixture review metadata; no
upstream legal text or upstream licence approval is included. `source/` is an original three-item library; `release/` is its deterministic local release
with an all-zero fixture commit, not a published release. `fenolite_library/` and `design.lock` were
written by `fenolite get` from that release. No third-party CAD payload is present.

```sh
fenolite get device FenoliteDevices:Demo900 --from release --offline --dry-run --json
fenolite get device FenoliteDevices:Demo900 --from release --offline --confirm --plan PLAN --json
fenolite build design.py --out out --frozen --dry-run --json
```

Replace `PLAN` with the returned plan id. The committed lock also holds the part reference. Building
uses no global CAD tables, cache payloads or network; a changed item must be obtained by an explicit
`get`. Every illustrative record stays `UNVERIFIED`. `tests/unit/test_examples.py -k library_devices`
regenerates the local release, restores the vendored item closure with connections blocked, and compares
the built files with the same authored records used directly from `devices/`.

See [device items and seed](../../docs/library-devices.md) for provenance and review rules.
