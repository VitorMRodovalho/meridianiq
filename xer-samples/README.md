# XER Sample Files

No real XER files are included in this repository. XER files contain client schedule data (activity names, dates, resource assignments, WBS structures) that is project-specific and confidential.

## Where to Find Sample XER Files

### Upstream Repository
The original Xer-Reader-PowerBI project includes a sample XER file:
https://github.com/djouallah/Xer-Reader-PowerBI/tree/master/xerfile

### Oracle Documentation
Oracle provides XER format documentation and data mapping references:
https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/index.htm

### Creating Your Own
If you have access to Oracle Primavera P6:
1. Open a project in P6 Professional
2. File > Export > XER format
3. Select the project(s) to export
4. The resulting `.xer` file can be used with the Power Query parsers in this repository

## XER File Format

See [docs/xer-format-reference.md](../docs/xer-format-reference.md) for a detailed description of the XER file structure, table definitions, and field descriptions.
