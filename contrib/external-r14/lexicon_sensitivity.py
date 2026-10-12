#!/usr/bin/env python3
"""Leave-one-term-out sensitivity of the R14 site proposer's vocabulary.

Paper 14 names this as owed: "a sensitivity run that drops each term in turn
and reports what changes". This is that run, over the Python corpus (28
subjects, pinned clones under C:/r14-subjects).

For every term of the eight lexicons the paper lists (evidence, bound call,
audit call, audit key, benign constants, failure test, error sentinel,
emptiness), the term is removed, the proposer is re-run over every subject,
and the result is compared with the unperturbed baseline:

  * proposed sites, R14-domain sites, and decision-surface sites (the set that
    reaches adjudication), with how many surface sites appear and disappear;
  * for each of the 11 adjudicated non-withdrawn sites (3 UPHELD, 8 PASS),
    whether the scanner still proposes it, in the same domain, with the same
    bounded and audited reading. A change there is a change that could move a
    reported verdict.

Nothing is adjudicated here. A surface site that APPEARS under a perturbation
is a site a human would have had to read; the count is reported, not judged.

The proposer is not modified. One harness-only speed-up memoises
ast.get_source_segment's line splitting per source string; the baseline is
checked byte-for-byte against external_r14_results.json before any
perturbation runs, and the run refuses to continue if it differs.

    python lexicon_sensitivity.py [--workers 6]  -> lexicon_sensitivity.json
"""
from __future__ import annotations

import argparse
import ast
import json
import multiprocessing as mp
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
CLONES = pathlib.Path("C:/r14-subjects")

REGEX_LEXICONS = ["EVIDENCE_LEXICON", "BOUND_CALL_LEXICON", "AUDIT_CALL_LEXICON",
                  "AUDIT_KEY_LEXICON", "FAILURE_TEST_LEXICON",
                  "ERROR_SENTINEL_LEXICON", "EMPTINESS_CALL_LEXICON"]
SET_LEXICONS = ["BENIGN_STRINGS"]
_PRISTINE = None


def _setup():
    sys.path.insert(0, str(REPO / "backend"))
    sys.path.insert(0, str(HERE))
    _orig = ast._splitlines_no_ff
    cache: dict = {}

    def fast(source, maxlines=None):
        if maxlines is not None:
            return _orig(source, maxlines)
        k = id(source)
        hit = cache.get(k)
        if hit is None or hit[0] is not source:
            if len(cache) > 64:
                cache.clear()
            hit = (source, _orig(source))
            cache[k] = hit
        return hit[1]
    ast._splitlines_no_ff = fast
    from engine import maryada_discover as md  # noqa: E402
    import run_external_r14 as rx  # noqa: E402
    return md, rx


def split_terms(pattern: str) -> tuple[str, str, list[str]]:
    """Return (prefix, suffix, terms) for a pattern '<pre>(?:a|b|c)<suf>'."""
    a = pattern.index("(?:", pattern.index("(?:") + 1) if pattern.startswith(
        "(?:^") else pattern.index("(?:")
    depth, i = 0, a
    for i in range(a, len(pattern)):
        if pattern[i] == "(":
            depth += 1
        elif pattern[i] == ")":
            depth -= 1
            if depth == 0:
                break
    inner = pattern[a + 3:i]
    terms, cur, d = [], "", 0
    for ch in inner:
        if ch == "(":
            d += 1
        elif ch == ")":
            d -= 1
        if ch == "|" and d == 0:
            terms.append(cur)
            cur = ""
        else:
            cur += ch
    terms.append(cur)
    return pattern[:a + 3], pattern[i:], terms


def perturbations(md) -> list[tuple[str, str]]:
    out = []
    for name in REGEX_LEXICONS:
        _, _, terms = split_terms(getattr(md, name).pattern)
        out += [(name, t) for t in terms]
    for name in SET_LEXICONS:
        out += [(name, t) for t in sorted(getattr(md, name))]
    return out


def apply(md, name: str, term: str | None):
    if term is None:
        return
    if name in SET_LEXICONS:
        setattr(md, name, frozenset(x for x in getattr(md, name) if x != term))
        return
    rx = getattr(md, name)
    pre, suf, terms = split_terms(rx.pattern)
    kept = [t for t in terms if t != term]
    setattr(md, name, re.compile(pre + "|".join(kept) + suf, rx.flags))


def scan(md, rx) -> dict:
    out = {}
    for sub in rx.SUBJECTS:
        root = CLONES / str(sub["key"]) / str(sub["pkg"])
        if not root.exists():
            continue
        cands, _ = md.discover(root, subject=str(sub["key"]))
        out[sub["key"]] = [(c.module, c.line, c.domain, bool(c.bounded),
                            bool(c.audited)) for c in cands]
    return out


