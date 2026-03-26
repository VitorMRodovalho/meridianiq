# MeridianIQ

**The intelligence standard for project schedules.**

Open-source schedule intelligence platform that transforms Oracle Primavera P6 XER files into actionable insights -- from DCMA validation to earned value forecasting.

---

## Vision

Construction and infrastructure projects lose billions annually to schedule disputes, undetected delays, and poor cost forecasting. MeridianIQ brings forensic-grade analysis to every project team -- not just the ones that can afford proprietary consultants.

## Capabilities

| Module | Standard | Status |
|--------|----------|--------|
| XER Parser | Oracle P6 XER format | Stable |
| DCMA 14-Point Assessment | DCMA IPMR/IMS guidelines | Stable |
| Critical Path Method (CPM) | PMI Practice Standard for Scheduling | Stable |
| Schedule Comparison | SCL Delay and Disruption Protocol | Stable |
| Forensic Window Analysis | AACE RP 29R-03 | Stable |
| Time Impact Analysis (TIA) | AACE RP 52R-06 | Stable |
| Contract Compliance | AIA A201 / ConsensusDocs 200 / FIDIC | Stable |
| Earned Value Management (EVM) | ANSI/EIA-748, AACE RP 10S-90 | v0.4-dev |

## Architecture

```
meridianiq/
  src/
    parser/          # XER file parser (models + reader)
    analytics/       # Analysis engines (DCMA, CPM, comparison, forensics, TIA, EVM)
    api/             # FastAPI REST endpoints
  web/               # SvelteKit + Tailwind CSS frontend
  tests/             # pytest test suite with fixture generators
```

**Stack:** Python 3.12+ / FastAPI / Pydantic v2 / NetworkX / SvelteKit 2 / Tailwind CSS 4

## Roadmap

| Version | Codename | Focus | Status |
|---------|----------|-------|--------|
| v0.1 | Parser | XER parsing, DCMA 14-point, CPM | Released |
| v0.2 | Forensics | Schedule comparison, window analysis, delay trends | Released |
| v0.3 | Claims | TIA (AACE 52R-06), contract compliance | Released |
| v0.4 | Controls | Earned Value Management (SPI/CPI/EAC/S-curve) | In Progress |
| v0.5 | Risk | Monte Carlo simulation, risk register | Planned |
| v1.0 | Production | PostgreSQL persistence, auth, multi-tenant | Planned |
| v1.5 | Intelligence | ML anomaly detection, schedule health scoring | Planned |
| v2.0 | Enterprise | Multi-project portfolio, P6 XML support, API keys | Planned |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+

### Backend

```bash
# Clone and install
git clone https://github.com/vitormrodovalho/meridianiq.git
cd meridianiq
pip install -e ".[all]"

# Run API server
uvicorn src.api.app:app --reload --port 8000

# Run tests
pytest
```

### Frontend

```bash
cd web
npm install
npm run dev
```

### Docker

```bash
docker compose up --build
```

Open http://localhost:3000 for the web UI, or http://localhost:8000/docs for the API.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, submitting code, and areas where help is needed.

## Acknowledgments

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for upstream projects, tools, and standards that made this possible.

## Citation

If you use MeridianIQ in academic work, please cite:

```bibtex
@software{rodovalho2025meridianiq,
  author       = {Rodovalho, Vitor Maia},
  title        = {MeridianIQ: Open-Source Schedule Intelligence Platform},
  year         = {2025},
  url          = {https://github.com/vitormrodovalho/meridianiq},
  license      = {MIT}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.

Copyright (c) 2025 Vitor Maia Rodovalho
