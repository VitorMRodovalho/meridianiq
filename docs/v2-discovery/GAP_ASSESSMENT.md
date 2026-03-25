# P6 XER Analytics v2 — Gap Assessment

## Competitive Landscape

### Tier 1: Enterprise Tools (Paid, $$$)

| Tool | Focus | Strengths | Weaknesses | Pricing |
|------|-------|-----------|------------|---------|
| **Deltek Acumen Fuse** | Gold standard forensic analysis | DCMA-14, comparison, risk, cleansing, multi-format import (P6, MSP, Asta, Phoenix, Safran) | Expensive, complex, enterprise-only, steep learning curve | Enterprise license |
| **Schedule Validator** | Cloud-based automated validation | Scoring (82/100 format), DCMA-14, diagnostic, comparison, traffic lights | Validation only — no forensic CPA, no TIA, no earned value | Subscription |
| **XER Schedule Toolkit** | All-in-one cloud toolkit | AI-generated summaries, quality checking, EV dashboards, viewer, comparison | No forensic delay analysis, no TIA, no CPA | Subscription |
| **SYSTECH Delay Analysis** | Forensic specialist | Daily windows analysis (30x more accurate), real-time alerts, contemporaneous records | Proprietary consulting-firm tool, not publicly available | Internal only |

### Tier 2: Viewers/Readers (Free or Low-Cost)

| Tool | Focus | Strengths | Weaknesses |
|------|-------|-----------|------------|
| **ScheduleReader** (Synami) | Leading XER viewer | Read-only XER/XML, Gantt, resources, costs, DCMA-14, baseline comparison (4x), progress update | Viewer only — no analytical engine, no forensic |
| **PrimaveraReader** | Basic XER viewing | Simple, accessible | Very basic, no analytics at all |

### Tier 3: Open-Source Libraries (Developer Tools)

| Tool | Language | License | Status | Capabilities | Limitations |
|------|----------|---------|--------|-------------|-------------|
| **xerparser** | Python | GPL v3 | Active (v0.13.9, Nov 2025) | All major XER tables, OOP API, error detection | Library only, no UI, no analytics |
| **PyP6Xer** | Python | — | Active | Full parsing, CP calculation, float, quality, EV, write-back | Library only, no UI |
| **MPXJ** | Java/.NET | LGPL | Active (industry standard) | Universal format support (XER, PMXML, MPP, Asta, Phoenix+) | Java-centric, library only |
| **djouallah/Xer-Reader-PowerBI** | Power Query/DAX | None specified | Abandoned (2020) | Basic XER reader in Power BI | Abandoned, Power BI lock-in, no analytics |
| **PrimeveraXEREditor** | Java | — | Inactive | GUI viewer using MPXJ, LOE filtering | Dated Swing UI, unmaintained |

---

## Gap Analysis Matrix

### Legend
- ✅ Full coverage (production-ready feature)
- ⚠️ Partial coverage (basic version or requires workarounds)
- ❌ Not covered
- ❓ Unknown / unverified

| Epic | Acumen Fuse | Schedule Validator | XER Toolkit | SYSTECH | ScheduleReader | xerparser | PyP6Xer | **P6 XER Analytics v2** |
|------|------------|-------------------|-------------|---------|---------------|-----------|---------|----------------------|
| **E1: XER Ingestion & Validation** | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | **Target: ✅** |
| **E2: Baseline Schedule Review** | ✅ | ⚠️ | ⚠️ | ❌ | ⚠️ | ❌ | ⚠️ | **Target: ✅** |
| **E3: Monthly Update Review** | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | **Target: ✅** |
| **E4: Schedule Comparison** | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ⚠️ | **Target: ✅** |
| **E5: CPA (Forensic)** | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | **Target: ✅** |
| **E6: TIA Support** | ⚠️ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | **Target: ✅** |
| **E7: Contract Compliance** | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | **Target: ✅** |
| **E8: Proactive Intelligence** | ⚠️ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | **Target: ✅** |
| **E9: Submittal/RFI Integration** | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | **Target: ✅** |
| **E10: Reporting** | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ | **Target: ✅** |

### Detailed Breakdown

#### Epic 1: XER Ingestion & Validation
| Feature | Acumen | SV | XER Toolkit | ScheduleReader | xerparser | PyP6Xer |
|---------|--------|-----|-------------|---------------|-----------|---------|
| XER file parsing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-format (MSP, Asta) | ✅ | ❌ | ❌ | ⚠️ (XML) | ❌ | ❌ |
| Validation score | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Open-end detection | ✅ | ✅ | ✅ | ⚠️ | ❌ | ✅ |
| OOS detection | ✅ | ✅ | ✅ | ❌ | ❌ | ⚠️ |
| DCMA-14 assessment | ✅ | ✅ | ✅ | ✅ | ❌ | ⚠️ |
| Traffic light indicators | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

