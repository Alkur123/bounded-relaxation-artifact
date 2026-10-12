# A hard-block category is demoted to SAFE on a substring match, on the default path

**Found 2026-08-17.** Not by reading our code, and not by citing Anthropic's risk
report. By treating one table in that report as **data** and computing something
nobody had computed, then testing the property it implied against our own system.

---

## 1. The route in: an unpublished quantity in a published table

Anthropic's August 2026 Risk Report, Table 2.23.1.2.B, gives its internal
monitoring pipeline's recall at two stages: a prompted first-stage monitor, and
that monitor plus a second-stage filter whose stated job is removing common
false positives before human review.

The report never computes the **conditional retention** of the second stage:

> R = P(survives stage 2 | flagged by stage 1) = (rate after 1+2) / (rate after 1)

This is directly observed on the same data. No independence assumption enters.
Computed across all twelve attack rows (`backend/eval/override_monotonicity_probe.py`
carries the transcription):

| | Opus 4.6 | Opus 4.8 |
|---|---:|---:|
| mean retention on attacks | 75.0% | 84.5% |
| range excluding the pair below | 71.3 to 83.7% | 77.5 to 100% |

And then the pair that matters. Same attacks, both at **100%** first-stage
recall, one manipulated variable:

| SHADE-Arena side-task attempts | Opus 4.6 | Opus 4.8 |
|---|---:|---:|
| **full extended thinking** (CoT discusses the side goal) | **45%** | **70%** |
| **side goal ablated** from the CoT | **97%** | **92%** |
| delta | **-52 pts** | **-22 pts** |

The full-CoT row is the only attack row far below the entire distribution, and
its ablated twin sits at the top. **The filter discards a flagged attack more
often when the incriminating evidence is more legible.**

We do not know their mechanism and the benign reading is available and likely:
the second stage filters traffic that looks like an evaluation, and full-CoT
SHADE transcripts are recognisable benchmark material. The report says as much,
that "certain forms of evals are often filtered out of the second stage prior to
review". That reading does not remove the property, it relocates it. A filter
that discards eval-shaped traffic discards real attacks that look eval-shaped,
and its benchmark-measured recall then does not transfer to attacks that do not.

**Do not cite this as a defect in their system.** Cite it as the observation
that a false-positive filter can be non-monotone in evidence strength, and that
nobody checks.

---

## 2. The invariant it implies, which none of our nine rungs checks

> **A stage may not relax a verdict past an invariant another module declares
> inviolable, and a relaxation must not be unconditional in the strength of the
> evidence it overrides.**

| rung | asks | catches this? |
|---|---|---|
| R1/R2 Pramāṇa | what kind of evidence each arm is | no |
| R3 Anupalabdhi | whether an arm is alive | no, the arm ran fine |
| R4 Ṛtvij | whether an evidence-only arm can act | no, this is not an action |
| R5 Vikalpa | whether the combinator over arms is licensed | no, this is not a combinator |
| R5-d | whether a detection function has redundancy | no |
| R6 | whether evidence mass is preserved | no |
| Sakṣin | non-self-observation | no |
| Egress closure | every PEP consults the exit gate | no |
| Cakraka | verdict-to-evidence circularity | no |

---

## 3. Run against ourselves, and it convicts us

`backend/eval/override_monotonicity_probe.py`, seconds, no model calls.

**`engine/classifier_overrides.py`** is default ON (disabled only by
`AEGIS_DISABLE_OVERRIDES`) and is called from `engine/pipeline_rings.py:449`, at
the end of the semantic-classification ring, so `ctx.semantic` is already
rewritten before context validation or the decision engine ever see it.

It carries **40 rules that demote a category to SAFE**. The entire guard is:

```python
if rule["phrase"] in q_lc and sem.get("category") == rule["wrong_category"]:
    _demote_to_safe(sem, ...)
```

A substring match and a category equality. **There is no confidence term.**
Measured sweep, input held fixed, only the classifier's confidence varying:

| harm confidence | 0.10 | 0.50 | 0.90 | 0.99 | 1.00 |
|---|---|---|---|---|---|
| verdict | SAFE | SAFE | SAFE | SAFE | **SAFE** |

