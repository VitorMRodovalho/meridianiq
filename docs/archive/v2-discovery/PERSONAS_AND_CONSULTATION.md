# Expert Consultation Framework

This document defines the personas whose expertise should shape the platform's requirements and the structured questions to guide consultations with them.

---

## Persona Categories

### Category A — Schedule Practitioners

#### 1. PSP-Certified Scheduler
- **Who they are:** Planning and Scheduling Professional certified by AACE International. The practitioner who builds, maintains, and updates schedules daily in Primavera P6 or equivalent tools.
- **What they do:** Create and maintain CPM schedules, perform schedule updates, resource loading, baseline management, and progress measurement.
- **Questions to ask:** What are the most common data quality issues in XER files? What analysis would you run first when receiving a new contractor schedule? What metrics do you wish your tools calculated automatically?

#### 2. Forensic Schedule Analyst (Claims)
- **Who they are:** Specialist in schedule delay analysis for construction claims and disputes. Often engaged during litigation or arbitration proceedings.
- **What they do:** Apply forensic methodologies (as-planned vs. as-built, time impact analysis, windows analysis) to determine liability for project delays.
- **Questions to ask:** Which AACE RP 29R-03 methodologies are most frequently used in practice? What data preservation requirements exist for forensic analysis? What are the biggest gaps in current forensic scheduling tools?

#### 3. Program Scheduler (IPS Maintainer)
- **Who they are:** Senior scheduler responsible for maintaining the Integrated Project Schedule across multiple contractors and disciplines on large programs.
- **What they do:** Integrate contractor schedules into the IPS, manage inter-project dependencies, maintain program milestones, and report to program leadership.
- **Questions to ask:** How do you handle integration of schedules from different contractors using different tools? What are the biggest challenges in maintaining IPS logic integrity? How do you manage the hierarchy from program to work package level?

---

### Category B — Project Management and Controls

#### 4. Project Manager (PM/PMP)
- **Who they are:** PMP-certified project manager responsible for overall project delivery, typically managing scope, cost, schedule, quality, and risk.
- **What they do:** Make decisions based on schedule and cost reports, manage stakeholder expectations, approve change orders, and direct the project team.
- **Questions to ask:** What schedule information do you actually use for decision-making? What format and frequency of reporting is most actionable? When does schedule data fail you — what do you wish you could see?

#### 5. Construction Manager (CM/CCM)
- **Who they are:** On-site construction management professional (often CCM-certified) who bridges the gap between the schedule and field execution.
- **What they do:** Coordinate field activities, manage subcontractors, resolve field conflicts, and translate schedule logic into daily work plans.
- **Questions to ask:** How well does the CPM schedule reflect field reality? Where does the disconnect between planned and actual sequences occur most? What field-level data would improve schedule accuracy?

#### 6. Cost Manager / Cost Engineer
- **Who they are:** Professional responsible for project cost estimation, budgeting, cost control, and earned value reporting. This is Vitor's current professional trajectory at a global cost management firm.
- **What they do:** Manage CBS structures, track actual costs against budgets, calculate EVM metrics (CPI, SPI, EAC, ETC), and produce financial progress reports.
- **Questions to ask:** How do you currently align WBS with CBS for EVM? What are the most common calibration issues between schedule and cost data? What would an ideal physical-to-financial convergence dashboard show?

#### 7. Risk Manager
- **Who they are:** Specialist in project risk identification, assessment, and mitigation, often using quantitative methods like Monte Carlo simulation.
- **What they do:** Maintain risk registers, perform schedule risk analysis (SRA), assign probability distributions to activity durations, and produce probabilistic schedule outputs.
- **Questions to ask:** What inputs do you need from the schedule for effective SRA? How do you calibrate risk models with historical project data? What risk metrics should be tracked across schedule update cycles?

---

### Category C — Owner/Client Side

#### 8. Owner Representative
- **Who they are:** The client-side project professional who oversees contractor performance and protects the owner's interests.
- **What they do:** Review contractor schedule submissions, approve baselines and updates, monitor milestone compliance, and manage contractual schedule requirements.
- **Questions to ask:** What are your minimum schedule specification requirements for contractors? How do you evaluate schedule quality during submittal review? What early warning indicators do you look for in contractor schedules?

#### 9. Program Director
- **Who they are:** Senior executive responsible for the overall delivery of a capital program (multiple projects, often $100M+).
- **What they do:** Make portfolio-level decisions, allocate resources across projects, report to board/stakeholders, and manage program-level risks.
- **Questions to ask:** What level of schedule detail is appropriate for program-level reporting? How do you benchmark schedule performance across projects? What predictive indicators would change how you allocate resources?

---

### Category D — Academic and Standards

