"""Run R14 against agent monitors and guardrail systems we did not write.

Paper 14 states its own worst limitation plainly: "One subject, and it is ours."
The invariant was built from a defect in our system, run against our system, and
the external half of that paper (a retention statistic computed from a published
table) exercises no R14 predicate at all, because we have neither that
developer's declarations nor their code. A rule validated only on the system
that authored it is a rule with one data point.

This script is the answer to that. It points the unmodified R14 certifier at
open-source systems whose authors have never heard of it.

Run:
    python run_external_r14.py --clone-root C:/r14-subjects
    python run_external_r14.py --offline --clone-root C:/r14-subjects

No API key, no model calls, no execution of any subject. Every subject is read
as text and parsed; nothing is imported. Reading a clone is the only network
step, and --offline removes even that.

METHOD, AND THE PARTS THAT PROTECT THE RESULT
---------------------------------------------
1. PRE-REGISTRATION. ``engine/maryada_discover.py`` proposes relaxation sites
   from source, so a subject does not have to declare anything. Its patterns
   derive from our own two sites and from apavada's floors, and it was
   committed BEFORE any subject below was fetched. The commit order is in the
   log. Its calibration is recorded in its own docstring, including the fact
   that its first version found neither of our two real sites.

2. FIXED SELECTION RULE, WRITTEN BEFORE SCANNING. A subject qualifies if it
     (a) makes or post-processes a safety decision about model or agent
         behaviour: a monitor, guardrail, scanner, detector or judge,
     (b) is written in Python, because the scanner is a Python AST tool,
     (c) is independent of us: we contributed nothing to it and it depends on
         nothing of ours,
     (d) is public and pinnable to a commit.

   STRATUM B, added after the first run and reported separately, relaxes (a) to
   classical detection tooling with the same architecture: a detector whose
   findings pass through a suppression layer before anyone acts. A secret
   scanner with an allowlist is a guardrail with an override table, minus the
   model. It exists to test whether the detection-to-enforcement gap is an
   AI-era accident or an older architectural property. Strata are never pooled.

3. NO DROPPING. Every subject in SUBJECTS is reported with whatever it
   produced, including subjects that come back clean, subjects that come back
   too noisy to adjudicate, and subjects that could not be acquired. A list
   that only contains convictions is a list that was filtered.

4. CANDIDATES, NOT VERDICTS. What this prints is what a static scanner
   proposes. R14-a over-reports by construction: a bound reached through an
   import, an injected object or a config lookup reads as unbounded. Nothing
   here is a statement about anybody's code until a human has read the lines it
   names. The adjudication is a separate, human step and is recorded separately.

WHAT R14 CAN AND CANNOT SAY HERE
--------------------------------
  R14-a  BOUNDED   asked of every discovered site.
  R14-b  AUDITED   asked of every discovered site, and it over-credits: a log
                   anywhere in the enclosing block counts. So R14-b findings
                   under-report, which is the safe direction for a claim about
                   somebody else's code.
  R14-c  FLOORED   engaged ONLY where the subject declares a category it treats
                   as unreleasable. Most do not, and NOT ENGAGED is reported as
                   NOT ENGAGED, never as a pass.
  R14-d  ENACTED   VACUOUS under discovery, because the symbols are extracted
                   from the subject's own source. Reported as vacuous and
                   excluded from the pass/fail count.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter
from typing import Dict, List, Optional

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from engine import maryada as mz                                  # noqa: E402
from engine import maryada_discover as md                         # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# The subjects. Written before any of them was scanned.
# ═══════════════════════════════════════════════════════════════════════════
# `pkg` is the import package inside the checkout, so the scan covers shipped
# library code rather than docs, examples and CI. `ref` pins the commit; where
# it is None the resolved HEAD sha is recorded in the output instead, which
# keeps the run reproducible even for a subject we did not pin in advance.

SUBJECTS: List[Dict[str, Optional[str]]] = [
    {
        "key": "control-arena",
        "name": "ControlArena (UK AI Safety Institute)",
        "repo": "https://github.com/UKGovernmentBEIS/control-arena",
        "pkg": "control_arena",
        "ref": None,
        "stratum": "A",
        "why": "AI-control monitors that score agent trajectories for "
               "suspicion. The closest existing thing to the subject R14 is "
               "about, and maintained by a national safety institute.",
    },
    {
        "key": "inspect_ai",
        "name": "Inspect AI (UK AI Safety Institute)",
        "repo": "https://github.com/UKGovernmentBEIS/inspect_ai",
        "pkg": "src/inspect_ai",
        "ref": None,
        "stratum": "A",
        "why": "The evaluation framework those monitors run inside. Its "
               "scorers turn model output into a graded verdict.",
    },
    {
        "key": "agentdojo",
        "name": "AgentDojo (ETH Zurich SRI Lab)",
        "repo": "https://github.com/ethz-spylab/agentdojo",
        "pkg": "src/agentdojo",
        "ref": None,
        "stratum": "A",
        "why": "Prompt-injection benchmark for tool-calling agents, with "
               "detector pipeline elements that suppress an attack.",
    },
    {
        "key": "nemo-guardrails",
        "name": "NeMo Guardrails (NVIDIA)",
        "repo": "https://github.com/NVIDIA/NeMo-Guardrails",
        "pkg": "nemoguardrails",
        "ref": None,
        "stratum": "A",
        "why": "Production guardrail runtime: input, output and dialog rails "
               "that decide whether a generation is allowed to proceed.",
    },
    {
        "key": "llm-guard",
        "name": "LLM Guard (Protect AI)",
        "repo": "https://github.com/protectai/llm-guard",
        "pkg": "llm_guard",
        "ref": None,
        "stratum": "A",
        "why": "Input/output scanner suite with explicit per-scanner "
               "thresholds, which is exactly the surface R14-a asks about.",
    },
    {
        "key": "guardrails",
        "name": "Guardrails AI",
        "repo": "https://github.com/guardrails-ai/guardrails",
        "pkg": "guardrails",
        "ref": None,
        "stratum": "A",
        "why": "Validator framework where a failed validation can be fixed, "
               "filtered, refrained from or passed through.",
    },
    {
        "key": "presidio",
        "name": "Presidio Analyzer (Microsoft)",
        "repo": "https://github.com/microsoft/presidio",
        "pkg": "presidio-analyzer/presidio_analyzer",
        "ref": None,
        "stratum": "A",
        "why": "PII detection with a first-class allow list and per-recogniser "
               "score adjustment. A textbook relaxation surface.",
    },
    {
        "key": "garak",
        "name": "garak (NVIDIA)",
        "repo": "https://github.com/NVIDIA/garak",
        "pkg": "garak",
        "ref": None,
        "stratum": "A",
        "why": "LLM vulnerability scanner whose detectors emit per-attempt "
               "scores that downstream code thresholds.",
    },
    {
        "key": "llama-firewall",
        "name": "LlamaFirewall (Meta)",
        "repo": "https://github.com/meta-llama/PurpleLlama",
        "pkg": "LlamaFirewall/src/llamafirewall",
        "ref": None,
        "stratum": "A",
        "why": "Agent guardrail system: prompt-injection scanning, alignment "
               "checking and code shielding behind one decision.",
    },
    {
        "key": "openai-agents",
        "name": "OpenAI Agents SDK",
        "repo": "https://github.com/openai/openai-agents-python",
        "pkg": "src/agents",
        "ref": None,
        "stratum": "A",
        "why": "Agent framework with first-class input and output guardrails "
               "whose tripwire decides whether execution halts.",
    },
    {
        "key": "petri",
        "name": "Petri (Anthropic)",
        "repo": "https://github.com/safety-research/petri",
        "pkg": "src/inspect_petri",
        "ref": None,
        "stratum": "A",
        "why": "Open-source automated auditing agent whose judge scores "
               "transcripts for misaligned behaviour.",
    },
    # ---- stratum A, added after the first run ------------------------
    {
        "key": "pyrit",
        "name": "PyRIT (Microsoft Azure)",
        "repo": "https://github.com/Azure/PyRIT",
        # At the commit resolved on 2026-08-18 this repository contains only a
        # published documentation site; the package is not present at any path.
        # Recorded as not acquired rather than silently dropped or guessed.
        "pkg": "pyrit",
        "ref": None,
        "stratum": "A",
        "why": "Risk identification toolkit for generative AI whose scorers "
               "turn model output into a graded verdict.",
    },
    {
        "key": "giskard",
        "name": "Giskard",
        "repo": "https://github.com/Giskard-AI/giskard",
        "pkg": "libs/giskard-scan/src/giskard",
        "ref": None,
        "stratum": "A",
        "why": "LLM vulnerability scanner with per-detector issue reporting.",
    },
    {
        "key": "rebuff",
        "name": "Rebuff (Protect AI)",
        "repo": "https://github.com/protectai/rebuff",
        "pkg": "python-sdk/rebuff",
        "ref": None,
        "stratum": "A",
        "why": "Prompt-injection detector combining heuristics, a model and a "
               "canary check behind one verdict.",
    },
    {
        "key": "modelscan",
        "name": "ModelScan (Protect AI)",
        "repo": "https://github.com/protectai/modelscan",
        "pkg": "modelscan",
        "ref": None,
        "stratum": "A",
        "why": "Scans model artifacts for unsafe operators and reports issues "
               "through a settings-driven suppression layer.",
    },
    {
        "key": "trulens",
        "name": "TruLens",
        "repo": "https://github.com/truera/trulens",
        "pkg": "src/core/trulens",
        "ref": None,
        "stratum": "A",
        "why": "Feedback functions that score LLM output for groundedness and "
               "harm, consumed as guardrails.",
    },
    {
        "key": "semantic-kernel",
        "name": "Semantic Kernel (Microsoft)",
        "repo": "https://github.com/microsoft/semantic-kernel",
        "pkg": "python/semantic_kernel",
        "ref": None,
        "stratum": "A",
        "why": "Agent framework with function-invocation filters that can "
               "block or rewrite a call. Also a subject of the July audit.",
    },
    {
        "key": "autogen",
        "name": "AutoGen (Microsoft)",
        "repo": "https://github.com/microsoft/autogen",
        "pkg": "python/packages/autogen-core/src/autogen_core",
        "ref": None,
        "stratum": "A",
        "why": "Multi-agent runtime with intervention handlers. Also a subject "
               "of the July audit, so the two corpora stay comparable.",
    },
    {
        "key": "crewai",
        "name": "CrewAI",
        "repo": "https://github.com/crewAIInc/crewAI",
        "pkg": "lib/crewai/src/crewai",
        "ref": None,
        "stratum": "A",
        "why": "Agent framework with guardrail callbacks on task output.",
    },
    {
        "key": "langgraph",
        "name": "LangGraph",
        "repo": "https://github.com/langchain-ai/langgraph",
        "pkg": "libs/langgraph/langgraph",
        "ref": None,
        "stratum": "A",
        "why": "Agent graph runtime with interrupt and checkpoint gates.",
    },
    # ---- stratum B: classical detection tooling ----------------------
    {
        "key": "bandit",
        "name": "Bandit (PyCQA)",
        "repo": "https://github.com/PyCQA/bandit",
        "pkg": "bandit",
        "ref": None,
        "stratum": "B",
        "why": "Security linter whose findings are suppressed by an inline "
               "nosec comment. The purest available example of a detection "
               "that a later stage discards on a syntactic trigger.",
    },
    {
        "key": "detect-secrets",
        "name": "detect-secrets (Yelp)",
        "repo": "https://github.com/Yelp/detect-secrets",
        "pkg": "detect_secrets",
        "ref": None,
        "stratum": "B",
        "why": "Secret scanner with an allowlist, an inline pragma and a "
               "baseline file: three independent suppression layers over one "
               "detector.",
    },
    # ---- stratum B, added 2026-08-18 to test the pre-registered audit-rate
    # hypothesis (PREREGISTRATION_audit_rate.md). Each was chosen for having an
    # explicit, documented suppression mechanism over its own findings.
    {
        "key": "pylint",
        "name": "Pylint (PyCQA)",
        "repo": "https://github.com/pylint-dev/pylint",
        "pkg": "pylint",
        "ref": None,
        "stratum": "B",
        "why": "Linter whose findings are suppressed by an inline "
               "`# pylint: disable=` comment and by per-file configuration.",
    },
    {
        "key": "mypy",
        "name": "mypy (Python)",
        "repo": "https://github.com/python/mypy",
        "pkg": "mypy",
        "ref": None,
        "stratum": "B",
        "why": "Type checker whose errors are suppressed by `# type: ignore`, "
               "the most widely used inline suppression in the ecosystem.",
    },
    {
        "key": "semgrep",
        "name": "Semgrep",
        "repo": "https://github.com/semgrep/semgrep",
        "pkg": "cli/src/semgrep",
        "ref": None,
        "stratum": "B",
        "why": "Static analysis engine with `# nosemgrep` inline suppression "
               "and rule-level exclusion.",
    },
    {
        "key": "checkov",
        "name": "Checkov (Prisma Cloud)",
        "repo": "https://github.com/bridgecrewio/checkov",
        "pkg": "checkov",
        "ref": None,
        "stratum": "B",
        "why": "Infrastructure scanner with an inline `checkov:skip=` comment "
               "that suppresses a specific check on a specific resource.",
    },
    {
        "key": "vulture",
        "name": "Vulture",
        "repo": "https://github.com/jendrikseipp/vulture",
        "pkg": "vulture",
        "ref": None,
        "stratum": "B",
        "why": "Dead-code detector whose false positives are suppressed by a "
               "whitelist file, a file-level rather than inline mechanism.",
    },
    {
        "key": "pip-audit",
        "name": "pip-audit (PyPA)",
        "repo": "https://github.com/pypa/pip-audit",
        "pkg": "pip_audit",
        "ref": None,
        "stratum": "B",
        "why": "Dependency vulnerability scanner with `--ignore-vuln`, a "
               "per-identifier suppression supplied at invocation.",
    },
    {
        "key": "vigil",
        "name": "Vigil (deadbits)",
        "repo": "https://github.com/deadbits/vigil-llm",
        "pkg": "vigil",
        "ref": None,
        "stratum": "A",
        "why": "Prompt-injection detection with a scanner ensemble and "
               "per-scanner suppression.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Acquisition
# ═══════════════════════════════════════════════════════════════════════════

def _run(cmd: List[str], cwd: Optional[pathlib.Path] = None,
         timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, timeout=timeout,
                          capture_output=True, text=True)


def acquire(sub: Dict, clone_root: pathlib.Path, offline: bool
            ) -> Dict[str, Optional[str]]:
    """Clone or reuse a checkout. Never raises; failure is a reported state."""
    dest = clone_root / str(sub["key"])
    if dest.exists():
        head = _run(["git", "rev-parse", "HEAD"], cwd=dest)
        return {"path": str(dest), "sha": head.stdout.strip() or None,
                "acquired": "reused"}
    if offline:
        return {"path": None, "sha": None, "acquired": "missing (offline)"}
    clone_root.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", "--quiet"]
    if sub.get("ref"):
        cmd += ["--branch", str(sub["ref"])]
    cmd += [str(sub["repo"]), str(dest)]
    res = _run(cmd)
    if res.returncode != 0:
        return {"path": None, "sha": None,
                "acquired": "clone failed: "
                            + (res.stderr.strip().splitlines() or ["?"])[-1][:200]}
    head = _run(["git", "rev-parse", "HEAD"], cwd=dest)
    return {"path": str(dest), "sha": head.stdout.strip() or None,
            "acquired": "cloned"}


# ═══════════════════════════════════════════════════════════════════════════
# Scan + certify
# ═══════════════════════════════════════════════════════════════════════════

def scan_subject(sub: Dict, checkout: pathlib.Path) -> Dict:
    """Discover sites, then certify them with the unmodified R14."""
    pkg_root = checkout / str(sub["pkg"])
    if not pkg_root.exists():
        # Reported, not guessed at. A moved package is a fact about the run.
        return {"error": f"package path not found: {sub['pkg']}"}

    cands, stats = md.discover(pkg_root, subject=str(sub["key"]))
    # Two different questions, and conflating them overstated R14-c engagement
    # on the first pass. The line scan finds any MENTION of floor-ish wording,
    # which in practice is error-message prose and, in one subject, the set of
    # letters a German passport number may not contain. The vocabulary is built
    # from actual ASSIGNMENTS whose name declares a floor, and that is what a
    # relaxation could be checked against.
    hard_block = md.declares_hard_block(pkg_root)
    vocab = sorted(md.hard_block_vocabulary(pkg_root))

    sites = [c.to_site(source_root=str(pkg_root)) for c in cands]
    result = mz.certify(sites, subject=str(sub["key"])) if sites else None

    # R14-d is vacuous here and is excluded from the counts rather than
    # inflating them with presence checks that cannot fail.
    findings = [f for f in (result.findings if result else [])
                if f.rule != "R14-d"]
    by_rule = Counter(f.rule for f in findings if f.severity == mz.VIOLATION)

    return {
        "scan": stats,
        "sites": len(cands),
        "unbounded": sum(1 for c in cands if not c.bounded),
        "unaudited": sum(1 for c in cands if not c.audited),
        "unbounded_and_unaudited": sum(
            1 for c in cands if not c.bounded and not c.audited),
        "fail_open_handlers": sum(1 for c in cands if c.from_handler),
        "r14a_violations": by_rule.get("R14-a", 0),
        "r14b_violations": by_rule.get("R14-b", 0),
        "r14c": ("ENGAGED" if vocab else "NOT ENGAGED"),
        "floor_vocabulary": vocab,
        "sites_reaching_floor": sum(
            1 for c in cands if c.domain == md.DOMAIN_R14 and c.reaches_hard_block),
        "lexical_floor_mentions": [
            {"module": m, "line": ln, "symbol": sym}
            for m, ln, sym in hard_block[:20]
        ],
        "r14d": "VACUOUS under discovery",
        "candidates": [c.as_dict() for c in sorted(
            cands, key=lambda c: (c.module, c.line, c.target))],
        "top_modules": [
            {"module": m, "sites": n}
            for m, n in Counter(c.module for c in cands).most_common(10)
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Driver
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clone-root", default="C:/r14-subjects",
                    help="where checkouts live")
    ap.add_argument("--offline", action="store_true",
                    help="use existing checkouts only; do not clone")
    ap.add_argument("--only", default=None,
                    help="comma-separated subject keys, for a partial re-run")
    ap.add_argument("--out", default=str(HERE / "external_r14_results.json"))
    args = ap.parse_args()

    clone_root = pathlib.Path(args.clone_root)
    wanted = set(args.only.split(",")) if args.only else None

    out: Dict = {
        "tool": "maryada R14 + maryada_discover",
        "certifier": "engine/maryada.py, unmodified predicates",
        "subjects": [],
    }

    for sub in SUBJECTS:
        if wanted and sub["key"] not in wanted:
            continue
        print(f"[{sub['key']}] ", end="", flush=True)
        rec: Dict = {k: sub[k] for k in ("key", "name", "repo", "pkg", "stratum", "why")}
        acq = acquire(sub, clone_root, args.offline)
        rec.update(acq)
        if acq["path"]:
            rec.update(scan_subject(sub, pathlib.Path(acq["path"])))
            if "error" in rec:
                print(f"SKIP: {rec['error']}")
            else:
                print(f"{rec['sites']} sites, "
                      f"{rec['unbounded']} unbounded, "
                      f"{rec['unaudited']} unaudited, "
                      f"R14-c {rec['r14c']}")
        else:
            print(acq["acquired"])
        out["subjects"].append(rec)

    # A partial re-run must MERGE, not clobber. Writing only the requested
    # subjects silently destroyed a full result once, which is the same shape
    # of defect this whole exercise is about: an operation that quietly
    # discards evidence and looks like it succeeded.
    out_path = pathlib.Path(args.out)
    if wanted and out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            merged = {s["key"]: s for s in prev.get("subjects", [])}
            for rec in out["subjects"]:
                merged[rec["key"]] = rec
            order = [x["key"] for x in SUBJECTS]
            out["subjects"] = sorted(
                merged.values(),
                key=lambda r: order.index(r["key"]) if r["key"] in order else 999)
        except (OSError, ValueError, KeyError):
            print("  (could not merge with the existing output; writing only "
                  "the subjects just run)")
    out_path.write_text(
        json.dumps(out, indent=2, sort_keys=False), encoding="utf-8")
    print(f"\nwrote {args.out}")

    scanned = [s for s in out["subjects"] if s.get("sites") is not None]
    print(f"\n{'subject':<26}{'sites':>7}{'unbnd':>7}{'unaud':>7}"
          f"{'both':>6}{'fail-open':>11}  R14-c")
    for s in scanned:
        print(f"{s['key']:<26}{s['sites']:>7}{s['unbounded']:>7}"
              f"{s['unaudited']:>7}{s['unbounded_and_unaudited']:>6}"
              f"{s['fail_open_handlers']:>11}  {s['r14c']}")
    print("\nCandidates, not verdicts. Adjudicate against source before "
          "quoting any of this.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
