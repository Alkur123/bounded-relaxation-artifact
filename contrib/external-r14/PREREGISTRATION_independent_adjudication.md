# Pre-registration: a second, different-family adjudication of every R14 decision-surface site

**Written 2026-10-12, BEFORE any model call was made.** The outputs named below
do not exist at the time of writing. This file is committed before the run
script is executed, and the script reads nothing from it.

## Why this exists

Paper 14 (`bounded_relaxation`) states as a limitation that "adjudication is
ours, and it is the load-bearing step ... a second adjudicator is owed". Every
one of the 331 decision-surface verdicts (136 Python in `adjudication.json`,
195 TypeScript in `adjudication_ts.json`) was made by the authoring side under
`ADJUDICATION.md`. This run asks whether an independent party, given the same
rubric and the same per-site evidence, reproduces those verdicts.

What it can establish: whether the rubric is **determinate** enough to be
reproduced. What it cannot establish: that either set of verdicts is
**correct**. A human adjudicator who has not seen this work is still owed, and
the paper will keep saying so.

## Procedure, fixed now

- Adjudicator: `gpt-5` via the OpenAI Responses API, reasoning effort medium,
  no access to the authoring session. Script:
  `contrib/external-r14/independent_adjudicator.py`, reusing the call helper
  already used for the namespace-collision Amendment 3.
