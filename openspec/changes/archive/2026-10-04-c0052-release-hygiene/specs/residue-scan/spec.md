## ADDED Requirements

### Requirement: Private gate is documented
`docs/provenance.md` SHALL hold a section "Private residue gate" that states, from the code of `tools/residue/scan.py` and the `Makefile`:
- what `FENOLITE_RESIDUE_TOKENS`, `FENOLITE_RESIDUE_TOKENS_FILE` and `FENOLITE_RESIDUE_BLOBS_FILE` do, their order of precedence and the two home-folder files read when they are unset;
- that the scan's last line reports the gate as `on` or `skipped`, and that a skipped gate is not an error;
- that the `Makefile` turns the gate on when the private list files exist, so `make residue`, `make check` and `make check-fast` run it, and a bare `scan.py` call does not;
- that CI and the release workflow run with the gate off, because the lists are never published;
- that the maintainer runs the gate locally, over the tree and over the history, before a release, and records the history run in `docs/evidence/residue-history.md`.

The section MUST NOT quote a private token, a private hash or the content of any private file.

#### Scenario: Section present
- **WHEN** `uv run pytest tests/residue/test_scan.py -k gate_documented` reads `docs/provenance.md`
- **THEN** the page holds the heading "Private residue gate" and names the three variables, each of which occurs in `tools/residue/scan.py`

#### Scenario: Gate off without a list
- **GIVEN** none of the three variables is set and neither home-folder file exists
- **WHEN** `uv run python tools/residue/scan.py` runs on a clean tree
- **THEN** the exit code is 0 and the last line ends with `private gate: skipped (no private list configured)`
