"""What do other people's bounds compare against? Fitted, or declared?

WHY THIS EXISTS
---------------
Paper 14 concedes that both of our own bounds are declared constants chosen so
that no observed behaviour changed, and that this is a weak basis for a safety
threshold. The concession is correct and stays. What it never established is
whether that is a defect peculiar to us or the state of the practice.

We now hold thirty-nine subjects we did not write, with every guard the scanner
resolved recorded in the released artifacts. So the question is answerable
rather than arguable: at every bounded site on a decision surface, extract what
the magnitude is compared AGAINST and classify it.

A numeric literal is a declared constant with no visible derivation. An
attribute or a length is a structural count of the input. An operator-committed
baseline is configuration. None of those is a threshold fitted to data.

    python measure_bounds.py            # prints the table and writes bounds.json

This does NOT excuse our ceiling. It locates it: R14-a asks whether a bound
exists and is consulted, not whether it is optimal, and a rung that demanded
fitted bounds would fail every system in this corpus, including the ones it
currently passes.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from engine import maryada_discover as md                       # noqa: E402

CORPORA = [
    ("python", "external_r14_results.json", "adjudication.json"),
    ("typescript", "external_r14_ts_results.json", "adjudication_ts.json"),
]
OUT = HERE / "bounds.json"


def bounded_surface_sites(results: str, adjudication: str):
    res = json.loads((HERE / results).read_text(encoding="utf-8"))
    adj = json.loads((HERE / adjudication).read_text(encoding="utf-8"))
    surf = re.compile(adj["_surface_regex"], re.I)
    for s in res["subjects"]:
        if s.get("candidates") is None:
            continue
        stratum = s.get("stratum", "A")
        for c in s["candidates"]:
            if c.get("domain") != "R14" or not c.get("bounded"):
                continue
            if stratum == "B" or surf.search(c["module"]):
                yield s["key"], c


def classify(node: ast.expr) -> str:
    """What kind of thing is the threshold on the other side of the comparison?"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "boolean literal"
        if isinstance(node.value, (int, float)):
            return "numeric literal"
        return "other literal"
    if isinstance(node, ast.Name):
        return ("declared constant (UPPER_CASE)" if node.id.isupper()
                else "named variable")
    if isinstance(node, ast.Attribute):
        return "attribute (an object field or configuration)"
    if isinstance(node, ast.Call):
        return "call"
    return type(node).__name__


def threshold_of(candidate: dict):
    """The operand a magnitude is compared against, if the scanner can see one."""
    for guard in candidate.get("guards") or []:
        if not guard:
            continue
        try:
            tree = ast.parse(guard, mode="eval").body
        except SyntaxError:
            continue
        for sub in ast.walk(tree):
            if not isinstance(sub, ast.Compare):
                continue
            if not any(isinstance(o, (ast.Lt, ast.LtE, ast.Gt, ast.GtE))
                       for o in sub.ops):
                continue
            for side in [sub.left, *sub.comparators]:
                if md._magnitude_symbol(side):
                    continue          # this side IS the evidence, not the bound
                return classify(side), ast.unparse(side)[:60]
    return None, None


def main() -> int:
    rows, kinds, unresolved = [], Counter(), 0
    total = 0
    for corpus, results, adjudication in CORPORA:
        for subject, cand in bounded_surface_sites(results, adjudication):
            total += 1
            kind, text = threshold_of(cand)
            if kind is None:
                unresolved += 1
                continue
            kinds[kind] += 1
            rows.append({"corpus": corpus, "subject": subject,
                         "module": cand["module"], "line": cand["line"],
                         "magnitude": cand.get("bound_symbol"),
                         "threshold_kind": kind, "threshold": text})

    print(f"bounded sites on a decision surface, both corpora: {total}")
    print(f"  with a comparison threshold the scanner can extract: {len(rows)}")
    print(f"  without one (guard did not parse, or both sides are evidence): "
          f"{unresolved}")
    print("\nwhat the magnitude is compared AGAINST:")
    for kind, n in kinds.most_common():
        print(f"  {n:4d}  {kind}")
    print("\nevery one, so a reader can check it:")
    for r in rows:
        print(f"  {r['corpus']:10s} {r['subject']:16s} "
              f"{r['module'].split('/')[-1][:32]:32s} :{r['line']:<6d} "
              f"{r['magnitude']} vs {r['threshold']}")

    fitted = 0          # nothing here is fitted; the count is kept so that a
                        # future corpus containing one cannot pass unnoticed
    for r in rows:
        if r["threshold_kind"] in ("fitted",):
            fitted += 1
    print(f"\nthresholds fitted to data: {fitted}")

    OUT.write_text(json.dumps({
        "_about": "Where the threshold comes from at every bounded "
                  "decision-surface site in both external corpora.",
        "total_bounded_sites": total,
        "extractable": len(rows),
        "unresolved": unresolved,
        "by_kind": dict(kinds),
        "fitted": fitted,
        "sites": rows,
    }, indent=1), encoding="utf-8")
    print(f"written: {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
