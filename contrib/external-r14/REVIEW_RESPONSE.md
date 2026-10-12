# Point-by-point against the review

The review of paper 14 made five claims. This is what exists for each, what does
not, and which gaps are structural rather than unfinished. Written 2026-08-18
after auditing the work against the review's own wording rather than against a
summary of it — an audit that found one item had been reported as done and was
not.

---

## 1. *"You need to show that R14 works on systems you did not design."*

**Built.** Twenty-three subjects selected under a rule fixed before scanning,
twenty-eight scanned, **7,050 files**, at pinned commits. Sites are proposed
**mechanically** by `engine/maryada_discover.py`, so no subject had to declare
anything and we did not choose which sites to declare. The certifier itself is
unmodified.

Subjects: ControlArena, Inspect AI (UK AISI); NeMo Guardrails, garak (NVIDIA);
LlamaFirewall (Meta); LLM Guard, Rebuff, ModelScan (Protect AI); Guardrails AI;
Presidio (Microsoft); OpenAI Agents SDK; AgentDojo (ETH Zurich); Petri; Giskard;
TruLens; Semantic Kernel, AutoGen (Microsoft); CrewAI; LangGraph; Vigil; plus
bandit and detect-secrets as a second stratum. PyRIT was selected and **not
acquired** — at its resolved commit that repository holds a documentation site
and no package — and is reported rather than dropped.

---

## 2. *"…if R14 finds: unbounded relaxations, evidence-independent overrides, missing audit trails, category-floor violations."*

Four named types. This is the item the audit caught.

| type | status | evidence |
|---|---|---|
| **unbounded relaxations** | **found** | NeMo `injection_detection` omit mode: verdict taken from whether the *repair* changed the text, never from the strength of the detection, ending at `RailOutcome.allow`. **Executed** against shipped code with a control. |
| **evidence-independent overrides** | **found** | The same site is exactly this: the override is independent of the evidence it overrides. |
| **missing audit trails** | **found** | LLM Guard: of three non-matching branches, the only one that *removes a detection* is the only one that does not log. **Executed.** Plus NeMo's short-input exemption, which is bounded and unrecorded. |
| **category-floor violations** | **now run — clean negative** | Was **never exercised**: `reaches_hard_block=False` was hardcoded for all 470 sites, so R14-c reported NOT ENGAGED everywhere. Now wired. See below. |

### What the floor predicate found, and why the negative matters

Engaging R14-c needs the subject to declare that some category is never
releasable, and a relaxation that cannot tell those categories apart. Across all
**twenty-eight** subjects, **not one declares such a set**. Three do declare a
constant whose name says *prohibited* or *forbidden*, and none is about content:
one holds the letters a German passport number may not contain, one the attribute
names a named tuple may not use, one lock-file names and a default network
action. **The words are there; the concept is not.**

So R14-c cannot fail externally — **not because these systems satisfy it, but
because the concept it checks is not expressed anywhere in the corpus.** An
invariant cannot be violated where it was never stated. Our own system states it
(`rta.py`: *"admin authority does not reach them"*), and stating it is what made
our defect describable as a floor violation rather than an ordinary bug.

Getting there required two corrections that the ground truth forced, both
recorded: floor-awareness is a property of the relaxation's **guard path**, not
of the enclosing function — whole-function scope reads our own shipped defect as
floor-aware, because `apply_overrides` names a protected category in an
unrelated *up*-classification branch — and the vocabulary had to stop scanning
the scanner, whose own pattern source was entering it. With guard scope the
check reproduces **by machine** the verdict we had reached by hand: the shipped
defect violates R14-a, R14-b **and** R14-c; the repair does not; the second site
still does.

---

## 3. *"…then the claim becomes much more compelling."*

**Partly, and the honest accounting is that the claim got smaller, not bigger.**

The corpus nearly doubled and the yield **fell from seven findings to three**,
because five of the original seven belonged to a sibling rung (R3,
`anupalabdhi`) which had already recorded three of the exact sites in July. Site
precision is **8.1%**, violation precision **2.2%**. Two of three findings are
one subject.

