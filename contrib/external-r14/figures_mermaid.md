# Paper 14 figures, in Mermaid

The paper compiles to PDF, so its four figures are TikZ
(`backend/paper/bounded_relaxation.tex`). Mermaid does not render inside LaTeX.

These are the same four figures in Mermaid, for slides, README pages, issue
threads and artifact pages, where TikZ does not render either.

**Edit them together.** A figure that says one thing in the paper and another in
a deck is the drift this project keeps building checkers against. Every number
below traces to the same artifacts the paper does:

| number | artifact |
|---|---|
| 470 / 237 / 72 / 161 / 136 / 3 / 8 | `external_r14_results.json` + `adjudication.json`, via `summarize.py` |
| 811 / 509 / 195 / 2 / 2 | `external_r14_ts_results.json` + `adjudication_ts.json`, via `summarize_ts.py` |
| 125 / 20 / 16.0% / 112 / 6 / 5.4% / p = 0.012 | `audit_rate.json`, via `audit_rate.py` |

---

## Figure 1 — the relaxation stage and the four obligations

Paper: `fig:stage`.

```mermaid
flowchart LR
    D["<b>detector</b><br/>classifier, rules, monitor"]
    R["<b>relaxation</b><br/>the stage this paper is about"]
    E["<b>enforcement</b><br/>block, escalate, review"]

    D -- "verdict <i>and its strength</i>" --> R
    R -- "weakened verdict" --> E

    R -.-> O

    subgraph O["R14: four predicates decidable from source"]
        direction TB
        A["<b>a. bounded</b><br/>consults the strength of the evidence it overrides"]
        B["<b>b. audited</b><br/>records every outcome, granted or refused"]
        C["<b>c. floored</b><br/>categories declared unreleasable are bounded separately, and more strictly"]
        F["<b>d. enacted</b><br/>every declared bound and audit field appears in the module named"]
    end

    R --> X["<b>what it found on our own request path</b><br/>a default-on stage whose entire guard was a substring test.<br/>Confidence swept 0.10 to 1.00 with the input fixed:<br/>verdict SAFE at every point, no record written."]

    classDef ok fill:#EEF3FA,stroke:#1A5FA8,color:#1A2A3A
    classDef bad fill:#F6EEF4,stroke:#A8156B,color:#3A1028,stroke-width:2px
    classDef neutral fill:#F2F2F2,stroke:#5C6773,color:#3D3D3D
    class D,E ok
    class R,X bad
    class A,B,C,F neutral
```

---

## Figure 2 — from source to verdict

Paper: `fig:pipeline`. The proposer judges nothing about safety; the rubric was
fixed before any external result was read.

```mermaid
flowchart TB
    S["subject source"] --> P

    P["<b>propose</b><br/>4 syntactic shapes:<br/>benign write, narrowing,<br/>waiver skip, discount<br/><i>a weakening write, dominated by a condition</i>"]
    P --> C{"<b>classify domain</b><br/>using the sibling rung's<br/>own guard classifiers"}

    C -- "a verdict existed<br/>and this weakened it" --> SF
    C -- "safe value because<br/>the check could not run" --> R3["<b>R3</b>, liveness rung<br/><i>deferred, reported not counted</i>"]
    C -- "a parameter was absent,<br/>nothing was judged" --> ST["<b>structural</b><br/><i>dropped</i>"]

    SF{"<b>decision surface?</b><br/>does this module make or<br/>post-process a safety decision"}
    SF -- no --> OUT["out of scope at step 0"]
    SF -- yes --> RU["<b>rubric</b>, fixed in advance<br/>A heuristic · B principal waiver<br/>C fail-open · D structural fact"]

    RU --> U["<b>UPHELD</b>"]
    RU --> PA["<b>PASS</b><br/>a real relaxation site<br/>where the invariant holds"]
    RU --> W["withdrawn"]

    classDef step fill:#EEF3FA,stroke:#1A5FA8,color:#1A2A3A
    classDef side fill:#F2F2F2,stroke:#5C6773,color:#3D3D3D
    classDef hit fill:#F6EEF4,stroke:#A8156B,color:#3A1028,stroke-width:2px
    classDef good fill:#FBF0E6,stroke:#CC5500,color:#4A2400
    class S,P,C,SF,RU step
    class R3,ST,OUT,W side
    class U hit
    class PA good
```

---

## Figure 3 — the funnel, in each language

Paper: `fig:funnel`. The last two stages are small because they are meant to be.

```mermaid
---
config:
  xyChart:
    width: 900
    height: 420
---
xychart-beta
    title "Proposals to verdicts. Blue: 28 Python subjects. Orange: 11 TypeScript subjects."
    x-axis ["proposed", "in R14 domain", "on a decision surface", "a real relaxation site", "violates the invariant"]
    y-axis "sites" 0 --> 850
    bar [470, 237, 136, 11, 3]
    bar [811, 509, 195, 4, 2]
```

Same data as a table, because a bar chart cannot show a 3 next to an 811:

| stage | Python (28 subjects) | TypeScript (11 subjects) |
|---|---:|---:|
| proposed by the scanner | 470 | 811 |
| in this rung's domain | 237 | 509 |
| deferred to the liveness rung | 72 | 91 |
| structural, dropped | 161 | 211 |
| on a decision surface | 136 | 195 |
| a real relaxation site (upheld + pass) | 11 | 4 |
| **violates the invariant (upheld)** | **3** | **2** |
| site precision | 8.1% | 2.1% |
| violation precision | 2.2% | 1.0% |

---

## Figure 4 — the pre-registered population test, falsified

Paper: `fig:auditrate`. The hypothesis was that stratum B would audit its
relaxations **more**. It audits them **less**, by 10.6 points, and the
difference does not survive dropping any one of three subjects
(`garak`, `mypy`, `pylint`).

```mermaid
---
config:
  xyChart:
    width: 760
    height: 300
---
xychart-beta
    title "Share of relaxation sites that leave a trace (Fisher exact two-sided p = 0.012)"
    x-axis ["stratum A: AI guardrails (20 of 125)", "stratum B: classical tooling (6 of 112)"]
    y-axis "audit rate, %" 0 --> 20
    bar [16.0, 5.4]
```

```mermaid
flowchart LR
    H["<b>pre-registered hypothesis</b><br/>classical tooling audits<br/>its relaxations MORE"]
    M["<b>measured</b><br/>16.0% vs 5.4%<br/>it audits them LESS"]
    V["<b>withdrawn</b><br/>and the effect itself is not robust:<br/>significance lost by dropping<br/>any one of three subjects"]
    H -- "tested on 6 further subjects,<br/>fetched after the registration" --> M --> V

    classDef q fill:#EEF3FA,stroke:#1A5FA8,color:#1A2A3A
    classDef r fill:#F6EEF4,stroke:#A8156B,color:#3A1028,stroke-width:2px
    class H q
    class M,V r
```
