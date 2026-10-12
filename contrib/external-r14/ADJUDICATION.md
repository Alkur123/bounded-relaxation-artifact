# Adjudication rubric for R14 findings in code we did not write

**Written and committed before any external finding was read.** The scanner
(`backend/engine/maryada_discover.py`) proposes candidates; this file says how a
candidate becomes a claim. Classifying after seeing the results, with no rule
fixed in advance, would let any distribution of findings be described as a
success.

This exists because of a recorded failure. R5-a, a sibling rung, once convicted
ControlArena's `ensemble_monitor` of an unlicensed combinator. The verdict was
wrong: the monitor samples one model ten times and averages, which is estimation
of one reading, not composition of several. **A false positive on correct
foreign code is not a mild defect. It is the failure mode that gets a checker
switched off**, and it is the outcome this rubric is built to detect rather than
avoid.

---

## Step 0a: which rung owns this site? (added 2026-08-18)

**Amendment, recorded rather than folded in silently.** The first external run
did not have this step, and its absence is the largest error the run contained:
five of its seven findings were "a safe value produced because the check could
not run", which is not R14's question at all. It is R3's (`engine/anupalabdhi.py`),
a sibling rung that has shipped a fail-open AST scanner since July and had
already recorded three of those sites.

Pooling them inflated R14's yield and, worse, hid the two contributions that are
genuinely separable. Every proposed site is now classified before it is read:

| domain | what it means | what happens to it |
|---|---|---|
| **R3** | a safe value produced because the check could not run: an exception handler, a `None` from a call made here, an error-status test, an in-band error sentinel | reported, and **never counted as R14 yield** |
| **STRUCTURAL** | the guard says a parameter is absent or empty, so there was nothing to judge | dropped |
| **R14** | a verdict existed and this branch weakened it | adjudicated below |

The classification is mechanical and uses R3's own guard classifiers, imported
rather than reimplemented, so the two rungs cannot drift apart on what an
unavailability guard is. A site the scanner cannot place lands in R14, which
costs precision rather than recall, and precision is what this document is for.

**This amendment strictly reduces what R14 may claim.** It was made after seeing
the first run's results, which is exactly the situation this rubric exists to
constrain, so it is written down as an amendment with its date and its reason
rather than presented as though it had always been the rule.

---

## Step 0: is the write on a safety-decision path at all?

A candidate is **out of scope** unless the value it writes reaches a decision
about whether content, a tool call, or an agent action is permitted, flagged, or
escalated. A benign write to a progress counter, a cache key, a display field or
a parser state is a scanner artifact, not a finding.

Judged by reading the source, not by module name. Out-of-scope candidates are
counted and reported as the scanner's false-positive load; they are never
quietly dropped.

---

## Step 1: what kind of trigger is it?

R14-a says a relaxation must consult the strength of the evidence it overrides.
That obligation does not have equal force behind every kind of trigger, and
pretending it does is how a static rule over-convicts.

### Class A — heuristic relaxation

The trigger is a pattern over untrusted content: a substring, a regex, a
keyword list, a similarity score, a model's own output. Nothing authenticates
it and the attacker can usually influence it.

**R14-a is fully engaged.** This is the class our own defect belonged to: forty
substring rules demoting a category to `SAFE` with no confidence term. A
heuristic that co-occurs with false positives also co-occurs with true ones, so
firing on it alone releases a maximally confident verdict exactly as readily as
a marginal one.

### Class B — principal waiver

The trigger is a decision by an identified party with authority: an
operator-configured allow list, a signed policy exemption, an explicit
per-deployment override.

**R14-a is NOT ENGAGED.** A waiver is not an estimate, so there is no strength
for it to consult; requiring one would be a category error. **R14-b and R14-c
remain fully engaged**: an unaudited waiver is still indistinguishable from a
hole, and a waiver that can reach a category the system elsewhere calls
unreleasable is still a path around every other control. This is exactly what
our own `rta.py` asserts when it says admin authority does not reach hard-block
categories.

### Class C — fail-open on error

The trigger is an exception, a timeout, a missing dependency, an unparseable
response. The permissive value is what the code produces when it could not
decide.

**R14-a is NOT ENGAGED** in its usual sense: there is no evidence to consult,
because obtaining the evidence is what failed. Reported as its own class, and
cross-referenced to the sibling rung R3 (`anupalabdhi`), whose whole subject is
that a silently dead arm looks identical to a clean pass. Whether a fail-open
default is right is a design decision the subject is entitled to make; whether
it is *recorded* is not, so R14-b still applies.

