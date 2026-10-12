"""Run R14 against TypeScript and JavaScript systems we did not design.

The twin of `run_external_r14.py`, for the second front end. Same shape, same
output schema, same unmodified certifier; the only difference is which walker
proposed the sites. The subjects and the strata were fixed before any of them
was fetched, in `PREREGISTRATION_cross_language.md`.

    python run_external_r14_ts.py                  # clone if absent, scan, certify
    python run_external_r14_ts.py --offline        # only what is already on disk
    python run_external_r14_ts.py --subject eslint # one subject

Writes `external_r14_ts_results.json`. Nothing is executed from any subject:
every file is read as text and parsed.
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
REPO = HERE.parents[1]
for extra in (str(REPO / "backend"), str(HERE)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import ts_frontend as tsf                                       # noqa: E402
from engine import maryada as mz                                # noqa: E402
from engine import maryada_discover as md                       # noqa: E402

OUT = HERE / "external_r14_ts_results.json"

# `pkg` is the shipped source inside the checkout, chosen the same way the
# Python run chose it: library code, not docs, examples, build output or tests.
SUBJECTS: List[Dict[str, Optional[str]]] = [
    # ---- stratum A: AI guardrails, monitors and agent frameworks ----------
    {
        "key": "openai-agents-js",
        "name": "OpenAI Agents SDK (JS)",
        "repo": "https://github.com/openai/openai-agents-js",
        "pkg": "packages",
        "stratum": "A",
        "why": "The JS twin of a subject already in the Python corpus, and it "
               "ships input and output guardrails as a first-class concept.",
    },
    {
        "key": "langchainjs",
        "name": "LangChain.js",
        "repo": "https://github.com/langchain-ai/langchainjs",
        "pkg": "libs",
        "stratum": "A",
        "why": "The most widely deployed agent framework in this language; its "
               "chains and parsers turn model output into graded verdicts.",
    },
    {
        "key": "mastra",
        "name": "Mastra",
        "repo": "https://github.com/mastra-ai/mastra",
        "pkg": "packages",
        "stratum": "A",
        "why": "A TypeScript-native agent framework with processors and scorers "
               "on the request path.",
    },
    {
        "key": "llamaindex-ts",
        "name": "LlamaIndexTS",
        "repo": "https://github.com/run-llama/LlamaIndexTS",
        "pkg": "packages",
        "stratum": "A",
        "why": "Retrieval and agent tooling in the same ecosystem, so the "
               "stratum is not one vendor's idioms.",
    },
    # ---- stratum A, added 2026-08-19 by PREREGISTRATION_cross_language_ext.md
    # The first stratum A was four agent frameworks, which mostly do not
    # produce verdicts. These three do; the registration explains the defect.
    {
        "key": "portkey-gateway",
        "name": "Portkey AI Gateway",
        "repo": "https://github.com/Portkey-AI/gateway",
        "pkg": ["src", "plugins"],
        "stratum": "A",
        "why": "An AI gateway with a first-class guardrails engine: named "
               "checks run on requests and responses and a verdict decides "
               "what passes. The closest TypeScript analogue that exists of "
               "NeMo Guardrails or LLM Guard.",
    },
    {
        "key": "promptfoo",
        "name": "promptfoo",
        "repo": "https://github.com/promptfoo/promptfoo",
        "pkg": ["src", "plugins"],
        "stratum": "A",
        "why": "A red-teaming and evaluation harness whose graders and "
               "moderation plugins produce verdicts about model output. The "
               "closest analogue of garak.",
    },
    {
        "key": "langfuse",
        "name": "Langfuse",
        "repo": "https://github.com/langfuse/langfuse",
        "pkg": ["packages", "web/src", "worker/src"],
        "stratum": "A",
        "why": "Tracing and evaluation for LLM applications; its evaluators "
               "score traces, which is the object ControlArena's monitors "
               "produce.",
    },
    # ---- stratum B: classical detection tooling with a suppression layer --
    {
        "key": "eslint",
        "name": "ESLint",
        "repo": "https://github.com/eslint/eslint",
        "pkg": "lib",
        "stratum": "B",
        "why": "The sharpest subject available in any language: its suppression "
               "layer is a documented feature with an inline directive, a flag "
               "to disable inline directives, and a report of unused ones.",
    },
    {
        "key": "typescript-eslint",
        "name": "typescript-eslint",
        "repo": "https://github.com/typescript-eslint/typescript-eslint",
        "pkg": "packages",
        "stratum": "B",
        "why": "A second, independently maintained implementation of the same "
               "architecture over a different parser.",
    },
    {
        "key": "stylelint",
        "name": "Stylelint",
        "repo": "https://github.com/stylelint/stylelint",
        "pkg": "lib",
        "stratum": "B",
        "why": "Same architecture again, different domain, and its own inline "
               "disable directive.",
    },
    {
        "key": "retire.js",
        "name": "retire.js",
        "repo": "https://github.com/RetireJS/retire.js",
        "pkg": "node/src",
        "stratum": "B",
        "why": "A vulnerability scanner rather than a linter, with an ignore "
               "file, which is the closest JS analogue of detect-secrets.",
    },
]


def _run(cmd: List[str], cwd: Optional[pathlib.Path] = None,
         timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, timeout=timeout,
                          capture_output=True, text=True)


def acquire(sub: Dict, clone_root: pathlib.Path, offline: bool) -> Dict:
    """Clone or reuse. Never raises; a failure is a reported state."""
    dest = clone_root / str(sub["key"])
    if dest.exists():
        head = _run(["git", "rev-parse", "HEAD"], cwd=dest)
        return {"path": str(dest), "sha": head.stdout.strip() or None,
                "acquired": "reused"}
    if offline:
        return {"path": None, "sha": None, "acquired": "missing (offline)"}
    clone_root.mkdir(parents=True, exist_ok=True)
    res = _run(["git", "clone", "--depth", "1", "--single-branch", "--quiet",
                str(sub["repo"]), str(dest)], timeout=1200)
    if res.returncode != 0:
        return {"path": None, "sha": None,
                "acquired": "clone failed: "
                            + (res.stderr.strip().splitlines() or ["?"])[-1][:200]}
    head = _run(["git", "rev-parse", "HEAD"], cwd=dest)
    return {"path": str(dest), "sha": head.stdout.strip() or None,
            "acquired": "cloned"}


def scan_subject(sub: Dict, checkout: pathlib.Path) -> Dict:
    # `pkg` may name several shipped-source roots. Each is scanned separately
    # and its module paths are prefixed with the root they came from, so a
    # module stays unambiguous and stays resolvable from the checkout.
    pkgs = sub["pkg"] if isinstance(sub["pkg"], list) else [str(sub["pkg"])]
    missing = [p for p in pkgs if not (checkout / p).exists()]
    if missing:
        return {"error": f"package path not found: {', '.join(missing)}"}

    cands, decls, vocab = [], [], set()
    stats = {"files": 0, "parsed": 0, "parse_errors": 0}
    for pkg in pkgs:
        root = checkout / pkg
        part, st, d, v = tsf.discover(root, subject=str(sub["key"]))
        for c in part:
            c.module = f"{pkg}/{c.module}" if len(pkgs) > 1 else c.module
        for entry in d:
            entry = dict(entry)
            if len(pkgs) > 1:
                entry["module"] = f"{pkg}/{entry['module']}"
            decls.append(entry)
        cands.extend(part)
        vocab.update(v)
        for k in stats:
            stats[k] += st.get(k, 0)
    vocab = sorted(vocab)
    base = checkout if len(pkgs) > 1 else checkout / pkgs[0]
    sites = [c.to_site(source_root=str(base)) for c in cands]
    result = mz.certify(sites, subject=str(sub["key"])) if sites else None
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
        "lexical_floor_mentions": decls[:20],
        "r14d": "VACUOUS under discovery",
        "candidates": [c.as_dict() for c in sorted(
            cands, key=lambda c: (c.module, c.line, c.target))],
        "scan_roots": pkgs,
        "top_modules": [
            {"module": m, "sites": n}
            for m, n in Counter(c.module for c in cands).most_common(10)
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clone-root", default="C:/r14-subjects-ts")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--subject", action="append", default=None)
    args = ap.parse_args()

    ok, why = tsf.available()
    if not ok:
        print(f"TS front end unavailable: {why}")
        return 2
    print(f"node {why}, typescript from contrib/external-r14/node_modules")

    clone_root = pathlib.Path(args.clone_root)
    wanted = set(args.subject) if args.subject else None
    out_subjects = []
    for sub in SUBJECTS:
        if wanted and sub["key"] not in wanted:
            continue
        got = acquire(sub, clone_root, args.offline)
        record = {k: sub[k] for k in ("key", "name", "repo", "pkg", "stratum", "why")}
        record.update({"path": got["path"], "sha": got["sha"],
                       "acquired": got["acquired"]})
        if got["path"] is None:
            record["candidates"] = None
            print(f"{sub['key']:20s} {got['acquired']}")
            out_subjects.append(record)
            continue
        try:
            record.update(scan_subject(sub, pathlib.Path(got["path"])))
        except tsf.TsFrontendUnavailable as exc:
            record["error"] = str(exc)
            record["candidates"] = None
        n = len(record.get("candidates") or [])
        stats = record.get("scan") or {}
        print(f"{sub['key']:20s} {stats.get('parsed', 0):5d} files  "
              f"{n:4d} sites  a={record.get('r14a_violations', 0):3d} "
              f"b={record.get('r14b_violations', 0):3d}  "
              f"{record.get('error', '')}")
        out_subjects.append(record)

    payload = {
        "_about": "R14 run against TypeScript/JavaScript subjects. Sites are "
                  "proposed by contrib/external-r14/ts_propose.mjs and judged "
                  "by the unmodified shipped lexicons and certifier. Subjects "
                  "and strata were fixed in PREREGISTRATION_cross_language.md "
                  "before any of them was fetched.",
        "_frontend": "typescript",
        "subjects": out_subjects,
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    scanned = [s for s in out_subjects if s.get("candidates") is not None]
    print(f"\n{len(scanned)} subjects scanned, "
          f"{sum(s['scan']['parsed'] for s in scanned)} files, "
          f"{sum(len(s['candidates']) for s in scanned)} sites proposed")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
