# tests

| Folder | What lives there | Needs |
|---|---|---|
| `unit/` | fast, hermetic tests of `fenolite` and of repository invariants | nothing |
| `consistency/` | CLI contract checks run against every registered command (change c0002) | nothing |
| `residue/` | IP residue scan over the tree and the built wheel (change c0003) | nothing; private token list optional |
| `corpus/` | tests over the fetched public corpus (`tools/corpus_fetch.py`) | `needs_corpus` |
| `kicad/` | tests that call `kicad-cli` 9.0/10.0 | `needs_kicad` |
| `data/` | small fixtures authored for Fenolite, declared in `data/MANIFEST.toml` | nothing |

Run everything that needs no external tool with `uv run pytest -q`.

## Markers and modes

| Marker or variable | Effect |
|---|---|
| `needs_kicad`, `needs_corpus`, `needs_libs` | skip when the resource is absent |
| `FENOLITE_REQUIRE=kicad,corpus,libs` | required-resource mode: those skips become failures (CI oracle jobs) |
| `kicad_min_major(10)` | skip when the running `kicad-cli` is older (for example `pcb upgrade`, 10.0 only); never a failure, even in required-resource mode |
| `FENOLITE_HEAVY=1` | include corpus files over 20 MB |
| `FENOLITE_KICAD_CLI=/path` | use this `kicad-cli` (a missing file counts as no `kicad-cli`) |

