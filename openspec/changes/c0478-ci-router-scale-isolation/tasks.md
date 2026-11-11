# Tasks

- [x] 1.1 Preserve the four original assignments and add an isolated, serial fifth partition.
  Proof: `uv run pytest tests/unit/test_ci_execution.py tests/unit/test_ci_profiles.py tests/unit/test_ci_workflow.py -q`.
- [ ] 1.2 Verify the dedicated partition runs the unchanged scale fixture and that the complete
  CI and coverage gates pass on the exact commit.