### Class D — structural fact

The trigger is a property of the request that cannot be influenced by the
content being judged: a feature is disabled, the scanner is not configured, the
input is empty, the value is of the wrong type.

**Out of scope for R14-a.** Not a relaxation of a verdict; a statement that no
verdict was produced. R14-b may still matter where the absence is invisible
downstream.

---

## Step 2: was the scanner simply wrong?

Every candidate that survives step 0 must be checked against the source for
these, because R14-a over-reports by construction:

- **Bounded elsewhere.** A threshold applied by the caller, by an imported
  helper, by an injected policy object, or by configuration the scanner cannot
  resolve. If a bound exists anywhere on the path, the finding is withdrawn.
- **Polarity misread.** `valid`, `clean`, `passed` and `level` mean different
  things in different files. If the write does not actually move the verdict in
  the permissive direction, the finding is withdrawn.
- **Audit reached another way.** R14-b already over-credits, so a withdrawal
  here is expected to be rare, but a trace emitted by a decorator or a context
  manager still counts.

Withdrawn candidates are reported by count and by cause. **The false-positive
rate is a headline number of this exercise, not a footnote.**

---

## Step 3: what may be claimed

For each surviving finding, the claim is limited to what static reading
supports:

- **Stated**: the trigger, the write, the absence of a bound or a trace, with
  file and line at a pinned commit.
- **Not stated**: that the site is exploitable, that any real deployment routes
  traffic to it, or that the maintainers were unaware.
- **Stated only where a proof exists** (amended 2026-08-18): reachability. A
  finding may say the path executes and produces the permissive result **only**
  if `prove_reachable.py` runs the shipped function, extracted from the pinned
  clone, and shows that outcome, with a control input that produces the strict
  outcome. Three findings carry such a proof. Every other finding remains a
  static claim and must say so. A proof of reachability constructs its input;
  an exploitability claim would have to stop doing that, and none is made.
- **Not stated**: any comparison of one subject against another as "more" or
  "less" safe. Different systems have different threat models and a raw site
  count is not a quality ranking.

A finding is reported to its maintainers before it appears in any paper if it
is a Class A relaxation that reaches an enforcement decision, and the paper says
whether that was done and what came back.

---

## What would falsify the exercise

Fixed in advance, so the result can come out against us:

1. **If nearly every candidate is withdrawn at step 2**, the scanner is a noise
   generator and R14 does not transfer to code that did not declare for it.
   That is a publishable negative result and it goes in the paper as one.
2. **If every surviving finding is Class B or C**, then R14 finds only design
   choices the subjects made deliberately, and the claim shrinks to "relaxation
   sites are undocumented and unaudited", which is weaker than the paper's
   current framing and must be stated that way.
3. **If findings cluster in one subject**, the result is about that subject, not
   about the field, and no general claim is available.

---

## Amendments made during the cross-language run (added 2026-08-19)

`PREREGISTRATION_cross_language.md` froze six things for the duration of the
TypeScript run and required any change to them to be recorded here with its
date and its reason, rather than folded in silently. Two were needed. Both are
declared below, and both are the kind that widen what can be *examined* without
widening what counts as a *violation*.

### A1. Identifier tokenisation before lexicon lookup

**What changed.** `contrib/external-r14/ts_frontend.py` tokenises an identifier
into snake_case before handing it to a lexicon. `isInjection` is looked up as
`is_injection`.

**Why.** The six lexicons anchor on `(?:^|_)` and `(?:$|_)` — snake_case word
boundaries — because they were written for Python. TypeScript is camelCase.
Measured directly: `_polarity_of("is_injection")` returns `risk` and
`_polarity_of("isInjection")` returns `None`. Without tokenisation the
instrument would report on naming convention rather than on semantics, and it
would do so in the direction that makes the second language look clean, which
is the worst available direction for a safety rule.

**What did not change.** Not one word was added to, removed from, or loosened in
any lexicon. The original spelling is what is recorded on the candidate and
shown to a reader. The effect is measured in both directions and pinned by
`backend/tests/test_maryada_ts_frontend.py`: with tokenisation off, the F1
validation finding disappears entirely.

**Honesty note.** This was decided *after* seeing a fixture result, which is why
it is an amendment and not part of the registration.

### A2. `RelaxationSite.module` accepts a non-Python source extension

**What changed.** `backend/engine/maryada.py` accepted only paths ending in
`.py`; it now accepts the TypeScript and JavaScript extensions as well.

