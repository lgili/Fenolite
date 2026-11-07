## Observations

The failed Mac job used CPython 3.12.10 on image `macos-26-arm64`, version
`20261026.0455.2`; the logged OS is macOS 26.6.2, build 25G83. The loaded zlib
versions were not recorded. The job uploaded no byte-test output: its only
declared unit artifact is the Ubuntu library review.

On exact `96d687d1`, the maintainer's five hash-seed probes and Decimal precision
40 retain the complete expected map. Additional bounded probes retain it with
ROUND_CEILING and after fourteen PCB/body/pour tests in the same process.
ROUND_FLOOR changes one Board6/Data ZOOMMULT digit and produces a different hash
from the Mac failure. A system Python 3.13.5 probe lacks geo support: its actual
staged receipt records an outline fallback instead of the expected computed pour.
That difference is not evidence of a Python or zlib cause. Python 3.12.10 is not
installed locally. No probe reproduces the Mac hash.

## Decisions

Decided 2026-11-01: retain evidence before changing output. Observe the original
staged bytes from the same dry run; do not rebuild, change the seed or timestamp,
alter expected digests, normalize streams, relax validators or retry the test.

Decided 2026-11-01: the internal helper may accept its expected map while keeping
its existing returned map unchanged. Diagnostics require an explicit external
directory and a mismatch of exactly the authored `board_40parts@altium` row.
The directory has the fixed basename `fenolite-byte-diagnostics`, is absolute
and resolves outside the checkout. Existing diagnostic files are not replaced.

Decided 2026-11-01: validate the selected plan row's path, kind, size and digest,
then read only that PcbDoc through the existing plan store. Reuse Fenolite's own
CFB reader for stream hashes. Never copy a plan folder, inputs, source files,
other generated files or arbitrary caller paths. Keep capture bounded to 16 MiB.

The receipt names only the fixed row/output, expected and observed digests,
bounded native stream hashes, validated GitHub SHA when available, Python/OS/
machine/zlib facts, Decimal context, fixed geo-package versions, pour mode and
issue code/severity counts. It includes no working-directory, interpreter,
source, state-store or input paths and no issue messages. A missing/damaged plan
or capture error remains explicit and cannot turn the original mismatch green.

Decided 2026-11-01: CI enables the observer only for the Mac unit test step, in
its runner temporary directory. The failure artifact lists the fixed PcbDoc and
receipt paths individually. No wildcard, complete temporary folder, plan store
or private input is uploaded. Other unit environments retain their old behavior.

## Limits

The failed Mac binary is unavailable retrospectively. A future actual failing
Mac row and its captured stream receipt are required to localize that mismatch.
Local forced-mismatch tests prove diagnostic fidelity and failure preservation;
they do not establish its cause or a native application acceptance result.

## Early observation follow-up

Decided 2026-11-02: run the unchanged strict authored single-row guard once
before the complete Mac unit step, with a separate runner-temporary basetemp.
Only this diagnostic preprobe may continue after failure. Upload its two fixed
files immediately using an early-specific artifact name. The complete unit step
still runs with its original strict outcome and late artifact capture; it never
inherits continue-on-error. Reuse first-evidence preservation. A matching early
probe leaves no capture, so a later full-suite mismatch can still be retained.
Neither preprobe success nor its tolerated failure proves the full unit result.

## Same-run geometry trace follow-up

Observed 2026-11-02: the actual early Mac artifact from run 41406065844 at
46d788ee reproduces 01fdc848. Only Regions6/Data and ShapeBasedRegions6/Data
differ from Linux 7f49; each is 32 bytes longer. Typed comparison isolates four
holes in region zero. A Linux re-pour identifies a candidate offset, but Mac
intermediate operations are unavailable, so no first-divergence cause is claimed.

Decided 2026-11-02: optionally wrap the five Clipper methods used by the authored
pour before its original build, after validating the fixed source SHA-256,
source location, external destination and fresh output/context. Restore every
method in finally. Observe operands/results without changing them or calling
the producer twice. Hash canonical integer geometry and its original ordering
separately, so input ordering can be distinguished from geometry; retain counts and only
method/delta/join/tol/miter parameters, never vertices, paths or exception text.
Bound the trace to 512 operations, 200000 vertices per operand and 192 KiB of
rows; bound the entire receipt to 256 KiB. Limits/errors remain explicit and
never replace the original comparison. Publish only after a valid same-run
authored mismatch. Matching/default/unrelated/private cases publish no trace.
The existing two-file artifact policy and every native byte baseline stay fixed.

## Actual platform trace comparison

Observed 2026-11-02: run 41421198968 at
`ea762411cbb24bc5f9ba5a16d8b372ae7c720568` retains early Mac artifact
13128924288. Its 100126-byte ZIP has SHA-256
`e92aca174a459166b9d922c2e26f79d45ae71037b6d2afea96ae7d8d8c525fe6`;
the receipt SHA-256 is
`e5c307773830c5e7e0a2d30ce10042732807b4519d78414f8db4381a2243c331`.
Compare it with the immutable Linux forced-mismatch control built at
`d47b67a5a1d0336b9d1fbacdc3b4ecb84eeb7236`; its external source receipt
binds that clean head rather than its deliberate embedded unit-test SHA marker.
Its receipt SHA-256 is
`59d80bfea4c6e2258d7f3ba18b9c3d9818f582ea959ed8b32f25a8235b72eef7`.
Both heads have production source tree
`1d51b381d12335342c68ec72a17039ed5747e7b9` and identical observer, byte-helper
and guard files. Each native file equals its own same-run receipt digest:
Linux remains 7f49a78f and actual Mac remains 01fdc848.

Both traces contain 188 completed operations, indexed 0..187, with zero errors
and no truncation. All 176 preceding rows, 0..175, match completely. The first
difference is operation 176, `difference`, with identical parameters and
identical ordered and canonical input hashes. Its subject has one polygon,
10 holes and 2764 vertices; its clip has 1140 polygons and 5294 vertices.
Both outputs have one polygon and 402 holes, but Linux has 5624 vertices and
Mac has 5631. Their ordered and canonical output hashes respectively agree
within each platform but differ between platforms:
`0712053a64ed8590a6452d6a903ffe7dd76ab1f0e7ed9e922416e22b98429143`
versus `a54862c20352c7dacf10bf1e46394caf0e00e617d31e084b8e164ae79d7b5369`.
Only one later row differs: operation 179, `intersection`, receives different
input downstream of 176 and returns identical output. All other rows match.

The receipts report pyclipper 1.4.0, NumPy 2.5.3, Shapely 2.1.2 and Decimal
precision 28 on both platforms. Mac uses arm64 CPython 3.12.10; Linux uses
x86_64 CPython 3.12.14. These observations locate actual divergence inside the
same-input Boolean difference. They do not identify its internal arithmetic
cause, justify a geometry or byte-baseline change, or prove native application
acceptance or the complete CI result. In particular, offset 69 and caller input
ordering do not explain the first actual trace difference.
