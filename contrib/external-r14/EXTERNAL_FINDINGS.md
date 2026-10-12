# R14 against twenty-eight systems we did not design

**Date:** 2026-08-18. Every number here is produced by `summarize.py`, which
joins the scan to the hand adjudication and refuses to print if the two
disagree. Nothing below is typed in by hand.

Paper 14 stated its own worst limitation: *"One subject, and it is ours."* This
is the answer, and a large part of the answer is against us. The first version
of this document reported "seven findings". **That number was wrong, and this
document explains why.**

---

## 1. The correction that reshaped the result

The first run pooled three different things and called them all R14 findings.
Five of the seven were *"a safe value produced because the check could not run"*
— which is **not R14's question**. It is R3's (`engine/anupalabdhi.py`), a
sibling rung that has shipped a fail-open AST scanner since July and had
**already recorded three of those exact sites**.

The two rungs ask different questions and the difference is the reason both
exist:

> **R3** — did the check *run*, and is its silence being read as a clean signal?
> **R14** — a verdict *existed*. Did the stage that weakened it consult its strength?

A site where no verdict was ever produced cannot answer R14's question, because
there is nothing to have consulted. Every proposed site is now classified into
exactly one domain before anyone reads it, using **R3's own guard classifiers,
imported rather than re-implemented**, so the two rungs cannot drift apart on
what an unavailability guard is:

| domain | meaning | disposition |
|---|---|---|
| **R3** | exception handler, `None` from a call made here, error-status test, in-band error sentinel | reported, **never counted as R14 yield** |
| **STRUCTURAL** | a parameter is absent or empty, so there was nothing to judge | dropped |
| **R14** | a verdict existed and this branch weakened it | adjudicated |

**This strictly reduces what R14 may claim**, and it was decided after seeing
the first results, so it is recorded as a dated amendment in `ADJUDICATION.md`
rather than presented as though it had always been the rule.

---

## 2. The result

Twenty-nine subjects selected, twenty-eight scanned, **7,050 files**. Stratum A
is the original rule: a monitor, guardrail, scanner, detector or judge over
model or agent behaviour. Stratum B is classical detection tooling with the same
architecture — a detector whose findings pass through a suppression layer — and
exists to test whether this is an AI-era accident or an older property. **Strata
are never pooled.**

| | sites proposed | R14 | R3 | structural |
|---|---:|---:|---:|---:|
| **all subjects** | **470** | **237** | 72 | 161 |

Of the 237 R14-domain sites, **136 sit on a decision surface**. All 136 are
recorded in `adjudication.json` with a class and a reason: thirty-three were
read against source one at a time, and a hundred and three were dismissed at
step 0 by the role of the module holding them, since in an analysis engine the
analysis *produces* the verdict and there is no prior verdict to weaken:

| | count |
|---|---:|
| **upheld** — a real relaxation that violates the invariant | **3** |
| **pass** — a real relaxation where the invariant is satisfied | **8** |
| withdrawn | 125 |

**Two precisions, and quoting either alone misleads.**

- **Site precision — 8.1%** (11 of 136). Was this a relaxation site at all? A
  pass counts here: the site is real, the rule simply holds on it. Excluding
  the 103 analysis internals that step 0 dismisses, it is 33.3%; the lower
  figure is the headline because the scope rule that admitted them was ours.
- **Violation precision — 2.2%** (3 of 136), or **0.6%** over all 470 proposals.

Withdrawals by cause: 110 out of scope, 11 structural facts, 3 the scanner was
plainly wrong, 1 waiver we could not establish as safety-relevant.

---

## 3. The three upheld findings

All at the pinned commits in `external_r14_results.json`. **Two of the three are
executed**, not merely read — see §5.

### 3.1 A matched injection can be allowed through
`nemo-guardrails` · `library/injection_detection/actions.py:240` · class A ·
**executed**

The only upheld violation of R14's *bounded* predicate, and the shape the rung
was built for. Reached only *after* the YARA rules matched and the library has
logged `Input matched on rule ...`. In `omit` mode each matched instance is
decoded inside a `try`; a decoding error is caught, logged, and the loop
**continues without removing that instance**. The verdict is then taken from
whether the text changed:

```python
if modified_text != original_text:
    is_injection = True
else:
    is_injection = False        # nothing removed -> "no injection"
```

