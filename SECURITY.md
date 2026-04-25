# Security Policy

## Supported Versions

Security fixes are applied to the default branch. Consumers should run the latest commit or latest tagged release when available.

## Reporting a Vulnerability

Do not open a public issue for suspected vulnerabilities. Use GitHub private vulnerability reporting if it is enabled for this repository, or contact the repository owner through their GitHub profile.

Please include:

- A clear description of the issue and affected component
- Reproduction steps or a minimal proof of concept
- Potential impact and any known mitigations
- Whether credentials, customer data, warehouse roles, or generated datasets may be exposed

## Security Expectations

- Never commit Snowflake credentials, private keys, connection profiles, or customer data.
- Keep demo data synthetic unless a customer-specific private fork is explicitly approved.
- Prefer least-privilege roles and dry-run validation for local development.
- Run local verification before merging:

```bash
python -m ruff check common demos
```
