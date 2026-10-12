"""Do classical detectors audit their relaxations more than AI guardrails?

Tests the hypothesis pre-registered in PREREGISTRATION_audit_rate.md, which was
committed before the additional subjects were fetched.

    python audit_rate.py
    python audit_rate.py --show-sample     # stratum B traces, for the confound check

No API key, no network, no execution of any subject. Reads the committed scan.

WHAT IS MEASURED, AND WHAT MAY NOT BE QUOTED
--------------------------------------------
Unit: one proposed site in the R14 domain, that is, a relaxation of a verdict
that existed. R3-domain and structural sites are excluded, because they are not
relaxations and the two strata could differ in their mix of them for unrelated
reasons.

Outcome: the scanner's ``audited`` flag, which OVER-CREDITS. It counts a trace
anywhere in the block performing the relaxation, not only on the relaxing path,
so the true rate is lower than measured in both strata. The bias is symmetric,
so it weakens neither direction of the comparison, but **no absolute rate here
may be quoted as "the fraction of relaxations that are audited"**. Only the
difference between strata is meaningful.

Fisher's exact test is computed directly from the hypergeometric distribution so
the result does not depend on SciPy being installed.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "external_r14_results.json"
OUT = HERE / "audit_rate.json"

MIN_B_SITES = 30          # pre-registered power floor for stratum B


def _logfact(n: int) -> float:
    return math.lgamma(n + 1)


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 [[a, b], [c, d]].

    Sums the hypergeometric probability of every table with the same margins
    whose probability is no greater than the observed one, which is the
    conventional two-sided definition and the one SciPy uses.
    """
    n = a + b + c + d
    row1, col1 = a + b, a + c

    def p_of(x: int) -> float:
        y, z, w = row1 - x, col1 - x, n - row1 - col1 + x
        if min(y, z, w) < 0:
            return 0.0
        return math.exp(
            _logfact(row1) + _logfact(n - row1) + _logfact(col1)
            + _logfact(n - col1) - _logfact(n)
            - _logfact(x) - _logfact(y) - _logfact(z) - _logfact(w))

    p_obs = p_of(a)
    lo, hi = max(0, col1 - (n - row1)), min(row1, col1)
    tol = p_obs * (1 + 1e-9)
    return min(1.0, sum(p_of(x) for x in range(lo, hi + 1) if p_of(x) <= tol))


def collect(res: dict) -> Dict[str, List[dict]]:
    """R14-domain sites per subject, tagged with stratum."""
    per: Dict[str, List[dict]] = defaultdict(list)
    for s in res["subjects"]:
        if not s.get("candidates"):
            continue
        for c in s["candidates"]:
            if c.get("domain") == "R14":
                per[s["key"]].append({**c, "_stratum": s.get("stratum", "A")})
    return per


