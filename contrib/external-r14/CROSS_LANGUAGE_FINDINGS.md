# R14 in a second language

**Date:** 2026-08-19. Every number here comes from `summarize_ts.py`, which
joins the scan to the hand adjudication and refuses to print if the two
disagree. Nothing below is typed in by hand.

Paper 14's remaining scope limit was not a shortage of subjects. It was that all
twenty-eight of them were Python, because the proposer is a Python AST tool. The
number of subjects had grown and the population had not. This is the test of
whether that was a limit of the rung or a limit of the tool, pre-registered in
[`PREREGISTRATION_cross_language.md`](PREREGISTRATION_cross_language.md) before
the second front end existed and before any subject was fetched, and extended
once, in [`PREREGISTRATION_cross_language_ext.md`](PREREGISTRATION_cross_language_ext.md),
for a reason given below.

---

## 1. What was built, and what was deliberately not

A second front end, `ts_propose.mjs`, walks TypeScript and JavaScript with the
TypeScript compiler API. **It judges nothing.** It reports what it saw — which
conditions dominate a statement, what is written where, which calls appear in
the relaxing block, whether it is inside a `catch` — and `ts_frontend.py` makes
every judgement by calling the shipped Python:

| judgement | shipped code that makes it |
|---|---|
| is this name risk- or permit-carrying | `maryada_discover._polarity_of` |
| is this value the permissive extreme | `maryada_discover._is_benign_constant` |
| does the guard consult a magnitude | `maryada_discover._GuardInspector` |
| does the block leave a trace | `AUDIT_CALL_LEXICON`, `AUDIT_KEY_LEXICON` |
| is this a detection collection | `RISK_COLLECTION` |
| is this a principal waiver | `WAIVER_COLLECTION` |
| which rung owns the site | `classify_domain`, which imports R3's own classifiers |
| do the four predicates hold | `maryada.certify`, unmodified |

Two front ends that each decided what a risk-carrying name is would drift, and
the drift would be invisible. So the vocabulary has exactly one home.

**Three things could not be shared and are declared, not buried.** Guard
conditions are translated into Python expression text, and one the translator
cannot render is dropped — which loses bounds and therefore over-reports R14-a,
the same direction the Python front end already errs in. Guard resolution
follows same-file helpers one level, where the Python front end follows two.
The audit scan is re-expressed over the JS AST, applying the identical two
lexicons.

**Three amendments were needed and each is dated in `ADJUDICATION.md`:**
identifiers are tokenised to snake_case before lexicon lookup, because the
lexicons anchor on `(?:^|_)` and TypeScript is camelCase; `RelaxationSite.module`
accepts `.ts`/`.js`, which is an input guard and not a predicate; and
`Array.isArray(x)` is translated as `isinstance(x, list)`, which the shared
emptiness lexicon already knows. **No lexicon word changed** in any of the
three, and the rejection case is still live.

---

## 2. The instrument was made to fire before it was believed

The Python front end was validated on two known positives that predate it: our
own defect and its repair, at two real commits. This one has no history, so the
registration committed it to a weaker and explicit substitute — hand
translations of the three upheld findings from the Python run, each with a
repaired control.

| fixture | translated from | defect | repair |
|---|---|---|---|
| F1 verdict from repair | nemo-guardrails `injection_detection/actions.py:240` | **R14-a fires** | clean |
| F2 ignore-list waiver | llm-guard `transformers_recognizer.py:308` | **R14-b fires** | clean |
| F3 short-input exemption | nemo-guardrails `heuristics/checks.py:89` | **R14-b fires**, R14-a satisfied by the length bound | clean |

These fixtures are **synthetic**, which is a real weakness relative to the
Python front end's validation and is stated rather than glossed. Pinned by
`backend/tests/test_maryada_ts_frontend.py`, which also pins a recorded false
positive of this front end so that it stays visible.

---

## 3. The first registration, and the defect in it

Eight subjects were named in advance and all eight acquired: four agent
frameworks in stratum A, four classical detectors in stratum B. **442 proposed
sites over 6,858 files, 136 on a decision surface (137 before amendment A3), one upheld and one pass —
both in stratum B, with stratum A empty across all four subjects.**

Put the two stratum A lists side by side and the reason is ours, not the
language's:

| | Python stratum A | TypeScript stratum A, first registration |
|---|---|---|
| what they are | NeMo Guardrails, LLM Guard, Presidio, garak, LlamaFirewall… | LangChain.js, Mastra, LlamaIndexTS, OpenAI Agents SDK |
| | **systems whose product is a verdict** | **agent runtimes** |