`_injection_detection_outcome` then falls through to `RailOutcome.allow`. The
guard consults whether the **repair** succeeded; it never consults the strength
of the **detection**, so a maximally confident match is released exactly as
readily as a marginal one. The subject's own docstring states the conflation:
*"False if the text is safe (i.e., not modified)"*.

**R3 scanned this file in July and could not reach this line.** It confirmed two
sites, both the `rules is None` case where the check never ran, and explicitly
classified the "no matches found" branch as an over-approximation rather than a
fault. This site is neither. That is the clearest available evidence that R14
asks a question its sibling does not.

### 3.2 The one path that removes a detection is the one that is silent
`llm-guard` · `input_scanners/anonymize_helpers/transformers_recognizer.py:308` ·
class B · **executed**

A deployer-configured `ignore_labels` entry suppresses a detected PII entity by
returning `None`. **R14's bound predicate is correctly not engaged** — a waiver
by an identified principal has no evidence strength to consult, and demanding a
confidence term from an operator allow list would be a category error. The audit
predicate is violated, and the shape is exact: the function has three
non-matching branches, two call `LOGGER.warning`, and the one that suppresses a
detection returns silently.

### 3.3 A bounded exemption that leaves no trace
`nemo-guardrails` · `library/jailbreak_detection/heuristics/checks.py:89` ·
class A

Prompts under twenty tokens return `{"jailbreak": False}` without running the
perplexity check. **The bound predicate is satisfied** and the reasoning is
sound and documented: GCG-style suffixes are not meaningful below that length.
The audit predicate is not. Nothing records that the check was skipped, so a
caller cannot distinguish an exempted prompt from a tested one. Included
precisely because it is the mild case, and because it shows the rung separating
its two obligations rather than firing as a single alarm.

---

## 4. Eight passes, six mechanisms — the constructive result

A rung that can only convict is an accusation generator. **Eight sites across
five subjects** are real relaxations where the obligation **is met**, and they do
not all meet it the same way. This taxonomy is the part of this work most worth
keeping: naming a defect class is worth less than naming the ways practitioners
have already solved it, and every one of these is running in production today in
a tool that has never heard of R14.

| mechanism | seen in | how the suppression is accounted for |
|---|---|---|
| **counted** | bandit | logs the suppressed check id **and** increments a metrics counter |
| **enumerable, by command** | detect-secrets | a scan path that *disables its own allowlist filter* to list what it suppressed |
| **enumerable, in the report** | checkov | `skipped_checks` is first-class, counted in the summary, serialised in output |
| **in band** | pylint | the suppression is emitted **as a finding**, in the same stream as the findings it suppressed — a reader cannot see the results without seeing the suppressions |
| **bounded** | detect-secrets | suppress only below a configured verification policy level (satisfies R14-a) |
| **downgraded, not discarded** | semgrep | the *action* weakens on a computed reachability property; the *record* is preserved and printed |

Two of these were found only by adjudicating the subjects added for the
audit-rate test, and one — pylint's in-band message — was a **false negative of
our own scanner**, whose audit lexicon does not know `add_message`.

A rung that can only convict is not an invariant, it is an accusation generator.
Four sites are real relaxations where the obligation **is met**, and all four are
in stratum B.

- **bandit** (`core/tester.py:94`) — the canonical suppression, an inline
  `# nosec` comment dropping a finding. The branch emits `LOG.debug` naming the
  suppressed test id **and** calls `self.metrics.note_skipped_test()`, so
  suppressions are counted in the run's own metrics rather than vanishing.
- **detect-secrets** (`filters/allowlist.py`, `transformers/config.py`) — an
  inline allowlist suppresses a detected secret, and the predicate itself
  neither logs nor counts. Withdrawn as a violation after reading the callers:
  `core/scan.py` ships `scan_for_allowlisted_secrets_in_file`, a dedicated path
  that **disables this very filter in order to enumerate what it suppressed**.
- **detect-secrets** (`filters/common.py:56`) — a secret is suppressed when its
  verification result is weaker than a configured minimum policy level. The
  relaxation consults a magnitude of the very evidence it overrides, and the
  threshold is operator configuration rather than a constant. This is R14-a
  satisfied in the strongest available sense, and the scanner read it as
  unbounded, so it is also a recorded false negative on the bound question.

