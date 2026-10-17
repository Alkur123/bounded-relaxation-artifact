# AEF-1 Checklist: bounded-relaxation (R14) audit

Filled voluntarily against AEF-1, "Minimum Operating Conditions for Independent Third Party AI Evaluations", version 1 (4 December 2025), Appendix A. Standard: https://aievaluatorforum.org/initiatives/minimum-operating-conditions
Filled 17 October 2026 by the evaluator. Not reviewed or endorsed by the AI Evaluator Forum.

**Evaluation:** a static audit of 39 open-source AI guardrails, monitors and detection tools (28 Python + 11 TypeScript, 18,767 files) at pinned commits. It looks for stages that weaken a safety verdict without consulting or recording it. Everything is in this repository.
**Evaluator:** Jaswanth Alkur, an individual and the founder of Aegis AI. **System providers:** the maintainers of the 39 projects. There was no agreement with any of them, and all access was public.

**Does this evaluation satisfy all the minimum requirements of AEF-1? No.** Requirement 2.5 (recusal) cannot be met by a single evaluator. Requirement 2.3 is met only partly, because the conflict-of-interest policy was published after the audit. See below.

## 1: Sufficient Access and Resources
| | Condition | Fulfilled? | Notes/Evidence |
|---|---|---|---|
| 1.1 | Sufficient technical access (Req.) | Yes | Full public source at pinned commits. Upheld findings were executed against released packages, with controls. |
| 1.1.1 | Query access | Yes | Each tool was run locally from its released package. |
| 1.1.2 | Scaffolding | Yes | Run as released, with default configuration. |
| 1.1.3 | Safeguard exemptions | N/A | The property is in the tools' own code. |
| 1.1.4 | Intermediate states | Yes | Full source and local runtime. |
| 1.1.5–1.1.6 | Finetuning / weights | N/A | No models are evaluated. |
| 1.1.7 | Other tools | N/A | |
| 1.1.8 | User data | No | Not used; not needed for a code property. |
| 1.2 | Provider shared information (Rec.) | No | No provider involvement before disclosure. Public documentation and security policies were read. |
| 1.3 | Sufficient compute (Req.) | Yes | Static scan and local executions on one workstation. |
| 1.4 | Adequate time (Req.) | Yes | Self-set timeline with no external deadline. Pre-registered. |
| 1.5 | Legal safe harbor (Rec.) | No | No formal safe harbor. Analysis covered only public code under open-source licences, run on local copies, with no live testing. |

## 2: Minimized Conflicts of Interest
| | Condition | Fulfilled? | Notes/Evidence |
|---|---|---|---|
| 2.1 | No contingent compensation (Req.) | Yes | Unpaid; no funding for this work. |
| 2.2 | No provider control (Req.) | Yes | No audited project owns or controls the evaluator. |
| 2.3 | Published CoI policy, applied (Req.) | Partly | [CONFLICTS_AND_DISCLOSURE_POLICY.md](CONFLICTS_AND_DISCLOSURE_POLICY.md), published 17 Oct 2026, **after** the audit. It records the practice the audit followed. |
| 2.4 | CoI disclosed (Req.) | Yes | Paid by a provider or competitor: no. Funding from a provider or competitor: no. Provider equity in the evaluator: no. Evaluator equity in providers: no. **Works for a competitor: yes.** The evaluator founded Aegis AI, which builds AI-governance software and may compete with some audited tools. Other conflicts: the checker is the evaluator's own research method. |
| 2.5 | Recusal (Req.) | **No** | There is one evaluator, so recusal is impossible. Mitigations: pre-registration, all verdicts (including withdrawn ones) public, executed proofs, and maintainer silence reported. |
| 2.6 | Separate agreements (Rec.) | Yes | None exist. |

## 3: Analytic Autonomy
| | Condition | Fulfilled? | Notes/Evidence |
|---|---|---|---|
| 3.1 | Define properties (Rec.) | Yes | |
| 3.2 | Method autonomy (Req.) | Yes | Pre-registered rubric and metrics. |
| 3.3 | Direct access (Rec.) | Yes | |
| 3.4 | Editorial control (Req.) | Yes | No provider review rights. |

## 4: Transparent Methods and Results
| | Condition | Fulfilled? | Notes/Evidence |
|---|---|---|---|
| 4.1 | Methodological transparency (Req.) | Yes | Full replication package. Low precision is reported as measured. |
| 4.2 | Disclosure rights (Rec.) | Yes | Public systems under public licences. |
| 4.3 | Audiences not narrowed (Rec.) | Yes | Negative outcomes and maintainer silence are reported. |
| 4.4 | No misrepresentation (Rec.) | Yes | No provider statements about the evaluation. |
| 4.5 | No content-based delay (Rec.) | Yes | Only the coordinated-disclosure hold (5.4). |
| 4.6 | No provider redaction authority (Req.) | Yes | None granted. |
| 4.7 | Redaction disclaimer (Rec.) | Yes | No authority granted. One finding is described unnamed under coordinated disclosure, and the repository says so. |

## 5: Protection of Sensitive Information
| | Condition | Fulfilled? | Notes/Evidence |
|---|---|---|---|
| 5.1 | Permission for non-public info (Req.) | Yes (N/A) | Only public information was used. |
| 5.2 | Methods not gamed or leaked (Rec.) | Yes | Static property of released code. |
| 5.3 | Protect confidential info (Req.) | Yes (N/A) | None received. |
| 5.4 | Responsible disclosure (Req.) | Yes | Findings were reported privately through each project's named channel before publication: NVIDIA PSIRT for NeMo Guardrails (acknowledged), security@protectai.com for LLM Guard (no response, reported as such), security@langfuse.com for Langfuse (fixed in v4.18.0), a GitHub issue for retire.js (no SECURITY.md; fixed in 5.6.0), and one further project's named security contact for a finding that this repository describes without naming the project, pending a response. Policy: [CONFLICTS_AND_DISCLOSURE_POLICY.md](CONFLICTS_AND_DISCLOSURE_POLICY.md). |
