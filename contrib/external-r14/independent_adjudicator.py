#!/usr/bin/env python3
"""Second, different-family adjudication of every R14 decision-surface site.

Pre-registered in PREREGISTRATION_independent_adjudication.md (committed before
this script was first run, with Deviation 1 also committed before any call).
This script reads nothing from that file.

Blinding: the model gets the rubric (ADJUDICATION.md Steps 0-3 verbatim), a
neutral subject description, the scanner's own record of the site, and source
context read from the pinned clone. It never sees the first verdict, class,
finding name, reason, execution status or any aggregate.

    python independent_adjudicator.py [--model gpt-5] [--batch 10]
        -> independent_adjudication.json   (raw, per site, with usage)
    python independent_adjudicator.py --dry-run   (build prompts, no calls)
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "contrib" / "namespace-collision"))
from f2_model_adjudicator import call_model, load_key  # noqa: E402

def load_gemini_key() -> str:
    import os
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    env = REPO / "backend" / ".env"
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call_gemini(key: str, model: str, prompt: str):
    """Deviation 2: same prompt, Gemini generateContent API."""
    import urllib.request
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = chr(10).join(p.get("text", "") for p in parts if not p.get("thought"))
    um = data.get("usageMetadata", {})
    return text, data.get("modelVersion", model), {
        "input_tokens": um.get("promptTokenCount", 0),
        "output_tokens": um.get("candidatesTokenCount", 0)
                         + um.get("thoughtsTokenCount", 0)}


def load_env_key(name: str) -> str:
    import os
    k = os.environ.get(name, "").strip()
    if k:
        return k
    for line in (REPO / "backend" / ".env").read_text(
            encoding="utf-8", errors="replace").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


_GROQ_LOCK = None
_GROQ_LAST = [0.0]
GROQ_MIN_GAP_SEC = 32.0   # 8,000 tokens/min at ~4,000 tokens per 3-site call


def call_groq(key: str, model: str, prompt: str):
    """Deviation 2b: same prompt, Groq's OpenAI-compatible chat API, throttled."""
    import threading
    import urllib.request
    global _GROQ_LOCK
    if _GROQ_LOCK is None:
        _GROQ_LOCK = threading.Lock()
    with _GROQ_LOCK:
        wait = GROQ_MIN_GAP_SEC - (time.time() - _GROQ_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _GROQ_LAST[0] = time.time()
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "User-Agent": "r14-adjudication"})
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    u = data.get("usage", {})
    return (data["choices"][0]["message"]["content"], data.get("model", model),
            {"input_tokens": u.get("prompt_tokens", 0),
             "output_tokens": u.get("completion_tokens", 0)})


CORPORA = [
    ("py", HERE / "adjudication.json", HERE / "external_r14_results.json",
     pathlib.Path("C:/r14-subjects")),
    ("ts", HERE / "adjudication_ts.json", HERE / "external_r14_ts_results.json",
     pathlib.Path("C:/r14-subjects-ts")),
]

STRATUM = {
    "A": "A: an AI guardrail, monitor, evaluation or agent framework",
    "B": ("B: a classical detection tool (linter, type checker, static "
          "analyser or vulnerability scanner)"),
}

#: Scanner fields the first adjudicator also had. Nothing from the verdict file.
SCANNER_FIELDS = ("function", "kind", "polarity", "written", "guards",
                  "bounded", "bound_symbol", "bound_via", "audited",
                  "audit_symbol", "shape", "reaches_hard_block")

MAX_FN_LINES = 160


def rubric() -> str:
    txt = (HERE / "ADJUDICATION.md").read_text(encoding="utf-8")
    a = txt.index("## Step 0: is the write")
    b = txt.index("## What would falsify")
    return txt[a:b].strip()


INSTRUCTIONS = """\
You are an independent adjudicator. A syntactic scanner proposed each site below
as a possible RELAXATION: a stage that takes a safety verdict and weakens it (a
category demoted to safe, a signal zeroed, a detection dropped, a block
downgraded, a check skipped). The invariant under test, R14, has these parts:
R14-a bounded: the relaxation consults the strength of the evidence it
overrides. R14-b audited: every outcome leaves a trace, granted or refused.
R14-c floored: categories the system declares unreleasable are bounded
separately. Apply the rubric that follows exactly as written.

For EACH site return one verdict:
- WITHDRAWN: out of scope at Step 0 (class OUT), a structural fact with no
  verdict to weaken (class D), or the scanner was wrong at Step 2 (class FP:
  bounded elsewhere, polarity misread, audit reached another way).
- UPHELD: a relaxation on a safety-decision path that fails an obligation the
  rubric engages for its class.
- PASS: a relaxation on a safety-decision path that meets every obligation the
  rubric engages for its class.
- UNSURE: the context given is not enough to decide.
and one class: A, B, C, D, OUT or FP (as defined in the rubric).

You see only the enclosing function and same-module references. Judge from what
is shown; if a decisive fact is not shown, say UNSURE rather than guessing.

Reply with ONLY a JSON array, one object per site, in any order:
[{"id": "<site id>", "verdict": "...", "class": "...", "reason": "<one sentence>"}]
"""


