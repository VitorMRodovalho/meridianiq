# Attribution

## Upstream Project

This project builds upon concepts from [Xer-Reader-PowerBI](https://github.com/djouallah/Xer-Reader-PowerBI) by djouallah (Mimoune).

- **Repository**: https://github.com/djouallah/Xer-Reader-PowerBI
- **Original author**: djouallah
- **Last upstream commit**: 2020-02-18
- **License**: No license specified (all rights reserved by upstream author)

The upstream project provided the foundational concept of parsing Oracle P6 XER files using Power Query in Power BI, with dual XER text file and SQLite database support.

## Vitor Rodovalho's Contributions

All code in this repository represents Vitor Rodovalho's independent enhancements and new creations built upon the upstream concept:

- **v1-reader**: Enhanced version with composite keys, forecast integration, 36 DAX schedule analysis measures, and improved date handling
- **v1-compare**: Entirely new tool for comparing two P6 schedules (not present in upstream)
- **v1-program-schedule**: Production-grade dashboard with 130 DAX measures for enterprise schedule management

## Oracle P6 XER Format

The XER file format is defined by Oracle Corporation as part of Primavera P6 Professional Project Management. Format documentation is available at:
https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/index.htm

## License Note

This repository's MIT license applies to Vitor Rodovalho's contributions only. The upstream project has no specified license. Users should review the upstream repository for any licensing updates.