A rung that asks whether the stage weakening a verdict consulted its strength
has little to ask of a codebase that mostly does not produce verdicts. Both
lists satisfy the letter of the stratum rule; one satisfies its intent.

Reporting that and stopping would leave a reader unable to tell a selection
defect from a real absence, so it was tested. The extension registration named
three TypeScript systems whose primary product **is** a verdict — Portkey's
gateway, promptfoo, Langfuse — and rejected a fourth candidate before fetching,
on the same rule, because it is a model-invocation SDK.

---

## 4. The corpus

Eleven subjects, **11,717 files**.

| | subjects | files | proposed | R14 | R3 | structural | on a surface |
|---|---:|---:|---:|---:|---:|---:|---:|
| **TypeScript** | 11 | 11,717 | **811** | 509 | 91 | 211 | **195** |
| Python | 28 | 7,050 | 470 | 237 | 72 | 161 | 136 |

Of the 195 decision-surface sites: **2 upheld, 2 passes, 191 withdrawn** — 166
dismissed at step 0 by module role, 22 as scanner error, 3 structural.

- **Site precision — 2.1%** (4 of 195)
- **Violation precision — 1.0%** (2 of 195), or **0.2%** over all 811 proposals

Worse than the Python corpus's 8.1% and 2.2%, for the same known cause: most
withdrawals are lint-rule and type-analysis internals admitted by the stratum B
exemption that treats a detector's whole package as its decision surface. See
`ADJUDICATION.md` for the measurement of what removing that exemption would
destroy.

### The selection correction worked, and not for the predicted reason

The extension registration expected better subjects to raise the stratum A site
**rate** toward Python's. Measured, the first stratum A was never site-poor:

| | files | surface sites | per 1,000 files |
|---|---:|---:|---:|
| TS stratum A, first registration | 5,479 | 42 | **7.67** |
| TS stratum A, extension | 4,859 | 59 | **12.14** |
| Python stratum A | 4,094 | 24 | **5.86** |

It was **survivor**-poor: 42 sites, none of which survived adjudication. The
corrected subjects raise the rate by half again *and*, more to the point,
produce sites a rubric can act on — both stratum A results in the corpus come
from them.

### ⚠ The shape mix is weaker evidence than the first run suggested

| shape | TS first | TS ext. | TS pooled | Python |
|---|---:|---:|---:|---:|
| benign write | 79.9% | **94.0%** | 86.3% | 77.4% |
| narrowing | 10.9% | 3.5% | 7.5% | 10.9% |
| waiver skip | 7.7% | 1.9% | 5.1% | 10.6% |
| discount | 1.6% | 0.5% | 1.1% | 1.1% |

The first run's mix sat strikingly close to Python's, and we said so. Adding
three verdict-producing subjects moved it to 94% benign write, because a
validator returning an object literal is most of what they contain. **The
proportions track what kind of system a subject is, not what language it is
written in.** All four shapes fire in both languages and none is a Python idiom
— that part stands — but proportion-matching is not the evidence for
language-independence that the eight-subject number made it look like.

---

## 5. The two upheld findings

**Langfuse · `packages/shared/src/in-app-agent/server/mcpPolicy.ts:557` · class B**

`withInAppAgentToolApproval` marks every tool `requireApproval: true` except
those `isInAppAgentAutoApprovedToolName` accepts — by name prefix, by a local
allowlist, or by a role-derived policy set. That predicate is the stage that
removes a human approval gate from an agent's tool call. Principal waiver, so
the bound obligation is not engaged. The audit obligation is, and **the module
contains zero logging calls**: nothing records that approval was skipped, so a
reader of the agent's trace cannot distinguish a tool a human approved from one
the policy waved through. The finding is the missing record, not the policy,
which is a considered role-based design.

**retire.js · `node/src/repo.ts:161` · class B · executed**

`loadJson` fetches every advisory the scanner reasons from. Under
`options.insecure` it sets `rejectUnauthorized = false`, disabling TLS
certificate verification on the channel its own evidence arrives on. Again a
principal waiver an operator may legitimately ask for; again unrecorded. The
only other occurrences of `insecure` in the package are the CLI flag's
declaration and its type, and the one line the function logs says
`Downloading <url> ...`.

`prove_reachable_ts.mjs` extracts the function from the pinned checkout by AST,
prints its source and a SHA-256 of it, transpiles it, and runs it against stubs
that record and decide nothing — `https.get` is a recorder that never fires its
callback, so what is read is what the function *asked for*. With
`insecure: true` the captured request carries `rejectUnauthorized: false` and
the captured log carries no mention of it. **Three controls hold**: unset, and
explicit `false`, both leave verification alone.

