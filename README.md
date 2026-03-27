<div align="center">

# MeridianIQ

**The intelligence standard for project schedules**

Open-source schedule intelligence platform — from validation to prediction.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SvelteKit](https://img.shields.io/badge/SvelteKit-2.0-FF3E00?logo=svelte&logoColor=white)](https://kit.svelte.dev)
[![NetworkX](https://img.shields.io/badge/NetworkX-CPM%20Engine-4C9A2A)](https://networkx.org)
[![NumPy](https://img.shields.io/badge/NumPy-Monte%20Carlo-013243?logo=numpy&logoColor=white)](https://numpy.org)
[![Tests](https://img.shields.io/badge/Tests-222%20passing-brightgreen)]()
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)

[**Documentation**](docs/) · [**Contributing**](CONTRIBUTING.md) · [**Changelog**](BUGS.md)

</div>

---

## Overview

**MeridianIQ** is an open-source platform for project schedule analysis in construction and engineering. It provides the tools that schedulers, project controls professionals, and forensic delay analysts need — transparent, auditable, and free.

Every methodology is traceable to published standards: AACE Recommended Practices, DCMA 14-Point Assessment, SCL Delay and Disruption Protocol, and GAO Schedule Assessment Guide.

> **Author:** Vitor Maia Rodovalho

---

## Key Numbers

| Indicator | Value |
|-----------|-------|
| Analysis engines | 8 (Parser · CPM · DCMA · Compare · CPA · TIA · EVM · Monte Carlo) |
| Tests passing | 222 |
| Python source lines | ~9,150 |
| Frontend pages | 12 |
| API endpoints | 32 |
| Released versions | 5 (v0.1.0 → v0.5.0) |
| Monthly infra cost | $0 |

---

## Capabilities

| Capability | Standard | Version |
|-----------|----------|---------|
| **XER Parsing** — Custom MIT-licensed Primavera P6 parser | — | v0.1 |
| **Schedule Validation** — DCMA 14-Point Assessment with scoring | DCMA EVMS | v0.1 |
| **Critical Path Analysis** — Forward/backward pass, total float | CPM (Kelly & Walker, 1959) | v0.1 |
| **Schedule Comparison** — Multi-layer matching, manipulation detection | — | v0.1 |
| **Forensic Analysis** — Contemporaneous Period Analysis | AACE RP 29R-03 | v0.2 |
| **Time Impact Analysis** — Delay fragments, impacted vs unimpacted CPM | AACE RP 52R-06 | v0.3 |
| **Contract Compliance** — Automated provision checks | AIA A201, SCL Protocol | v0.3 |
| **Earned Value Management** — SPI, CPI, EAC, S-Curve | ANSI/EIA-748 | v0.4 |
| **Monte Carlo Simulation** — QSRA with PERT-Beta distributions | AACE RP 57R-09 | v0.5 |

---

## Architecture

```mermaid
graph TB
    subgraph Client
        A[Browser] --> B[SvelteKit + Tailwind]
        B --> C[SVG Charts]
    end

    subgraph "FastAPI Backend"
        D[REST API<br/>32 endpoints]
        D --> E[XER Parser<br/>Streaming · Encoding Detection]
        D --> F[CPM Engine<br/>NetworkX]
        D --> G[DCMA 14-Point<br/>Validation]
        D --> H[Comparison Engine<br/>Multi-layer Matching]
        D --> I[Forensics<br/>CPA · Window Analysis]
        D --> J[TIA Engine<br/>Fragment Insertion]
        D --> K[EVM Engine<br/>SPI · CPI · S-Curve]
        D --> L[Risk Engine<br/>Monte Carlo · PERT-Beta]
    end

    subgraph "Data Layer"
        M[(In-Memory Store<br/>v0.x prototype)]
        N[(SQLite → PostgreSQL<br/>v1.0 planned)]
    end

    B <-->|HTTP| D
    E --> M
    F --> M
    D --> M

    style A fill:#1a1a2e,color:#fff
    style D fill:#009688,color:#fff
    style F fill:#4C9A2A,color:#fff
    style L fill:#013243,color:#fff
    style M fill:#3FCF8E,color:#fff
```

---

## Analysis Pipeline

```mermaid
flowchart LR
    A[Upload XER] --> B[Parse]
    B --> C[Validate<br/>DCMA 14-Point]
    B --> D[CPM<br/>Critical Path + Float]
    B --> E[Compare<br/>Two Versions]
    E --> F[Manipulation<br/>Detection]

    C --> G[Dashboard]
    D --> G
    F --> G

    E --> H[CPA<br/>Window Analysis]
    H --> I[Delay Waterfall]

    B --> J[TIA<br/>Fragment Insertion]
    J --> K[Impacted CPM]
    K --> L[Responsibility<br/>Matrix]

    B --> M[EVM<br/>Cost Integration]
    M --> N[S-Curve<br/>SPI · CPI]

    B --> O[Monte Carlo<br/>1000 iterations]
    O --> P[Histogram<br/>P10 · P50 · P80 · P90]
    O --> Q[Tornado<br/>Sensitivity]
    O --> R[Criticality<br/>Index]

    style A fill:#FF3E00,color:#fff
    style G fill:#009688,color:#fff
    style I fill:#D97757,color:#fff
    style P fill:#013243,color:#fff
```

---

## Roadmap

| Version | Codename | Focus | Status |
|---------|----------|-------|--------|
| v0.1.0 | **Foundation** | Parse · Validate · Compare · Visualize | ✅ Released |
| v0.2.0 | **Forensics** | CPA / Window Analysis | ✅ Released |
| v0.3.0 | **Claims** | TIA + Contract Compliance | ✅ Released |
| v0.4.0 | **Controls** | EVM / WBS-CBS-BOQ | ✅ Released |
| v0.5.0 | **Risk** | Monte Carlo / QSRA | ✅ Released |
| v0.6 | **Cloud** | Supabase + Fly.io + CF Pages | 🚧 Next |
| v0.7 | **Identity** | Auth + RLS + Ownership | 🔜 Planned |
| v0.8 | **Intelligence** | Float Trends + Early Warning | 🔜 Planned |
| v0.9 | **Polish** | UX + Performance + CI/CD | 🔜 Planned |
| v1.0 | **Enterprise** | Teams + IPS Reconciliation + Audit | 🔜 Planned |
| v2.0 | **AI** | ML Predictions · NLP · Anomaly Detection | 🔮 Future |

See [full roadmap with architecture decisions](docs/v06-planning/ROADMAP_v06_to_v20.md).

---

## Quick Start

```bash
# Clone
git clone https://github.com/VitorMRodovalho/meridianiq.git
cd meridianiq

# Backend
pip install -e ".[dev]"
python -m uvicorn src.api.app:app --reload --port 8000

# Frontend
cd web
npm install
npm run dev -- --port 5173

# Open http://localhost:5173
```

**Or with Docker:**
```bash
docker compose up
```

---

## Technical Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12+ · FastAPI · Pydantic v2 |
| **CPM Engine** | NetworkX (BSD) |
| **Monte Carlo** | NumPy (BSD) |
| **Frontend** | SvelteKit · Tailwind CSS v4 |
| **Charts** | SVG (hand-crafted, zero dependencies) |
| **Deployment** | Docker · docker-compose |
| **Testing** | pytest (222 tests, <2s) |

---

## Standards & References

MeridianIQ implements methodologies from these published standards:

| Standard | Application |
|----------|------------|
| AACE RP 29R-03 | Forensic Schedule Analysis |
| AACE RP 52R-06 | Time Impact Analysis |
| AACE RP 57R-09 | Integrated Cost and Schedule Risk Analysis |
| AACE RP 10S-90 | Cost Engineering Terminology |
| ANSI/EIA-748 | Earned Value Management Systems |
| DCMA EVMS | 14-Point Schedule Assessment |
| GAO Schedule Guide | Schedule Assessment Methodology |
| SCL Protocol | Delay and Disruption Protocol (2nd Ed.) |
| CPM | Kelly & Walker (1959) |

---

## Repository Structure

```
meridianiq/
├── src/
│   ├── parser/           # Custom MIT XER parser
│   │   ├── xer_reader.py # Streaming parser, encoding detection
│   │   ├── models.py     # 17+ Pydantic models
│   │   └── validator.py  # Constraint validation
│   ├── analytics/
│   │   ├── cpm.py        # NetworkX CPM engine
│   │   ├── dcma14.py     # DCMA 14-Point Assessment
│   │   ├── comparison.py # Multi-layer matching
│   │   ├── forensics.py  # CPA per AACE RP 29R-03
│   │   ├── tia.py        # TIA per AACE RP 52R-06
│   │   ├── contract.py   # Contract compliance
│   │   ├── evm.py        # EVM per ANSI/EIA-748
│   │   └── risk.py       # Monte Carlo per AACE RP 57R-09
│   └── api/
│       ├── app.py        # FastAPI (32 endpoints)
│       └── schemas.py    # Request/response models
├── web/                  # SvelteKit + Tailwind
├── tests/                # 222 tests
├── docs/                 # Discovery & definition documents
├── v1-reader/            # Legacy P6 reader (upstream attribution)
├── v1-compare/           # Original XER compare tool
├── v1-program-schedule/  # Production schedule analytics
├── docker-compose.yml
├── pyproject.toml
├── LICENSE (MIT)
├── CONTRIBUTING.md
├── ATTRIBUTION.md
└── ACKNOWLEDGMENTS.md
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas where help is needed:**
- 🌍 Additional schedule formats (Microsoft Project XML, Asta Powerproject)
- 🔬 Methodology validation against real-world experience
- 🏗️ International contract compliance (FIDIC, NEC, JCT)
- ⚡ Performance optimization for 50,000+ activity schedules
- 📊 Additional chart types and visualizations

---

## Academic Use

MeridianIQ is designed to support academic research in project controls and forensic schedule analysis. If you use MeridianIQ in your research, please cite:

```bibtex
@software{meridianiq,
  author = {Rodovalho, Vitor Maia},
  title = {MeridianIQ: Open-Source Schedule Intelligence Platform},
  year = {2025},
  url = {https://github.com/VitorMRodovalho/meridianiq},
  note = {Implements AACE RP 29R-03, 52R-06, 57R-09; DCMA 14-Point; ANSI/EIA-748}
}
```

---

## License

Code is licensed under [MIT](LICENSE).

See [ATTRIBUTION.md](ATTRIBUTION.md) for upstream credits and [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for tooling acknowledgments.

---

<div align="center">

**MeridianIQ** · MIT License · © 2025 Vitor Maia Rodovalho

*Built with academic rigor. Every methodology traceable to published standards.*

</div>