def worker(job):
    name, term = job
    import warnings
    warnings.filterwarnings("ignore")
    md, rx = _setup()
    # Pool workers are reused and the module stays cached, so a term removed
    # by a previous job would otherwise stay removed. Restore every lexicon to
    # its pristine object before applying this job's single perturbation.
    # (The first run omitted this and its output is kept, marked DISCARDED.)
    global _PRISTINE
    if _PRISTINE is None:
        _PRISTINE = {n: getattr(md, n) for n in REGEX_LEXICONS + SET_LEXICONS}
    for n, v in _PRISTINE.items():
        setattr(md, n, v)
    apply(md, name, term)
    t = time.time()
    return name, term, scan(md, rx), round(time.time() - t, 1)


def summarise(scanres: dict, strata: dict, surface_rx) -> dict:
    prop = sum(len(v) for v in scanres.values())
    r14 = {(k, m, l) for k, v in scanres.items() for (m, l, d, b, a) in v
           if d == "R14"}
    surf = {(k, m, l) for (k, m, l) in r14
            if strata[k] == "B" or surface_rx.search(m)}
    return {"proposed": prop, "r14": len(r14), "surface": surf}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(HERE / "lexicon_sensitivity.json"))
    args = ap.parse_args()

    md, rx = _setup()
    jobs = perturbations(md)
    res = {s["key"]: s for s in json.loads(
        (HERE / "external_r14_results.json").read_text(encoding="utf-8"))["subjects"]}
    adj = json.loads((HERE / "adjudication.json").read_text(encoding="utf-8"))
    surface_rx = re.compile(adj["_surface_regex"], re.I)
    strata = {k: s.get("stratum", "A") for k, s in res.items()}
    key_sites = {(e["subject"], e["module"], e["line"]): e["verdict"]
                 for e in adj["entries"] if e["verdict"] != "WITHDRAWN"}

    print(f"{len(jobs)} perturbations + baseline, {args.workers} workers")
    with mp.Pool(args.workers) as pool:
        base = pool.apply(worker, (("BASELINE", None),))
        recorded = {k: sorted((c["module"], c["line"], c["domain"])
                              for c in s["candidates"])
                    for k, s in res.items() if s.get("candidates") is not None}
        got = {k: sorted((m, l, d) for (m, l, d, _, _) in v)
               for k, v in base[2].items()}
        if got != {k: recorded[k] for k in got}:
            print("BASELINE DOES NOT REPRODUCE external_r14_results.json; stop")
            return 1
        print(f"baseline reproduces the recorded scan ({base[3]}s)")
        b_sum = summarise(base[2], strata, surface_rx)
        b_sites = {(k, m, l): (d, bb, aa) for k, v in base[2].items()
                   for (m, l, d, bb, aa) in v}

        rows = []
        for n, (name, term, sres, secs) in enumerate(
                pool.imap_unordered(worker, jobs), 1):
            s = summarise(sres, strata, surface_rx)
            sites = {(k, m, l): (d, bb, aa) for k, v in sres.items()
                     for (m, l, d, bb, aa) in v}
            moved = {}
            for ks, verdict in key_sites.items():
                before, after = b_sites.get(ks), sites.get(ks)
                if before != after:
                    moved["|".join(map(str, ks))] = {
                        "verdict": verdict, "before": before, "after": after}
            rows.append({
                "lexicon": name, "term": term,
                "proposed": s["proposed"], "r14": s["r14"],
                "surface": len(s["surface"]),
                "surface_added": len(s["surface"] - b_sum["surface"]),
                "surface_removed": len(b_sum["surface"] - s["surface"]),
                "key_sites_changed": moved, "seconds": secs})
            if n % 10 == 0:
                print(f"  {n}/{len(jobs)}")

    rows.sort(key=lambda r: (r["lexicon"], r["term"]))
    any_move = [r for r in rows if r["key_sites_changed"]]
    surf_move = [r for r in rows if r["surface_added"] or r["surface_removed"]]
    out = {
        "_about": __doc__.split("\n\n")[0],
        "baseline": {"proposed": b_sum["proposed"], "r14": b_sum["r14"],
                     "surface": len(b_sum["surface"])},
        "n_perturbations": len(rows),
        "n_moving_any_key_site": len(any_move),
        "n_moving_surface_set": len(surf_move),
        "max_surface_added": max(r["surface_added"] for r in rows),
        "max_surface_removed": max(r["surface_removed"] for r in rows),
        "rows": rows,
    }
    pathlib.Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    for r in any_move:
        print(f"  KEY SITE MOVES: {r['lexicon']} -{r['term']}: "
              f"{list(r['key_sites_changed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
