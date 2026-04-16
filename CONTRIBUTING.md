# Contributing to MeridianIQ

Thank you for your interest in contributing to MeridianIQ. This document outlines how to report issues, submit code, and where help is most needed.

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include the MeridianIQ version, Python version, and OS
- For parsing issues, include a minimal XER file (with sensitive data removed) that reproduces the problem
- For analysis issues, describe the expected vs. actual result with specific metric values

## Code Contributions

1. Fork the repository and create a feature branch from `main`
2. Install development dependencies: `pip install -e ".[all]"`
3. Write tests for any new functionality
4. Ensure all tests pass: `pytest`
5. Follow existing code style (enforced by `ruff`)
6. Submit a pull request with a clear description of the change

### Code Standards

- Python 3.14+ type hints on all public functions
- Docstrings on all public classes and functions (Google style)
- MIT license header on all source files
- No client names, proprietary data, or credentials in code
- Reference industry standards (AACE RP, DCMA, PMI) in docstrings where applicable
- Keep test fixtures synthetic -- never commit real project data

### Branch Naming

- `v0.X-feature` for version-aligned feature branches
- `fix/description` for bug fixes
- `docs/description` for documentation changes

## Areas Where Help is Needed

- **XER format edge cases:** P6 versions produce subtle format variations; more test files help
- **Calendar-aware duration calculations:** Converting hours to workdays using P6 calendar definitions
- **CI/CD pipeline:** GitHub Actions for test, lint, build, deploy on merge to main
- **E2E tests:** Playwright test suite for critical user flows
- **Additional schedule formats:** Microsoft Project XML, Asta Powerproject
- **Internationalization:** Date format handling, currency support, translations (i18n infrastructure)
- **Methodology validation:** Testing against real-world schedules and industry expert review
- **International contract compliance:** FIDIC, NEC, JCT provisions
- **Performance optimization:** 50,000+ activity schedules

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1 plus domain-specific expectations for the construction and engineering scheduling community (synthetic fixtures only, cite published standards when debating methodology, treat schedules as evidence).

## Security

See [SECURITY.md](SECURITY.md) for responsible disclosure. Do not open public issues for suspected vulnerabilities.
