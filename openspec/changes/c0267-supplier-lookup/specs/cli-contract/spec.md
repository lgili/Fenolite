## ADDED Requirements

### Requirement: Supplier plugins in capabilities
`fenolite capabilities` SHALL list `result.suppliers`, sorted by name, each with `name`, `available` (verified source readiness), `credential_env_present` (names only), `sends_data_offsite`, `sends`, `cache` and `extra_installed`, without reading a secret's value or opening a connection. `result.sends_data_offsite` MUST stay `false`.

#### Scenario: Suppliers listed offline
- **GIVEN** `socket.socket` patched to raise and only `FENOLITE_MOUSER_API_KEY` set
- **WHEN** `fenolite capabilities --json` runs
- **THEN** `result.suppliers` lists `digikey`, `farnell`, `mouser` and `nexar` with `sends_data_offsite: true`, only `mouser` reports environment credentials present, while unverified source policies remain unavailable, and `result.sends_data_offsite` is `false`

### Requirement: Supplier errors
`FEN-6005` SHALL mean that a supplier refused the credentials (exit 6, not retryable), with a hint naming the variables and keyring service to check; it MUST be listed in `docs/cli-contract.md` beside `FEN-6001` and `FEN-6003`.

#### Scenario: Rejected credentials
- **GIVEN** an authored enabled test plugin answering 403
- **WHEN** `fenolite pick examples/picks --propose "resistor(10kΩ)" --supplier authored --allow-offsite --dry-run --json` runs
- **THEN** the exit code is 6, stderr holds `FEN-6005` with `retryable` false, and nothing is planned


### Requirement: Filtered transient plan results
Commands MAY provide a filtered subset of result data for plan storage. Filtering MUST only remove data and MUST NOT change inputs, issues, plan metadata, receipt metadata or staged write bytes. Supplier offers and reported attributes MUST appear only in the immediate reply; confirmation MUST replay the exact reviewed bytes without another lookup.

#### Scenario: Offers do not outlive a reply
- **GIVEN** an authored supplier dry run displays an offer
- **WHEN** its stored plan and confirmation reply are inspected
- **THEN** neither holds the offer and the receipt digest matches the reviewed bytes without a request
