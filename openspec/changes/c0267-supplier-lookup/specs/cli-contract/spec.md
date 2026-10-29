## ADDED Requirements

### Requirement: Supplier plugins in capabilities
`fenolite capabilities` SHALL list `result.suppliers`, sorted by name, each with `name`, `available` (credentials present, values never read out), `sends_data_offsite`, `sends`, `cache` and `extra_installed`, without reading a secret's value or opening a connection. `result.sends_data_offsite` MUST stay `false`.

#### Scenario: Suppliers listed offline
- **GIVEN** `socket.socket` patched to raise and only `FENOLITE_MOUSER_API_KEY` set
- **WHEN** `fenolite capabilities --json` runs
- **THEN** `result.suppliers` lists `digikey`, `farnell`, `mouser` and `nexar` with `sends_data_offsite: true`, only `mouser` is `available`, and `result.sends_data_offsite` is `false`

### Requirement: Supplier errors
`FEN-6005` SHALL mean that a supplier refused the credentials (exit 6, not retryable), with a hint naming the variables and keyring service to check; it MUST be listed in `docs/cli-contract.md` beside `FEN-6001` and `FEN-6003`.

#### Scenario: Rejected credentials
- **GIVEN** a fake transport answering 403 to the token request of `nexar`
- **WHEN** `fenolite pick examples/picks --propose "resistor(10kΩ)" --supplier nexar --allow-offsite --dry-run --json` runs
- **THEN** the exit code is 6, stderr holds `FEN-6005` with `retryable` false, and nothing is planned
