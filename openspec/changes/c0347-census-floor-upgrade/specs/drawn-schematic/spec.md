## ADDED Requirements

### Requirement: Qualified floor-upgrade census evidence
The census SHALL preserve an original below-floor input's explicit refusal and immutable manifest identity. It SHALL NOT relabel that original as equal. A separately identified official-tool upgraded copy MAY qualify as `upgraded/equal` only after exact tool/version/digest provenance and complete SAME-native10 original/upgraded and own/lowered/native pin/partition/name comparisons. No intersection, accepted difference, loss flag or uncompleted comparison may substitute for proof.

#### Scenario: Original remains below the supported reader floor
- **GIVEN** checked original bytes whose actual format is below the published floor
- **WHEN** the core reader and native census run
- **THEN** the original refusal is retained without writes and the independently exported native-old graph is recorded separately

#### Scenario: Upgrade is electrically exact
- **GIVEN** immutable originals and their recorded official CLI10 copy upgrade
- **WHEN** every complete native-original/upgraded and supported own/lowered/native comparison succeeds
- **THEN** only the upgraded electrical probe receives the qualified result, retaining the original refusal and every source digest

#### Scenario: Partial or changed upgrade cannot qualify
- **WHEN** an upgrade changes a pin, partition, net name, original input or expected output digest, or a required comparison is missing
- **THEN** the probe remains failed/partial and no equality or original-support claim is made

### Requirement: Versioned floor evidence requires both native jobs
The required same-commit native9 and native10 jobs SHALL retain complete primary row records and link the same checked originals. Native10 SHALL supply every required copy-upgrade probe; native9 SHALL NOT pretend to read newer upgraded formats. Missing inputs, artifacts, graph/name proofs or commit identities SHALL fail the bridge gate. Other strict failures and incompatible primary records SHALL remain visible.

#### Scenario: Native9 lacks the upgrade operation
- **WHEN** the native9 job records an original floor boundary
- **THEN** it retains its real native-old evidence and missing-upgrade capability, while the independently required native10 job supplies the upgrade proof

#### Scenario: Native major versions disagree on the original legacy graph
- **GIVEN** the maintainer-authorized native10-only copy-upgrade qualification and a below-floor original
- **WHEN** actual native9 and native10 original observations differ
- **THEN** both complete observations and the original refusal remain visible without any9 equivalence claim
- **AND** qualification still requires every exact native10 original/upgraded pin, partition and name plus all supported own/lowered/native comparisons