def subjects(results: pathlib.Path) -> dict:
    return {s["key"]: s for s in
            json.loads(results.read_text(encoding="utf-8"))["subjects"]}


def resolve(e: dict, s: dict, root: pathlib.Path) -> pathlib.Path | None:
    base = root / s["key"]
    pkgs = s.get("pkg") or []
    pkgs = [pkgs] if isinstance(pkgs, str) else list(pkgs)
    roots = list(s.get("scan_roots") or []) + pkgs + [""]
    for r in roots:
        c = base / r / e["module"]
        if c.is_file():
            return c
    return None


def scanner_record(cands: list, e: dict) -> dict:
    for c in cands:
        if c.get("module") == e["module"] and c.get("line") == e["line"]:
            return {k: c.get(k) for k in SCANNER_FIELDS}
    return {}


def py_enclosing(src: str, line: int):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(n, "end_lineno", n.lineno)
            if n.lineno <= line <= end and (best is None or n.lineno > best[1]):
                best = (n.name, n.lineno, end)
    return best


_FN_START = re.compile(
    r"(\bfunction\b|=>\s*\{?\s*$|\)\s*(:\s*[^={]+)?\{\s*$|^\s*(async\s+)?"
    r"[A-Za-z_$][\w$]*\s*\([^)]*\)\s*(:\s*[^{]+)?\{\s*$)")


_CONTROL = re.compile(r"^\s*(\}\s*)?(if|else|for|while|switch|catch|try|do|"
                      r"finally|return|case|with)\b")


def _continues_control(lines: list, start: int) -> bool:
    """A line like `) {` closes a condition opened above; find its opener."""
    if not lines[start].lstrip().startswith(")"):
        return False
    bal = 0
    for k in range(start, max(-1, start - 40), -1):
        bal += lines[k].count(")") - lines[k].count("(")
        if bal <= 0:
            return bool(_CONTROL.match(lines[k]))
    return False


def ts_enclosing(lines: list, line: int):
    """Nearest function-like line above `line` whose block contains it."""
    depth = []
    d = 0
    for ln in lines:
        stripped = re.sub(r"(['\"`]).*?\1", "", ln)
        depth.append(d)
        d += stripped.count("{") - stripped.count("}")
    i = line - 1
    for start in range(i, max(-1, i - 400), -1):
        if (_FN_START.search(lines[start]) and not _CONTROL.match(lines[start])
                and not _continues_control(lines, start)):
            d0 = depth[start]
            end = start
            dd = d0
            for j in range(start, len(lines)):
                s = re.sub(r"(['\"`]).*?\1", "", lines[j])
                dd += s.count("{") - s.count("}")
                if j > start and dd <= d0:
                    end = j
                    break
            else:
                end = len(lines) - 1
            if start <= i <= end:
                m = re.search(r"([A-Za-z_$][\w$]*)\s*(=|\(|:)", lines[start])
                return (m.group(1) if m else "?", start + 1, end + 1)
    return None


