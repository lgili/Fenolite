# Tasks

- [x] 1.1 Preserve the four original assignments and add an isolated, serial fifth partition.
  Proof: `uv run pytest tests/unit/test_ci_execution.py tests/unit/test_ci_profiles.py tests/unit/test_ci_workflow.py -q`.
- [x] 1.2 Verify the dedicated partition runs the unchanged scale fixture and that the complete
  CI and coverage gates pass on the exact commit.
  Proof: GitHub Actions run 42985032593 passed the full CI and coverage gates on
  `eee9f53a243ea0fed73aa25c5b7ce91240ed48f9`. The serial KiCad 10 partition ran all eight
  scale cases. The two-layer 150-component shapes case proposed 121 connections
  with zero unknowns in 293.097 s of routing, within the existing 600 s budget.