> **OUTCOME 2026-08-21 — acknowledged, code shipped, fix is partial.** Reported
> as a public GitHub issue on 2026-08-20 (`RetireJS/retire.js#615`); a maintainer
> answered within hours and closed it as completed via `8c911d6` the same day.
> His own restatement of the case — "It could be a good signal for consumers of
> the report (if that is not the same as the person running the scan)" — is this
> rung's threat model arrived at independently.
>
> **The commit records which repository, not whether it was verified.**
> `reporters/json.ts` gains `vulnerabilityRepositories`, the CycloneDX reporters
> gain a `retirejs:vulnerability-repository` metadata property, and `cli.ts:71`
> resolves the default so the field is populated without `--jsrepo`. But
> `node/src/repo.ts` is **not among the twelve files touched**: at `8c911d6` it
> still logs `Downloading <url> ...` (`repo.ts:152`) and still sets
> `rejectUnauthorized = false` under `options.insecure` (`repo.ts:160-161`). So
> `retire --outputformat json` and `retire --insecure --outputformat json`
> against the same repository still emit the same output. **The provenance half
> is closed; the relaxation record is not.**
>
> **OUTCOME 2026-08-24 — the residual is closed too, in released code.** We said
> the above on the issue and offered a PR. The maintainer's reply was a question
> rather than an acceptance — *if you know it's set to true, what does that tell
> you?* — answered with the third-party reader (an auditor or SBOM pipeline
> cannot distinguish "the repository said this" from "whatever answered said
> this") and with the aggregate case (across an org, which scans ran with
> verification off). He implemented it in **`72438a0`**, released as **5.6.0**:
> `ignoreRepositoryCertificateErrors` in the JSON report and
> `retirejs:ignore-repository-certificate-errors` under `metadata.properties` in
> every CycloneDX report, **emitted only when the flag is set** — his design, and
> the right one. Confirmed by **running the released package**, not by reading
> the patch: `verify_retirejs_remediation.py`, five report formats, present under
> `--insecure` and absent in every control.
>
> **The relaxation itself is unchanged**, and was never what we asked to change:
> `repo.ts` still sets `rejectUnauthorized = false` under the flag. R14 asks that
> a relaxation be recorded, not forbidden — so this is the rung's claim shown end
> to end on code we do not own. The accurate sentence is *reported, rejected as
> first worded, accepted on the reframing, partially remediated in `8c911d6`
> (v5.5.0) and fully remediated in `72438a0` (v5.6.0)*. The partial stage stays
> in the record; it is not tidied away now that it closed.
>
> **A methodological result.** The finding as first worded did not land — the
> maintainer's first reply was that this is an intentional feature, and it is. It
> landed on the reframing to *a verified run and an unverified run produce the
> same report*. The obligation is legible to a maintainer as **two runs, one
> output** and illegible as "an unaudited relaxation". Full record, including the
> verbatim thread and the follow-up posted, in `DISCLOSURE_DRAFTS.md`.

---

## 6. The passes, and the mechanism that proposed no site at all

**stylelint · `utils/suppressionsService.mjs:183`** drops a rule's warnings only
under `problemsCount <= suppressionsCount` — the bound obligation met in a
**quantitative** form stronger than any site in the Python corpus, comparing a
magnitude of the evidence against an operator-committed baseline. Exceed the
baseline and nothing is suppressed.

**Langfuse · `packages/shared/src/server/deletionGuard.ts:23`** skips a deletion
for an operator-configured project id and logs the skip with the configuration
key that caused it *and* every entity id skipped, so the waiver is not merely
recorded but enumerable afterwards.

### And the strongest mechanism in either corpus proposed no site

ESLint's `lib/linter/apply-disable-directives.js` is the file this exercise most
wanted to look at, and the scan returned nothing from it. That is a **true
negative, not a miss**, and reading it is how we know:

```js
if (disableDirectivesForProblem.length > 0) {
    const suppressions = disableDirectivesForProblem.map(directive => ({
        kind: "directive",
        justification: directive.unprocessedDirective.justification,
    }));
    ...
}
problems.push(problem);          // unconditional
```

**ESLint does not weaken the verdict. It annotates it.** The suppressed problem
stays in the list carrying the directive kind and the developer's written
justification; unused directives are reported separately; and it all surfaces
publicly as `linter.getSuppressedMessages()` and `result.suppressedMessages`.
There is no permissive write, no narrowing, no waiver-skip — so a proposer
looking for a *relaxation* correctly finds none.

Call it **retained, not removed**: a seventh mechanism, and the only one where
the suppressed finding remains a first-class finding addressable by API.

---

