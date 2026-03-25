# v1-program-schedule -- Production Enterprise Schedule Dashboard

Production-grade enterprise schedule dashboard built on the Reader parsing patterns. 130 DAX measures and 84 M parameters for comprehensive schedule management.

## Overview

This is the production evolution of the v1-reader, adapted for a major infrastructure program. It extends the basic XER parsing with enterprise-grade features including activity code filtering, user-defined field support, financial period integration, and multi-XER schema management.

## Scale

| Metric | Count |
|--------|-------|
| DAX Measures | 130 |
| M Parameters | 84 |
| Power Queries | 20 |
| Schema Columns | 269 |
| Data Model Relationships | 10 |
| DAX Calculated Columns | 63 |

## Key Differences from v1-reader

- **130 DAX measures** (vs 36 in Reader) covering additional schedule health metrics
- **84 M parameters** for configuration management (vs simple path parameters)
- **Activity code integration** (ACTVCODE/ACTVTYPE tables) for filtering by P6 activity codes
- **User-defined fields** (UDFTYPE/UDFVALUE) for custom P6 field support
- **Multi-XER schema management** with schema helper tables for handling different XER export versions
- **Production-hardened queries** with additional error handling and type safety

## Anonymization Note

This dashboard was heavily anonymized from its production deployment. Connection parameters, project-specific references, client names, and infrastructure identifiers have been replaced with generic placeholders. The DAX logic and Power Query patterns are preserved intact.

## Contents

```
v1-program-schedule/
+-- dax-measures/measures.md    -- All 130 DAX measure definitions
+-- power-query/queries.md      -- All 20 Power Query/M expressions
+-- data-model/
|   +-- schema.csv              -- Table and column schema
|   +-- relationships.csv       -- Model relationships
+-- README.md                   -- This file
```
