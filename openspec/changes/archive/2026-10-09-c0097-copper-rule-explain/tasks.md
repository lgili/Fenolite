# Tasks

- [x] 0.1 Register revised scope, scenarios and evidence. Proof: `openspec validate c0097-copper-rule-explain --strict`.
- [x] 1.1 Replace entity traces with hashable candidate rows. Proof: `uv run pytest tests/unit/checks/test_copper_rule_review.py tests/unit/checks/test_clearance.py -q`.
- [x] 1.2 Explain the actual arc/fill judgment and normalize zone candidates. Proof: `uv run pytest tests/unit/checks/test_copper_rule_review.py -q`.
- [x] 1.3 Remove the unsupported track-size diagnostic and advice; preserve grouping exactly once. Proof: `uv run pytest tests/unit/checks/test_copper_rule_review.py -q`; `git grep -n -i -e width_explanation -e matches_subject -- . ':!openspec/changes/c0097-copper-rule-explain'` (exit 1: no matches).
- [x] 1.4 Prove item-kind/layer scopes and arc normalization without changing precedence. Proof: `uv run pytest tests/unit/checks/test_copper_rule_review.py -q`.
- [x] 2.1 Update guide, hypothesis and one Unreleased line; restore coordinator status pages. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`; `git diff origin/dev -- docs/roadmap.md openspec/README.md` (empty).
- [x] 2.2 Run and record all eleven handover commands in design Implementation notes on the rebased committed tree. Proof: all recorded commands exit 0. No full `make check`.
- [x] 2.3 Deliver one signed local commit; repeat validation, manifest/residue and DCO after recording results. Proof: `openspec validate --all --strict`; `uv run pytest tests/corpus/test_manifest.py tests/residue -q`; `python3 tools/dco_check.py origin/dev..HEAD`; `git diff --check`. No push, merge or archive.
