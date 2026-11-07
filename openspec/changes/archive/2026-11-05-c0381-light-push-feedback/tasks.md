## 1. Light feedback
- [x] 1.1 Add whole-file long_flow classification and fast filtering; preserve complete selection and guard test changes. Proof: focused policy/selection tests and collect-only subset comparison.
- [x] 1.2 Document profiles and Unreleased; validate format, lint and OpenSpec.
- [x] 1.3 Partition light feedback across two file-preserving runners and require a fail-closed exact-commit union audit. Proof: focused partition, receipt, gate and workflow tests; actionlint.
- [x] 1.4 Increase light parallelism to three after the measured two-runner workflow exceeded ten minutes. Keep exact union and gates. Proof: focused tests, static checks, actionlint. Live measurement remains in 2.1.
## 2. Integration
- [x] 2.1 Publish and measure a live fast probe; confirm complete CI on exact commit before integration. No merge while mandatory checks fail or are missing.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): fast probe 41948075827 green (fast partitions 5m03, 12m21, 6m22; 17m33 wall after the first job); complete CI CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete.

Local proof: 150 focused policy/execution/workflow/light controls passed; lint, format, types, residue, actionlint and strict OpenSpec passed. Portable full collection retains every prior id with three added controls. Native/resource parameter sets differ between local installed resources and the portable CI environment; do not compare those as lost tests. Live timing and full validation remain pending.

Two-partition proof: 152 focused controls passed; actionlint passed. The light union is unchanged.