def rate(sites: List[dict]) -> Tuple[int, int, float]:
    n = len(sites)
    k = sum(1 for c in sites if c.get("audited"))
    return k, n, (100.0 * k / n if n else float("nan"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(RESULTS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--show-sample", action="store_true")
    args = ap.parse_args()

    res = json.loads(pathlib.Path(args.results).read_text(encoding="utf-8"))
    per = collect(res)
    strat = {s["key"]: s.get("stratum", "A") for s in res["subjects"]}

    A = [c for k, v in per.items() if strat.get(k) == "A" for c in v]
    B = [c for k, v in per.items() if strat.get(k) == "B" for c in v]

    print("R14-domain relaxation sites, by stratum\n")
    print(f"{'subject':<18}{'stratum':>8}{'sites':>7}{'audited':>9}{'rate':>8}")
    print("-" * 50)
    for key in sorted(per, key=lambda k: (strat.get(k, 'A'), -len(per[k]))):
        k, n, pct = rate(per[key])
        if n:
            print(f"{key:<18}{strat.get(key,'A'):>8}{n:>7}{k:>9}{pct:>7.1f}%")

    ka, na, pa = rate(A)
    kb, nb, pb = rate(B)
    print("-" * 50)
    print(f"{'stratum A (AI)':<18}{'':>8}{na:>7}{ka:>9}{pa:>7.1f}%")
    print(f"{'stratum B (classic)':<18}{'':>8}{nb:>7}{kb:>9}{pb:>7.1f}%")

    summary = {
        "hypothesis": "stratum B audits its relaxations at a higher rate than A",
        "unit": "one R14-domain proposed site",
        "outcome": "scanner 'audited' flag, which over-credits symmetrically",
        "stratum_A": {"sites": na, "audited": ka, "rate_pct": round(pa, 1)},
        "stratum_B": {"sites": nb, "audited": kb, "rate_pct": round(pb, 1)},
        "per_subject": {k: {"stratum": strat.get(k, "A"), "sites": rate(v)[1],
                            "audited": rate(v)[0],
                            "rate_pct": round(rate(v)[2], 1)}
                        for k, v in per.items() if v},
    }

    # ── the pre-registered power floor ───────────────────────────────────
    if nb < MIN_B_SITES:
        print(f"\nSTRATUM B HAS {nb} SITES, BELOW THE PRE-REGISTERED FLOOR OF "
              f"{MIN_B_SITES}.")
        print("  Reporting no p-value. The pre-registration fixed this case in")
        print("  advance precisely so a number would not be produced from thin")
        print("  data: the honest report is that the comparison could not be")
        print("  made, not a test statistic nobody should trust.")
        summary["verdict"] = "UNDERPOWERED, NO TEST REPORTED"
        summary["min_b_sites"] = MIN_B_SITES
        pathlib.Path(args.out).write_text(json.dumps(summary, indent=2),
                                          encoding="utf-8")
        print(f"\nwrote {args.out}")
        return 0

    p = fisher_exact_two_sided(kb, nb - kb, ka, na - ka)
    diff = pb - pa
    print(f"\ndifference (B minus A) : {diff:+.1f} percentage points")
    print(f"Fisher exact, two-sided: p = {p:.4g}")
    verdict = ("SUPPORTED" if (p < 0.05 and diff > 0) else
               "OPPOSITE DIRECTION" if (p < 0.05 and diff < 0) else
               "NOT SUPPORTED")
    print(f"pre-registered verdict : {verdict}")

    # ── leave-one-subject-out, also pre-registered ───────────────────────
    print("\nleave-one-subject-out (does any single subject carry it?)")
    fragile = []
    for drop in sorted(per):
        if not per[drop]:
            continue
        A2 = [c for k, v in per.items() if strat.get(k) == "A" and k != drop for c in v]
        B2 = [c for k, v in per.items() if strat.get(k) == "B" and k != drop for c in v]
        if not A2 or not B2:
            continue
        ka2, na2, pa2 = rate(A2)
        kb2, nb2, pb2 = rate(B2)
        p2 = fisher_exact_two_sided(kb2, nb2 - kb2, ka2, na2 - ka2)
        if (p < 0.05) and (p2 >= 0.05):
            fragile.append(drop)
            print(f"  without {drop:<16} p = {p2:.4g}   <-- significance lost")
    if not fragile:
        print("  significance survives dropping any single subject"
              if p < 0.05 else "  (not significant to begin with)")
    else:
        print("\n  THE RESULT IS CARRIED BY THE SUBJECTS ABOVE. Per the")
        print("  pre-registration it is a claim about them, not about a field.")

    summary.update({
        "difference_pp": round(diff, 1),
        "fisher_p_two_sided": p,
        "verdict": verdict,
        "significance_lost_without": fragile,
    })

    if args.show_sample:
        print("\nstratum B audited sites, for the confound check "
              "(is the trace a RECORD or merely console output?)")
        for c in [c for c in B if c.get("audited")][:12]:
            print(f"  {c['subject']:<15} {c['module'][-40:]:<40}:"
                  f"{c['line']:<5} via {c.get('audit_symbol')}")

    pathlib.Path(args.out).write_text(json.dumps(summary, indent=2),
                                      encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