### 4a. The generalisation this invited — pre-registered, run, FALSIFIED

Those four sites invited an obvious claim, and an earlier version of this
document made it: *"what varies is not difficulty but whether anyone asked."*
That is a claim about a **population**, and we had never measured one.

So we pre-registered it (`PREREGISTRATION_audit_rate.md`, committed **before**
the six subjects that test it were fetched), fixed the unit, the test, a
leave-one-out requirement and a power floor of 30 stratum-B sites, and ran it.

> **H1: classical detection tooling audits its relaxations more than AI
> guardrails do.** — **FALSE.**

| stratum | R14 sites | leave a trace | rate |
|---|---:|---:|---:|
| A — AI guardrails, agent frameworks | 125 | 20 | **16.0%** |
| B — classical detection tooling | 112 | 6 | **5.4%** |

Difference **−10.6pp**, Fisher exact two-sided **p = 0.012** — significant, and
**in the opposite direction**. Then it fails its own robustness check: dropping
any one of `garak`, `mypy` or `pylint` removes significance. Per falsification
criterion #2 fixed in advance, that makes it a statement about those subjects,
not about a field.

**Three consequences, and only the first is comfortable:**

1. **The generalisation is withdrawn.** bandit and detect-secrets are
   **exceptional within their own stratum**, not representative of it. Of six
   classical subjects, one counts its suppressions and the rest look like
   everyone else.
2. **The metric is narrower than the question, which partly explains the
   direction.** `audited` is site-local. It cannot see an obligation met at the
   *system* level — which is exactly how detect-secrets meets it, via a separate
   command that enumerates what its allowlist suppressed. That subject scores
   **0%** on this metric and is a **PASS** in adjudication. Both are correct.
3. **We do not re-slice to rescue it.** Stratum A contains agent frameworks as
   well as guardrails, and a narrower population might behave differently.
   Testing that *now*, having seen the result, would be choosing the population
   to fit the answer. Named as a follow-up needing its own pre-registration.

**What survives:** the obligation is demonstrably satisfiable in shipped
production tooling — four sites, three mechanisms — and nothing we measured
shows either stratum doing it systematically.

---

## 5. Executed, not only read

The review's central objection was that a correlational observation cannot
establish causation. True for a published table; **fixable here**, because for
these subjects we have the implementation.

`prove_reachable.py` reads the subject file from the clone at its pinned commit,
extracts the named function with a syntax-tree query, prints that source and its
digest so a reader can diff it, executes it in a namespace whose stubs record
calls and **decide nothing**, and reports what came back. Every case carries a
control that must produce the strict outcome.

| finding | triggering input | observed | control |
|---|---|---|---|
| NeMo omit mode | matched bytes are not valid UTF-8 | `is_injection=False`, text unchanged, **`RailOutcome.allow`**, matched rule still in `detections` | decodable bytes → `True`, `transform` |
| LlamaFirewall PII *(R3 domain)* | the model call raised | score `0.0` → below `0.7` → **`ALLOW`**, `status=SUCCESS` | real PII → `1.0`, `BLOCK` |
| LLM Guard ignore-list | label on the configured ignore list | detection dropped, **zero log lines** | unrecognised label → entity returned, one log line |

All three prove; all three controls hold; exit status is non-zero if any fails.

Established: the paths exist, are reachable with a constructed input, and produce
the permissive result at the pinned commit. **Not established:** that ordinary
traffic reaches them, that any deployment is configured as the harness configures
it, or that a maintainer is unaware. A reachability proof constructs its input;
an exploitability claim would have to stop doing that, and none is made.

---

## 6. The R3 domain, reported not counted

Seventy-two sites were deferred to R3 across the full 28-subject corpus. Two are worth naming because of *how they
were found*.

**LlamaFirewall's PII scanner** (`piicheck_scanner.py:90`) fails open: the error
sentinel `["ERROR"]` is explicitly excluded by the score conversion, giving
`0.0` → `ALLOW`, reported with `status=SUCCESS` while `ScanStatus.ERROR` sits
unused in the same enum. Its **sibling in the same directory, sharing the same
base class, fails closed** with the comment *"Due to an error, treating as
potentially compromised for safety"*.

**Six sites in NeMo's `jailbreak_detection/request.py`** map transport failures
to "not a jailbreak".