#### 10. Construction Management Professor (PhD Advisor)
- **Who they are:** University faculty member specializing in construction management, project controls, or construction informatics. Potential PhD thesis advisor.
- **What they do:** Conduct research, supervise doctoral students, publish in peer-reviewed journals, and maintain connections between academia and industry practice.
- **Questions to ask:** What research gaps exist in construction scheduling analytics? Is there sufficient novelty for a PhD thesis in open-source schedule intelligence? What methodological frameworks would strengthen the research contribution?

#### 11. AACE Technical Board Member
- **Who they are:** Senior member of the Association for the Advancement of Cost Engineering who contributes to the development of recommended practices and technical standards.
- **What they do:** Author and review AACE Recommended Practices, participate in technical committees, and shape industry standards for cost engineering and project controls.
- **Questions to ask:** Which RPs are most in need of digital tooling support? How can an open-source platform contribute to RP adoption? What data standards does AACE envision for the future of project controls?

#### 12. PMI Practice Standard Author
- **Who they are:** Contributor to PMI practice standards, particularly the Practice Standard for Scheduling, Practice Standard for EVM, or the PMBOK Guide itself.
- **What they do:** Define the body of knowledge for project management practices, ensure standards reflect current industry reality, and guide professional development.
- **Questions to ask:** How does the PMBOK 8th Edition's value delivery focus change schedule analysis requirements? What gaps exist between current scheduling tools and PMI's practice standards? How should schedule analytics evolve to support the principles-based approach?

---

### Category E — Technology

#### 13. Open-Source Platform Architect
- **Who they are:** Software architect with experience building and maintaining successful open-source platforms, particularly in data-intensive domains.
- **What they do:** Design scalable architectures, define API contracts, establish contribution workflows, and make technology stack decisions that support long-term community growth.
- **Questions to ask:** What architectural patterns best support multi-tenant schedule data? How should the platform balance flexibility with opinionated defaults? What open-source governance model is most sustainable for a domain-specific tool?

#### 14. AI/ML for Construction Researcher
- **Who they are:** Researcher at the intersection of artificial intelligence, machine learning, and construction project management.
- **What they do:** Develop predictive models for schedule performance, apply NLP to construction documents, and publish research on ML applications in AEC.
- **Questions to ask:** What ML techniques are most promising for schedule outcome prediction? What training data requirements exist for construction schedule models? How do you validate predictive models in a domain with high project variability?

---

## Consultation Questions

### Theme 1: Schedule as a Component (PMBOK 8 Alignment)

**Q1.** The PMBOK 8th Edition positions schedule as one component of a value delivery system, not a standalone discipline. How should a schedule analysis platform reflect this integrated view?

**Q2.** If schedule is a means to deliver value (not an end), what other project dimensions must the platform integrate to provide meaningful intelligence?

**Q3.** How do you currently measure whether a project is delivering value beyond schedule adherence? What data would you need to answer that question systematically?

---

### Theme 2: Multi-Level Scheduling Reality

**Q4.** In your experience, how many levels of schedule hierarchy exist in a typical large capital program? How are they related?

**Q5.** What is the practical relationship between the IPS and individual contractor schedules? Where does integration break down most often?

**Q6.** How should a platform handle the reality that different schedule levels have different update frequencies, different tools, and different owners?

---

### Theme 3: Forensic Analysis Gaps

**Q7.** Which of the AACE RP 29R-03 forensic methodologies do you use most frequently, and why?

**Q8.** What data must be preserved from each schedule update to enable retrospective forensic analysis? Are current tools adequate for this?

**Q9.** What is the biggest gap between what forensic schedule analysis needs and what current tools provide?

**Q10.** How could automated anomaly detection (logic changes, constraint additions, out-of-sequence progress) improve forensic analysis quality?

---

### Theme 4: Proactive vs. Reactive

**Q11.** Most schedule analysis today is retrospective (what happened). What proactive/predictive analysis would change how you manage projects?

**Q12.** If you could predict, with quantified confidence, that a project would finish late — at what point in the project lifecycle would that prediction be most valuable?

**Q13.** What patterns in early schedule updates are the best predictors of eventual project outcomes?

---

### Theme 5: Technology and Adoption

**Q14.** What has prevented adoption of more advanced schedule analytics tools in the construction industry? Is it cost, complexity, trust, or something else?

**Q15.** Would an open-source, community-driven platform lower barriers to adoption? What would make you (or your organization) contribute to or use such a platform?

---

### Theme 6: Academic Contribution

**Q16.** What research questions in construction scheduling are both practically relevant and academically publishable?

**Q17.** Is there a viable PhD thesis in building an open-source schedule intelligence platform? What would the research contribution be — the tool, the methodology, or the empirical findings?

**Q18.** What existing academic work should this platform build upon or reference?

---

### Theme 7: Data Center Program Specifics

**Q19.** Data center construction programs have unique characteristics: fast-track delivery, repetitive building types, hyperscaler clients with strict SLAs. How do these characteristics change scheduling requirements?

**Q20.** In a data center program with multiple campuses and hundreds of buildings, what schedule analytics would provide the most value to the program director?
