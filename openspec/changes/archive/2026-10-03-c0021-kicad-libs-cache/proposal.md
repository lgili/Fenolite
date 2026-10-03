## Why

c0008 resolves KiCad library identifiers from a local install or `KICAD*` folders. Its design (Decision 18) moved the rest here: a pinned library cache, `kicad_common.json` variables, a directory-scan fallback, the 9.0.9 census, and `kicad-cli` probes for four rules that are still `INFERRED` (`H-K-LIB-RELPATH`, `-FALLBACK`, `-NESTED`, `-CONFIGHOME`). Without a cache, no 9.0.9 library can be read, and the residue test compares only against an install. The official libraries are CC-BY-SA as a collection (S-0048), so they are fetched, never committed.

## What Changes

- `tools/kicad_libs_fetch.py` downloads `kicad-footprints` and `kicad-symbols` at the pinned commits of tags 10.0.6 and 9.0.9 (S-0042, S-0043, S-0096). It extracts with the `tarfile` data filter (S-0095), checks a tree hash and a file count, writes a `.fenolite-verified` stamp and moves the tree into place (S-0097). `--verify` re-hashes.
- `backends/kicad/data/libraries.toml` holds the pins (tags API, first fetch); `libcache.py` loads them and computes tree hashes.
- The resolver gains:
  - a `cache` source, opt-in through `LibraryConfig.cache_dir` or `FENOLITE_LIBS_CACHE`, ranked after `env` and before `install`;
  - `environment.vars` of the target major's `kicad_common.json`, only with `LibraryConfig.read_common=True` and below process variables (S-0045), its layout observed on a file that `kicad-cli` writes;
  - a directory scan when no global or template table exists. Cache sources always use it.
- Census of both fetched trees, plus install-versus-pin and scan-versus-template comparisons; counts only.
- Probes for the four rules and for `kicad_common.json` (`H-K-LIB-COMMON`), through `KicadCli.drc`, which gains an `env` keyword, on authored CC0 boards on both majors, pinned per version.
- Demo-library corpus rows tagged `rt0` and `libs`, a test that rebuilds each demo project in `tmp_path` and resolves its placed footprints, and `--uses libs` in the `kicad-10` fetch.
- The `needs_libs` skip message names the fetch.
- `fenolite build` sees cache and scan rows: `result.libraries` reports `scan`, and `test_build_official.py` sets `FENOLITE_LIBS_CACHE`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-library-resolution`: MODIFIED "Path variable expansion", "Table discovery and precedence", "Library sources" and "Resolution evidence"; ADDED "Library pins", "Library cache fetch" and "Install tree compared with its pin".
- `corpus-policy`: MODIFIED "Skip markers"; ADDED "Demo library corpus rows".
- `ci-baseline`: MODIFIED "kicad-10 oracle job".
- `kicad-oracle`: MODIFIED "DRC verdicts come from the JSON report"; ADDED "Library table probes".
- `design-dsl` (c0011): MODIFIED "Library resolution during build" and "Build command" (c0019's text).

## Non-goals

- `H-K-LIB-DRC`, settled by c0017.
- 3D models, a `fenolite libs` command, a CI job that fetches the official libraries, and a cache of parsed definitions.
- Symbol-side demo rows (schematic backend, v0.2a).
- Library environment pass-through for `fenolite check` (c0013 left it here; decided: no), and `--uses project` (c0025).
- Any change to the `kicad-9` job, which c0020 modifies.

## Evidence level required

- Pins, tree hash, fetch tool, cache source and scan: mechanical, by unit tests without network.
- `H-K-LIB-RELPATH`, `-FALLBACK`, `-CONFIGHOME` and `H-K-LIB-COMMON`: `KICAD-VERIFIED (10.0.x)` when their probes hold on 10.0.6; 9.0.9 outcomes are recorded. `H-K-LIB-NESTED`: `KICAD-VERIFIED (9.0.x, 10.0.x)` when 10.0.6 expands the nested table and 9.0.9 does not. A refuted rule changes the resolver and its requirement before archive; `read_common` ships only if `H-K-LIB-COMMON` holds.
- Directory scan: `INFERRED` (`H-K-LIB-SCAN`), with the census of the install and both fetched trees as supporting data.
- Census and install comparison: supporting data in `docs/evidence/kicad-libs.md`.

## Impact

- `libs.py` gains a source kind, a row origin and two `LibraryConfig` fields, and `KicadCli.drc` gains `env`, all additive. No runtime dependency, CLI change or model change.
- Depends on c0017 (archived); implemented after c0019 and c0020, and archived after c0011, c0027 and c0019 (build texts). Estimated at 9.5 days against the roadmap's 5 (design, "Budget"); cuttable to v0.2a.
