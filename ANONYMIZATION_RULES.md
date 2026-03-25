# Anonymization Rules

This document describes the anonymization methodology applied to all files in this repository.
All sensitive, proprietary, or personally identifiable information has been replaced with
generic placeholders to allow safe public sharing of the Power BI knowledge artifacts.

## Methodology

1. **Pattern Inventory** -- All connection strings, paths, URLs, company names, and personal
   identifiers were cataloged from the original Power BI extraction files.
2. **Find-and-Replace** -- A deterministic script applies every rule below in a single pass
   over every text file in the repository.
3. **Validation** -- After replacement, a grep-based scan checks for any surviving original
   patterns, IP addresses, email addresses, and real usernames.

## Replacement Categories

| Category | Replacement | Reason |
|----------|-------------|--------|
| Internal database IP addresses | `db-server.example.com` | Replaced internal network addresses |
| Cloud analytics workspace URLs | `adb-example.azuredatabricks.net` | Replaced cloud infrastructure identifiers |
| SharePoint tenant URLs | `sharepoint.example.com` | Replaced organizational SharePoint domain |
| Company name variants (all case variants) | `RealEstateCo` / `REALESTATECO` / `realestateco` | Replaced client company identity |
| Company abbreviations | `contoso` | Replaced tenant identifiers |
| Personal OneDrive paths | `my.sharepoint.com/personal/analyst_example_com` | Replaced personal cloud storage paths |
| Windows user profile paths | `C:\Users\analyst` | Replaced local machine user paths |
| Personal identifiers in URLs | `analyst_name` | Replaced PII in connection strings |
| Databricks warehouse identifiers | `warehouses/example-id` | Replaced infrastructure identifiers |
| Client organization names | `[ClientOrg]` | Replaced client company names in project context |
| Project program names | `[ProjectProgram]` | Replaced program-level identifiers |
| Division codes | `[DivisionCode]` | Replaced organizational division codes |
| ERP integration names | `ERP_INTEGRATION` | Replaced proprietary ERP system names |
| ERP vendor names | `ERP vendor` | Replaced third-party vendor identifiers |

## Validation Checklist

After sanitization, verify that **none** of the following categories appear anywhere in the repo:

- [ ] No internal IP addresses remain
- [ ] No company names or variants remain
- [ ] No cloud workspace identifiers remain
- [ ] No personal identifiers remain
- [ ] No email addresses remain
- [ ] No client organization names remain
- [ ] No project program names remain
- [ ] No division codes remain

## Note on Code Comments

Some Power Query and DAX code may contain Portuguese-language variable names and comments.
These are technical artifacts from the original development environment and do not contain
sensitive information. They have been preserved to maintain code accuracy.
