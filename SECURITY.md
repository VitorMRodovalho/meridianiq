# Security Policy

MeridianIQ handles scheduling data that may include sensitive project information (construction budgets, baselines, claim evidence). We take security reports seriously.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report suspected vulnerabilities privately via one of:

- GitHub's [private vulnerability reporting](https://github.com/VitorMRodovalho/meridianiq/security/advisories/new) (preferred — enables coordinated disclosure)
- Email: `vitorodovalho@gmail.com` with subject `[MeridianIQ security] <short description>`

Include:

- Affected component (backend engine, API endpoint, web page, MCP tool, parser)
- Reproduction steps, proof-of-concept, or minimal failing input
- Impact assessment (information disclosure, privilege escalation, denial of service, etc.)
- Your disclosure timeline preference

We aim to acknowledge within **3 business days** and provide an initial assessment within **7 business days**.

## Supported Versions

MeridianIQ follows a rolling release from `main`. Security fixes land on `main` and are tagged in the next minor release.

| Version | Supported |
|---|---|
| `v3.6.x` | ✅ current stable |
| `v3.5.x` and earlier | ⚠️ best-effort — upgrade to latest minor |

## Scope

**In scope:**

- The FastAPI backend (`src/api/`) — authentication, authorization (RLS), rate limiting, input validation, error disclosure
- The XER parser (`src/parser/`) — malicious file handling, encoding attacks, resource exhaustion
- Database abstractions (`src/database/`) — data access, RLS policy enforcement
- Supabase migrations (`supabase/migrations/`) — RLS coverage on user-owned tables
- The MCP server (`src/mcp_server.py`) — local-only by design; report if tools leak across projects
- The SvelteKit frontend (`web/`) — XSS, token handling, auth state leaks

**Out of scope:**

- Vulnerabilities in third-party dependencies (report upstream; we'll pick up fixes on their release)
- Social engineering or physical access to user machines
- Denial of service via trivially rate-limitable inputs
- Issues requiring an already-compromised user account with legitimate access

## Handling Sensitive Data

MeridianIQ deployments typically contain:

- Uploaded XER files (project schedules, sometimes contract-sensitive)
- CBS cost data (budget, contingency, commitments)
- Forensic analysis artifacts (delay windows, narratives)

If your report requires sample data, please use **synthetic fixtures only**. Do not share real project data over unencrypted channels.

## Credit

Reporters who follow this policy and request attribution will be credited in the CHANGELOG entry that ships the fix.
