## Summary

<!-- One or two sentences on what changed and why. Lead with the outcome, not the implementation. -->

## Changes

<!-- Bullet list of what's in the diff. Call out anything non-obvious. -->
-
-

## Standards / references

<!-- If this touches analysis logic, cite the AACE / DCMA / ANSI / SCL / GAO / PMI standard that governs the calculation. Delete this section for pure plumbing PRs. -->

## Test plan

<!-- How did you verify this? Commands run, pages visited, fixtures used. Synthetic data only — never commit real project data. -->
- [ ]
- [ ]

## Docs touched

<!-- Mark any that apply — helps reviewers see KB impact quickly. -->
- [ ] `CHANGELOG.md` entry added
- [ ] `docs/api-reference.md` regenerated (`python3 scripts/generate_api_reference.py`)
- [ ] `docs/methodologies.md` regenerated (`python3 scripts/generate_methodology_catalog.py`)
- [ ] `docs/mcp-tools.md` regenerated (`python3 scripts/generate_mcp_catalog.py`)
- [ ] Other: ___

## Checklist

- [ ] Tests added / updated and passing locally (`python3 -m pytest tests/ -q`)
- [ ] Ruff clean (`ruff check src/ tests/ scripts/ && ruff format --check src/ tests/ scripts/`)
- [ ] Frontend check passes if UI changed (`cd web && npm run check`)
- [ ] No real project data, client names, or credentials in commits
- [ ] Follows [CONTRIBUTING.md](../CONTRIBUTING.md) code standards
