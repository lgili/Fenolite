## Context

- **Upstream (archived).**
  - c0008 delivered the library readers and `LibraryResolver`: `env` and `install` sources, the template fallback, nested tables and path variables (`docs/formats/kicad/libraries.md`). Its Decision 18 moved the following here:
    - the fetch tool, the pins and a `cache` source;
    - the 9.0.9 and fetched-10.0.6 census, a check of the install against its pin, and the residue comparison against the cache;
    - `kicad_common.json` variables and the directory-scan fallback;
    - demo-library rows tagged `rt0` and `libs`, `--uses libs` in the `kicad-10` fetch, and a test that rebuilds the demo project layout in `tmp_path`;
    - the probes of `H-K-LIB-RELPATH`, `-FALLBACK`, `-NESTED` and `-CONFIGHOME`, whose rows in `docs/hypotheses.md` name the placeholders `tests/kicad/libs/test_lib_tables_drc.py::test_relpath`, `::test_fallback`, `::test_nested` and `::test_config_home`.
  - c0014 registered `H-K-LIB-DRC` and c0017 settled it, `KICAD-VERIFIED (9.0.x, 10.0.x)`. With a project `fp-lib-table` and an empty `KICAD_CONFIG_HOME`, both majors report `lib_footprint_issues` without the table and exactly one `lib_footprint_mismatch` for an altered placement. It is not part of this change.
  - **Runner (c0009, c0017).** `KicadCli.run(args, *, files, env=None)` copies `files` into a fresh temporary folder and drops caller variables whose names start with `KICAD`. It sets `KICAD_CONFIG_HOME` to `<tmp>/config` and then applies the explicit `env`. `_relative` refuses `files` names under `config`. `KicadCli.drc(board, *, files=None)` calls `run` with no `env` and returns `DrcRun.report` through `drc.read_drc_report`, and `drc.LIB_FOOTPRINT_ISSUES` and `drc.LIB_FOOTPRINT_MISMATCH` name the two library checks.
  - **Probes (c0017).** `tests/kicad/_probes.py` defines `PROBES`, `Probe`, `run`, `runner`, `major` and `libdrc`. Outcomes are pinned per version in `docs/evidence/kicad/probes/<version>.json` (`kicad-oracle`, "Probe results per kicad-cli version"). The bench `tests/kicad/board/_bench.py` provides `control`, `CONTROLS`, `write`, `TABLE_10` and `TABLE_9`, and `_triad.library(target)` gives the mini library of a major. On 9.0.9 and 10.0.6, `pcb-libdrc-missing-table` and `pcb-libdrc-unmirrored` are both `present`.
  - `kicad-oracle` "DRC verdicts come from the JSON report": every DRC verdict comes through `KicadCli.drc` and `read_drc_report`, and the requirement fixes the signature `KicadCli.drc(board, *, files=None)`. A report without violations is no evidence that a table was loaded, so every such proof carries a control that fires only when the file was loaded.
- **Official libraries.**
  - They are CC-BY-SA 4.0 as a collection, with an exception for designs (S-0048). They are never committed, and only counts are recorded.
  - The register records the tag commits by short id: `kicad-footprints` 10.0.6 `819223b66f96` and 9.0.9 `2b941bf1d978` (S-0042); `kicad-symbols` 10.0.6 `7800d91437ce` and 9.0.9 `ad36cd14bcd1` (S-0043). It also records the table syntax of each tag.
  - At 10.0.6 the symbol repository stores each library as a `.kicad_symdir` folder, and an install packs the folders into `.kicad_sym` files (S-0043, S-0044). Both repositories keep their table at the root, and an install uses it as its template (S-0042, S-0043). Whether the 10.0.6 `sym-lib-table` names the folders or the packed files is not recorded.
  - c0008's census read the local 10.0.6 install (`docs/evidence/kicad-libs.md`). Three sampled footprint files equal tag 10.0.6; whole-tree identity is not claimed.
- **Downloads.** GitLab serves the archive of one commit through `GET /projects/:id/repository/archive[.format]` with `sha` (S-0096). The archive is generated on request, and its byte stability is not documented.
- **Python.** `tarfile` extraction filters (`filter="data"`, `tarfile.data_filter`) are new in 3.11.4 as a security backport, and a program checks for them with `hasattr(tarfile, "data_filter")` (S-0095). Fenolite requires Python 3.11 or newer (`pyproject.toml`). `os.replace` renames atomically on POSIX when it succeeds, may fail across filesystems, and fails when the target is a non-empty folder (S-0097).
- **KiCad configuration.** KiCad keeps a per-OS configuration folder with one subfolder per version, which `KICAD_CONFIG_HOME` overrides. Path variables `${NAME}` can be set in KiCad, and the environment overrides that configuration. An undefined `KICAD9_X` falls back to `KICAD10_X` (S-0045). Nested tables load as if listed in the parent (S-0046), and since 10.0.1 their path variables are resolved (S-0049). No public page cited here names the file `kicad_common.json` or its `environment.vars` key, so both are observed on a file that `kicad-cli` writes (Decision 7). No KiCad source code is read for them.
- **Tests and CI.**
  - `tests/_resources.kicad_library_dirs()` returns the env folders, else the install folders. It decides the `needs_libs` skip and feeds `tests/residue/test_official_libs.py`. `tests/_libcensus.census_sources()` parametrises the census.
  - The unit tests build `LibraryConfig(env={}, …)` without `home`, so a default cache location would leak into them.
  - The `kicad-10` job fetches `--uses rt0 --exclude-uses heavy`, and the `kicad-9` job fetches nothing (`ci-baseline`). c0020 MODIFIES "KiCad 9.0 oracle job" so that it fetches only the `rt2-9` board rows; no active change modifies "kicad-10 oracle job".
  - Demo board rows identical at both tags are listed once under 10.0.6, with notes ending `identical at tag 9.0.9.1 (commit …)`. Two demo library rows exist, `kicad-demo-10-0-6-fplib-01` and `kicad-demo-10-0-6-mod-01`. The RT0 id pattern allows the kinds `pcb`, `sch`, `sym`, `mod`, `fplib` and `wks`.
- **Build (c0011, c0027, c0019).** `fenolite build` resolves through `LibraryResolver(LibraryConfig(target_major=…, project_dir=<script folder>))`, whose `env` defaults to a snapshot of `os.environ`, so `FENOLITE_LIBS_CACHE` reaches it. c0011's "Library resolution during build" allows only `env` and `install` sources, and c0019's text of "Build command" lists the row origins `project`, `global` and `template`. c0027 vendors the footprints of every row whose origin is not `project` (default `vendor="all"`). c0011's `tests/libs/test_build_official.py` (`needs_libs`) builds the official blink whenever `census_sources()` finds a source. Its hermetic helper `tests/_buildhelp.py` passes `env={}` and turns `use_global_table` off, so neither the cache nor the scan reaches the unit build tests.
- **Hand-overs.** c0013's design (Open Questions) leaves two decisions here: an opt-in pass-through of the user's library environment to `check`, and `--uses project` in the `kicad-10` fetch ("c0021 or c0025"). c0008's Decision 18 names a "directory-scan fallback" without defining it.
- **Environment.** KiCad 10.0.6 is installed locally (macOS). 9.0.9 runs from the pinned image, locally and in the `kicad-9` job.

