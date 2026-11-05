## Why

The public CI runs 41294183261, 40987149835 and 40951865684 spend 84–101 minutes in the KiCad 10 job, almost entirely executing tests. Every working-branch push currently starts the complete matrix. Faster feedback must not turn skipped jobs, missing partitions or omitted tests into a complete result.

## What Changes

- Add conservative fast/full event profiles: all pull requests, integration branches, unknown events/branches and CI-control changes require full; only recognized working-branch pushes and explicit working-branch manual fast requests can use fast.
- Keep the complete five-platform/Python unit matrix, both KiCad majors, all existing corpus/heavy inputs, routers, viewer, MCP and packaging coverage at the full gate.
- Partition KiCad 10 into four file-preserving shards, retaining loadfile scheduling and within-file order.
- Record complete collections, planned selections, observed outcomes, exit codes, durations and exact commit identity; audit the disjoint exhaustive union before a full result can pass.
- Close the existing gap where resource-dependent unit tests skip in the unit matrix but are outside native job roots. Include their whole files in KiCad 10 and cross-audit resource cases against the Linux unit inventory, without repeating every tool-free unit file.
- Run platform-independent static checks once, publish timing/JUnit artifacts, and provide distinct fast/full aggregate checks. A fast result can never satisfy the full aggregate.
- Start three measured expensive whole files early with the locked loadfile scheduler, preserving all membership and internal ordering; prove the scheduling option with actual worker execution.
- Reuse identical complete owner-project census measurements within one test module, after checking
  every copied input again. Retain every sheet case, owner/instance context, strict failure and
  independent report; expose whether its project measurement was reused.
- Keep nightly/release responsibilities unchanged; document required-check configuration and migration.

## Impact

CI tooling/workflows, test-only census execution, regression tests, agent workflow instructions and documentation only. No public Fenolite command, runtime dependency, private board data, corpus assertions or comparison tolerance changes. Full local suites remain prohibited; full proof comes from exact-head CI.

## Non-goals

No dependency-based test omission, replacement of the loadfile scheduler/grouping, automatic branch-protection mutation, release publication change or migration of required heavy tests to nightly.

## Evidence level required

INFERRED for authored policy/partition/gate regressions; complete exact-head GitHub CI for integration. Historical public timing sources: https://github.com/lgili/Fenolite/actions/runs/41294183261 and https://github.com/lgili/Fenolite/actions/runs/40987149835.
