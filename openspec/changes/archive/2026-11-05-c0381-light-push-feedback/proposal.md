## Why
Working pushes still spend ~40 minutes executing complete board flows. The user chose a 5–10 minute light-feedback target; every PR retains complete validation.

## What Changes
Classify measured whole-file board flows with long_flow; fast excludes these and runs Python 3.13, which was faster in both captured cohorts. Full and local check-fast retain all cases. Changes to tests or classification require full. Actual timing is required before claiming the target.

## Impact
CI/test classification only; no product code, assertions, golden bytes or full environments change.
