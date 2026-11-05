## 1. Light feedback
- [x] 1.1 Add whole-file long_flow classification and fast filtering; preserve complete selection and guard test changes. Proof: focused policy/selection tests and collect-only subset comparison.
- [x] 1.2 Document profiles and Unreleased; validate format, lint and OpenSpec.
- [x] 1.3 Partition light feedback across two file-preserving runners and require a fail-closed exact-commit union audit. Proof: focused partition, receipt, gate and workflow tests; actionlint.
- [x] 1.4 Increase light parallelism to three after the measured two-runner workflow exceeded ten minutes. Keep exact union and gates. Proof: focused tests, static checks, actionlint. Live measurement remains in 2.1.
## 2. Integration
- [ ] 2.1 Publish and measure a live fast probe; confirm complete CI on exact commit before integration. No merge while mandatory checks fail or are missing.

Local proof: 150 focused policy/execution/workflow/light controls passed; lint, format, types, residue, actionlint and strict OpenSpec passed. Portable full collection retains every prior id with three added controls. Native/resource parameter sets differ between local installed resources and the portable CI environment; do not compare those as lost tests. Live timing and full validation remain pending.

Two-partition proof: 152 focused controls passed; actionlint passed. The light union is unchanged.