## Goals / Non-Goals

**Goals:**
- A verified, reproducible local copy of the official libraries at 10.0.6 and 9.0.9, usable by the resolver and the tests, with no library content in the repository.
- KiCad's own path variables on request, with the precedence that S-0045 states.
- Resolution over a library folder without a table, and over the fetched trees.
- `H-K-LIB-RELPATH`, `-FALLBACK`, `-NESTED` and `-CONFIGHOME` settled by `kicad-cli` with positive controls, plus the new `H-K-LIB-COMMON`.
- Counts: the 9.0.9 and fetched-10.0.6 census, the install against its pin, and scanned rows against template rows; the residue test runs against the cache.

**Non-Goals:**
- `H-K-LIB-DRC` (c0017), and the optional corpus comparison of bottom footprints with library footprints: `H-G-BOTTOM-STORE`, `H-G-FLIP` and `H-G-PAD-ANGLE-ABS` are already `KICAD-VERIFIED` by c0017.
- 3D models (`kicad-packages3D`), a `fenolite libs` command, a CI job that fetches the official libraries, and a cache of parsed definitions (c0008's open question, default no).
- Symbol-side demo rows and `sym-lib-table` rows. They need a new id kind and symbol identifiers from schematics (schematic backend, v0.2a).
- A library pass-through for `fenolite check` (Decision 14) and `--uses project` (Decision 13).
- Any change to the `kicad-9` job, to c0009's `KicadCli.run` or to the DRC reader. `KicadCli.drc` only gains an `env` keyword (Decision 8).
- Writing KiCad configuration files from `src`: the resolver only reads `kicad_common.json`. Only the probes write one, into a temporary folder.

## Decisions

1. **Pins: commit, tree hash and file count, fetched by commit.** `src/fenolite/backends/kicad/data/libraries.toml` lives beside `tokens.toml` and is read with `tomllib` through `importlib.resources`, as `versions` reads `tokens.toml`. Its shape:

   ```toml
   schema = 1
   archive = "https://gitlab.com/api/v4/projects/{project}/repository/archive.tar.gz?sha={commit}"

   [[pin]]
   tag = "10.0.6"
   major = 10
   repo = "kicad-footprints"
   project = "kicad/libraries/kicad-footprints"
   commit = "…"  # 40 hex digits, recorded by task 2.3
   tree = "…"    # 64 hex digits, recorded by task 2.3
   files = 0     # recorded by task 2.3
   ```

   - There are four pins: both repositories at 10.0.6 (major 10) and at 9.0.9 (major 9).
   - `commit` is the `commit.id` of the tags API URLs of S-0042 and S-0043. Its first 12 digits must equal the short ids already recorded there.
   - `tree` and `files` come from the first verified fetch (`--print-pin`). This proposal records no value.
   - The archive is always requested by commit, so a moved tag cannot change what is fetched.
   - Rejected: the SHA-256 of the archive. The archive is generated on request (S-0096), and no public source says its bytes are stable.
   - Rejected: git tree ids. They need file modes, and an archive applies export attributes, so its files may differ from the commit's tree.
   - Rejected: fetching by tag name; pins under `tests/`, because the `cache` source in `src` needs them.

2. **Tree hash, scheme `fenolite-tree-1`.** `libcache.tree_hash(folder) -> tuple[str, int]` walks `folder` and refuses symlinks and other non-regular entries with `ValueError`. It skips the stamp and hashes one line `<sha256 hex> <size> <path>\n` per regular file, sorted by the UTF-8 bytes of the POSIX relative path. Empty folders do not count. Modification times and permissions are ignored, because extraction does not keep them reliably. Every stamp names the scheme, so a later scheme can be told apart.
   - Rejected: hashing the tar stream (Decision 1); a Merkle tree per folder (no partial verification is needed); file modes (they depend on the platform after extraction).

3. **The fetch tool.** `tools/kicad_libs_fetch.py` is stdlib-only, like the other tools. It imports `fenolite.backends.kicad.libcache` by putting `<repo>/src` on `sys.path`, as `tools/kicad_token_fuzz.py` does. For each selected pin:
   1. Without `tarfile.data_filter`, exit 2 naming Python 3.11.4, before any network or cache access (S-0095).
   2. If the stamp of `<cache>/<tag>/<repo>` equals the pin, report `cached`. With `--verify`, re-hash instead and report `verified`, or fail with exit 5.
   3. Download `archive` filled with the URL-encoded project and the commit, through `urllib.request` with a 60 s timeout and 1 MiB reads, into a temporary file in `<cache>/<tag>/`. Stop with exit 3 past `MAX_ARCHIVE_BYTES` (1 GiB).
   4. Before extracting, refuse any link member and a total size past `MAX_TREE_BYTES` (4 GiB), with exit 3. Then run `extractall(tmp, filter="data")` into `tmp = tempfile.mkdtemp(dir=<cache>/<tag>)`. The data filter refuses absolute paths, `..` and special files (S-0095); a refusal exits 3.
   5. Require exactly one top-level folder, whatever its name, and compare its `tree_hash` and file count with the pin. A difference exits 5.
   6. Write the stamp into that folder. Move an existing `<repo>` aside to `<cache>/<tag>/.old-<random>` with `os.replace`, move the new folder to `<repo>` with `os.replace` (S-0097), and remove the old folder. If the second move fails, the old folder is moved back.
   7. Remove the archive and `tmp` in every case.

   Exit codes follow the meanings of the CLI contract: 0 success, 2 usage or environment, 3 bad input, 5 findings. The tool is not a `fenolite` command, and prints plain lines `<tag>/<repo>: fetched|cached|verified|failed (<reason>)`. `--print-pin --tag T --repo R --commit C` runs steps 3–5 without a pin and prints the TOML entry. The unit tests use `file://` tarballs built in `tmp_path` and a temporary pins file, so no test touches the network.
   - Rejected: `shutil.move`, which copies across filesystems and is not atomic; extracting in place, which leaves a partial tree after a failure; `filter="fully_trusted"`; `git clone`, which needs another tool and fetches the history; a third-party downloader, because tools are stdlib-only.

4. **Stamps are trusted when resolving.** The resolver compares the stamp with the pin and never re-hashes. `--verify` re-hashes on demand.
   - Rejected: re-hashing at every resolver start, which reads every file of a tree once per process.

5. **The `cache` source.** `find_library_sources` reports `LibrarySource(kind="cache", root=<cache>/<tag>, major=pin.major)` when `kicad-footprints` or `kicad-symbols` under it holds a stamp equal to its pin.
   - **Location.** It is opt-in: `LibraryConfig.cache_dir`, else `FENOLITE_LIBS_CACHE` of `LibraryConfig.env`, whose default is a snapshot of `os.environ`. The resolver never looks at `~/.cache/fenolite/libs` by itself; the fetch tool and the tests use `libcache.default_cache_dir()`.
   - **Selection for target M.** `env`, then `cache`, then `install`, each of major M. An explicit, pinned source ranks above an implicit install.
   - **Defaults.** `KICAD<M>_FOOTPRINT_DIR = <root>/kicad-footprints` and `KICAD<M>_SYMBOL_DIR = <root>/kicad-symbols`, each only when verified. There is no `KICAD<M>_3DMODEL_DIR`, because models are not fetched, so `missing_models` reports the unresolved variable. There is no `KICAD<M>_TEMPLATE_DIR`.
   - `libs.py` imports `libcache`. Both are in `backends.kicad`, so `package-layering` is unchanged.
   - **Build.** `fenolite build` keeps the process environment, so `FENOLITE_LIBS_CACHE` gives its resolver a `cache` source; it passes no `cache_dir` (Decision 16).
   - Rejected: a default location searched by the resolver. Results would depend on the machine, and c0008's hermetic tests would see a developer's cache.
   - Rejected: install before cache; one source per subfolder, because two sources of one tag complicate the selection.

6. **The directory-scan fallback.** c0008 named it without a definition; this change defines it.
   - **Rule.** When no global table and no template table exists for a kind, the resolver scans the folder that `${KICAD<M>_FOOTPRINT_DIR}` or `${KICAD<M>_SYMBOL_DIR}` expands to. Each library becomes a `KiCad` row: a `<X>.pretty` folder, or a `<X>.kicad_sym` file or `<X>.kicad_symdir` folder. The file wins for one stem, as the resolver's lookup inside a folder already prefers `<entry>.kicad_sym`. The nickname is `X`, the uri is `${KICAD<M>_…_DIR}/<name>`, the order is sorted by name, and the origin is `scan`.
   - **Code.** `scan_library_folder(folder, kind, *, variable)` builds the rows; `locate` needs no change.
   - **Cache sources.** The template search is skipped, so the scan always applies. The fetched trees are source trees, not installs: their root tables are install templates (S-0042, S-0043), and at 10.0.6 the symbol tree stores folders that an install packs into files (S-0043, S-0044). The scan follows what is on disk, whatever the template names.
   - **Namespace.** The scan matches KiCad's namespace only if official nicknames equal the library stems. `H-K-LIB-SCAN` checks this on the install and on both fetched trees (Decision 10).
   - **`use_global_table`.** c0008's `LibraryConfig.use_global_table` (default true) already turns off the global and template tables (`rows` in `libs.py`, tested by `test_resolver_rows.py::test_global_table_can_be_switched_off`), but no living requirement names it. "Table discovery and precedence" now states this existing flag and extends it to the scan: with the flag false, only project rows are used. The scan stands in for a missing global or template table, so it is switched off with them. A resolver asked for project rows then ignores a library variable that is set (scenario "Project rows only").
   - **Build.** The build handles a `scan` row like any row whose origin is not `project` (Decision 16).
   - Rejected: the in-tree template for cache sources, whose uris may name packed files (not recorded).
   - Rejected: mapping a missing `<X>.kicad_sym` to `<X>.kicad_symdir` for every source, which would resolve rows that KiCad reports as missing.
   - Rejected: scanning even when a template exists, which would shadow KiCad's own table.
   - Rejected: scanning while `use_global_table` is false, which would add rows from a library variable to a resolver asked for project rows only.

7. **`kicad_common.json` variables.** With `LibraryConfig.read_common=True` (default false), the resolver reads `<config>/<M>.0/kicad_common.json` once, lazily, the first time a name reaches step 3 of the lookup. `<config>` is the folder of the global table: `config_home`, else `KICAD_CONFIG_HOME`, else the per-OS folder.
   - **Order.** `KIPRJMOD`, process environment, `environment.vars`, source defaults, versioned fallback. S-0045 says the environment overrides KiCad's configuration. Configured values rank above Fenolite's source defaults, because those defaults stand in for KiCad's built-in values.
   - **One major.** Only the target major's file is read, because KiCad keeps one folder per version (S-0045).
   - **Content.** A missing file, a missing `environment` or `vars`, or `vars: null` give no variables. Invalid JSON, or `vars` that is not an object of strings, raises `FormatError` with the file and the JSON pointer; the dispatcher maps it to `FEN-3004`. Values are used as written: Fenolite does not expand `${…}` inside environment values either, and no public source describes KiCad's behaviour here.
   - **Hint.** While `read_common` is false, the hint of an unresolved variable that is neither `KIPRJMOD` nor a library variable names `LibraryConfig.read_common`. No command sets it in this change, and the unit tests always use an empty configuration folder.
   - **Basis.** S-0045 gives the per-version folders, configured path variables and the precedence of the environment. The file name and the `environment.vars` layout come from no KiCad source code:
     - `test_common_file_layout` observes the file that `kicad-cli` writes into an empty, isolated configuration folder under `tmp_path`, recording key names only;
     - `pcb-libtable-common` and `pcb-libtable-common-env` show that KiCad reads that key and that the environment wins (`H-K-LIB-COMMON`);
     - the observation is recorded under S-0020, whose "used for" cell task 1.1 extends.
   - **Gate.** If `H-K-LIB-COMMON` does not hold on 10.0.6, `read_common` is removed from this change, "Path variable expansion" keeps its living text, and the docs keep the limitation.
   - Rejected: reading by default (machine-dependent results, against c0013's isolated `check`); reading another major's file; recursive expansion; a warning instead of `FormatError` for a broken file, because the caller opted in.
   - The layout is never taken from KiCad source code: by the clean-room rule, KiCad source is read only for keyword or version-history facts.

8. **Library table probes.** `tests/kicad/_libtables.py` holds the layouts and the outcome rule. `_probes.libtable_probes()` registers them for majors 9 and 10, the way c0018 adds its `fp-write-*` and `dru-*` probes to `PROBES`. `_libtables` takes the runner as an argument, so it does not import `_probes`.
   - **Board and control.** Every probe writes `_bench.control(target, _bench.CONTROLS["unmirrored"])` with `_bench.write(…, table=False)`: one bottom QFP whose children are not mirrored. It gives exactly one `lib_footprint_mismatch` on both majors when its library is found (c0017's results). That mismatch is the control that fires only when the library was loaded, as `kicad-oracle` requires. The library is a copy of `_triad.library(target)`.
   - **Outcome.** `absent` means no `lib_footprint_issues` and one mismatch (found). `present` means `lib_footprint_issues` and no mismatch (not found). Other reports are `different`, a missing report is `reject`, and a slow run is `timeout`. Every probe is `inconclusive` when `pcb-libdrc-missing-table` is not `present`, as in `libdrc()`.
   - **Layouts.** The thirteen layouts of `kicad-oracle` "Library table probes". Tables use the `_bench.TABLE_10` and `TABLE_9` syntax; a `Table` row in 9.0 syntax is written with bare atoms.
   - **`env` pass-through.** Every probe runs `KicadCli.drc(board, files=…, env=…)`. c0017's `KicadCli.drc` takes no `env`, so this change adds the keyword `env=None` and passes it unchanged to `KicadCli.run`, whose `env` parameter already exists (c0009). This is a MODIFIED delta of `kicad-oracle` "DRC verdicts come from the JSON report", with a hermetic scenario on the fake `kicad-cli` (task 6.1). c0009's runner requirement is unchanged: `run` already applies the explicit entries after its own `KICAD_CONFIG_HOME` (`_environment` in `cli.py`). Callers that pass no `env`, such as c0013's oracle and c0020's stages, run as before.
   - **Outside folders.** Folders that must lie outside the runner's directory are created in a temporary folder of the probe: the library for the variable and configuration probes, an empty folder, and the configuration folder D. D reaches `kicad-cli` as the `env` entry `KICAD_CONFIG_HOME` of `KicadCli.drc`, which the runner applies after its own default, because `_relative` refuses `files` under `config`.
   - **`kicad_common.json`.** The `common` probes first run `KicadCli.drc` once with D empty. If that run wrote `D/<M>.0/kicad_common.json`, the probe adds `FENOLITE_PROBE_LIBS` to its `environment.vars` and leaves the rest as `kicad-cli` wrote it; otherwise it writes the minimal object. `_boards.census` records which case occurred.
   - **Isolation.** Tested variables reach `kicad-cli` only through the `env` argument of `KicadCli.drc`, D is never the user's configuration folder, and the runner drops the user's `KICAD*` variables. The local 9.0.9 runs pass `-e HOME=/tmp`, as c0007's harness does. `tools/kicad_token_fuzz.py` is unchanged, because its cases use no library.
   - **Assertions.** `tests/kicad/libs/test_lib_tables_drc.py` keeps the placeholder names of `docs/hypotheses.md` (`test_relpath`, `test_fallback`, `test_nested`, `test_config_home`) and adds `test_common_vars` and `test_common_file_layout`. The tests assert the 10.0.6 criteria, and on 9.0.9 only `test_nested`; `test_probe_results.py` pins every other 9.0.9 outcome.
   - Rejected: the exact control, whose empty report proves nothing; exact and altered boards per probe (twice the runs for the same information).
   - Rejected: staging under the runner's `config` folder (refused).
   - **Reversed on 2026-10-02 (cross-check).** This decision first rejected "a new runner option", so as not to MODIFY c0009's runner requirement, and still had the probes run `KicadCli.drc`. That could not work: `KicadCli.drc` takes no `env`, and the runner drops the caller's `KICAD*` variables and sets its own `KICAD_CONFIG_HOME`. So the `fallback`, `confighome` and `common` probes and `test_common_file_layout` could not reach `kicad-cli` with their variables. The runner stays as it is; only `KicadCli.drc` gains `env`.
   - Rejected: calling `KicadCli.run` directly with the `pcb drc` arguments, then `read_drc_report`. It breaks the living rule that every DRC verdict comes through `KicadCli.drc`, or needs an exception to it, and it copies the argument list.
   - Rejected: setting the variables in `os.environ`. The runner drops names that start with `KICAD` and sets its own `KICAD_CONFIG_HOME`.
   - Rejected: demo boards, which are CC-BY-SA copies and need demo rows that the `kicad-9` job does not fetch.

9. **The 9.0 half of `H-K-LIB-NESTED` on an authored board.** `pcb-libtable-nested` runs in the `kicad-9` job on the CC0 bench board and `Mini_v9.pretty`, so it needs no corpus file. The job's requirement stays untouched: c0020 is the one active change that modifies it, and after c0020 the job fetches only the `rt2-9` board rows.
   - Rejected: a demo-board copy, which needs demo rows that the `kicad-9` job does not fetch.

10. **Census, scan comparison and install check.**
    - `_libcensus.census_sources()` gains `cache-10` and `cache-9` sources from `libcache.verified_folders(libs_cache_dir())`. `resolver_for` passes `cache_dir` with an empty environment, an empty configuration folder and no install. The read and resolve tests then cover the fetched trees unchanged.
    - `test_official_resolve.py::test_scan_matches_template` compares, for each source with a template table, the template rows with the `scan_library_folder` rows of the same folder, using the four counts of "Resolution evidence". It asserts the `H-K-LIB-SCAN` criterion: every count is 0. The row stays `INFERRED` with the counts as supporting data, because `CORPUS-VERIFIED` needs files from two or more origins (`corpus-policy`, "Upgraded copies keep their origin") and the official libraries are one origin.
    - `tests/libs/test_install_pin.py` compares an install with the cache of its major: footprint files by bytes, symbol libraries by the multiset of their flattened definitions, because the install packs folders (S-0044) and a folder has no order (the first run counted 42 libraries as different that differ in order only). It writes counts only and never fails on a difference.
    - The closing task copies every count to `docs/evidence/kicad-libs.md`.
    - Rejected: asserting install identity, which depends on the machine's install; hashing a whole install with `tree_hash`, because an install omits the repository's other files and packs symbols.

11. **Test resources and residue.**
    - `tests/_resources.py` gains `libs_cache_dir()`: `FENOLITE_LIBS_CACHE`, else `~/.cache/fenolite/libs`.
    - `kicad_library_dirs()` returns the env folders (else the install folders), followed by the verified cache folders. So `needs_libs` tests run with only a cache, and `tests/residue/test_official_libs.py` also compares committed files with the cache.
    - `ip-hygiene` "Official KiCad libraries are never committed" already names the cache. Its scenario becomes runnable, and its text needs no delta.
    - `LIBS_HINT` names the fetch. Pytester sessions set `FENOLITE_LIBS_CACHE` to an empty folder where they expect a skip.

12. **Demo-library corpus rows.**
    - **Rows.** Footprint side only: for each tag, the `fp-lib-table` of a demo folder whose boards place footprints through its `${KIPRJMOD}` rows, and the `.kicad_mod` files those boards place. They are found through S-0024, licensed like the demo rows (S-0023, S-0025), and tagged `libs`, `rt0` and `origin:kicad-demos`.
    - **Limits.** Files identical at both tags are listed once, like board rows. The two-digit ids cap the rows; whole demo folders are taken in name order.
    - **Test.** `tests/corpus/test_demo_libs.py` rebuilds each folder in `tmp_path` from the URL paths and reads the boards with `read_board`. It resolves each `FootprintInstance.lib_ref` through the rebuilt project table with no other source, and counts the other nicknames.
    - The rows also join RT0. The test is supporting data from one origin, so no label changes.
    - Rejected: symbol rows now, because a `sym-lib-table` row needs a new id kind and symbol identifiers come from schematics.
    - Rejected: whole `.pretty` folders (rows with no consumer); folder archives (bytes not pinned); per-tag duplicates (the corpus lists identical files once).

13. **CI.** The `kicad-10` fetch becomes `--uses rt0 --uses libs --exclude-uses heavy`, and `tests/unit/test_ci_workflow.py` checks `--uses libs`.
    - Today every `libs` row is also `rt0`, so the extra tag fetches nothing new. It is kept because c0008's Decision 18 and the roadmap commit to it, and it names what the job's tests need.
    - The MODIFIED text starts from the living requirement: no active change modifies "kicad-10 oracle job", and c0020 modifies only "KiCad 9.0 oracle job". If c0020's final text also modifies "kicad-10 oracle job", this change rebases on it, because c0020 archives first.
    - `--uses project` stays out (Open Questions).
    - Rejected: dropping the delta as redundant (a deviation from the roadmap for no gain); adding `--uses project` here, because this change is second in the v0.1 cut order.

14. **No library pass-through for `fenolite check`.** c0013 runs `kicad-cli` with an empty `KICAD_CONFIG_HOME` and left an opt-in pass-through to this change. This change adds none: the user's tables or variables would make `check` depend on the machine and weaken its isolation.
    - Rejected for now: a reproducible option that resolves official libraries from the pinned cache. It would change c0013's requirements and the CLI contract (Open Questions).

15. **Order and archive.**
    - The change depends on c0008 and c0017 (archived). c0018's edits of `tests/kicad/_probes.py` land first, because the file is shared.
    - Implementation and archive order (canonical, 2026-10-02): c0010, c0026, c0011, c0027, c0013, c0019, c0020, this change, then c0012. c0012 modifies no requirement that this change modifies, so archiving it later needs no rebase.
    - The MODIFIED requirements of `kicad-library-resolution`, `corpus-policy`, `ci-baseline` and `kicad-oracle` exist in the living specs, and no other active change modifies them, so they carry no archive-order dependency. That includes `kicad-oracle` "DRC verdicts come from the JSON report" (Decision 8). c0013 and c0020 call `KicadCli.drc` without `env` and modify no `kicad-oracle` requirement of c0017.
    - The `design-dsl` deltas carry one (Decision 16). "Library resolution during build" copies c0011's ADDED text, which c0027 and c0019 leave alone, and "Build command" copies c0019's MODIFIED text, which is c0027's text with c0019's edits. `openspec archive` of this change needs c0011, c0027 and c0019 archived first, as the canonical order does. c0028, c0029 and c0030 later extend "Build command" through ADDED requirements that name it, so none of them copies this change's text.
    - c0011 ADDs "Project library tables are written per target" to `kicad-library-resolution`, and c0010 ADDs two `corpus-policy` requirements. The drafts of this batch add "RT2 rows for KiCad 9.0" to `corpus-policy` and four `kicad-oracle` requirements (c0020), and "Preserved layouts pass the oracle" to `kicad-oracle` (c0019). None of them overlaps with this change.

16. **Build hand-over.** c0011's build resolver sees the `cache` source and `scan` rows (Context). This change MODIFIES c0011's "Library resolution during build" and c0019's text of "Build command":
    - **Cache.** The build keeps it: `FENOLITE_LIBS_CACHE` gives a `cache` source between `env` and `install` (Decision 5), and the build passes no `cache_dir`. A pinned cache is the only way to build an official-library design for target 9 on a machine with a 10.0 install, and c0027 vendors what the build places, so the built project does not need the cache.
    - **Scan rows.** They are handled like any row whose origin is not `project`. c0027's vendoring rules name `project` only, so their footprints are vendored by default, or give `build.global-library` with `vendor="project"`. No delta of "Built project files", "Build issue codes" or c0027's "Footprints of every row origin are vendored" (which names `scan` already) is needed, and `lens/build.py` needs no code for it.
    - **`result.libraries`** reports `scan` under its own name, as `Location.origin` does; `docs/dsl.md` lists the four origins. No committed schema enumerates the values.
    - **`tests/libs/test_build_official.py`** sets `FENOLITE_LIBS_CACHE` to `libs_cache_dir()` when the verified cache is one of its `needs_libs` sources, so the build sees what the census sees, and c0011's "Blink examples" stays true without a delta.
    - **Evidence.** "Build evidence" is unchanged: the build envelope is `INFERRED`, and c0027's `VENDOR_EVIDENCE` already joins when a scan row is vendored.
    - Rejected: excluding the cache from the build (`cache_dir=None` and no `FENOLITE_LIBS_CACHE`); an `env` source without a table still gives scan rows, and `test_build_official.py` would need a skip beyond `needs_libs`. Rejected: a default cache location searched by the build (Decision 5). Rejected: reporting scan rows as `template` (it hides the origin and differs from `Location.origin`). Rejected: a `needs_libs` that counts the cache only when `FENOLITE_LIBS_CACHE` is set (it weakens Decision 11 for every other `needs_libs` test).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/kicad/libcache.py` | `SCHEME = "fenolite-tree-1"`; `STAMP = ".fenolite-verified"`; `REPOS = ("kicad-footprints", "kicad-symbols")`; `CACHE_VARIABLE = "FENOLITE_LIBS_CACHE"`; `@dataclass(frozen=True, slots=True) class LibraryPin(tag: str, major: int, repo: str, project: str, commit: str, tree: str, files: int)`; `load_pins(path: Path \| None = None) -> tuple[LibraryPin, ...]`; `archive_template(path: Path \| None = None) -> str`; `tree_hash(folder: Path) -> tuple[str, int]`; `read_stamp(folder: Path) -> dict[str, object] \| None`; `stamp_matches(folder: Path, pin: LibraryPin) -> bool`; `write_stamp(folder: Path, pin: LibraryPin) -> None`; `verified_folders(cache: Path, pins: Sequence[LibraryPin] \| None = None) -> tuple[tuple[LibraryPin, Path], ...]`; `default_cache_dir(env: Mapping[str, str] \| None = None, home: Path \| None = None) -> Path`. Imports only `core` and the standard library |
| `src/fenolite/backends/kicad/data/libraries.toml` | `schema`, `archive` and four `[[pin]]` tables (Decision 1) |
| `src/fenolite/backends/kicad/libs.py` | `SourceKind = Literal["env", "cache", "install"]`; `RowOrigin = Literal["project", "global", "template", "scan"]`; `COMMON_FILE = "kicad_common.json"`; `LibraryConfig` gains `cache_dir: Path \| None = None` and `read_common: bool = False`; `scan_library_folder(folder: Path, kind: TableKind, *, variable: str) -> tuple[LibRow, ...]`; `find_library_sources` and `LibraryResolver` follow Decisions 5–7 |
| `src/fenolite/backends/kicad/cli.py` | `KicadCli.drc(board: Path, *, files: Mapping[str, Path] \| None = None, env: Mapping[str, str] \| None = None) -> DrcRun`; `env` is passed unchanged to `KicadCli.run` (Decision 8). Nothing else changes |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows of task 1.2 |
| `tests/_buildhelp.py` (c0011; extended) | `resolver(…, cache_dir: Path \| None = None)` and `build(…, cache_dir=…)`: a cache source for the hermetic build tests, which also turns on `use_global_table` (Decision 16) |
| `tests/unit/lens/test_build_resolve.py` (c0011; extended) | `test_footprint_from_a_scanned_cache` |
| `tests/libs/test_build_official.py` (c0011, c0027; extended) | sets `FENOLITE_LIBS_CACHE` when the verified cache is a `needs_libs` source |
| `docs/dsl.md` (c0011) | the cache in the build, and the four row origins of `result.libraries` |
| `tools/kicad_libs_fetch.py`, `tools/README.md` | `main(argv: list[str] \| None = None) -> int`; options `--cache`, `--tag`, `--repo`, `--pins`, `--verify`, `--print-pin`, `--commit`; `MAX_ARCHIVE_BYTES`, `MAX_TREE_BYTES` |
| `tests/_resources.py` | `libs_cache_dir() -> Path`; `kicad_library_dirs()` with the verified cache folders; `LIBS_HINT` naming the fetch |
| `tests/_libcensus.py` | `CensusSource.kind` gains `cache`; `census_sources()` adds `cache-<major>`; `resolver_for` passes `cache_dir` |
| `tests/unit/backends/kicad/test_libcache.py`, `tests/unit/test_libs_fetch.py` | hermetic tests of pins, tree hash, stamps and the tool |
| `tests/unit/backends/kicad/test_libs_sources.py`, `test_lib_vars.py`, `test_resolver_rows.py`, `test_resolver.py` | extended with cache, `read_common` and scan cases |
| `tests/unit/test_conftest_libs.py`, `tests/unit/test_ci_workflow.py`, `tests/unit/test_kicad_probes.py` | extended: skip message and cache; `--uses libs`; the outcome rule on hand-built reports |
| `tests/unit/backends/kicad/test_cli_runner.py` | `test_drc_env_entries`: the fake `kicad-cli` records the environment of a `drc` run, with and without `env` |
| `tests/libs/test_official_resolve.py`, `tests/libs/test_install_pin.py`, `tests/libs/README.md` | `test_scan_matches_template`; the install check; how to fetch |
| `tests/kicad/_libtables.py`, `tests/kicad/_probes.py`, `tests/kicad/libs/test_lib_tables_drc.py` | layouts and outcome rule; `libtable_probes()`; the six tests of Decision 8 |
| `docs/evidence/kicad/probes/10.0.6.json`, `docs/evidence/kicad/probes/9.0.9.json` | outcomes of the `pcb-libtable-*` probes |
| `tests/corpus/manifest.toml`, `tests/corpus/test_manifest.py`, `tests/corpus/test_demo_libs.py`, `docs/formats/kicad/corpus.md` | demo-library rows, their rule, the rebuild test, the row description |
| `.github/workflows/ci.yml` | `--uses libs` in the `kicad-10` fetch |
| `docs/formats/kicad/libraries.md`, `docs/evidence/kicad-libs.md`, `docs/hypotheses.md`, `docs/evidence/sources.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md` | facts, counts, register rows and session rows |

Layering: `libcache` imports `core` and the standard library, and `libs` imports `libcache`. The tool imports by path. `package-layering` gains no edge.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0095 | https://docs.python.org/3.11/library/tarfile.html | PSF License Version 2 (stated in the footer of the current version of the page; to verify on the 3.11 page) | extraction filters (`filter="data"`, `tarfile.data_filter`); "New in version 3.11.4" as a security backport; `hasattr(tarfile, "data_filter")` as the check |
| S-0096 | https://docs.gitlab.com/api/repositories/ | CC BY-SA 4.0 (stated on the page) | `GET /projects/:id/repository/archive[.format]` with `sha`: the archive of one commit |
| S-0097 | https://docs.python.org/3/library/os.html#os.replace | PSF License Version 2 (to verify on the page) | `os.replace`: atomic when it succeeds (POSIX), may fail across filesystems, fails for a non-empty target folder |

S-0098 and S-0099 are not used.

Sources of other changes cited here:
- S-0018, S-0042, S-0043 (trees, tags, commits, table syntax) and S-0044 (packing);
- S-0045 (configuration folders, path variables, precedence), S-0046 (tables) and S-0049 (variables in nested tables);
- S-0048 (licence);
- S-0022 and S-0037 (`pcb drc` options);
- S-0023, S-0024 and S-0025 (demo files, their licences and the APIs that list them);
- S-0020 (observed `kicad-cli` 10.0.6 behaviour). Task 1.1 extends its "used for" cell with the `kicad_common.json` observation.

No KiCad C++ source is read for this change. The `kicad_common.json` facts come from S-0045 and from observation.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-LIB-COMMON | `kicad-cli` takes path variables from the `environment.vars` object of `kicad_common.json` in `<KICAD_CONFIG_HOME>/<M>.0/`, and a process variable of the same name overrides it (S-0045; file layout observed, S-0020) | `tests/kicad/libs/test_lib_tables_drc.py::test_common_vars`; observation `::test_common_file_layout` | on 10.0.6, `pcb-libtable-common` is `absent` and `pcb-libtable-common-env` is `present`; the 9.0.9 outcomes and the observed layout (key names only) are recorded |
| H-K-LIB-SCAN | Every `KiCad` row of an official template table is named after the stem of its library folder or file, and a directory scan of the same tree finds the same nicknames, with no `disabled` or `hidden` row (S-0042, S-0043) | `tests/libs/test_official_resolve.py::test_scan_matches_template` | every count of the comparison is 0 on the 10.0.6 install and on the fetched 10.0.6 and 9.0.9 trees; the counts are supporting data and the row stays `INFERRED` (one origin) |

Neither id is registered in `docs/hypotheses.md` or proposed by another active change.

## Hypotheses settled by this change

| id | settling test | criterion (amended) | level when it holds |
|---|---|---|---|
| H-K-LIB-RELPATH | `tests/kicad/libs/test_lib_tables_drc.py::test_relpath` | on 10.0.6, `pcb-libtable-relpath-project` and `pcb-libtable-relpath-nested` are `absent` | refuted on 2026-10-03: a nested row with uri `../<lib>` is not found; see the note below |
| H-K-LIB-RELPATH-2 (successor) | the same test | on 10.0.6, `pcb-libtable-relpath-project`, `-nested`, `-global` and `-cwd` are `absent`, and `-nested-folder` and `-project-folder` are `present` | `KICAD-VERIFIED (10.0.x)` |
| H-K-LIB-FALLBACK | `tests/kicad/libs/test_lib_tables_drc.py::test_fallback` | on 10.0.6, `pcb-libtable-fallback` is `absent` and `pcb-libtable-fallback-defined` is `present` | `KICAD-VERIFIED (10.0.x)` |
| H-K-LIB-NESTED | `tests/kicad/libs/test_lib_tables_drc.py::test_nested` | `pcb-libtable-nested` is `absent` on 10.0.6 and `present` on 9.0.9, on the authored CC0 board | `KICAD-VERIFIED (9.0.x, 10.0.x)` |
| H-K-LIB-CONFIGHOME | `tests/kicad/libs/test_lib_tables_drc.py::test_config_home` | on 10.0.6, `pcb-libtable-confighome` is `absent` and `pcb-libtable-confighome-flat` is `present`; the 9.0.9 outcomes are recorded | `KICAD-VERIFIED (10.0.x)` |

**Refuted during implementation: `H-K-LIB-RELPATH`.** The first probe run on 10.0.6 gave `present` for a nested row with uri `../<lib>`. Further layouts, on 10.0.6 and 9.0.9, showed the rule: `kicad-cli` resolves a relative uri against its working directory, in project, nested and global tables alike. A library next to the board is not found when `kicad-cli` runs in the parent folder, and a library in the working directory is found. So the folder of the table never counts, and the project folder counts only when it is the working directory. Following "Refuted rows keep their id", the row is refuted and `H-K-LIB-RELPATH-2` states the observed rule. The resolver joins a relative uri to `project_dir`, which stands for the working directory of a KiCad run in the project, and leaves it relative without one; depending on the caller's working directory when a project folder is known would make results differ between two runs of one design. The probes grew from nine to thirteen (four more `relpath` layouts), two of which run `KicadCli.run` directly because `KicadCli.drc` runs in the board's folder. The nested fixture row changed from `../../Mini_v9.*` to `../Mini_v9.*`.

The old criteria ("no library violation on 10.0.6", and for `H-K-LIB-NESTED` "a violation on 9.0.9") predate the `kicad-oracle` rule that an empty report proves nothing. The amended criteria add the altered placement as a positive control and keep the meaning. A probe that refutes its row follows `verification-evidence` "Refuted rows keep their id": the row is marked refuted, a successor states the observed rule, and the resolver rule and its MODIFIED requirement change before archive.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Pin commits equal the tag commits | fact from the tags API (S-0042, S-0043), checked against the recorded short ids | task 2.3 |
| Pins file rules, tree hash, stamps | mechanical | `test_libcache.py` |
| Fetch tool: filter, atomic move, verify, exit codes | mechanical | `test_libs_fetch.py` |
| Cache source, selection and defaults | mechanical (Fenolite choice) | `test_libs_sources.py`, `test_lib_vars.py` |
| `kicad_common.json` variables | `KICAD-VERIFIED (10.0.x)` (`H-K-LIB-COMMON`), otherwise the rule is removed (Decision 7) | `test_lib_vars.py`, `test_lib_tables_drc.py` |
| Directory scan | `INFERRED` (`H-K-LIB-SCAN`); the census counts are supporting data | `test_resolver_rows.py`, `test_official_resolve.py` |
| `env` of `KicadCli.drc` reaches `kicad-cli` | mechanical | `test_cli_runner.py::test_drc_env_entries` |
| Relative URIs in KiCad (working directory) | `KICAD-VERIFIED (10.0.x)` (`H-K-LIB-RELPATH-2`); joining to `project_dir` is a Fenolite choice | `test_relpath`, `test_lib_vars.py` |
| Versioned fallback | `KICAD-VERIFIED (10.0.x)` (`H-K-LIB-FALLBACK`) | `test_fallback` |
| Nested tables in 10.0, and none in 9.0 | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-LIB-NESTED`) | `test_nested` |
| Configuration folder of the major | `KICAD-VERIFIED (10.0.x)` (`H-K-LIB-CONFIGHOME`) | `test_config_home` |
| Project-over-global precedence | `INFERRED` (S-0046); not probed here | unit tests |
| Census of the fetched trees | supporting data for `H-K-LIB-READ` (counts) | `tests/libs` |
| Install against its pin | measurement (counts) | `test_install_pin.py` |
| Demo projects resolve their own footprints | supporting data (one origin) | `test_demo_libs.py` |
| Residue against the cache | mechanical | `tests/residue/test_official_libs.py` |
| `needs_libs` sources and message | mechanical | `test_conftest_libs.py` |
| Build with a cache source and scan rows | mechanical; the official blink from the cache is supporting data (`needs_libs`) | `test_build_resolve.py`, `test_build_official.py` |
| `kicad-10` fetch step | mechanical | `test_ci_workflow.py` |

When a probe refutes its rule, the level is that of the observed rule, after the change of "Hypotheses settled by this change". The labels in `docs/formats/kicad/libraries.md` follow this table.

## Budget (about 9.5 days; the roadmap line is 5)

| work | days |
|---|---|
| sources, hypotheses, provenance, format page (1.1–1.3) | 0.75 |
| `libcache` module and tests (2.1) | 0.5 |
| fetch tool and tests (2.2) | 1.0 |
| pins recorded, both tags fetched (2.3) | 0.5 |
| `cache` source (3.1) | 0.75 |
| `kicad_common.json` and directory scan (3.2) | 0.75 |
| test resources, skip message, residue (4.1) | 0.5 |
| census, scan comparison, install check (4.2) | 0.75 |
| demo-library rows (5.1) | 0.75 |
| rebuild test and CI step (5.2) | 0.5 |
| build hand-over (4.3) | 0.5 |
| `env` keyword of `KicadCli.drc` (6.1) | 0.25 |
| probe layouts and probes on 10.0.6 (6.2, 6.3) | 1.0 |
| probes on 9.0.9, results files, outcomes (6.4) | 0.5 |
| closing (7.1–7.3) | 0.5 |
| **total** | **9.5** |

c0008's Decision 18 estimated about one week for this follow-up, and the roadmap line is 5 days. c0008 itself took about three times its plan line. If v0.1 runs late, the cut order before moving the whole change to v0.2a is below. A cut removes the requirements and scenarios it names before archive, so no requirement is archived without its implementation, and the proposal follows.

1. **Demo-library rows, rebuild test and CI step** (tasks 5.1 and 5.2, 1.25 days). Removed:
   - `corpus-policy` ADDED "Demo library corpus rows", with its four scenarios "Library row without rt0", "Demo projects resolve their own footprints", "Other nicknames are counted" and "Rows fetched by use";
   - the whole `ci-baseline` delta, MODIFIED "kicad-10 oracle job", with its added scenario "Library rows not fetched", so the living text stays;
   - Decisions 12 and 13, and their rows in "Files and public API" and "Evidence level per behaviour".
2. **Install check** (part of task 4.2, 0.25 days). Removed:
   - `kicad-library-resolution` ADDED "Install tree compared with its pin", with its two scenarios "Install of 10.0.6 compared with its pin" and "No cache of the install's major";
   - the install bullet of Decision 10, `tests/libs/test_install_pin.py` and its proof in task 4.2, and the row "Install against its pin".
3. **`kicad_common.json` reading and its probes** (parts of tasks 3.2 and 6.2–6.4, about 0.75 days). Removed:
   - the whole `kicad-library-resolution` delta MODIFIED "Path variable expansion", because each of its edits concerns `kicad_common.json`. The living text stays, including "KiCad's own configuration file `kicad_common.json` MUST NOT be read". Its five added scenarios go: "KiCad's configuration is read only on request", "Process environment wins over KiCad's configuration", "KiCad's configuration wins over the source default", "Only the target major's file is read" and "Malformed configuration file";
   - in MODIFIED "Resolution evidence", the words "and the variables of `kicad_common.json`";
   - in `kicad-oracle` ADDED "Library table probes": the probes `pcb-libtable-common` and `pcb-libtable-common-env`, the sentences of "Configuration files" about `kicad_common.json`, the "Observation" bullet, `test_common_vars` and `test_common_file_layout`, and the scenarios "Process variable wins over kicad_common.json" and "Layout of kicad_common.json observed";
   - Decision 7, `read_common`, `COMMON_FILE`, the hypothesis `H-K-LIB-COMMON` and the S-0020 extension of task 1.1.

   A refuted `H-K-LIB-COMMON` is not a cut: Decision 7's gate applies, and the probes and the refuted row stay.

With all three cuts the change takes about 7.25 days. The pins, the fetch tool, the cache source, the scan, the build hand-over (without it c0011's build texts are false), the `env` keyword of `KicadCli.drc` and the four c0008 probes are not optional.

## Risks / Trade-offs

- [A probe refutes its hypothesis] → "Refuted rows keep their id" applies. The resolver rule and its MODIFIED requirement change before archive; all four rules live in requirements this change already modifies. The docs follow.
- [9.0.9 writes no report for a table with a `Table` row] → the outcome `reject` still shows that 9.0 does not expand nested tables. The 9.0 criterion of `H-K-LIB-NESTED` is then amended to "`present` or `reject`" with the observation, and the test asserts the recorded outcome.
- [`kicad-cli` writes no `kicad_common.json`, or rewrites it at start-up] → the probe starts from the file `kicad-cli` wrote, else from a minimal one, and the behavioural probe settles the layout. If it fails on 10.0.6, `read_common` is cut (Decision 7).
- [Official nicknames are not stems, so `H-K-LIB-SCAN` is refuted] → the fallback of Open Questions applies, and "Table discovery and precedence" is amended before archive.
- [Upstream re-tags, or GitLab changes the archive layout] → pins name the commit and the tree. The tool requires one top folder and ignores its name. A re-pin is a reviewed change of `libraries.toml`.
- [Large downloads and disk use] → only maintainers and contributors fetch, never CI. Caps: 1 GiB per archive, 4 GiB per tree. Task 2.3 measures the sizes, and `tests/libs/README.md` states them.
- [Two fetches at once] → there is no lock. The move-aside order keeps a complete folder in place, and the README says to run one fetch at a time.
- [A developer's cache changes test outcomes] → the resolver's cache is opt-in, pytester sessions set `FENOLITE_LIBS_CACHE`, and unit tests pass `env={}`.
- [Library content leaks into the repository] → only counts are recorded, the residue test compares against the cache, the probes use the CC0 mini library, and demo rebuilds live in `tmp_path`. Every proof that touches libraries checks `git status --porcelain`.
- [Rate limits on demo-row fetches] → CI caches the corpus by manifest hash, and the id cap bounds the rows.
- [Budget overrun] → the cut order of "Budget".

## Migration Plan

- Additive. The new `LibraryConfig` fields default to the old behaviour (no cache, no configuration file), so existing callers resolve as before. `KicadCli.drc`'s `env` defaults to `None`, so every existing call runs as before.
- `fenolite build`'s `result.libraries` gains the value `scan`, and a build run with `FENOLITE_LIBS_CACHE` set resolves official libraries from the cache (Decision 16).
- `SourceKind` and `RowOrigin` gain one value each. No code in `src` matches them exhaustively today; `tests/_libcensus.py` is extended (task 4.2), and pyright checks the rest (task 3.1).
- Rollback: remove `libcache.py`, `libraries.toml`, the tool, the probes and their outcomes, and the `libs` rows; revert the CI step; delete `~/.cache/fenolite/libs`, which lies outside the repository.

## Open Questions

- **Directory-scan fallback.** c0008 named it without a definition. Default: Decision 6, rows from a folder scan when no global or template table exists, and always for cache sources.
- **`check` and official libraries.** Should `fenolite check` get an opt-in that resolves official libraries from the pinned cache? Default: no in v0.1 (Decision 14); proposed for v0.2a with `verification-loop` and `cli-contract` deltas.
- **`--uses project`.** c0013 assigned it to "c0021 or c0025". Default: c0025, because this change is second in the v0.1 cut order.
- **A `fenolite libs fetch` command,** so that users of the wheel can create the cache without a checkout. Default: after v0.1.
- **Budget (the user question on the re-baseline and the cut order, which names this change).** Default: accept 9.5 days with the cut order of "Budget"; the whole change moves to v0.2a if v0.1 still runs late.
- **If `H-K-LIB-SCAN` is refuted.** Default: cache sources use the in-tree template tables, and for cache sources only, a template row whose `<X>.kicad_sym` is missing resolves to `<X>.kicad_symdir`. "Table discovery and precedence" is amended before archive.
- **Amended criteria of the four c0008 rows.** Default: accepted, because they add a positive control and keep the meaning.
- **Fetching the cache in CI** to run `needs_libs` tests there. Default: no (c0008's non-goal; download size; the KiCad images ship their own install).
- **Build hand-over.** Default: Decision 16. The build keeps the cache through `FENOLITE_LIBS_CACHE`, reports `scan` rows under their own name and vendors them like other non-project rows; `test_build_official.py` sets the cache. Optional, default no: a target-9 build of `blink_official` from the 9.0.9 cache.
