"""Print the source behind a discovered candidate, for adjudication.

Every claim in the write-up has to be checked against the lines it names, and a
reviewer has to be able to check it the same way. This does that and nothing
else.

    python show.py --results external_r14_results.json --subject llm-guard
    python show.py --results external_r14_results.json --subject llm-guard \
                   --module output_scanners/x.py --context 14
    python show.py --results external_r14_results.json --subject presidio \
                   --unbounded-only --limit 20
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def main() -> int:
    # Subject source can contain any unicode; a Windows console defaults
    # to cp1252 and would crash mid-dump on the first emoji in a comment.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="external_r14_results.json")
    ap.add_argument("--clone-root", default="C:/r14-subjects")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--module", default=None, help="substring filter on path")
    ap.add_argument("--context", type=int, default=10)
    ap.add_argument("--domain", default=None,
                    help="R14 | R3 | STRUCTURAL. Without it every domain is "
                         "shown, which is NOT the adjudication set and was "
                         "misread as one once.")
    ap.add_argument("--unbounded-only", action="store_true")
    ap.add_argument("--unaudited-only", action="store_true")
    ap.add_argument("--handlers-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    data = json.loads(pathlib.Path(args.results).read_text(encoding="utf-8"))
    subs = {s["key"]: s for s in data["subjects"]}
    if args.subject not in subs:
        print(f"no such subject. have: {', '.join(sorted(subs))}")
        return 2
    sub = subs[args.subject]
    if not sub.get("candidates"):
        print(f"{args.subject}: no candidates ({sub.get('acquired')})")
        return 0

    # `pkg` may name several shipped-source roots. Where it does, the scan
    # prefixed each module with the root it came from, so the checkout
    # itself is what a module resolves against.
    root = (pathlib.Path(sub["path"]) if isinstance(sub["pkg"], list)
            else pathlib.Path(sub["path"]) / sub["pkg"])
    cands = sub["candidates"]
    if args.domain:
        cands = [c for c in cands
                 if c.get("domain", "R14").upper() == args.domain.upper()]
    if args.module:
        cands = [c for c in cands if args.module in c["module"]]
    if args.unbounded_only:
        cands = [c for c in cands if not c["bounded"]]
    if args.unaudited_only:
        cands = [c for c in cands if not c["audited"]]
    if args.handlers_only:
        cands = [c for c in cands if c["from_handler"]]
    if args.limit:
        cands = cands[:args.limit]

    print(f"# {sub['name']}  @ {sub.get('sha')}")
    print(f"# {len(cands)} candidate(s) shown\n")

    cache: dict = {}
    for c in cands:
        path = root / c["module"]
        if path not in cache:
            try:
                cache[path] = path.read_text(
                    encoding="utf-8", errors="replace").splitlines()
            except OSError:
                cache[path] = []
        lines = cache[path]
        lo = max(1, c["line"] - args.context)
        hi = min(len(lines), c["line"] + args.context)
        print("=" * 78)
        print(f"{c['module']}:{c['line']}  fn={c['function']}  "
              f"target={c['target']!r}  writes {c['written']}")
        print(f"  bounded={c['bounded']} ({c['bound_symbol']} via "
              f"{c['bound_via']})  audited={c['audited']} "
              f"({c['audit_symbol']})  fail_open={c['from_handler']}")
        print(f"  guards: {' AND '.join(c['guards']) or '(none)'}")
        print("-" * 78)
        for n in range(lo, hi + 1):
            mark = ">>" if n == c["line"] else "  "
            print(f"{mark}{n:>6}  {lines[n - 1]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