Neither file was in the July audit's declared set. That audit reached its
subjects by hand-written per-system declarations; these were reached by a
mechanical scan. **That is the second contribution of this work, and it is
independent of R14 being right about anything**: hand-declaration misses files,
and a scan does not.

### 6a. The deferral, checked rather than asserted

Until 2026-08-18 "deferred to R3" was a **claim**: the sites labelled R3's
and R3's scanner had never been run on them. `handoff_to_r3.py` closes that. The
permissive polarity is taken **per module from R14's own reading**, because R3
takes its polarity from the caller and never infers it — asking it about one
global guess would measure the guess.

| outcome | sites | why |
|---|---:|---|
| **both rungs flag it** | **27** | the deferral is complete |
| ours only | 39 | 15 narrowing + 7 waiver-skip are not sentinel returns at all; 17 are sentinel-shaped and land in R3's own documented gaps |
| outside R3's interface | 5 | the benign value is an empty container, not an `ast.Constant`, and R3's shapes match constants |
| **theirs only** | **122** | sites in the same modules R14 never proposed |

**The last row vindicates the deferral.** In the very modules R14 declined to
judge, the rung that owns them finds 71 sites R14 never proposed. Handing them
over was not shedding work — it is where they are seen better.

One defect in the handoff script is worth recording, because it is the same
shape as the findings: the first version silently substituted `False` when a
module's benign value was an empty container, which asked R3 about a value the
module never writes and would have scored the non-hit as a shape disagreement.
It now reports those five as outside the interface.

Three further NeMo sites are straight **replications** of what the July audit
already confirmed at an older commit.

---

## 6b. The floor predicate: run at last, and it found nothing

The review named four things a run against foreign code should look for:
unbounded relaxations, evidence-independent overrides, missing audit trails, and
**category-floor violations**. The first three were exercised from the start.
**The fourth was not**, and the reason was one hardcoded field: every discovered
site went to the certifier with `reaches_hard_block=False`, so R14-c reported
NOT ENGAGED for all 470 of them. Subject-level "does this project declare an
unreleasable category" was reported and then never connected to a site.

It is now wired. Engaging it needs the subject to declare that some category is
never to be released, and a relaxation that cannot tell those categories apart —
decided from the relaxation's **own guards**, resolved one frame into
same-module helpers.

Whole-function scope was tried first and was wrong. Our own defect reads as
floor-aware under it, because `apply_overrides` names a protected category in an
unrelated *up*-classification branch several screens from the demotion. With
guard scope the check reproduces **by machine** the verdict we had reached by
hand: the shipped defect reaches the floor and violates R14-a, R14-b **and**
R14-c; the repair does not; the distress site still does.

**Across all 28 subjects, not one declares a set of categories it treats as
unreleasable.** The widened corpus sharpens this. Three subjects *do* declare a
constant whose name says prohibited or forbidden, and none is about content:
`forbidden` holds the letters a German passport number may not contain,
`NAMEDTUPLE_PROHIBITED_NAMES` holds reserved attribute names, and
`PROHIBITED_FILES` holds lock-file names. **The words are there; the concept is
not**, and a rung that counted these as engaged floors would be manufacturing a
subject out of a word.

So R14-c cannot fail externally — **not because these systems satisfy it, but
because the concept it checks is not expressed anywhere in the corpus.** You
cannot violate an invariant nobody stated. Our own system states it (`rta.py`:
"admin authority does not reach them"), and stating it is what made our defect
describable as a floor violation rather than an ordinary bug. On this evidence,
"some categories are releasable by no override" is not part of how this software
is written. That absence is a more useful result than another conviction.

---

## 6c. Our own ceilings: we tried to fit them and could not

Paper 14's first limitation, and the standing top owed item, is that our two
bounds (`0.95` general, `0.70` hard-block) are **declared constants**.
`backend/eval/override_ceiling_measure.py` attempts to fit them and reports why
it cannot:

> The override table declares **78** trigger phrases. The adversarial corpus
> holds **3,364** samples. Samples containing any trigger phrase: **zero**.

The stage this entire paper is about is exercised by **none** of the data every
measured number in the project is computed on. One consequence is against us:
every published run sets `AEGIS_DISABLE_OVERRIDES=1`, and on this corpus that
flag changes nothing, because the table never fires there anyway.

