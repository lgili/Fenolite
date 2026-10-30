## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, and `part-selection` once c0254 is archived) and the changes it builds on (c0248, c0254, c0259). Write under this task, with the date and the base commit:
  - c0254's final names for the query model, the row loader, the ranking function, `pick.series.SERIES` and the lock entry keys;
  - c0259's record keys and its stable-id function (decision 2 of `design.md`);
  - c0248's `DeviceDef` fields and rating units (decision 7);
  - where c0266 reads vendored library items and the `catalog` label it gives their rows;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0263-passive-families --strict`.
- [ ] 0.2 Register the public sources of the value-code schemes (`eia3`, `eia4`, `eia96` multiplier letters, `rkm`), each with what is used and what is not copied, and write `docs/formats/library/value-codes.md` with each rule and its label. Proof: `uv run pytest tests/unit/test_provenance.py -q`.

## 1. Schema and value codes

- [ ] 1.1 `pick/grammar/schema.py`: the `fenolite.family.v1` reader (closed keys, no float, fields, codes, matrix rows) and the dispatch in `pick/rows.py` (scenario "An unknown key"). Proof: `uv run pytest tests/unit/pick/grammar/test_schema.py tests/unit/pick/test_rows.py -q`.
- [ ] 1.2 `pick/grammar/valuecodes.py`: the four schemes, canonical spelling, exact integers (scenario "Codes round-trip"). Proof: `uv run pytest tests/unit/pick/grammar/test_valuecodes.py -q`.

## 2. Lint, expansion, decode

- [ ] 2.1 `pick/grammar/lint.py` and `codes.py`: pattern and field checks, prefix-free fields, matrix codes, unencodable values, `prefer`, sources (scenarios "A field without a placeholder", "An ambiguous field"). Proof: `uv run pytest tests/unit/pick/grammar/test_lint.py -q`.
- [ ] 2.2 `pick/grammar/expand.py`: canonical order, per-field pruning by a query, the validity matrix with `[[exclude]]`, `EXPANSION_LIMIT` (scenario "A query prunes before it expands"). Proof: `uv run pytest tests/unit/pick/grammar/test_expand.py -q`.
- [ ] 2.3 `pick/grammar/decode.py`: left-to-right parse, `in_matrix`, opaque tails, several families (scenarios "An excluded combination", "A decode names where it failed", "A tail is kept, not read"). Proof: `uv run pytest tests/unit/pick/grammar/test_decode.py -q`.
- [ ] 2.4 The round-trip property over every authored grammar (scenario "Every expanded MPN decodes to itself"). Proof: `uv run pytest tests/unit/pick/grammar/test_roundtrip.py -q`.

## 3. Picks

- [ ] 3.1 Encode in `pick/match.py`, candidates as c0248 devices, the candidate's canonical text and hash in the lock entry (scenarios "A query gives an exact MPN", "A pick of an exact MPN", "An unrelated grammar edit keeps the pick"). Proof: `uv run pytest tests/unit/pick/test_match.py tests/unit/pick/test_resolve.py -k grammar -q`.

## 4. Command

- [ ] 4.1 `cli/cmd_family.py` (`list`, `show`, `lint`, `decode`, `encode`, `expand`), `explain.toml` entries, the MCP tool by c0195's rule (scenarios "Family example is hermetic", "Every family code is explained"). Proof: `uv run pytest tests/unit/cli/test_family_cmd.py tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_explain_cmd.py -q`.

## 5. Examples, docs and guide

- [ ] 5.1 `examples/families/example_mlcc.toml` and `example_chip_r.toml` (illustrative, `Example Passive`, `example.invalid`, authored-for-Fenolite line) and a script that picks from them (scenario "No real series in the package"). Proof: `uv run pytest tests/unit/pick/grammar/test_shipped.py tests/unit/test_examples.py -k families -q`.
- [ ] 5.2 `docs/picking.md`, section "Families with ordering codes" (schema, value codes, matrix, lint, encode, decode, tails, the lock), and `docs/cli-contract.md`, "family". Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.3 Agent guide: a tested line for `family` on `commands`, for grammar families on `parts`, and for the `family.*` codes on `recovery`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Residue: every authored grammar and fixture carries its authored line; no real manufacturer, series code or table is in the package, examples or tests. Proof: `make residue`.
- [ ] 6.2 Evidence: `H-G-FAMILY-ROUNDTRIP` in `docs/hypotheses.md` with its measurement; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 6.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.
