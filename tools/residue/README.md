# Residue scan

`scan.py` looks for material that must not be in a public repository: absolute user paths,
cloud-drive paths, internal revision or part-number shapes in data files, whole files known to be
derived from non-public material, and private tokens.

```bash
uv run python tools/residue/scan.py              # tree (+ dist/*.whl if present); exit 5 on hits
uv run python tools/residue/scan.py --staged     # what `git commit` would record
uv run python tools/residue/scan.py --list-patterns
make hooks                                        # install the pre-commit hook
```

Output lines are `path:offset:pattern-id`; the matched text is **never** printed.

## Sources

| Source | Where | Public? |
|---|---|---|
| structural regexes | `patterns.regex` | yes |
| whole-file SHA-256 list | `blobs.sha256` | yes (hashes only) |
| private tokens | `FENOLITE_RESIDUE_TOKENS` (inline, comma or newline separated), the file named by `FENOLITE_RESIDUE_TOKENS_FILE`, or `~/.fenolite-residue-tokens` | **never committed** |
| private whole-file SHA-256 list | the file named by `FENOLITE_RESIDUE_BLOBS_FILE`, or `~/.fenolite-residue-blobs` | **never committed** |

Token file format: one token per line; `#` starts a comment; a plain token matches
case-insensitively when not surrounded by letters or digits; a line starting with `re:` is a
regular expression. Blob files: `<sha256> <label>` per line.

A private gate with the maintainers' token list runs before every release; its content is not
published. No token list may be committed here, not even hashed (`tests/residue/test_no_token_list.py`).