#### Epic 5: CPA (The Key Differentiator)
| Feature | Acumen | SYSTECH | SV | XER Toolkit | ScheduleReader | Libraries |
|---------|--------|---------|-----|-------------|---------------|-----------|
| Delay trend chart | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Window analysis | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Bifurcated analysis | ⚠️ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Delay classification | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Driving CP per period | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Automated (not manual) | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| Web-based | ❌ | ❌ | N/A | N/A | N/A | N/A |

---

## Strategic Classification

### 1. Blue Ocean — Features NO Competitor Offers (Our Differentiators)

These are features that would make P6 XER Analytics v2 genuinely unique in the market:

| Feature | Why No One Has It | Our Advantage |
|---------|------------------|---------------|
| **Contract compliance monitoring (E7)** | Not a schedule analysis feature — it's a project management feature. No scheduling tool tracks NOD/PCO deadlines or entitlement status. | We understand the intersection of schedule analysis and contract administration. The [Forensic Consultant] memo proves this is where claims are won or lost. |
| **Submittal/RFI timeline integration (E9)** | Schedule tools analyze schedules. Document tools manage documents. Nobody connects them on a single timeline. | The 121-day gap analysis in the [Forensic Consultant] memo was the smoking gun — this requires cross-system data. |
| **Proactive float erosion alerts (E8.2)** | Tools compare two schedules retroactively. Nobody watches float trends proactively and alerts before activities go critical. | Simple to build on top of comparison engine: store historical float values, calculate trend, alert on threshold. |
| **TIA gap detection (E6.3)** | SYSTECH may do this manually. No tool automates detection of timeline gaps where the contractor held the ball. | Pattern matching on submittal/RFI timelines against schedule activities — unique analytical capability. |
| **Schedule manipulation detection (E8.6)** | Acumen can detect anomalies. Nobody explicitly flags retroactive date changes, unjustified relationship changes, or duration padding as potential manipulation. | Comparison engine + rule set = automated manipulation flagging. The ACT-0870 case (actual start changed from 02/13/2023 to 06/21/2024) is a textbook example. |
| **Time extension calculator (E8.7)** | Claims consultants do this manually in spreadsheets. No tool automates the entitlement calculation with contract rule integration. | CPA results + contract rules (NOD deadlines, PCO deadlines, recovery schedule requirements) = automated entitlement computation. |
| **Web-based CPA (E5 on web)** | Acumen and SYSTECH are desktop. Nobody offers CPA in a browser. | Modern web stack makes this possible. Would be the first web-based forensic schedule analysis tool. |

### 2. Table Stakes — Features Everyone Has (We Must Have)

These are non-negotiable. If we don't have these, we're not a serious tool:

| Feature | Standard Set By | Minimum Viable |
|---------|----------------|----------------|
| XER file parsing | All tools | Parse all standard P6 XER tables (TASK, PROJECT, PROJWBS, TASKPRED, CALENDAR, TASKRSRC) |
| Schedule counts summary | Schedule Validator | Activities, relationships, resources by type and status |
| Gantt chart visualization | ScheduleReader | Basic Gantt with critical path highlighting |
| Critical path identification | All tools | Longest path calculation and display |
| Float distribution | All tools | Histogram or pie chart with float categories |
| DCMA-14 metrics | Acumen, SV, ScheduleReader | 14-point assessment with pass/fail indicators |
| Schedule comparison (basic) | Schedule Validator | Activity/relationship adds, deletes, modifications |
| PDF/Excel export | All tools | Standard report formats |

### 3. Fast Followers — Features Only Premium Tools Have (Opportunity to Democratize)

These features currently require expensive enterprise licenses. Offering them at lower cost or open-source creates market disruption:

| Feature | Currently Only In | Democratization Opportunity |
|---------|------------------|---------------------------|
| **CPA / Window Analysis** | Acumen Fuse ($$$), SYSTECH (private) | First open-source or affordable CPA engine |
| **Bifurcated Analysis** | SYSTECH (private), Acumen (partial) | First web-accessible bifurcated analysis |
| **PERT Duration Probability** | Acumen Fuse | PERT calculation from XER data — implementable with standard statistics |
| **Earned Value dashboards** | XER Toolkit, Acumen | SPI/BEI/SRI from XER + payment data |
| **S-Curve generation** | Acumen, XER Toolkit | Resource-loaded S-curve from XER TASKRSRC data |
| **AI-generated summaries** | XER Toolkit (new feature) | LLM-based narrative generation from analysis results |
| **Multi-format import** | Acumen (P6, MSP, Asta, Phoenix) | MPXJ library supports all these formats |

