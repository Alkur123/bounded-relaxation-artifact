"""Hand the deferred sites to the rung that owns them, and see if it agrees.

R14's scan classifies each proposed site into one of three domains and defers
everything it labels R3 to the sibling liveness rung. Until now that deferral
was a **claim**: 52 sites were labelled R3's and R3's own scanner was never run
on them. Asserting a partition without letting the other side adjudicate its
half is exactly the shape of gap this project keeps finding in other people's
code, so it is closed here.

    python handoff_to_r3.py
    python handoff_to_r3.py --show-disagreements

No API key, no network, no execution of any subject.

HOW THE POLARITY IS CHOSEN, AND WHY IT IS NOT A GLOBAL GUESS
------------------------------------------------------------
``anupalabdhi.scan_fail_open`` takes the "safe" polarity per scan and never
infers it, which is a stated limitation of that rung rather than an oversight.
Applying one global sentinel set across twenty-two heterogeneous subjects would
therefore measure our guess, not their code.

Instead the polarity is derived **per module from R14's own scan**: for each
module holding deferred sites, the set of benign values R14 recorded at those
sites becomes that module's ``safe_sentinels``. So the two rungs are asked about
the same values, and any disagreement is about SHAPE rather than about what
counts as permissive.

WHAT AGREEMENT AND DISAGREEMENT EACH MEAN
-----------------------------------------
  BOTH        R3 flags the same line. The deferral is complete: the site is
              really in R3's domain and R3 can see it.
  R14 ONLY    R14 proposed a site R3's shapes do not reach. This is EXPECTED in
              two documented cases, and finding them is the point of running
              this: R3's own docstring states it does not catch a guarded
              fall-through bare constant, nor an interprocedural fail-open where
              the sentinel is returned from a helper. It is also expected for
              the shapes R14 added later, since narrowing a collection and
              skipping a check are not sentinel returns at all.
  R3 ONLY     R3 flags a line R14 never proposed. R14's proposer is not a
              superset of R3's and was never meant to be; this quantifies the
              difference.

A clean partition would be all BOTH. Anything else is reported, because the
useful result here is the shape of the disagreement, not a number that flatters
either rung.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from engine import anupalabdhi as an                                # noqa: E402

RESULTS = HERE / "external_r14_results.json"
OUT = HERE / "r3_handoff.json"

#: R14 records the benign value as source text; these map back to real objects.
_LITERAL = {
    "False": False, "None": None, "0": 0, "0.0": 0.0, "True": True,
    "empty container": None, "empty dict": None,
}


def sentinels_for(candidates: List[dict]) -> Tuple[Tuple[object, ...],
                                                   frozenset, List[str]]:
    """The benign values R14 saw in this module, as R3 wants them declared.

    Returns the constants, the enum members, and the values that **cannot be
    expressed to R3 at all**. That third list is load bearing. R3's sentinel
    shapes match an ``ast.Constant``, and an empty list or dict is not one, so a
    site whose benign value is ``[]`` is invisible to R3 by construction rather
    than by oversight. An earlier version of this function silently substituted
    ``False`` in that case, which asked R3 about a value the module never
    writes and would have scored the resulting non-hit as a disagreement about
    shape when it was really a limit of the interface.
    """
    consts: Set[object] = set()
    enums: Set[str] = set()
    inexpressible: List[str] = []
    for c in candidates:
        w = (c.get("written") or "").strip()
        if w in ("empty container", "empty dict"):
            inexpressible.append(w)
            continue
        if w in _LITERAL:
            consts.add(_LITERAL[w])
            continue
        # a quoted string constant, e.g. "'SAFE'"
        if len(w) >= 2 and w[0] in "'\"" and w[-1] == w[0]:
            consts.add(w[1:-1])
            continue
        # a dotted enum member mentioned in the written description
        matched = False
        for tok in w.replace("(", " ").replace(")", " ").split():
            if tok.count(".") == 1 and tok.replace(".", "").isidentifier():
                enums.add(tok)
                matched = True
        if not matched:
            inexpressible.append(w[:40])
    return tuple(consts), frozenset(enums), inexpressible


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(RESULTS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--show-disagreements", action="store_true")
    ap.add_argument("--allow-missing-clones", action="store_true",
                    help="exit 0 with a SKIPPED notice when the subject "
                         "checkouts are absent. For CI, which has none.")
    args = ap.parse_args()

    res = json.loads(pathlib.Path(args.results).read_text(encoding="utf-8"))

    # R3's scanner reads the subject's source, which is third-party and never
    # committed. A skip must be loud rather than an empty run reported as clean.
    probe = next((s.get("path") for s in res["subjects"] if s.get("path")), None)
    if probe is None or not pathlib.Path(probe).is_dir():
        print(f"subject checkouts not found (looked for {probe})")
        if args.allow_missing_clones:
            print("SKIPPED: R3's scanner was not run and no handoff is claimed.")
            return 0
        print("FAILED: pass --allow-missing-clones to treat this as a skip.")
        return 1

    # group the deferred sites by (subject, module)
    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    roots: Dict[str, pathlib.Path] = {}
    for s in res["subjects"]:
        if not s.get("candidates") or not s.get("path"):
            continue
        roots[s["key"]] = pathlib.Path(s["path"]) / s["pkg"]
        for c in s["candidates"]:
            if c.get("domain") == "R3":
                groups[(s["key"], c["module"])].append(c)

    total_sites = sum(len(v) for v in groups.values())
    print(f"deferred sites: {total_sites} across {len(groups)} modules "
          f"in {len({k[0] for k in groups})} subjects\n")

    records = []
    tally: Counter = Counter()
    shape_of_r14_only: Counter = Counter()

    for (subject, module), cands in sorted(groups.items()):
        path = roots[subject] / module
        consts, enums, inexpr = sentinels_for(cands)
        try:
            hits = an.scan_file_fail_open(
                path, safe_sentinels=consts, safe_enum_members=enums)
        except (OSError, SyntaxError) as exc:
            records.append({"subject": subject, "module": module,
                            "error": f"{type(exc).__name__}: {exc}"})
            tally["scan_error"] += 1
            continue

        # A site whose benign value R3 cannot be told about is not a
        # disagreement about shape; it is outside the interface. Counted apart.
        inexpr_lines = {c["line"] for c in cands
                        if (c.get("written") or "").strip()
                        in ("empty container", "empty dict")}
        r14_lines = {c["line"] for c in cands}
        r3_lines = {h.lineno for h in hits}
        both = sorted(r14_lines & r3_lines)
        r14_only = sorted(r14_lines - r3_lines - inexpr_lines)
        not_expressible = sorted(inexpr_lines - r3_lines)
        r3_only = sorted(r3_lines - r14_lines)

        tally["both"] += len(both)
        tally["r14_only"] += len(r14_only)
        tally["r3_only"] += len(r3_only)
        tally["not_expressible"] += len(not_expressible)
        for c in cands:
            if c["line"] in r14_only:
                shape_of_r14_only[c.get("shape", "?")] += 1

        records.append({
            "subject": subject, "module": module,
            "declared_sentinels": [repr(x) for x in consts],
            "declared_enum_members": sorted(enums),
            "r14_deferred_lines": sorted(r14_lines),
            "r3_flagged_lines": sorted(r3_lines),
            "both": both, "r14_only": r14_only, "r3_only": r3_only,
            "not_expressible_to_r3": not_expressible,
            "inexpressible_values": sorted(set(inexpr)),
            "r3_shapes": sorted({h.shape for h in hits}),
        })

    agreed = tally["both"]
    pct = 100 * agreed / max(total_sites, 1)
    print(f"{'both rungs see it':<28}{agreed:>5}   ({pct:.1f}% of deferred)")
    print(f"{'R14 proposed, R3 does not':<28}{tally['r14_only']:>5}")
    print(f"{'R3 flags, R14 never proposed':<28}{tally['r3_only']:>5}")
    print(f"{'outside R3 interface':<28}{tally['not_expressible']:>5}"
          "   (benign value is not an ast.Constant, e.g. an empty list)")
    if tally["scan_error"]:
        print(f"{'modules that would not scan':<28}{tally['scan_error']:>5}")

    if shape_of_r14_only:
        print("\nthe R14-only sites, by the shape that proposed them:")
        for shape, n in shape_of_r14_only.most_common():
            print(f"  {shape:<16}{n:>4}")
        print("  (narrowing and waiver-skip are not sentinel returns at all, so"
              "\n   R3's shapes cannot reach them by construction)")

    if args.show_disagreements:
        print("\ndisagreements, by module:")
        for r in records:
            if r.get("error") or (not r["r14_only"] and not r["r3_only"]):
                continue
            print(f"\n  {r['subject']}  {r['module']}")
            print(f"    sentinels declared : {r['declared_sentinels']}")
            if r["r14_only"]:
                print(f"    R14 only           : {r['r14_only']}")
            if r["r3_only"]:
                print(f"    R3 only            : {r['r3_only']} "
                      f"shapes={r['r3_shapes']}")

    summary = {
        "deferred_sites": total_sites,
        "modules": len(groups),
        "both": tally["both"],
        "r14_only": tally["r14_only"],
        "r3_only": tally["r3_only"],
        "not_expressible": tally["not_expressible"],
        "scan_errors": tally["scan_error"],
        "agreement_pct": round(pct, 1),
        "r14_only_by_shape": dict(shape_of_r14_only),
        "modules_detail": records,
    }
    pathlib.Path(args.out).write_text(json.dumps(summary, indent=2),
                                      encoding="utf-8")
    print(f"\nwrote {args.out}")
    print("\nThe deferral is now a completed handoff rather than a claim: every "
          "site R14 labelled R3's has been put to R3's own scanner, with the "
          "polarity taken from R14's own reading of that module.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