**Why.** A site in `repo.ts` could not be constructed at all, so no predicate
could run on it.

**What did not change.** No predicate reads the extension, and `_source_of`
reads a module as text and never parses it as Python. The rejection case is
still live and is pinned by `backend/tests/test_maryada.py`, which now checks
both that a `.ts` path is accepted and that a `README.md` path is still refused.

### What was NOT amended, and the cost of that

The decision-surface rule was left exactly as it is, including the exemption
that treats a stratum B subject's whole package as its decision surface. That
exemption is why 121 of this corpus's 137 adjudicated sites are dismissed at
step 0, and it is the single largest cost to precision in both corpora.

It was tempting to remove it. Measured before deciding: applying the surface
regex uniformly to stratum B in the **Python** corpus takes the adjudicated set
from 136 sites to 75, raises violation precision from 2.2% to 4.0% — and
**destroys six of the eight passes**, including four of the six mechanisms in
the taxonomy that is the constructive half of that paper. The rule that admits
the noise is the same rule that finds the sites where the obligation is met.
The exemption stays, the precision cost is reported, and the reason it cannot
be cheaply removed is now measured rather than asserted.

### A3. `Array.isArray(x)` is translated as `isinstance(x, list)` (2026-08-19)

**What changed.** The TypeScript translator renders `Array.isArray(x)` into the
Python expression text as `isinstance(x, list)`.

**Why.** `EMPTINESS_CALL_LEXICON` knows `isinstance` and classifies a guard on
it over a parameter as STRUCTURAL — there was nothing to judge. It does not
know the JavaScript spelling of the same test, so `if (!Array.isArray(x))
return undefined` reached this rung while its Python twin did not. The
instrument was reporting on a spelling difference between two languages.

**What did not change.** Not one lexicon. This is a translation rule of exactly
the kind already applied to `.length` → `len()` and `.includes()` → `in`, and
it is confined to the second front end, so the Python corpus is byte-identical.

**Measured effect, both directions.** It moved **11 candidates** out of this
rung's domain into STRUCTURAL and **one site** off the decision surface: the
TypeScript corpus goes 196 → 195 adjudicated sites, false positives 23 → 22,
site precision 2.0% → 2.1%. One site with an `Array.isArray` guard survives, and
the reason is worth recording rather than patching: its guard is
`x === undefined || Array.isArray(x)`, and the shared classifier's structural
rule does not see through a disjunction. That is a limit of the classifier both
front ends share, not of the translation, and it is left alone.

**Found by this run, not before it.** It was recorded as an instrument defect in
the first cross-language write-up and fixed afterwards, which is the order the
registration required: the front end was frozen while the corpus was being
scanned, and the fix and its effect are dated here.

---

## A4. Corrections after the second adjudication (2026-10-12)

**What happened.** The pre-registered second adjudication
(`PREREGISTRATION_independent_adjudication.md`) returned 73 sites that `gpt-5`
upheld and this rubric's first application withdrew. Outcome O4 required the
first adjudicator to read each against the source. All 73 were read; 21 are
reversed to UPHELD and 52 stand. Every ruling, with both adjudicators' reasons,
is in `O4_author_reading.json`.

**The error the 21 expose is ours.** For four large stratum B subjects, step 0
was applied at module granularity (`_step0_note`): "in an analysis engine the
analysis produces the verdict ... only the reporting and suppression layer can
discard one." That note is right, and the shortcut contradicted it: 19 of the 21
are configured lists that name specific subjects to exempt (modules, words,
namespaces, function and method names, types, numbers, call specifiers,
patterns), which is the suppression layer the note describes and this rubric's
own Class B "operator-configured allow list". None writes a per-outcome trace.
The other two are a class A heuristic in Checkov's secret scanner (a secret is
dropped if any earlier line in the file opens a `data` block) and one relaxation in a
TypeScript gateway, described here unnamed while its disclosure is open.

**The line drawn, so it can be checked.** A condition that is part of what a
rule means (a built-in exemption, a constant, a special case, an option that
changes the rule for a whole kind of code such as `allow: ["constructors"]`) is
the analysis producing its verdict, and stays out of scope. A list that names
specific subjects to exempt is a waiver. A check switched off entirely is not a
relaxation of any verdict.

**What does not change.** `adjudication.json` and `adjudication_ts.json` are
left exactly as the pre-registered first-round record, so every number the
paper reports for that round still reproduces. The corrected figures are
computed from this amendment by `score_corrected.py` and are reported beside the
originals, never in place of them. The pre-registered agreement statistics are
computed against the original verdicts.
