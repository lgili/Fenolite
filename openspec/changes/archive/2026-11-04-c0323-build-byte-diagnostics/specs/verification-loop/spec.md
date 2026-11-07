## ADDED Requirements

### Requirement: Bounded authored byte-failure evidence
The internal byte guard SHALL preserve its exact comparison. When explicitly enabled, a mismatch of the authored `board_40parts@altium` row MUST retain only its same-run staged PcbDoc and a bounded stream/runtime receipt outside the checkout. It MUST NOT rebuild, change a baseline, capture unrelated rows or inputs, overwrite prior evidence, or turn a failure into success.

#### Scenario: Original staged file is retained
- **WHEN** the authored row has a forced digest mismatch with capture enabled
- **THEN** the original assertion fails, the build runs once, and the retained file equals its staged bytes and digest
- **AND** the receipt's stream hashes match that file

#### Scenario: Capture is outside its boundary
- **WHEN** the row matches, capture is disabled, the row is unrelated, or the destination is inside the checkout
- **THEN** no diagnostic PcbDoc is written and the comparison result is unchanged

#### Scenario: Staging or evidence is unavailable
- **WHEN** staged bytes are missing or damaged, or the diagnostic already exists
- **THEN** no arbitrary payload is copied or existing evidence replaced
- **AND** the original digest mismatch still fails

### Requirement: Mac failure artifact stays scoped
The Mac unit job SHALL upload only the fixed authored diagnostic PcbDoc and its receipt after failure. It MUST NOT upload temporary trees, plan stores or unrelated/private inputs. Successful rows and other platforms MUST retain their existing behavior.

#### Scenario: Fixed failure artifact
- **WHEN** the workflow contract is checked
- **THEN** capture is enabled only for Mac and the failure upload lists exactly those two external files without a wildcard

### Requirement: Early Mac observation preserves strict unit outcome
The Mac unit job SHALL run the same strict authored single-row guard before the complete unit step and immediately upload only its two diagnostic files. Only this preprobe MAY continue after failure. The complete unit step MUST retain its strict outcome and late capture, using a distinct artifact name.

#### Scenario: Early evidence does not replace the complete test result
- **WHEN** the early guard fails or matches
- **THEN** the complete unit step still runs without continue-on-error
- **AND** a matching early guard leaves capture available for a later mismatch

### Requirement: Bounded same-run geometry hashes
The enabled authored guard SHALL trace geometry only after source and destination checks, restore wrapped methods in finally, and call the build once. A failed authored capture MUST retain bounded integer-geometry hashes/counts and operation parameters in its existing receipt, without vertices or paths. Matching/default/private cases MUST publish no trace; errors MUST preserve the original assertion and output bytes.

#### Scenario: Original geometry is observed once
- **WHEN** the exact authored guard has a forced mismatch with tracing enabled
- **THEN** its retained receipt contains same-run operation hashes while its native bytes and one-build assertion behavior stay unchanged

#### Scenario: Trace is unavailable or outside its boundary
- **WHEN** source checks fail, operation/size limits are reached, hashing fails, or the build raises
- **THEN** private geometry is not retained, limits remain explicit, methods are restored, and the original outcome stays in control