No fitted ceiling is reported. Reading one off an empty sample is exactly the
false assurance the rung warns about. **What is owed is a corpus, not a number**:
per phrase, benign carriers of the kind each rule exists to rescue, and harmful
carriers that decide whether a ceiling can exist at all. Authoring the harmful
half is a human labelling task and is deliberately not generated.

---

## 7. Against the criteria fixed in advance

1. **"If nearly every candidate is withdrawn, the scanner is a noise
   generator."** Site precision is **8.1%** and violation precision **2.2%**.
   This is a triage instrument a human must finish. It is not something to put in
   anyone's CI as it stands, and the paper says so.
2. **"If every surviving finding is class B or C, the claim shrinks."** After the
   domain correction, **two of three upheld findings are class A**, and one of
   those reaches an enforcement decision and is executed. The class C population
   did not vanish; it was correctly reassigned to R3.
3. **"If findings cluster in one subject, the result is about that subject."**
   Two of three upheld findings are NeMo. With only three findings this criterion
   is close to firing, and the honest statement is that **R14's external evidence
   is thin: three findings, two subjects, one executed enforcement-reaching
   case.** What is *not* thin is the passes: the invariant is shown satisfiable
   in two independent mature tools.

---

## 8. The scanner was wrong, repeatedly, and that is reported

Before any subject was fetched it found **neither** of our own two ground-truth
sites; four defects were fixed against our own code first. Pointing it outward
found three more:

- **An initialiser below a bail-out clause is not a relaxation.** A guard clause
  at the top of a function puts a condition on the stack, after which
  `highest_score = 0.0` reads as a guarded weakening write. **8 of 10** LLM Guard
  candidates, every one correct code. Fixed by requiring the target to already be
  bound: you cannot relax a verdict that does not exist yet.
- **The same confusion in the helper classifier**, where a helper opening with
  `max_score = 0.0` counted as always-weakening.
- **A negated membership guard is not a waiver.** Walking the whole guard stack
  reported an exclusion list again at the next `continue` below it.

Every fix strictly **reduces** findings, all preserve the historical ground truth
exactly (the shipped defect still convicts on all five sites, the repair still
clears on all three, both in the R14 domain), and every subject was re-scanned
after each.

Three new detector shapes were added because the original could only see a benign
constant written to a name — which is not how guardrails usually weaken a verdict:
**narrowing** a findings collection, **arithmetic discount**, and a **waiver that
skips** the check entirely. They contributed 23 of the 136 surface candidates
and one recorded false positive each way.

---

## 9. Owed, and not done

* ~~**Nothing has been disclosed to any maintainer.**~~ **DONE 2026-08-20.**
  Both Python subjects were contacted: the class A NeMo Guardrails finding that
  reaches an enforcement decision went to **NVIDIA PSIRT**, and the class B
  LLM Guard finding to **`security@protectai.com`**. Neither went to the issue
  tracker, because both vendors' published policies say not to — see the dated
  amendment in `DISCLOSURE_DRAFTS.md`. The rubric's precondition for publishing
  the class A finding is discharged.
  **What is still owed is the other half: report what comes back**, including a
  maintainer saying we are wrong, at the same prominence as the finding.
  **One of the four has answered, and that one is now closed.** retire.js, a
  TypeScript-corpus subject, replied and shipped `8c911d6` on 2026-08-21 — a
  **partial** fix, recording which advisory repository was used but not whether
  the fetch was verified. After a follow-up naming the residual, it shipped the
  rest in `72438a0`, released as **5.6.0** on 2026-08-22 and confirmed on the
  issue on 2026-08-24; verified by running the released package rather than by
  reading the patch (`verify_retirejs_remediation.py`). The relaxation itself is
  unchanged, which was never the ask. The two Python subjects above, NeMo
  Guardrails and LLM Guard, both still read "awaiting", and if they still do at
  submission the paper says exactly that rather than stopping at "disclosed".
  **One of four is a report of what happened, not a base rate.**
* **A second adjudicator.** The rubric was fixed in advance and every verdict
  ships with its reason, but it is still one team applying its own rule.
* **PyRIT was not acquired** — at the resolved commit that repository contains a
  published documentation site and no package. Reported, not dropped.
* **Subjects are pinned to HEAD at scan time**, not to releases.
