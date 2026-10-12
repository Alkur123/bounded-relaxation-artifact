# Pre-registration: is R14 a property of guardrails, or of Python guardrails?

**Written and committed before any subject in the list below was fetched or
scanned, and before a single line of the second front end was written.** The
commit order is the pre-registration and is checkable in the log.

---

## Why this, and why now

Paper 14's own limitations section concedes a scope limit that the corpus cannot
argue its way out of:

> The proposer is a Python AST tool. The population it can speak about is
> **Python guardrails**, not guardrails.

Twenty-eight subjects do not fix that, because all twenty-eight are Python. The
number of subjects grew and the population did not. A reviewer is entitled to
read the whole external run as a fact about one language's idioms — about how
Python code happens to spell a permissive write — rather than about how
detection systems are built.

The claim under test is the one that separates those two readings.

---

## Hypothesis, fixed in advance

> **H1.** The invariant, the rubric and the certifier are language-independent.
> Only the *front end* that proposes sites is language-specific. A second front
> end, written for TypeScript and JavaScript to the **same four shapes** and
> reading the **same pre-registered lexicons**, handing its candidates to the
> **unmodified** certifier and the **unmodified** domain classifier, will
> propose adjudicable relaxation sites in subjects written in that language.

**H0** is that it will not: that the shapes are Python idioms, that the lexicons
do not survive a different naming culture, or that what comes back is noise a
rubric cannot act on.

A result supporting **H0 is a real outcome and will be reported as prominently
as one supporting H1**, in the paper's own results section and not in a
footnote. The precedent is the audit-rate hypothesis in
`PREREGISTRATION_audit_rate.md`, which this project pre-registered, tested, and
**falsified**, and then published against itself.

---

## What may not change, and what counts as a protocol violation

The point of the exercise is destroyed if the rung is quietly widened until the
new language passes. Frozen for the duration:

| frozen | file |
|---|---|
| the four predicates | `backend/engine/maryada.py` |
| the domain classifier (R14 / R3 / STRUCTURAL) | `maryada_discover.classify_domain` |
| R3's guard classifiers it imports | `backend/engine/anupalabdhi.py` |
| the six lexicons and the benign-value set | `maryada_discover` module constants |
| the decision-surface regex | `adjudication.json::_surface_regex` |
| the adjudication rubric, including step 0 | `ADJUDICATION.md` |

The second front end must **read** the lexicons out of the shipped Python
module rather than restate them, so the two front ends cannot drift into
disagreeing about what a risk-carrying name is. Any change to any row above is
a **protocol violation** and will be recorded as a dated amendment in
`ADJUDICATION.md`, in the same form as the R14/R3 domain split was, rather than
folded in silently.

---

## Subjects, fixed in advance

Selected before scanning, by the same stratum rule as the Python run. Two
strata, never pooled.

**Stratum A — AI guardrails, monitors and agent frameworks, in TS/JS**

| subject | owner |
|---|---|
| `openai/openai-agents-js` | OpenAI |
| `langchain-ai/langchainjs` | LangChain |
| `mastra-ai/mastra` | Mastra |
| `run-llama/LlamaIndexTS` | LlamaIndex |

**Stratum B — classical detection tooling in TS/JS with a suppression layer**

| subject | owner |
|---|---|
| `eslint/eslint` | OpenJS Foundation |
| `typescript-eslint/typescript-eslint` | typescript-eslint |
| `stylelint/stylelint` | stylelint |
| `RetireJS/retire.js` | RetireJS |

Stratum B is the same test it was in the Python run: whether this is an AI-era
accident or an older property of detectors. ESLint is the sharpest available
subject in any language, because its suppression layer is a first-class,
documented feature (`/* eslint-disable */`, `--no-inline-config`,
`reportUnusedDisableDirectives`) rather than an implementation detail.

Every subject is pinned to the commit resolved at fetch time and the hash is
recorded. A subject that cannot be acquired is **reported as not acquired**,
never dropped, as PyRIT was.

---

## The instrument must be shown to fire before it is believed

The Python front end was validated on two known positives that predate it: our
own shipped defect and its repair. The second front end has no such history, and
saying so is part of the registration.

It will be validated on **hand-translated fixtures of the three upheld findings
from the Python run** — the NeMo omit-mode verdict, the LLM Guard ignore-list
waiver, and the NeMo short-input exemption — plus a repaired control for each
that it must **not** fire on. These fixtures are **synthetic**, which is a
weaker validation than the Python front end's, and that difference will be
stated in the paper rather than glossed.

A front end that cannot fire on a translation of a finding we have already
adjudicated is not ready to be pointed at anybody's code, and if it cannot, that
is the result and the run stops there.

---

## Outcomes, fixed in advance

Reported whichever way they fall:

1. **Sites proposed**, by subject, by shape, by domain (R14 / R3 / STRUCTURAL),
   with the same table columns as the Python run so the two are comparable.
2. **Decision-surface sites**, adjudicated under the unchanged rubric, into
   upheld / pass / withdrawn with the withdrawal cause.
3. **Both precisions**, site and violation, computed the same way.
4. A **shape-mix comparison** between the two languages. If the same four shapes
   fire in wildly different proportions, that is evidence the shapes are partly
   idiomatic, and it will be reported as such.

### What would count against H1

Fixed now, so it cannot be renegotiated later:

- **Zero R14-domain decision-surface sites** across all eight subjects. The
  front end found nothing to adjudicate and the cross-language claim is not
  supported.
- **Every decision-surface proposal withdrawn as FP** (the scanner was wrong
  about what the code does). That is an instrument that does not transfer, as
  distinct from a language that has no relaxations.
- The front end **only** fires on the fixtures and never on real source. That is
  a tool tuned to its own tests.

### What would count for H1

- At least one decision-surface site in a real subject that survives
  adjudication as a **pass or an upheld finding** — either is evidence the rung
  is askable in the language, since a pass means the obligation was recognised
  and met.

### What is NOT claimed either way

That two languages are a population. Eight TS/JS subjects would make the scope
"Python and TypeScript guardrails", which is still not "guardrails". The scope
limit shrinks; it does not disappear, and the paper will say so.

---

## Registered

2026-08-18, before fetching. Same session that unified the corpus prose and
added `verify_paper_consistency.py`.
