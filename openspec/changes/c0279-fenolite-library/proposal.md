## Why

Fenolite needs real third-party material: boards to start from and to benchmark the generators against,
and symbols, footprints, devices and blocks beyond what can be authored by hand. The tool repository must
stay Fenolite-authored (AGENTS.md, clean-room). `docs/research/board-library.md` (sections 3, 4.5, 5)
proposes a separate repository. The maintainer decided on 2026-10-29 that **one** repository,
`fenolite-library` (github.com/lgili/fenolite-library), holds **all** third-party-derived material
converted to Fenolite formats: symbols, footprints, devices, circuit blocks and boards. Copying from third
parties is allowed there only, each item keeping its upstream licence, NOTICE and `PROVENANCE.json`, and
users pull items with one command.

## What Changes

- **The repository.** Layout `<kind>/<licence family>/<item>/` for `symbols`, `footprints`, `devices`,
  `blocks` and `boards`. Each item holds `item.json`, its payload, the upstream `LICENSE`, a `NOTICE` with
  a dated modification notice, and `PROVENANCE.json` (`fenolite.provenance.v0`): upstream URL and commit,
  authors, SPDX id, conversion tools, versions and steps, fidelity proof result, accepted differences.
- **Licence lists** enforced by its CI. Allowed: CERN-OHL-P/W/S v2 and v1.2, CC0, CC BY, CC BY-SA, MIT,
  BSD, Apache-2.0, Solderpad, GPL-2.0-or-later, GPL-3.0, TAPR. Denied: NC, ND, no licence,
  platform-restricted origins (EasyEDA/OSHWLab, vendor-bundled examples).
- **Its CI** calls a pinned released `fenolite`: audit of layout, licences, notices and provenance;
  regeneration of each changed item from its pinned upstream commit; c0278's proof on boards; a scheduled
  benchmark of every board with the newest Fenolite.
- **Releases with digests:** `index.json`, deterministic archives, `SHA256SUMS`.
- **A static gallery** of Fenolite renders with attribution and licence: the only marketing source for
  third-party boards.
- **One command,** `fenolite get <kind> <id> [--version V]`, through plan and confirm. Licences and
  obligations are shown before confirm, and any licence other than CC0 is accepted by name. It copies the
  item and its dependencies into the project with LICENSE, NOTICE and PROVENANCE, regenerates
  `fenolite_library/ATTRIBUTION.md`, pins version, release and tree digest in the design lock (c0249), and keeps an
  offline cache. Also `--list`, `--search`, `--status`, `--locked`, `--refresh`, `--remove`.
- **Verbs** `fenolite library audit|replay|release|gallery` are the library's CI tooling, so the library
  holds no tooling code.
- **Codes** `FEN-6004` (pinned item missing), `FEN-6006` (not in the offline cache), `FEN-4003` (licence
  not accepted), `FEN-3008` (licence not allowed). **ADR-0008**: `get` is the second downloading command.
- **AGENTS.md** gains the sentence: third-party material lives only in `fenolite-library`, with a licence
  and provenance per item. `corpus-policy`, `ip-hygiene` and `public-presentation` are aligned.
- c0266 (devices) and c0273 (blocks) become kinds of this repository pulled by `fenolite get`, replacing
  the separate repositories `fenolite-devices` and `fenolite-blocks`.

## Non-goals

- No machine-learning training on items: they are test and benchmark inputs. Any training use is a
  separate public decision.
- No conversion, drawn schematic or proof logic (c0275 to c0278).
- No private or employer material in either repository.
- No registry service, account or upload command.

## Evidence level required

- `get`, cache, lock pins, licence gate and audit: `INFERRED`, unit-tested against a local release built
  from authored fixtures, no network (`H-G-LIBRARY-GET`).
- Replay from a pinned commit: `INFERRED` (`H-G-LIBRARY-REPLAY`). A real download stays `UNVERIFIED`.

## Impact

- New: `src/fenolite/library/`, `cli/cmd_get.py`, the `library` verbs, `cli/data/library.toml`,
  `cli/data/library-licences.toml`, `docs/library-repo.md`, ADR-0008, tests, authored fixtures.
- Changed: `AGENTS.md`, ADR-0003 and ADR-0007 (dated lines), `cli/errors.py`, `explain.toml`,
  `docs/cli-contract.md`, the agent guide, `CHANGELOG.md`.
- Outside: `lgili/fenolite-library`, its workflows and its Pages gallery.
- Depends on c0249 and c0259 (phase A); the boards kind on c0275–c0278 (phase B). c0266 and c0273 depend
  on phase A.
- Size: about 12 design-days (L): 7 for phase A, 5 for phase B.