### 3.1 And it crosses the hard-block floor

`engine/rta.py`: `HARD_BLOCK_CATEGORIES = frozenset({"SELF_HARM", "SEXUAL"})`,
described in its own docstring as protected in four places, with the line
**"Admin authority does not reach them."**

Of the 40 demoting rules, **15 target a hard-block category**: SELF_HARM 5,
SEXUAL 10, plus 6 more on SELF_HARM_PASSIVE. All four tested crossings demote at
confidence 0.99:

```
SELF_HARM + 'phone battery is dying'         -> SAFE
SELF_HARM + 'killing investor confidence'    -> SAFE
SEXUAL    + 'how does tor work technically'  -> SAFE
SEXUAL    + 'cult manipulation tactics'      -> SAFE
```

`classifier_overrides.py` contains **zero** references to `HARD_BLOCK`, and
**zero** audit writes. It is a fifth path to a hard-block release, it is not in
the list of four the architecture documents, and admin authority is irrelevant
because no admin is involved.

### 3.2 The remedy is already written and connected to nothing

`engine/apavada.py` exists to admit exceptions only on a static proof that they
are strictly narrower than the rule they defeat. Its docstring names the exact
two floors this violates:

> * a category in `engine/rta.py`'s `HARD_BLOCK_CATEGORIES` ...
> * a relaxation without an audit obligation. If an apavāda is less restrictive
>   than its utsarga, `audit_required` must be True. **An unaudited relaxation is
>   indistinguishable from a hole.**

**Corrected 2026-08-17,** after a wider grep than the one this section first
relied on. `apavada` is not "imported by nothing": it is imported by **exactly
one file, `backend/tests/test_apavada.py`**. It has passing tests and **no
production caller**. That is a sharper statement than the original and a worse
one, because it is a shape this project has already published about:
`evaluation_paradox.tex` reports "a second mechanism shipped with 24 passing
unit tests and was structurally incapable of ever firing". This is the same
pattern, recurring, in the module whose entire purpose is to forbid the
relaxation that section 3.1 measures.

The first version of this section said "imported by nothing" on the strength of
a grep scoped to `backend/engine`. The scoped grep was not wrong about
production callers, but the phrasing overstated what had been checked. Anyone
who runs the obvious command finds `test_apavada.py` and concludes the finding
was written carelessly, which is the correct inference from the sentence as it
stood.

---

## 4. What this is NOT. Read before repeating any of it

- **Not a claim that the override table should not exist.** The rules encode
  real misclassifications. "phone battery is dying" genuinely was a SELF_HARM
  false positive and fixing it was right. The defect is that the fix is
  unconditional, not that it exists.
- **Not a measured end-to-end exploit.** The probe constructs the semantic dict
  rather than eliciting it, deliberately, so that no harmful text is written.
  What is proven is the mechanism: given a hard-block classification at any
  confidence, a trap phrase in the query demotes it. What is **not** measured is
  whether a real harmful request carrying a trap phrase actually classifies into
  the trap's category first. That measurement is owed before any severity claim.
- **Not present in benchmark numbers.** Every measured result in this repository
  runs with `AEGIS_DISABLE_OVERRIDES=1`, so no published number is affected.
- **Not a finding about Anthropic.** Their table supplied the question. The
  defect is ours.

---

## 4bis. FIXED 2026-08-17, and what the fix does not do

Bounded by a confidence ceiling rather than a refusal, because the table is
legitimate: an idiom collision is a *low-confidence* artifact of surface
vocabulary overlap, and a *high-confidence* harmful classification is not
something a phrase should be able to excuse.

| | ceiling | behaviour |
|---|---:|---|
| `SELF_HARM`, `SEXUAL` (hard block) | **0.70** | demote below, refuse at or above |
| everything else | **0.95** | demote below, refuse at or above |

Enforced inside `_demote_to_safe`, not at the three call sites, so a fourth
table added later inherits the bound instead of silently escaping it. Tunable by
`OVERRIDE_HARD_BLOCK_CEILING` and `OVERRIDE_CEILING`.

