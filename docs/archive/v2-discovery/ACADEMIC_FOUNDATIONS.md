# Academic Foundations for the Platform

This document maps the academic and standards landscape that underpins the platform's methodology. Every analytical feature must trace back to published research, recognized standards, or recommended practices.

---

## 1. Research Areas

### 1.1 Earned Value Management (EVM)

The quantitative foundation for integrating scope, schedule, and cost performance measurement.

**Key References:**
- Fleming, Q.W. & Koppelman, J.M. (2010). *Earned Value Project Management* (4th ed.). Project Management Institute.
- PMI (2019). *Practice Standard for Earned Value Management* (3rd ed.). Project Management Institute.
- PMI (2025). *PMBOK Guide* (8th ed.) — integrates EVM within the value delivery framework.
- AACE International. *RP 10S-90: Cost Engineering Terminology*. Provides standard EVM definitions.

**Platform Relevance:** EVM metrics (CPI, SPI, EAC, ETC, TCPI, VAC) form the core of the physical-to-financial convergence analysis. The platform must calculate these from schedule and cost data alignment.

---

### 1.2 Forensic Schedule Analysis

Methodologies for determining causation and liability for project delays in construction claims.

**Key References:**
- AACE International (2011, revised). *RP 29R-03: Forensic Schedule Analysis*. The industry-standard taxonomy of nine forensic methodologies.
- Wickwire, J.M., Driscoll, T.J. & Hurlbut, S.B. (2003). *Construction Scheduling: Preparation, Liability, and Claims* (2nd ed.). Aspen Publishers.
- Arditi, D. & Pattanakitchamroon, T. (2006). Selecting a delay analysis method in resolving construction claims. *International Journal of Project Management*, 24(2), 145-155.
- Braimah, N. & Ndekugri, I. (2008). Factors influencing the selection of delay analysis methodologies. *International Journal of Project Management*, 26(8), 789-799.

**Platform Relevance:** The platform must preserve sufficient schedule update data to support retrospective forensic analysis using any of the RP 29R-03 methodologies. Automated anomaly detection (logic changes, constraint shifts, out-of-sequence progress) directly supports forensic workflows.

---

### 1.3 Critical Chain Project Management (CCPM)

An alternative to traditional CPM that focuses on resource constraints and buffer management.

**Key References:**
- Goldratt, E.M. (1997). *Critical Chain*. North River Press.
- Leach, L.P. (2014). *Critical Chain Project Management* (3rd ed.). Artech House.
- Tukel, O.I., Rom, W.O. & Eksioglu, S.D. (2006). An investigation of buffer sizing techniques in critical chain scheduling. *European Journal of Operational Research*, 172(2), 401-416.

**Platform Relevance:** Buffer consumption analysis and feeding buffer monitoring provide proactive indicators of schedule health, complementing traditional float analysis.

---

### 1.4 Schedule Risk Analysis (SRA)

Probabilistic approaches to schedule uncertainty, replacing deterministic single-point estimates with probability distributions.

**Key References:**
- AACE International. *RP 57R-09: Integrated Cost and Schedule Risk Analysis Using Monte Carlo Simulation of a CPM Model*.
- AACE International. *RP 65R-11: Integrated Cost and Schedule Risk Analysis and Contingency Determination Using Expected Value*.
- Hulett, D.T. (2009). *Practical Schedule Risk Analysis*. Gower Publishing.
- Vose, D. (2008). *Risk Analysis: A Quantitative Guide* (3rd ed.). Wiley.

**Platform Relevance:** Monte Carlo simulation capabilities, producing P50/P80/P90 completion dates and risk-driven critical path identification. Integration with the schedule model for automated SRA.

---

### 1.5 Project Value Delivery

The PMBOK 8th Edition paradigm shift from process-based to principles-based project management, with value delivery as the central organizing concept.

**Key References:**
- PMI (2025). *A Guide to the Project Management Body of Knowledge (PMBOK Guide)* (8th ed.). Project Management Institute.
  - Six core principles, seven performance domains, five focus areas with 40 processes.
  - Emphasis on value delivery, adaptability, and accountability.
  - Success measured by value delivered to stakeholders, not merely on-time/on-budget completion.