What did get stronger is different and, we think, better: three findings are
**executed** against shipped code with controls, so they are no longer static
claims; and four sites came back as **passes**, real relaxations where the
obligation is met.

---

## 4. *"…field-changing: false-positive mitigation layers routinely create a previously under-measured security boundary between detection and final enforcement."*

**Cannot be claimed, and two pieces of the evidence now exist.**

The claim as the review states it requires *independent teams adopting R14*.
That is not something we can do for ourselves, and nothing here substitutes for
it.

What we can show:

- **The layer is pervasive and undeclared.** 237 relaxation sites across 28
  independent systems, none of which declares any of them as a relaxation. The
  stage exists everywhere and is named nowhere.
- **It is not an AI-era accident.** Stratum B was added to test exactly this. A
  linter and a secret scanner have the same architecture — a detector whose
  findings pass through a suppression layer — and both **satisfy** the
  obligation: bandit logs the suppressed check id *and* increments a metrics
  counter; detect-secrets ships a scan path that disables its own allowlist
  filter in order to enumerate what it suppressed. The obligation is
  demonstrably satisfiable in shipped production tooling. **What varies is not
  difficulty but whether anyone asked.**

  ⚠ **That last sentence was a population claim and we have since falsified
  it.** Pre-registered, six further classical subjects fetched to test it, and
  measured: classical tooling audits its relaxations *less* (5.4% vs 16.0%,
  p=0.012), and even that fails leave-one-out. The two admired subjects are
  exceptional within their own stratum, not representative. What survives is
  that the obligation is *satisfiable* — four sites, three mechanisms — not that
  anyone satisfies it systematically. See `PREREGISTRATION_audit_rate.md`.

So the second bullet survives only in its narrow form: the obligation is
*satisfiable*, demonstrated by four sites in two subjects. The claim that
classical tooling generally satisfies it does not survive, and we falsified it
ourselves rather than leaving it for a reviewer.

---

## 5. *"Don't make the external observation the central proof. Make it the motivation."*

**Done, structurally.** The retention analysis is retitled *Provenance: where
the question came from* and opens by saying it is the discovery and not the
evidence, that it exercises no predicate of R14 and could not, and that a reader
who rejects the section entirely should find the empirical sections unaffected.
It no longer opens the abstract; it closes the conclusion in one line. The core
empirical contribution is now the defect, the certification, the repair, the
second site, and the external run — which is what the review asked for.

---

## What is still owed, and why

| owed | why it is not done |
|---|---|
| **Disclosure to maintainers** | Required by our own rubric before the enforcement-reaching finding appears in a paper. Filing issues is outward-facing and is a founder decision. **No issue has been opened.** |
| **A second adjudicator** | The rubric was fixed in advance and every verdict ships with its reason, but it is still one team applying its own rule to twenty-eight unfamiliar codebases. Needs a person who is not us. |
| **Independent adoption** | Definitionally cannot be self-served. It is the gap between "compelling" and "field-changing" and no amount of our own work closes it. |
| **A corpus that exercises our own override table** | We tried to fit the two declared ceilings and could not: the table declares **78** trigger phrases, our adversarial corpus holds **3,364** samples, and the number containing any trigger phrase is **zero**. No fitted ceiling is reported, because reading one off an empty sample is the false assurance the rung warns about. Authoring the harmful half is a human labelling task and is deliberately not generated. |

One consequence of that last item is worth stating against ourselves: every
published run in this project sets `AEGIS_DISABLE_OVERRIDES=1`, and on this
corpus that setting changes nothing, because the table never fires there anyway.

---

## Reproduce any of it

```
python run_external_r14.py --clone-root <dir>   # acquire + scan
python summarize.py                             # every number in the write-up
python prove_reachable.py                       # the three executed findings
python verify_paper_table.py                    # paper table vs artifact
python ../../backend/eval/override_ceiling_measure.py
```

No API key, no network beyond the clones, and no subject is imported or executed
except by the reachability harness, which executes only the three functions it
names.