Both of `apavada`'s floors are now enforced here directly, since that module
still has no production caller: the hard-block floor by the stricter ceiling,
and the audit obligation by an `override_audit` record on **every** outcome,
granted or refused, plus a WARNING log on a refused hard-block. "An unaudited
relaxation is indistinguishable from a hole" was the reason this survived
unnoticed.

Two deliberate non-behaviours. An unreadable confidence **fails closed**, since
a parse error is not evidence of weakness. And a refusal leaves the
classification exactly as it was rather than escalating it: a refused excuse is
not evidence of harm, and inventing severity from one would be its own defect.

**Measured after:** the 17 pre-existing override tests pass **unchanged**, 10
new ones added, full suite **2,386** green. A mutation probe that disables the
ceiling fails 5 of the 10 by name. The genuine low-confidence idiom demotions
still fire, which is the regression guard for the reason the table exists.

**What the fix does NOT do.** The ceilings are **declared, not fitted.** They
were chosen to change no observed behaviour, and that is a weak basis for a
safety bound. The right number comes from the real false-positive confidence
distribution on the demo corpus, which has not been measured. Until it is, the
possibility remains that a genuine idiom collision scores above 0.70 and is now
blocked, or that a real attack scores below it and is still released. Neither
has been observed; neither has been ruled out.

---

## 5. Owed, in order

1. ~~**Founder call: bound the relaxation.**~~ **DONE**, see 4bis. What remains
   is measuring the false-positive confidence distribution so the two ceilings
   stop being declared constants.
2. **Wire `apavada`,** or delete it. An admission checker with passing tests and
   no production caller is worse than none, because both a reader and a test
   count read it as coverage. This is the second recorded instance of that shape
   here; the first is in `evaluation_paradox.tex`.

   **The obvious generalisation is a candidate, and a first attempt at it
   failed.** A "module has tests but no non-test importer" scan over the 99
   engine modules returned 14 candidates, and at least two are false:
   `engine/signals/pii_targeting.py` is imported at `pipeline_rings.py:64` by a
   dotted path (`from engine.signals.pii_targeting import detect`), and
   `engine/ring12/verifier.py` is reached as `from engine.ring12 import
   Ring12Verifier`, a package re-export. **That count is not reported anywhere
   and must not be quoted.** A sound version has to resolve dotted module paths
   and `__init__` re-exports, which is what `pramana_substrate` already does for
   the import graph and is where such a check should live.

   The `apavada` claim itself was re-verified against exactly those two escape
   routes plus dynamic loading: no `__init__` re-export, no `importlib`, and no
   symbol of its API (`Apavada`, `Utsarga`, `resolve_exception`) referenced
   anywhere in `engine/` or `server.py`. It holds.
3. **Make the probe a test** so the property cannot regress silently.
4. ~~Decide whether this is a new rung or a paper of its own.~~ **BOTH, DONE
   2026-08-17** (`d53e569`). It became **R14, Maryādā**, `engine/maryada.py`,
   17 tests, two mutation probes. Numbered 14 because R12 and R13 are the
   runtime rings.

   It turned out to be **static, not behavioural** as this line first guessed.
   Four predicates over declared relaxation sites plus module source: bounded,
   audited, floored, enacted. That is a better fit for the family than the
   metamorphic version, and the metamorphic probe survives separately as
   `eval/override_monotonicity_probe.py`.

   Run on this system it reports **one violation, and it is correct**: the
   distress site declares one symbol as both its general and its hard-block
   bound, which R14-c calls a nominal floor. That is exactly the compromise
   §4bis describes. The rule convicts a choice made deliberately and the
   response is to report it, not to widen the rule.

   Paper: `backend/paper/bounded_relaxation.tex`, 4.77 pages, passes
   `verify_paper.py`. Deliberately **unrouted** until after 29 August.
   The retention analysis is now a committed artifact,
   `eval/results/stage_retention.json`, generated by `eval/stage_retention.py`,
   which also carries an outlier check confirming the full-CoT row is strictly
   the lowest attack row on both monitors.
