# Provenance rules

How Fenolite proves where its format knowledge comes from (ADR-0003, `LEGAL.md`).

## Source ids

Every public source is a row of `docs/evidence/sources.md` with an id `S-NNNN`. Format pages,
ADRs and proposals cite those ids (or the URL itself).

## `PROVENANCE.md` in every backend package

Each package `src/fenolite/backends/<name>/` contains a `PROVENANCE.md` with this table:

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| `via` node grammar | S-0007 | CC-BY-SA-4.0 (documentation) | 2026-10-02 | facts only |

`how used` is one of `facts only`, `design with attribution` (then the work is also listed in
`NOTICE`) or `oracle` (a tool run as a subprocess to compare outputs).

## Format pages cite sources

Every page under `docs/formats/` (except `README.md`) cites at least one `S-NNNN` id or URL.

## Session log

`LEGAL-ANNEX.md` gets one row per working session on `src/fenolite/backends/` or `docs/formats/`.
CI checks that every ISO week in which a commit touched those paths has at least one row dated in
that week. Content is reviewed by humans.

## Private residue gate

The residue scan (`tools/residue/scan.py`, `tools/residue/README.md`) has a public part and a private
part. The public part is the structural patterns and the whole-file hash list committed under
`tools/residue/`. The private part, "the gate", is a list of tokens and a list of whole-file hashes that
only the maintainers hold. They are never committed, not even hashed
(`tests/residue/test_no_token_list.py`), and the scan prints `path:offset:pattern-id`, never the text it
matched.

Three environment variables configure the gate:

| variable | what it does |
|---|---|
| `FENOLITE_RESIDUE_TOKENS` | the tokens themselves, separated by commas or line breaks. When it is set and not empty, no token file is read |
| `FENOLITE_RESIDUE_TOKENS_FILE` | the path of a token file: one token per line, `#` starts a comment, a line starting with `re:` is a regular expression. Read only when `FENOLITE_RESIDUE_TOKENS` is unset or empty |
| `FENOLITE_RESIDUE_BLOBS_FILE` | the path of a hash file: `<sha256> <label>` per line. Its hashes are added to the public list |

- Without the two token variables, the scan reads `~/.fenolite-residue-tokens`. Without
  `FENOLITE_RESIDUE_BLOBS_FILE`, it reads `~/.fenolite-residue-blobs`. A file that does not exist is an
  empty list, not an error.
- A plain token matches without regard to case, and only when no letter or digit touches it.
- The last line of every scan says which case ran: `private gate: on` when at least one private token
  or hash was loaded, `private gate: skipped (no private list configured)` otherwise. A skipped gate
  exits 0 on a clean tree: it proves the public patterns only.

Where the gate is on and where it is off:

| where | gate | why |
|---|---|---|
| `make residue`, `make check`, `make check-fast` | on, when the list files exist in the checkout | the `Makefile` exports `FENOLITE_RESIDUE_TOKENS_FILE` and `FENOLITE_RESIDUE_BLOBS_FILE` when it finds the two list files in the ignored folder `private/` |
| the pre-commit hook (`make hooks`) | on, in the same way | `tools/hooks/pre-commit` sets the two variables before it scans the staged files |
| `uv run python tools/residue/scan.py`, called directly | off, unless a variable or a home-folder file is set | the script looks for no list inside the checkout |
| a linked worktree or a fresh clone | off | the list files are ignored by the version control, so they exist only where a maintainer put them |
| CI (the `unit` job) and the release workflow | off | the lists are never published, so no runner has them |

So a green CI run and a green release workflow prove the public patterns only. Before a release the
maintainer runs the gate locally, in the checkout that holds the lists:

```bash
make residue                                       # the tree, and dist/*.whl when present
FENOLITE_RESIDUE_TOKENS_FILE=<token file> FENOLITE_RESIDUE_BLOBS_FILE=<hash file> \
  uv run python tools/residue/scan.py --history    # every blob reachable from any ref
```

Both runs must end with `private gate: on` and 0 hits. The history run is recorded as a row of
`docs/evidence/residue-history.md` before the tag is made.

## Enforcement

`tests/unit/test_provenance.py` checks the first three rules. `tests/residue/test_scan.py` checks that
the gate section names the variables the scan reads.
