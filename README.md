# Bounded Relaxation: replication package

Artifact for *Bounded Relaxation: Certifying That a False-Positive Filter
Consults the Evidence It Overrides* (A Jaswanth, 2026; manuscript in
preparation for *Automated Software Engineering*).

A **relaxation** is a stage that takes a verdict and weakens it: an allowlist,
an override table, a suppression directive, an exemption. **R14** is a static
invariant for such stages: the relaxation consults the strength of the evidence
it overrides (R14-a), records every outcome (R14-b), bounds separately the
categories its system declares unreleasable (R14-c), and enacts what it
declares (R14-d).

## What is here

| path | what it is |
|---|---|
| `backend/engine/maryada.py` | R14, the certifier over declared relaxation sites |
| `backend/engine/maryada_discover.py` | the site proposer: finds relaxation sites in code that declares nothing |
| `backend/engine/anupalabdhi.py`, `pramana.py` | the sibling rung whose guard classifiers the proposer imports, so the two cannot drift |
| `backend/engine/classifier_overrides.py`, `backend/data/known_misclassifications.json` | the stage on our own system that R14 convicted, as repaired |
| `backend/eval/override_monotonicity_probe.py` | reproduces that defect and its fix in seconds, no model call |
| `backend/eval/stage_retention.py` | recomputes the retention table from the transcribed source values |
| `backend/tests/test_maryada*.py` | the rung's tests (the TypeScript ones need `npm ci`, below) |
| `contrib/external-r14/ADJUDICATION.md` | the rubric, fixed before any external result was read, with dated amendments |
| `contrib/external-r14/PREREGISTRATION_*.md` | every pre-registration, each committed before the run it governs |
| `contrib/external-r14/run_external_r14*.py` | runners: acquire each subject at its pinned commit, scan, certify |
| `contrib/external-r14/ts_propose.mjs`, `ts_frontend.py` | the TypeScript front end, which proposes and judges nothing |
| `contrib/external-r14/adjudication*.json` | every decision-surface verdict in both corpora, with its reason |
| `contrib/external-r14/prove_reachable*.{py,mjs}` | reachability harnesses: run each upheld function from the pinned clone, with a control |
| `contrib/external-r14/independent_adjudicator.py`, `score_independent_adjudication.py` | the second, different-family adjudication and its scoring |
| `contrib/external-r14/lexicon_sensitivity.py` | leave-one-term-out sensitivity of the proposer's vocabulary |
| `contrib/external-r14/final_check.py` | one command that runs every checker over the paper and its data |

## Reproduce

```sh
pip install pytest
cd backend && python -m pytest -q tests/          # rung tests
python eval/override_monotonicity_probe.py        # our own defect and its fix
cd ../contrib/external-r14
npm ci                                            # TypeScript front end
python run_external_r14.py --clone-root <dir>     # clones the 28 Python subjects at their pinned commits
python run_external_r14_ts.py --clone-root <dir>  # the 11 TypeScript subjects
python summarize.py && python summarize_ts.py     # every reported count
```

No API key is needed for anything except `independent_adjudicator.py`
(OpenAI, Gemini or Groq), whose recorded outputs are included.

**Status, 12 October 2026.** The second adjudication is in progress: `gpt-5`
reached 250 of 331 sites before its credit ran out and Gemini 120 before its
free-tier quota did (both outputs included); a complete run by
`qwen3.8-27b` and the lexicon sensitivity results will be added when they
finish. Every change to the plan is recorded, dated, in
`contrib/external-r14/PREREGISTRATION_independent_adjudication.md`, each before
the calls it governs. No subject is imported or executed
except the functions the reachability harnesses name.

## Licence

MIT. The subjects are third-party code and are not redistributed here; the
runners fetch them from their own repositories at the commits listed in the
paper.