- Unit: every entry of `adjudication.json` and `adjudication_ts.json` (331).
- The model receives, per site: the rubric (`ADJUDICATION.md` Steps 0, 1, 2
  and 3, verbatim; the Step 0a domain step is omitted because it is mechanical
  and already applied to every site in the unit), the subject's name, stratum
  and the one-line description recorded in the run's results file, the module
  path and line, the scanner's own record of the site (function, kind of
  write, polarity, value written, guard text, whether a bound and an audit call
  were found and by what symbol, shape), and source context read from the
  pinned clone (`C:/r14-subjects`, `C:/r14-subjects-ts`, each at the commit in
  the paper's provenance table): the enclosing function capped at 160 lines,
  plus every other line in the same module that names that function, with two
  lines either side.
- Withheld: the first verdict, its class, its finding name, its reason, whether
  it was executed, any prior-work cross-reference, and every aggregate number.
- Labels: verdict UPHELD / PASS / WITHDRAWN / UNSURE, with class
  A / B / C / D / OUT / FP as defined in the rubric, and a one-sentence reason.
- Batches of 10 sites. A batch whose JSON does not cover every site is retried
  once; sites still missing are recorded MISSING, excluded, and counted.

## Known asymmetry, stated before the data

The first adjudicator could follow a bound into a caller, an imported helper or
configuration anywhere in the repository (rubric Step 2, "bounded elsewhere").
The model sees one function and its same-module call sites. Disagreements where
the first verdict is WITHDRAWN and the second is UPHELD are therefore expected
to include sites the first adjudicator withdrew for a bound outside the module.
They will be counted and each one read, not explained away in aggregate.

Step 0 for four large stratum B subjects was applied at module granularity
(`_step0_note`); the model judges those 103 sites one by one. This is a second
expected source of disagreement, also counted.

## Pre-registered outcomes

- **O1.** Raw agreement and Cohen's kappa on the three-way verdict
  (UPHELD / PASS / WITHDRAWN), over sites the model did not label UNSURE or
  MISSING; reported overall, for Python and for TypeScript. Because about 95%
  of first verdicts are WITHDRAWN, raw agreement is expected to be high by base
  rate alone, so kappa is the headline, and agreement on the **15 non-withdrawn
  sites** is reported separately.
- **O2.** Survival of each of the 5 UPHELD and 10 PASS sites: does the second
  adjudicator give the same verdict? Reported site by site.
- **O3.** Intersection counts: findings UPHELD by both, passes PASS by both.
  This is the figure that survives either adjudicator being wrong.
- **O4.** Sites the second adjudicator UPHELDs that the first WITHDREW. Each is
  read by the author against the source and reported with the outcome of that
  reading; none is added to the paper's findings without that reading.
- **O5.** Distinct pass mechanisms (of the paper's nine) whose sites both
  adjudicators call PASS.

## Adverse prior and what would change the paper

Prior, committed now: kappa is moderate (0.4 to 0.6); the model upholds more
sites than the first adjudicator, mostly through the bounded-elsewhere
asymmetry; at least one of the 15 non-withdrawn verdicts is not reproduced.

- If fewer than 3 of the 5 UPHELD findings survive (O2), the paper reports the
  findings as adjudicator-dependent, with both counts at equal prominence.
- If fewer than half of the 10 PASS verdicts survive, the taxonomy section says
  so and reports which mechanisms both adjudicators recognise.
- If kappa is below 0.4, the paper says the rubric is not yet determinate
  enough to be applied by a second party without training, and states that as a
  threat to validity rather than claiming the adjudication is reproducible.
- Whatever the result, O1 to O5 are reported and the original verdicts stay in
  the paper beside them. Nothing is replaced.

## Deviation 1, recorded 2026-10-12 BEFORE any model call

The procedure above says the model receives "the one-line description recorded
in the run's results file". On reading those descriptions while writing the
script, several are evaluative rather than descriptive: Presidio is "a textbook
relaxation surface", LLM Guard has thresholds that are "exactly the surface
R14-a asks about", bandit is "the purest available example of a detection that
a later stage discards", ESLint is "the sharpest subject available in any
language". Passing them would tell the second adjudicator what the first one
expected to find, which is the contamination this run exists to exclude.

The model therefore receives instead: the subject's name, its repository, and a
neutral stratum label, either "A: an AI guardrail, monitor, evaluation or
agent framework" or "B: a classical detection tool (linter, type checker,
static analyser or vulnerability scanner)". The stratum label is the same fact
the first adjudicator applied the step 0 exemption on. Nothing else changes.

## Deviation 2, recorded 2026-10-12, BEFORE any call to the second model (commit 42e4de0; an earlier draft of this line gave the time as 21:45 IST, which was wrong; the commit time is authoritative)

**What happened.** The `gpt-5` run stopped at 250 of 331 sites when the OpenAI
account's credit balance was exhausted (HTTP 429 `credit_balance_exhausted`).
The 81 sites not run are all TypeScript and include two of the five upheld
findings. The 250 verdicts already returned are kept unchanged.

**What is added.** A second model of a third family, Google `gemini-3.5-flash`
via the Gemini API (the Pro tier has no quota on the available key), adjudicates
**all 331 sites**, with exactly the same prompt, rubric excerpt, blinding,
batching and retry rule as above. Output: `independent_adjudication_gemini.json`.
Anthropic models are excluded as adjudicators because a model of that family
was the drafting assistant on this work.

**What is reported.** O1 to O5 for the complete Gemini adjudication against the
first verdicts (the headline, since it covers every site); the same for the 250
`gpt-5` sites, labelled partial; and model-to-model agreement on those 250, which
says whether the two independent raters agree with each other where both ran.
The adverse-prior thresholds above apply to the Gemini adjudication. The
interim `gpt-5` result was seen before this deviation was written (kappa 0.155
on 217 scored sites, all 50 reversals in four stratum B subjects); this
deviation changes no threshold and no outcome definition, and it is recorded
here so the reader can weigh that.

**Known weakness.** A Flash-tier model is weaker than `gpt-5` with reasoning;
disagreement attributable to that is not separable from disagreement about the
rubric, and the paper will say so.

### Deviation 2a (same evening, before any verdict from the run was read)

`gemini-3.5-flash` returned HTTP 503 ("currently experiencing high demand") on
every call, through five retries per batch. An availability check sent the
first 10-site prompt to three Gemini models: `gemini-3.5-flash` (503),
`gemini-2.5-flash` (404, retired for new users) and `gemini-3-flash-preview`
(answered; only the count of parseable verdicts was printed, 10 of 10, and the
response was discarded unread). The run therefore uses
**`gemini-3-flash-preview`**, a Flash-tier preview model of the same family.
Everything else in Deviation 2 stands.

### Deviation 2b (same evening, before the run below)

The Gemini run stopped at 120 of 331 sites: the key is on the free tier, whose
quota for this model is 20 requests per day per project (HTTP 429,
`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, reset in about 7h40m). All
120 completed sites are Python, so they overlap `gpt-5`'s 250 and do not cover
the 81 TypeScript sites `gpt-5` did not reach.

A model of a third family, Alibaba **`qwen/qwen3.8-27b`** served by Groq, is
therefore run over **all 331 sites** with the identical prompt, rubric excerpt
and blinding, in batches of **3** rather than 10 (the account's limit is 8,000
tokens per minute and a 10-site prompt is about 10,000 tokens), with a pause
between calls to stay under that limit. An availability check sent one 3-site
prompt; only the count of parseable verdicts (3 of 3) and the token usage were
printed, and the response was discarded unread. Output:
`independent_adjudication_qwen.json`.

What is reported: O1 to O5 for the complete Qwen adjudication against the first
verdicts (the headline, because it alone covers every site); `gpt-5` (250 sites)
and Gemini (120 sites) as partial raters, each labelled with its coverage; and
pairwise model-to-model agreement wherever two models both ran. The adverse
prior thresholds apply to the Qwen adjudication. The Gemini run may be
completed after its quota resets; if it is, it is reported in the same way and
nothing above changes.
