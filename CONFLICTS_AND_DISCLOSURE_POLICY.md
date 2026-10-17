# Conflict-of-interest and disclosure policy

Applies to: the bounded-relaxation (R14) audit in this repository, and future audits of third-party AI-safety tools by the same author.
Published: 17 October 2026. Author: Jaswanth Alkur (ORCID 0009-0006-8826-866X).

This policy was written down after the audit was run. It records the practice the audit followed, so that readers can check it against the record in this repository and hold future audits to it.

## Conflicts of interest
- **Competing interest.** The author founded Aegis AI, an early-stage company building AI-governance software. Some audited tools (for example guardrail frameworks) may compete with it. Every publication and disclosure arising from these audits states this.
- **No payment.** No audited project, and no competitor of an audited project, has paid for or funded this work. If that ever changes, it will be disclosed on the affected output.
- **No equity.** The author holds no equity in any audited project's organisation.
- **No recusal is possible**, because the author is the only evaluator. The mitigations are listed instead:
  1. methods and decision rules are pre-registered before running;
  2. the rubric, every verdict (including withdrawn ones) and all code are public in this repository;
  3. upheld findings are executed against the projects' released packages, with controls;
  4. silence and disagreement from maintainers are reported with the same prominence as confirmations.

## Disclosure
1. **Privately first**, through the channel the project names: its SECURITY.md or security contact. A public issue is used only where the project names none.
2. **Executed proof.** A finding is reported with a script that reproduces it against the pinned release, and a control.
3. **Unnamed while the vendor is silent.** A finding is published without naming the project until the maintainer responds, or until **60 days** after the report, whichever comes first. The exception is a finding that would be an information hazard (AEF-1 §5.4); those stay withheld.
4. **Outcomes reported**, including no response.
5. **No live testing** of any third-party service. All analysis runs on local copies of public code.

Contact: jaswanthalkur@gmail.com