def context(path: pathlib.Path, line: int, lang: str) -> str:
    src = path.read_text(encoding="utf-8", errors="replace")
    lines = src.splitlines()
    enc = py_enclosing(src, line) if lang == "py" else ts_enclosing(lines, line)
    if enc:
        name, a, b = enc
    else:
        name, a, b = None, max(1, line - 40), min(len(lines), line + 40)
    if b - a + 1 > MAX_FN_LINES:
        a = max(a, line - MAX_FN_LINES // 2)
        b = min(b, a + MAX_FN_LINES - 1)
    out = [f"--- {'enclosing function ' + name if name else 'window'} "
           f"(lines {a}-{b}; site line marked >>) ---"]
    for k in range(a, b + 1):
        mark = ">>" if k == line else "  "
        out.append(f"{mark}{k:5d}  {lines[k - 1]}")
    if name and name != "?":
        refs = [k for k, ln in enumerate(lines, 1)
                if re.search(rf"\b{re.escape(name)}\b", ln) and not (a <= k <= b)]
        if refs:
            out.append(f"--- other lines in this module naming {name} ---")
            shown = set()
            for k in refs[:12]:
                for j in range(max(1, k - 2), min(len(lines), k + 2) + 1):
                    if j not in shown:
                        shown.add(j)
                        out.append(f"  {j:5d}  {lines[j - 1]}")
                out.append("  ...")
    return "\n".join(out)


def items() -> list[dict]:
    out = []
    for lang, adj, res, root in CORPORA:
        subs = subjects(res)
        for n, e in enumerate(json.loads(adj.read_text(encoding="utf-8"))["entries"]):
            s = subs[e["subject"]]
            p = resolve(e, s, root)
            out.append({
                "id": f"{lang}-{n:03d}",
                "lang": lang,
                "subject": e["subject"],
                "module": e["module"],
                "line": e["line"],
                "first_verdict": e["verdict"],   # NEVER sent to the model
                "first_class": e.get("class"),    # NEVER sent to the model
                "subject_desc": f"{s['name']} ({s.get('repo', '')}); stratum "
                                f"{STRATUM[s['stratum']]}",
                "scanner": scanner_record(s.get("candidates") or [], e),
                "context": context(p, e["line"], lang) if p else
                           "(source file not found in the pinned clone)",
            })
    return out


def site_block(it: dict) -> str:
    return (f"### SITE {it['id']}\n"
            f"subject: {it['subject_desc']}\n"
            f"module: {it['module']}   line: {it['line']}\n"
            f"scanner record: {json.dumps(it['scanner'])}\n"
            f"{it['context']}\n")


def prompt_for(batch: list[dict], rub: str) -> str:
    return (INSTRUCTIONS + "\n=== RUBRIC (verbatim) ===\n" + rub +
            "\n=== SITES ===\n" + "\n".join(site_block(b) for b in batch))


def parse(text: str) -> dict:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return {}
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return {a["id"]: a for a in arr if isinstance(a, dict) and "id" in a}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5")
    ap.add_argument("--provider", choices=("openai", "gemini", "groq"), default="openai")
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--out", default=str(HERE / "independent_adjudication.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--parallel", type=int, default=4)
    args = ap.parse_args()

    rub = rubric()
    its = items()
    print(f"{len(its)} sites; source not found for "
          f"{sum(1 for i in its if 'not found' in i['context'])}")
    if args.dry_run:
        pathlib.Path(HERE / "_dry_prompt.txt").write_text(
            prompt_for(its[:args.batch], rub), encoding="utf-8")
        print("wrote _dry_prompt.txt (first batch); no call made")
        return 0

    key = {"gemini": load_gemini_key, "groq": lambda: load_env_key("GROQ_API_KEY"),
           "openai": load_key}[args.provider]()
    caller = {"gemini": call_gemini, "groq": call_groq,
              "openai": call_model}[args.provider]
    if not key:
        print("no OPENAI_API_KEY (env or backend/.env)")
        return 2
    out = pathlib.Path(args.out)
    state = (json.loads(out.read_text(encoding="utf-8")) if out.exists() else
             {"model_requested": args.model, "verdicts": {}, "usage": [],
              "missing": []})
    todo = [i for i in its if i["id"] not in state["verdicts"]]
    lock = threading.Lock()

    def run_batch(batch):
        got, usages = {}, []
        for attempt in (1, 2):
            want = [b for b in batch if b["id"] not in got]
            for net_try in range(5):
                try:
                    text, served, usage = caller(key, args.model,
                                                     prompt_for(want, rub))
                    break
                except Exception as exc:  # transient network / 5xx
                    print(f"  call failed ({type(exc).__name__}); retry "
                          f"{net_try + 1}/5")
                    time.sleep(15 * (net_try + 1))
            else:
                return  # left undone; a re-run resumes it
            usages.append({"served": served, "usage": usage})
            got.update(parse(text))
            if all(b["id"] in got for b in batch):
                break
        with lock:
            state["usage"].extend(usages)
            for b in batch:
                v = got.get(b["id"])
                if v is None:
                    state["missing"].append(b["id"])
                    continue
                state["verdicts"][b["id"]] = {
                    "subject": b["subject"], "module": b["module"],
                    "line": b["line"], "lang": b["lang"],
                    "verdict": str(v.get("verdict", "")).upper(),
                    "class": v.get("class"), "reason": v.get("reason")}
            tmp = out.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
            tmp.replace(out)
            print(f"  {len(state['verdicts'])}/{len(its)} done")

    batches = [todo[k:k + args.batch] for k in range(0, len(todo), args.batch)]
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        list(ex.map(run_batch, batches))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
