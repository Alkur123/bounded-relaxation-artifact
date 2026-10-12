# Pre-registration: do classical detectors audit their relaxations more than AI guardrails?

**Written and committed before the additional subjects were fetched or scanned.**
The commit order is the pre-registration and is checkable in the log.

---

## Why this, and why now

The strongest single result of the external run so far is a contrast, not a
conviction: two mature classical detectors (`bandit`, `detect-secrets`) **meet**
the audit obligation on their relaxations — one counts suppressions in its own
metrics, the other ships a command to enumerate them — while the AI guardrail
whose ignore-list we convicted does not.

That is currently **four sites in two subjects**. An anecdote. The reviewer's bar
for "field-changing" was that false-positive mitigation layers *routinely* create
an under-measured boundary between detection and enforcement. "Routinely" is a
claim about a population, and we have never measured one.

We already compute an `audited` flag for every proposed site and have never
aggregated it. This turns the anecdote into a rate, or fails to.

---

## Hypothesis, fixed in advance

> **H1.** Among relaxation sites in the R14 domain, the proportion that leave a
> trace is **higher in stratum B (classical detection tooling) than in stratum A
> (AI guardrails, monitors and agent frameworks).**

**H0** is no difference. A result in the *opposite* direction is a real outcome
and will be reported as prominently as a confirming one.

---

## The measurement, fixed in advance

- **Unit:** one proposed site in the **R14 domain**. R3-domain and structural
  sites are excluded, because they are not relaxations of an existing verdict
  and the two strata could differ in their mix of those for unrelated reasons.
- **Outcome:** the scanner's `audited` flag — a logging call, a metric, or an
  audit-shaped key written anywhere in the block performing the relaxation.
- **Populations:** stratum A versus stratum B, pooled within stratum. Per-subject
  rates are reported alongside so a single large subject cannot carry the result.
- **Test:** Fisher's exact test, two-sided, on the 2×2 of stratum by audited.
  Implemented directly from the hypergeometric distribution so the result does
  not depend on an optional dependency being present.
- **Significance:** $p < 0.05$. With a corpus this small the effect size and the
  raw counts matter more than the p-value, and all three are reported.

---

## The bias in the instrument, and which way it cuts

`audited` **over-credits**. It counts a log anywhere in the enclosing block, not
only on the relaxing path, so the true audit rate is *lower* than measured in
both strata.

This matters for the direction of the claim. If stratum A shows a **lower** rate
despite that over-crediting applying equally to both, the finding is
conservative: the real gap is at least as large as measured. If stratum A shows a
*higher* rate, the over-crediting cannot explain it away either. The bias is
symmetric across strata, so it weakens neither direction of inference — but it
does mean **no absolute rate from this measurement should be quoted as "the
fraction of relaxations that are audited"**. Only the comparison is meaningful.

---

## What would falsify the claim, or make it unquotable

1. **No significant difference.** Then the contrast is two anecdotes and the
   paper says so, dropping "routinely" entirely.
2. **The difference is carried by one subject.** If removing any single subject
   from either stratum eliminates significance, the result is about that subject
   and will be reported as such. This is checked by leave-one-subject-out.
3. **Stratum B is too small to test.** Fewer than roughly 30 R14-domain sites in
   stratum B and the test has no power worth reporting; the honest report is then
   that the comparison could not be made, not a p-value from thin data.
4. **The strata differ on a confound we can name.** Stratum B tools are older and
   have CLI-shaped output; if their "audit" is really just printing to a console
   because that is their entire interface, the mechanism is different even if the
   rate differs. This is checked by reading a sample of stratum B audited sites
   and asking whether the trace is a *record* or merely *output*.

---

## Subjects to be added, chosen before scanning

Stratum B needs to be more than two subjects to support any rate. Selection rule,
unchanged from the original: a detector whose findings pass through a suppression
layer before anyone acts on them; Python; independent of us; pinnable to a commit.
Chosen for having an explicit, documented suppression mechanism:

| subject | suppression mechanism |
|---|---|
| pylint | `# pylint: disable=` inline and per-file |
| mypy | `# type: ignore` |
| semgrep | `# nosemgrep` |
| checkov | `checkov:skip=` |
| vulture | a whitelist file |
| pip-audit | `--ignore-vuln` |

Every subject fetched is reported whatever it produces, including ones that
cannot be acquired.
