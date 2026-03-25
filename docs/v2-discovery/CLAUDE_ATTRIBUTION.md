# AI Assistant Attribution in Academic and Open-Source Projects

How to properly credit AI assistants in open-source software, academic research, and GitHub repositories.

---

## 1. The Question

This project is developed with significant assistance from Claude (Anthropic), an AI assistant. As both an open-source software project and a potential academic research contribution, it must address a fundamental question:

**How should AI assistants be credited in open-source, academic, and GitHub contexts?**

The answer must satisfy three domains simultaneously:
- Academic publishing norms (for journal papers and a potential PhD thesis)
- Open-source community expectations (for GitHub collaboration)
- Professional integrity standards (for the construction management industry)

---

## 2. Current Academic Consensus (2024-2025)

### Universal Prohibition on AI Authorship

All major academic publishers have converged on a clear position: **AI tools cannot be listed as authors.** This consensus is remarkably uniform across disciplines and publishers.

- **IEEE** (April 2024): Requires disclosure of AI use in the acknowledgment section. Explicitly prohibits listing AI as an author. Prohibits use of AI tools in the peer review process.
- **ACM**: States that "authorship implies responsibilities and tasks that can only be attributed to and performed by humans." Generative AI tools may not be listed as authors of any ACM published work. Use must be fully disclosed.
- **Nature Portfolio**: Prohibits AI authorship and AI-generated images. Requires documentation of LLM use in the Methods section. Does not require disclosure for minor copy-editing assistance.
- **Science / AAAS**: Aligns with the broader consensus — AI cannot be an author, and use must be disclosed.
- **Elsevier and Springer Nature**: Both require explicit disclosure statements when AI tools are used in manuscript preparation. Neither accepts AI as an author.

### PhD Thesis Context

University policies on AI use in doctoral research are converging around these principles:

- **Disclosure, not citation.** AI output is not a source — it is a tool. When AI is permitted, disclose its use rather than cite it (Princeton scholarly integrity guidance).
- **Sole responsibility.** The student retains full intellectual responsibility for all content, regardless of AI assistance used.
- **Disclosure statement.** Provide a statement identifying the tool, version, and how it contributed. Some departments request the prompt or date of use.
- **Placement.** Add a brief disclosure in the preface, acknowledgments, or methods section of the thesis.
- **No direct copying.** Even when AI is permitted for brainstorming or outlining, copying AI output verbatim without disclosure violates academic integrity.

### GitHub and Open-Source Community

The open-source community is navigating AI attribution through evolving norms:

- **Transparency over prohibition.** The community consensus favors clear disclosure of AI use combined with quality standards, rather than outright bans on AI-assisted contributions.
- **Quality matters more than origin.** Code is evaluated on its merits — correctness, readability, test coverage — regardless of whether AI assisted in writing it.
- **Maintainer concerns.** GitHub has observed a flood of low-quality AI-generated contributions, leading to proposed configurable PR permissions and better attribution tooling.
- **Attribution norms.** Human contributors go in CONTRIBUTORS.md or AUTHORS files. AI tools are acknowledged separately, typically in README, ACKNOWLEDGMENTS, or a dedicated AI disclosure section.

---

## 3. Proposed Attribution for This Project

### Guiding Principles

1. **Claude is NOT a co-author.** AI cannot take responsibility for intellectual decisions, defend methodology choices, or be held accountable for errors. Authorship requires accountability.
2. **Claude IS acknowledged as a development tool and assistant.** Its contribution to code generation, literature review, requirements analysis, and documentation drafting is real and should be transparently disclosed.
3. **The author retains full responsibility.** All intellectual decisions, domain expertise, methodology choices, and professional judgment are the sole responsibility of the human author.

### Acknowledgment Text (Standard)

For use in the repository README, thesis acknowledgments, or paper acknowledgment sections:

> *"This project was developed with assistance from Claude (Anthropic), an AI assistant used for code generation, literature review, requirements analysis, and documentation drafting. All intellectual decisions, domain expertise, methodology choices, and professional judgment are the sole responsibility of the author."*

### For Academic Papers

Follow the specific AI disclosure policy of each target journal or conference:

- **IEEE venues:** Include disclosure in the Acknowledgment section per IEEE's April 2024 policy.
- **ACM venues:** Include disclosure per ACM's authorship policy. Do not list AI in the author byline.
- **ASCE / Automation in Construction:** Check the publisher's current AI policy at submission time and comply with their specific requirements.
- **PhD thesis:** Include the disclosure statement in the Preface or Acknowledgments chapter, plus a methodological note in the Research Methodology chapter describing how AI tools were used and what safeguards were applied.

### For GitHub Repository

Maintain two separate files:

- **CONTRIBUTORS.md** — For human contributors only. Lists people who contributed code, documentation, domain expertise, or reviews.
- **ACKNOWLEDGMENTS.md** — For tools, libraries, AI assistants, and other non-human contributions. Claude is listed here with a description of how it was used.

### Commit-Level Attribution

When AI assists with specific code commits, use the `Co-Authored-By` trailer as a transparency signal, not as an authorship claim:

```
Co-Authored-By: Claude (Anthropic) <noreply@anthropic.com>
```

This follows GitHub's existing convention for indicating collaborative work and makes AI involvement discoverable in the git history.

---

## 4. References

### Publisher Policies
- [Nature Portfolio — AI Editorial Policy](https://www.nature.com/nature-portfolio/editorial-policies/ai)
- [ACM Policy on Authorship (includes AI provisions)](https://www.acm.org/publications/policies/new-acm-policy-on-authorship)
- [IEEE Author Guidelines (April 2024 AI disclosure update)](https://journals.ieeeauthorcenter.ieee.org/)
- [AI Policies in Academic Publishing 2025: Guide and Checklist](https://www.thesify.ai/blog/ai-policies-academic-publishing-2025)

### University and Thesis Guidance
- [Navigating AI Policies for PhD Students in 2025](https://www.thesify.ai/blog/phd-ai-policies-2025)
- [Generative AI Policies at the World's Top Universities: October 2025 Update](https://www.thesify.ai/blog/gen-ai-policies-update-2025)
- [Template: AI Use Disclosure Statement for Academic Papers](https://hastewire.com/blog/template-ai-use-disclosure-statement-for-academic-papers)
- [Understanding AI Disclosures in Academia — Paperpal](https://paperpal.com/blog/academic-writing-guides/ai-disclosures-purpose-guidelines-and-templates)

### GitHub and Open-Source Community
- [GitHub's 2026 Report on AI and Open Source](https://www.infoq.com/news/2026/03/github-ai-2026/)
- [GitHub Discussion: Tackling Low-Quality AI Contributions](https://github.com/orgs/community/discussions/185387)
- [AI-Assisted Development in 2026: Best Practices and Risks](https://dev.to/austinwdigital/ai-assisted-development-in-2026-best-practices-real-risks-and-the-new-bar-for-engineers-3fom)

### Comparative Analyses
- [Publisher Guidelines on AI-Assisted Scholarly Writing: A Comparative Analysis](https://project-rachel.4open.science/Rachel.So.Publisher-Guidelines-AI-Assisted-Scholarly-Writing-Comparative-Analysis.pdf)
- [Purdue University: Publisher Policies on AI](https://guides.lib.purdue.edu/c.php?g=1371380&p=10135076)
- [Ethical Guidelines for AI in Scholarly Publishing — Thematic Analysis](https://www.escienceediting.org/journal/view.php?number=358)