- PMI (2021). *The Standard for Project Management* — introduced the value delivery system concept.
- Thiry, M. (2015). *Program Management*. Gower. — Program-level value delivery frameworks.

**Platform Relevance:** The platform's architecture must reflect that schedule is a component of value delivery, not an end in itself. Analytics must connect schedule performance to stakeholder value outcomes.

---

### 1.6 Systems Engineering in Construction

Application of systems engineering principles to infrastructure and construction project delivery.

**Key References:**
- INCOSE (2023). *Systems Engineering Handbook* (5th ed.). Wiley.
  - Includes infrastructure examples such as the Oresund Bridge.
  - Argues that "the greatest benefits of applying SE principles are gained in the systems integration and construction stage."
- INCOSE Infrastructure Working Group. *Guide for the Application of Systems Engineering in Large Infrastructure Projects*.
- Ferrer et al. (2022). Benefits of Systems Engineering in Large Infrastructure Projects: the much-anticipated empirical proof. *INCOSE International Symposium*.
- Whyte, J. et al. *Systems Engineering and the Project Delivery Process in the Construction Industry*. Imperial College London.

**Platform Relevance:** The platform itself is a system of systems — schedule, cost, risk, and resource subsystems must be engineered with clear interfaces, defined behaviors, and traceable requirements. Systems engineering provides the meta-framework for the platform's architecture.

---

### 1.7 Construction Informatics

The application of information technology, data science, and computational methods to construction processes.

**Key References:**
- Eastman, C.M., Teicholz, P., Sacks, R. & Lee, G. (2018). *BIM Handbook: A Guide to Building Information Modeling* (3rd ed.). Wiley.
- Turk, Z. (2006). Construction informatics: Definition and ontology. *Advanced Engineering Informatics*, 20(2), 187-199.
- Bilal, M. et al. (2016). Big data in the construction industry: A review of present status, opportunities, and future trends. *Advanced Engineering Informatics*, 30(3), 500-521.
- Pan, Y. & Zhang, L. (2021). A BIM-data mining integrated digital twin framework for advanced project management. *Automation in Construction*, 124, 103564.

**Platform Relevance:** The platform is a construction informatics contribution — it applies data science to scheduling data. BIM-schedule integration (4D) and digital twin concepts are future extension points.

---

### 1.8 Predictive Analytics in Construction

Machine learning and AI applications for construction project performance prediction.

**Key References:**
- Seyisoglu, B., Shahpari, A. & Talebi, M. (2024). Predictive Project Management in Construction: A Data-Driven Approach to Project Scheduling and Resource Estimation Using Machine Learning. *SSRN*.
- Automation in Construction (2024). Predicting construction schedule performance with last planner system and machine learning. (Demonstrated ML models including SVR, Random Forest, LSTM, and GRU for schedule prediction.)
- Springer Nature (2025). Application of artificial intelligence and machine learning in construction project management: A comparative study of predictive models. *Asian Journal of Civil Engineering*. (Found Random Forest achieved R-squared of 0.88, outperforming ANN and SVM.)
- Springer Nature (2025). Impact of Predictive Analytics, AI, and Digital Twin on Construction Planning and Scheduling.
- Gondia, A. et al. (2020). Machine learning algorithms for construction projects delay risk prediction. *Journal of Construction Engineering and Management*, 146(1).

**Platform Relevance:** ML-based schedule outcome prediction is a Tier 4 capability. Historical schedule update data from the platform becomes training data for predictive models. Key techniques: Random Forest for baseline predictions, LSTM for time-series schedule trends.

---

### 1.9 Open-Source in AEC

Adoption patterns, challenges, and opportunities for open-source software in the Architecture, Engineering, and Construction industry.

