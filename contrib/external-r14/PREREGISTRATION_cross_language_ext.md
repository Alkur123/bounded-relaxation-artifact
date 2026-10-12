# Pre-registration, extension: the first TypeScript stratum A was the wrong stratum A

**Written and committed after the first cross-language run and before any
subject named below was fetched.** The commit order is the pre-registration and
is checkable in the log. This is an *extension* with its own date and its own
reason, not a revision of
[`PREREGISTRATION_cross_language.md`](PREREGISTRATION_cross_language.md), whose
result stands exactly as reported.

---

## The defect in the first registration, stated plainly

The first cross-language run yielded one upheld finding and one pass, and
**both are in stratum B**. Stratum A — four TypeScript subjects — produced 137
proposals, 42 decision-surface sites, and nothing that survived adjudication.

Read the first registration's stratum A list next to the Python run's:

| | Python stratum A | TypeScript stratum A (first run) |
|---|---|---|
| what they are | NeMo Guardrails, LLM Guard, Presidio, garak, LlamaFirewall, Rebuff, Vigil, ControlArena, Inspect AI… | LangChain.js, Mastra, LlamaIndexTS, OpenAI Agents SDK |
| | **guardrails, scanners and monitors** | **agent frameworks** |

The Python stratum A is dominated by systems whose *product* is a verdict about
content or behaviour. The TypeScript stratum A I selected is dominated by
systems whose product is an agent runtime, in which a detector is an optional
component someone else supplies. Both satisfy the letter of the stratum rule —
"a monitor, guardrail, scanner, detector or judge over model or agent
behaviour" — because these frameworks do ship processors and scorers. They do
not satisfy its intent.

**A rung that asks "did the stage weakening a verdict consult its strength" has
little to ask of a codebase that mostly does not produce verdicts.** The
selection, not the language and not the rung, is the most likely explanation of
that empty stratum, and it is our error rather than a property of TypeScript.

Reporting that and stopping would leave the reader unable to tell a selection
defect from a real absence. So it is tested.

---

## Hypothesis, fixed in advance

> **H2.** The empty stratum A of the first TypeScript run is explained by
> subject selection. Scanning TypeScript systems whose *primary product is a
> verdict* — guardrail gateways and red-teaming/eval harnesses — will yield
> decision-surface sites in stratum A at a rate comparable to the Python
> stratum A, and at least one that survives adjudication.

**H0** is that it will not: that TypeScript stratum A is empty for a reason that
survives better selection, which would mean either that this ecosystem's
guardrails genuinely relax less, or that the front end sees less in them than
the Python one does in its own stratum A.

**A result supporting H0 is reported as prominently as one supporting H2**, in
the paper's results section. The precedent is this project's own falsified
audit-rate hypothesis.

---

## Subjects, fixed in advance

Selected for one property, stated before fetching: **the system's primary
product is a verdict about content, a model, or an agent's behaviour**, and it
is written in TypeScript or JavaScript.

| subject | owner | why it is stratum A in the intended sense |
|---|---|---|
| `Portkey-AI/gateway` | Portkey | An AI gateway with a first-class **guardrails engine**: named checks run on requests and responses and a verdict decides what passes. The closest TypeScript analogue of NeMo Guardrails or LLM Guard that exists. |
| `promptfoo/promptfoo` | promptfoo | A red-teaming and evaluation harness whose graders and moderation plugins **produce verdicts about model output**. The closest analogue of garak. |
| `langfuse/langfuse` | Langfuse | Tracing and **evaluation** for LLM applications; its evaluators score traces, which is the same object ControlArena's monitors produce. |

`vercel/ai` was considered and **rejected before fetching**, on the same rule
that made this extension necessary: it is a model-invocation SDK, not a producer
of verdicts, and admitting it would repeat the defect this registration exists
to correct.

Every subject is pinned to the commit resolved at fetch time. A subject that
cannot be acquired is reported as not acquired, never dropped.

---

## What may not change

Everything frozen by the first registration stays frozen: the four predicates,
`classify_domain`, R3's guard classifiers, the six lexicons and the benign-value
set, the decision-surface regex, and the adjudication rubric including step 0.
The two amendments already recorded in `ADJUDICATION.md` — identifier
tokenisation and the module-suffix guard — remain in force and are not extended.

**The second front end is frozen too.** It was written and validated before
these subjects existed and it is not to be adjusted after seeing what they
contain. If it misses something here, that is a reported miss.

---

## Outcomes, fixed in advance

Reported whichever way they fall, and **reported separately from the first
run's numbers** so that the pooled figure can never be the only one a reader
sees:

1. Sites proposed, by subject, by shape, by domain, on the same table columns.
2. Decision-surface sites adjudicated under the unchanged rubric.
3. Both precisions, for the extension alone and for the TypeScript corpus pooled.
4. **The stratum A comparison this registration exists to make**: decision-surface
   sites per thousand files in TypeScript stratum A, before and after the
   selection correction, against Python stratum A.

### What counts against H2

- **Zero decision-surface sites across all three**, which would mean better
  selection did not help and the empty stratum A is not a selection artifact.
- **Sites, but every one withdrawn**, in which case the yield gap is real and
  the honest statement is that this rung finds less in TypeScript guardrails
  than in Python ones, with no explanation offered that the data does not
  support.

### What counts for H2

- At least one decision-surface site surviving as a pass or an upheld finding
  **in stratum A**, and a stratum A site rate materially above the first run's.

### What is not claimed either way

That three more subjects fix the yield. The paper's yield is thin and will
remain thin; this tests one specific explanation for one specific empty cell.

---

## Registered

2026-08-19, after the first cross-language run reported and committed
(`4bc9ba1`), before any subject above was fetched.