## 7. Every way this front end was wrong

- **`verdict: false` means *blocked* in Portkey — 10 sites, a new
  false-positive mechanism.** A plugin returns `{verdict, error, data}` where
  `verdict` is the pass/fail of the *check*, so the write the scanner read as
  permissive is the deny branch. The lexicon assumes low/false is the permissive
  extreme for a risk-carrying name; a subject whose verdict field is a pass/fail
  rather than a level of risk inverts that. This is distinct from a polarity
  guess being wrong about a *name*, and it is the sharpest instrument defect
  either corpus has produced.
- **`return null` from a detection-named handler — 11 sites.** Mastra's PII,
  prompt-injection and language detectors all end in
  `handleDetectedX(...): Message | null`, where `null` means "no message
  modification" — the line's own comment says so. A language-idiom difference,
  not a new rule: the Python front end has the same rule, and `null`-for-no-change
  is far more common in TypeScript.
- **`Array.isArray` was not reaching `EMPTINESS_CALL_LEXICON` — FIXED after the
  run, as amendment A3.** A type guard `if (!Array.isArray(x)) return undefined`
  is structurally Python's `if not isinstance(x, list): return None`, which the
  lexicon knows and calls STRUCTURAL; the JS spelling reached R14 instead. The
  translator now renders it, moving **11 candidates** out of the domain and one
  off the decision surface. Reported rather than patched *mid*-run, because the
  front end was frozen while the corpus was being scanned. One such site
  survives, and the reason is left alone rather than patched: its guard is
  `x === undefined || Array.isArray(x)`, and the shared classifier does not see
  through a disjunction.
- **`ok`, `scorers`, `blocksCheckpoint`, `skip`** all matched a polarity lexicon
  while meaning something else. The Python module's docstring already warns that
  polarity is a guess from a name; this is that warning coming true in a second
  naming culture.

**Declined rather than upheld, and recorded so a reader can disagree:**
promptfoo's `csrfProtection.ts:44` treats loopback-to-loopback as same-site.
That is a structural fact about two hostnames rather than a verdict being
weakened, and a local dev server documenting that intent is not a finding — but
it is the closest this corpus came to a third one.

---

## 8. Against the criteria fixed in advance

| fixed in advance | outcome |
|---|---|
| **H1:** zero R14-domain decision-surface sites | **no** — 196 |
| **H1:** every decision-surface proposal withdrawn as scanner error | **no** — 23 of 196; most were out of scope |
| **H1:** fires only on its own fixtures | **no** — every result is in a real subject |
| **H1, for:** at least one real site surviving as a pass or an upheld finding | **met** — two of each |
| **H2:** zero decision-surface sites in the corrected stratum A | **no** — 59 |
| **H2:** sites, but every one withdrawn | **no** — one upheld and one pass |
| **H2, for:** a stratum A survivor and a materially higher site rate | **met** — 7.67 → 12.14 per 1,000 files |

**Both hypotheses are supported on their own pre-registered terms**, and H2's
mechanism was not the predicted one: the first stratum A was survivor-poor
rather than site-poor.

### What is NOT claimed

That two languages are a population. The scope moves from "Python guardrails" to
"Python and TypeScript guardrails", which is still not "guardrails". The yield
is thinner than the Python corpus's, the fixtures are synthetic, precision is
lower, and eleven subjects is eleven subjects.

---

## 9. Owed, and not done

* ~~**Nothing has been disclosed to any maintainer**, here or in the Python
  corpus.~~ **DONE 2026-08-20**, all four subjects across both corpora. Both
  findings here are class B, so the rubric never compelled disclosure before
  publication — but retire.js is a security tool and Langfuse ships an agent,
  and telling them was the right thing to do regardless. **Langfuse** went to
  `security@langfuse.com`; **retire.js** to a public GitHub issue, which is
  their only published route since they ship no `SECURITY.md`.
  Responses tracked in `DISCLOSURE_DRAFTS.md`. **retire.js answered 2026-08-21
  and the finding is fully remediated upstream as of 2026-08-24** — partial
  `8c911d6` (v5.5.0), residual closed in `72438a0` (v5.6.0), verified against the
  released package (see the two OUTCOME blocks on that finding above);
  **Langfuse is still "awaiting"**, and silence is itself a reportable outcome
  rather than a gap to leave blank. **One remediation out of four contacted is
  not a base rate**, and nothing here should be read as one.
* **A second adjudicator**, as in the Python run.
* **The fixtures are synthetic.** Real known positives in this language, at two
  commits of the same project, would be a stronger validation and do not exist.
* **Subjects are pinned to HEAD at fetch time**, not to releases.