**Key References:**
- opensource.construction — Community platform cataloging open-source tools for AEC.
- IfcOpenShell, xBIM, IFC.js — Leading open-source platforms for OpenBIM development, increasingly adopted in academia.
- ScienceDirect (2024). Technology adoption in the construction industry (1999-2023): Science mapping and visualization. *Automation in Construction*. (Comprehensive review of 124 peer-reviewed articles.)
- PMC (2021). Digital Technologies in the Architecture, Engineering and Construction (AEC) Industry — A Bibliometric-Qualitative Literature Review.
- Moradi, Y. (2024). Why Open Source Opens New Doors for AEC. *Medium / mod.construction*.

**Platform Relevance:** The platform contributes to a growing but still nascent open-source ecosystem in AEC. Understanding adoption barriers (proprietary data formats, industry conservatism, fragmented tool chains) is essential for designing a platform that practitioners will actually use.

---

## 2. Potential PhD Research Questions

The following research questions position the platform as an academic contribution with both theoretical and practical significance:

**RQ1.** How can an open-source, integrated schedule intelligence platform improve the accuracy and timeliness of project delivery predictions compared to traditional CPM-based reporting?

**RQ2.** What is the relationship between schedule update patterns (float deterioration, logic changes, constraint additions) and eventual project outcomes across a statistically significant sample of construction projects?

**RQ3.** Can machine learning models trained on historical XER/P6 schedule data predict project completion dates more accurately than deterministic CPM forward pass calculations?

**RQ4.** How does the integration of physical progress (schedule-based) and financial progress (cost-based) data improve earned value management accuracy in multi-contractor construction programs?

**RQ5.** What are the barriers to adoption of open-source project controls tools in the construction industry, and how can platform design mitigate them?

---

## 3. Standards Library

The following standards and recommended practices should be acquired, referenced, and — where the platform provides analytical support — implemented:

| # | Standard | Publisher | Relevance |
|---|----------|-----------|-----------|
| 1 | **PMBOK Guide, 8th Edition** (2025) | PMI | Value delivery framework, performance domains, principles |
| 2 | **Practice Standard for Scheduling** (3rd ed.) | PMI | CPM methodology, schedule development, maintenance |
| 3 | **Practice Standard for Earned Value Management** (3rd ed.) | PMI | EVM calculations, performance measurement baseline |
| 4 | **RP 29R-03: Forensic Schedule Analysis** | AACE | Nine forensic methodologies, delay analysis taxonomy |
| 5 | **RP 57R-09: Integrated Cost and Schedule Risk Analysis** | AACE | Monte Carlo simulation, probabilistic scheduling |
| 6 | **RP 10S-90: Cost Engineering Terminology** | AACE | Standard definitions for all cost/schedule terms |
| 7 | **RP 65R-11: Integrated Cost and Schedule Risk Analysis and Contingency Determination** | AACE | Expected value method for contingency |
| 8 | **Systems Engineering Handbook** (5th ed.) | INCOSE | Systems thinking, requirements engineering, V-model |
| 9 | **ISO 21500:2021 — Project, Programme and Portfolio Management** | ISO | International PM framework alignment |
| 10 | **ISO 19650 Series — BIM Information Management** | ISO | Data exchange standards for construction information |
| 11 | **NISTIR 7417 — Cost Analysis of Inadequate Interoperability in the U.S. Capital Facilities Industry** | NIST | Quantifies the cost of data interoperability failures — motivates open-source, open-format approaches |

---

## Additional References from Literature Review

### Journals to Target for Publication
- *Journal of Construction Engineering and Management* (ASCE)
- *Automation in Construction* (Elsevier)
- *International Journal of Project Management* (Elsevier)
- *Engineering, Construction and Architectural Management* (Emerald)
- *AACE International Transactions* (annual conference proceedings)

### Conference Venues
- PMI Global Conference
- AACE International Conference and Expo
- ASCE Construction Research Congress (CRC)
- INCOSE International Symposium
- Computing in Civil Engineering (ASCE)

### Datasets and Benchmarks
- Historical XER files from completed projects (anonymized) — primary data source
- ELCAS (Earned Value Learning Curve Analysis System) datasets
- Construction Industry Institute (CII) benchmarking data
- UK Infrastructure and Projects Authority (IPA) annual reports
