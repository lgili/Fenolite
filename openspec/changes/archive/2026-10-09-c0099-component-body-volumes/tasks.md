# Tasks

Status: all review corrections and ten handover gates passed after the c0136 rebase; ready for coordinator review.

- [x] R1 Resolve rebase conflicts, source allocations and scope promises. Proof: `openspec validate c0099-component-body-volumes --strict`; `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
- [x] R2 Correct unknown-body census and add its authored regression. Proof: `uv run pytest tests/unit/backends/altium/test_body_volume_import.py tests/unit/backends/altium/adapter -q`.
- [x] R3 Align code tables, model and CLI documentation, explain entry and legal annex. Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/test_legal_docs.py tests/unit/test_provenance.py -q`; `rg -n model.body-volume docs/cli-contract.md docs/design-model.md`.
- [x] R4 Generate a genuine v0.2.0 fixture and compatibility regression, register its manifest. Proof: `uv run pytest tests/unit/model/test_body_volumes.py tests/corpus/test_manifest.py -q`; genuine v0.2.0-reader rejection probe (exit 0).
- [x] R5 Measure public body counts, validation changes and project exits before/after, update evidence. Proof: `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus -q -k "bod"`; `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_documents.py -q` with an external census file.
- [x] R6 Regenerate schemas/matrix and run all requested handover gates on the signed committed tree. Proof: `openspec validate --all --strict`; `make check-fast`; `uv run --isolated --python 3.11 --extra dev pytest tests/unit -q -n 4 -p no:cacheprovider`; `uv run pytest tests/corpus/test_manifest.py tests/residue -q`; `uv run python tools/gen_schemas.py --check`; `uv run python tools/gen_evidence_matrix.py --check`; `python3 tools/dco_check.py origin/dev..HEAD`; `uv run pytest tests/unit/model tests/unit/analysis/test_body_volumes.py tests/unit/backends/altium/test_body_volume_import.py tests/unit/backends/altium/test_body_projection_facts.py tests/unit/backends/altium/adapter tests/unit/cli/test_explain_cmd.py tests/unit/test_schema_drift.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py -q`; `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus -q -k "bod"`; `FENOLITE_REQUIRE=corpus FENOLITE_CENSUS_OUT=<external-file> uv run pytest tests/corpus/test_altium_documents.py -q`. No full make check, push, merge or archive.

The design records every full gate command, exit and result on the rebased tree. The last amendment
only records proofs: post-amend OpenSpec, manifest/residue, DCO and documentation checks pass;
source/test subtree ids stay identical to those of the gated commit. No push, merge or archive.
