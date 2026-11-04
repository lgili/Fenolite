## Why

Exact commit `96d687d1`, CI run `41359100272`, macOS job `125005408793`, fails
the authored `board_40parts@altium` byte guard. Only its PcbDoc differs: expected
`7f49a78f2726633ab31fbe956a187bbd85fee9af8878d42710f10a5930adc6a1`, observed
`01fdc8486cd05e964850311b2e473487759ee11f81891da0bfe43220f8698911`.
Model JSON and the other native files match. The dry-run helper records hashes
and CI retains no corresponding file, so the failed streams cannot be compared.

## What Changes

Add optional internal test diagnostics for this one authored row. On mismatch,
copy only its original staged PcbDoc and a bounded receipt with per-stream hashes
to a fixed external diagnostic folder. Enable it in the Mac unit job and upload
only those two files after failure. Keep the original equality assertion.

## Capabilities

- Modified: `verification-loop`.

## Impact

Only the byte-test helper, its tests, CI artifact wiring and documentation change.
No writer, model, CLI, public schema, dependency, baseline, native gate or evidence
level changes. Root owns publication and complete validation. A successful
diagnostic test is not a resolution of the original Mac mismatch.
