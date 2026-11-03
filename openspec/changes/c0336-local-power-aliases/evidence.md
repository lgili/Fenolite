# Local proof, 2026-11-02

Base: `d348705f6344a542c842e8cd8bd4423e75c9bca7`; implementation is the two-line KiCad-policy join in `drawn_connect.py`. The shared interpreter was bound to this isolated source with `PYTHONPATH=src:tests`. No model, schema, DSL, dependency, acceptance or baseline changed.

## Independent authored observation

`tests/kicad/schematic/test_drawn_power_alias.py` constructs original Mini native inputs, without using the resolver to make them valid. Native KiCad 10.0.6 exports their netlists as a subprocess. Before the fix the equal-name local/power positive failed: both sides contained all 34 pins, own had 34 groups and native had 33, with two own groups versus one native group. Unequal-name, missing-power and global-label controls passed independently. The pre-fix test log SHA-256 is `51c26076936fbc60c0c6622b1a15ec32ca4057e0dab4434845f6db571fdd2b86`.

Afterward, the same positive and negatives agree on complete partitions. A hierarchy control retains all 36 pins and proves that a root power does not promote an identically named child-local label without a child power declaration. Generic/default-policy and passive/power-output negatives remain separate. The authored native and model controls plus existing native bus/scalar neighbors passed: **62 passed**, exit 0, 42.85 seconds. Bound log SHA-256: `94f21c03d369e22860e53d5ccbd88c3b86799125b6d865de3d1ec2788166e80c`.

An earlier attempted after-run accidentally imported the shared interpreter's editable root source; its failures are retained as invalid repair validation, not reported as corrected-source results. The explicit source-bound rerun above supplies the proof. Earlier input-construction probes were also retained separately; only the valid original native inputs establish the measured rule.

## Public owner regression

Actual declared `kicad-demo-10-0-6-sch-036`, `037`, `038`, tag `10.0.6`, source commit `caf7377e9cb6`, passed all three focused census rows. The input manifest hashes remain checked. Each owner-context report retains **647/647 pins, 155/155 groups**, zero missing/extra pins and zero differing electrical groups. The original-native/lowered-native comparison also retains all 155 groups and names. Five dangling warnings and **two resolver/native naming differences among 72 named nets** remain visible; this fix claims electrical correction, not complete naming fidelity or full CAC acceptance.

The literal 130-row census on the earlier immutable snapshot remains an independent pre-fix census. Its results are not relabeled as fixed. Full required KiCad 9/10 jobs and root-owned combined fast gate remain task 2.2, uncompleted here.

## Static proof

Strict OpenSpec validation passed; ruff check and format check passed for the three touched Python files; pyright reported zero errors/warnings for `src/fenolite/model/drawn_connect.py`. Native format observation is registered as S-1282 with INFERRED scope pending required matrix CI.

VME public owner regression `kicad-demo-10-0-6-sch-106` also passed (201.20 seconds): all 6811 pins and 1800 electrical groups remain equal, with zero missing/extra pins. Existing 486 own/native naming differences among 967 named nets remain visible; no naming fidelity is claimed.

A separate strict OpenAir import at public revision `97acc80c223d75520c03fc44cab63cd9a3202c42` remains refused after the split correction. Independent original-source native comparison finds all 647 board/schematic pins but 156 board versus 155 schematic groups: one board-unconnected pin joins the 102-pin ground group in the original schematic. This upstream board/schematic discrepancy is not accepted, modified or hidden.