### 4. Build vs Buy/Integrate — Technology Decision Matrix

| Epic | Build from Scratch | Leverage Existing | Recommendation |
|------|-------------------|-------------------|----------------|
| **E1: XER Parsing** | ❌ Don't reinvent | **xerparser** or **PyP6Xer** for parsing; **MPXJ** for multi-format | **Integrate**: xerparser for core parsing, MPXJ for format expansion |
| **E1: Validation/Scoring** | ✅ Custom rules engine | PyP6Xer has basic quality checks | **Build**: Custom scoring algorithm modeled on DCMA-14 + Schedule Validator patterns |
| **E2: Baseline Review** | ✅ Custom analysis | PyP6Xer has CP/float calculation | **Hybrid**: Use PyP6Xer for CP/float math, build PERT and memo generation |
| **E3: Monthly Review** | ✅ Custom analysis | — | **Build**: EV metrics (SPI, BEI, SRI) are domain-specific calculations |
| **E4: Comparison** | ⚠️ Partial build | PyP6Xer has basic comparison | **Hybrid**: Extend PyP6Xer comparison with detailed change tracking (description, codes, float) |
| **E5: CPA** | ✅ Novel engine | **NetworkX** for graph algorithms | **Build**: Core novel IP. Use NetworkX for CP recalculation per window. No existing library does CPA. |
| **E6: TIA Support** | ✅ Novel engine | — | **Build**: Entirely novel. Gap detection, fragnet validation, pre-impact schedule selection. |
| **E7: Compliance** | ✅ Rules engine | — | **Build**: Contract rule configuration + deadline tracking. No existing tool covers this. |
| **E8: Proactive** | ✅ Novel engine | — | **Build**: Alert system on top of comparison engine. Trend analysis over historical data. |
| **E9: Submittal/RFI** | ✅ Data integration | — | **Build**: Import layer for external document logs. Timeline merging. |
| **E10: Reporting** | ⚠️ Partial build | **Plotly/D3.js** for charts, **WeasyPrint/ReportLab** for PDF | **Hybrid**: Charting libraries for visualization, custom templates for memos |

---

## Key Libraries for v2 Build

### Core Parsing Layer
| Library | Role | License | Risk |
|---------|------|---------|------|
| **xerparser** (Python) | Primary XER parser — OOP API, all tables, error detection | GPL v3 | ⚠️ GPL v3 is copyleft — any code linking to it must also be GPL. Consider implications for commercial licensing. |
| **PyP6Xer** (Python) | Alternative parser with CP calculation, float, EV, quality checks, zero deps | Unspecified | ⚠️ License unclear — needs verification before adoption. Has write-back capability (can modify XER). |
| **MPXJ** (Java/.NET) | Multi-format support (P6, MSP, Asta, Phoenix) for future format expansion | LGPL | ✅ LGPL is permissive for linking. Java/.NET requires interop layer if core is Python. |

### Analysis Layer
| Library | Role | License |
|---------|------|---------|
| **NetworkX** (Python) | Graph algorithms for critical path, float calculation, path enumeration | BSD |
| **NumPy/SciPy** (Python) | PERT probability calculations, statistical analysis | BSD |
| **pandas** (Python) | Data manipulation, comparison engine, time series | BSD |

### Visualization Layer
| Library | Role | License |
|---------|------|---------|
| **Plotly** (Python/JS) | Interactive charts — delay trends, S-curves, float distribution | MIT |
| **D3.js** (JavaScript) | Custom visualizations — Gantt charts, CPA diagrams, TIA timelines | BSD |
| **Mermaid** (JS) | Diagram generation — architecture, flow charts | MIT |

### Reporting Layer
| Library | Role | License |
|---------|------|---------|
| **WeasyPrint** or **ReportLab** (Python) | PDF generation for professional memos | BSD/Commercial |
| **Jinja2** (Python) | Template engine for memo/report generation | BSD |
| **openpyxl** (Python) | Excel export for data tables | MIT |

---

## License Strategy Consideration

The **xerparser GPL v3 license** is the most significant technical constraint:

| Option | Implication |
|--------|------------|
| **A: Use xerparser, release as GPL v3** | Full open-source. Cannot offer proprietary/commercial version. Community-driven model. |
| **B: Use xerparser, offer SaaS** | GPL covers distributed software, not SaaS (the "SaaS loophole"). Could offer as web service without distributing GPL code. However, AGPL would close this — check if xerparser is GPL or AGPL. |
| **C: Use PyP6Xer (if permissively licensed)** | Avoids GPL constraint entirely. Need to verify PyP6Xer's license. |
| **D: Build custom parser** | Full license freedom but duplicates existing work. XER format is well-documented — custom parser is feasible but slower. |
| **E: Use MPXJ (LGPL)** | LGPL allows linking without copyleft. But MPXJ is Java — requires Jython bridge or subprocess calls from Python. |

**Recommendation**: Verify PyP6Xer license first. If permissive, use it. If not, evaluate whether the SaaS model with xerparser (GPL v3) meets business goals. Custom parser is the fallback — XER format is tab-delimited text, not complex to parse.

---

## Open Questions for Expert Consultation

These questions should be posed to PSP-certified schedulers, construction managers, and claims consultants to validate the backlog and gap assessment:

### Schedule Analysis Methodology
1. **How do you currently perform CPA?** Manual in P6? Acumen? Spreadsheets? What's the most painful part of the process?
2. **How accurate does the bifurcated (half-step) analysis need to be?** Daily windows vs monthly windows — does the 30x accuracy claim from SYSTECH matter in practice, or is monthly sufficient for most disputes?
3. **When performing a TIA review, what's your workflow?** Do you reconstruct the fragnet independently, or primarily evaluate the contractor's submission?
4. **How often do you encounter schedule manipulation?** Retroactive date changes, lump-sum fragnets, missing logic — is this 10% of projects or 80%?

### Market and Pricing
5. **What do you currently pay for Acumen Fuse?** Per seat? Per year? Is cost a barrier for smaller CM firms?
6. **Would you pay for a web-based CPA tool?** What price point? Per-project or subscription?
7. **Would an open-source schedule validation tool (free) drive adoption** if premium forensic features (CPA, TIA) were paid?

### Feature Priorities
8. **If you could automate ONE thing in your workflow, what would it be?** The monthly update memo? The CPA? The TIA review? The schedule diagnostic?
9. **How valuable is proactive alerting vs reactive analysis?** Would you use float erosion alerts if they existed?
10. **Is contract compliance tracking (NOD/PCO deadlines) currently done in a dedicated system** or is it tracked in spreadsheets/email?

### Data and Integration
11. **Do you typically receive XER files or PMXML?** Has P6 Cloud changed the file format landscape?
12. **How do you currently track submittals and RFIs?** Procore? Bluebeam? Excel? Would a combined timeline view with the schedule be valuable?
13. **Would integration with P6 EPPM (cloud) be more valuable than XER file upload?** Or do most disputes still work with exported XER files?

### Legal and Claims Context
14. **In a dispute, what documentation format do arbitrators/courts expect?** PDF memos? Interactive dashboards? What level of detail?
15. **How important is the audit trail?** If a tool generates a CPA, does the methodology need to be fully transparent and reproducible for legal proceedings?

---

## Strategic Positioning Summary

```
                    FORENSIC DEPTH
                         ▲
                         │
              SYSTECH    │    P6 XER Analytics v2
              (private)  │    (target position)
                         │
         Acumen Fuse ────┼──────────────────────
              ($$$)      │
                         │
                         │        XER Toolkit
                         │        (cloud, no forensic)
         Schedule ───────┼──────────────────────
         Validator       │
         (validation     │    ScheduleReader
          only)          │    (viewer only)
                         │
         ─────────────── ┼──────────────────────► ACCESSIBILITY
              Desktop    │    Web/Cloud
              Enterprise │    Open/Affordable
```

**Target position**: Acumen-level forensic depth with web-based accessibility at a fraction of the cost. The first tool to offer CPA, TIA support, and contract compliance monitoring in a browser.

**Moat**: The combination of forensic analysis (CPA/TIA) + contract compliance (NOD/PCO tracking) + proactive intelligence (float erosion alerts, manipulation detection) creates a unique value proposition that no single existing tool offers.

**Entry strategy**: Open-source validation/comparison (Epics 1, 4) to build community → Premium forensic features (Epics 5, 6, 7) for revenue → Proactive intelligence (Epic 8) as the long-term differentiator.

---

*This assessment is based on publicly available information about competitor tools as of March 2026. Pricing and feature sets may have changed. Direct evaluation of Acumen Fuse and SYSTECH was not performed — assessment is based on published documentation and industry knowledge.*
