"""Join the scan to the human adjudication and compute every reported number.

Nothing in the write-up is typed by hand. Run this and the tables in
EXTERNAL_FINDINGS.md are what comes out.

    python summarize.py

THE CUT THAT MATTERS IS BY RUNG DOMAIN
---------------------------------------
Every proposed site is classified R14, R3 or STRUCTURAL before anyone reads it:

  R3          a safe value produced because the check could not run. R3
              (engine/anupalabdhi.py) owns this and has shipped a fail-open
              scanner for it since July. Reported, never counted as R14 yield.
  STRUCTURAL  the guard says there was nothing to judge. Not a relaxation.
  R14         a verdict existed and something weakened it. R14's own question.

The first external run pooled all three and reported "seven findings", five of
which were R3's. That inflated the yield and hid the two contributions that are
actually separable: that mechanical discovery beats hand-declaration, and that
R14 is a distinct invariant. Precision is therefore reported over the R14 domain
alone, and separately over everything, so neither number can be quoted without
the other.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent

res = json.loads((HERE / "external_r14_results.json").read_text(encoding="utf-8"))
adj = json.loads((HERE / "adjudication.json").read_text(encoding="utf-8"))
SURFACE = re.compile(adj["_surface_regex"], re.I)

by_key = {(e["subject"], e["module"], e["line"]): e for e in adj["entries"]}
# Finding-level adjudication covers one scope; the audit-rate test covers a
# wider one. Demanding a verdict for a subject fetched only for the rate test
# would report a gap that is a deliberate scope boundary, so the boundary is
# read from the verdict file rather than assumed.
ADJUDICATED = set(adj.get("_adjudicated_subjects") or
                  {e["subject"] for e in adj["entries"]})
extra = set(by_key)
missing = []

rows = []
not_acquired = []
tot = Counter()

for s in res["subjects"]:
    if s.get("candidates") is None:
        not_acquired.append((s["key"], s.get("acquired") or s.get("error", "?")))
        continue
    cands = s["candidates"]
    dom = Counter(c.get("domain", "R14") for c in cands)
    # A stratum B subject IS the detector, so the surface regex, tuned to
    # AI-guardrail module names, would exclude the whole package.
    stratum = s.get("stratum", "A")
    surface = [c for c in cands
               if c.get("domain") == "R14"
               and (stratum == "B" or SURFACE.search(c["module"]))]
    upheld = passes = 0
    rate_only = s["key"] not in ADJUDICATED
    for c in (() if rate_only else surface):
        k = (s["key"], c["module"], c["line"])
        e = by_key.get(k)
        if e is None:
            missing.append(k)
            continue
        extra.discard(k)
        if e["verdict"] == "UPHELD":
            upheld += 1
        elif e["verdict"] == "PASS":
            passes += 1
    rows.append({
        "key": s["key"], "stratum": s.get("stratum", "A"),
        "files": s["scan"]["parsed"], "cand": len(cands),
        "r14": dom.get("R14", 0), "r3": dom.get("R3", 0),
        "structural": dom.get("STRUCTURAL", 0),
        "rate_only": rate_only,
        "surface": 0 if rate_only else len(surface),
        "upheld": upheld, "passes": passes,
        "withdrawn": 0 if rate_only else len(surface) - upheld - passes,
        "r14c": s["r14c"],
    })
    for k in ("files", "cand", "r14", "r3", "structural", "surface", "upheld",
              "passes", "withdrawn"):
        tot[k] += rows[-1][k]

if missing:
    print("UNADJUDICATED R14-domain candidates on the decision surface:")
    for m in missing[:40]:
        print("   ", m)
    if len(missing) > 40:
        print("    ... and %d more" % (len(missing) - 40))
if extra:
    print("\nAdjudication entries with no matching R14-domain candidate "
          "(stale, or the site moved domain):")
    for m in sorted(extra):
        print("   ", m)
if missing or extra:
    print("\nThe adjudication and the scan disagree. Fix before quoting.\n")

hdr = (f"{'subject':<17}{'st':>3}{'files':>7}{'cand':>6}{'R14':>5}{'R3':>5}"
       f"{'struct':>7}{'surf':>6}{'upheld':>7}{'pass':>6}{'w/dn':>6}")
print(hdr)
print("-" * len(hdr))
for st in ("A", "B"):
    band = [r for r in rows if r["stratum"] == st]
    if not band:
        continue
    for r in band:
        print(f"{r['key']:<17}{r['stratum']:>3}{r['files']:>7}{r['cand']:>6}"
              f"{r['r14']:>5}{r['r3']:>5}{r['structural']:>7}{r['surface']:>6}"
              f"{r['upheld']:>7}{r['passes']:>6}{r['withdrawn']:>6}")
    if st == "A" and any(r["stratum"] == "B" for r in rows):
        print("-" * len(hdr))
print("-" * len(hdr))
print(f"{'TOTAL':<17}{'':>3}{tot['files']:>7}{tot['cand']:>6}{tot['r14']:>5}"
      f"{tot['r3']:>5}{tot['structural']:>7}{tot['surface']:>6}"
      f"{tot['upheld']:>7}{tot['passes']:>6}{tot['withdrawn']:>6}")

if not_acquired:
    print("\nNot acquired, reported rather than dropped:")
    for k, why in not_acquired:
        print(f"  {k:<17} {why[:88]}")

print(f"\nsites proposed                      : {tot['cand']}")
print(f"  of which R14 domain               : {tot['r14']}")
print(f"  of which R3 domain (deferred)     : {tot['r3']}")
print(f"  of which structural (dropped)     : {tot['structural']}")
print(f"R14-domain, on a decision surface   : {tot['surface']}")
print(f"upheld after adjudication           : {tot['upheld']}")
print(f"passed the invariant                : {tot['passes']}")
print(f"withdrawn                           : {tot['withdrawn']}")

# Two precisions, and quoting either alone misleads. SITE precision asks
# whether this was a relaxation site at all, and a PASS is a correct
# identification there. VIOLATION precision asks whether it broke the rule.
_found = tot["upheld"] + tot["passes"]
print(f"\nsite precision, R14 on a safety path      : "
      f"{_found}/{tot['surface']} = "
      f"{100*_found/max(tot['surface'],1):.1f}%  (a real relaxation site)")
print(f"\nviolation precision, R14 on a safety path : "
      f"{tot['upheld']}/{tot['surface']} = "
      f"{100*tot['upheld']/max(tot['surface'],1):.1f}%")
print(f"violation precision, every proposed site  : "
      f"{tot['upheld']}/{tot['cand']} = "
      f"{100*tot['upheld']/max(tot['cand'],1):.1f}%")

scanned = [r for r in rows]
subj_with = sorted({e["subject"] for e in adj["entries"]
                    if e["verdict"] == "UPHELD"})
print(f"\nsubjects scanned                       : {len(scanned)} "
      f"({sum(1 for r in rows if r['stratum']=='A')} stratum A, "
      f"{sum(1 for r in rows if r['stratum']=='B')} stratum B)")
print(f"subjects with an upheld finding        : {len(subj_with)} "
      f"({', '.join(subj_with)})")

print("\nWithdrawals by rubric class:")
for cls, n in sorted(Counter(e["class"] for e in adj["entries"]
                             if e["verdict"] == "WITHDRAWN").items()):
    label = {"A": "heuristic relaxation", "B": "principal waiver",
             "C": "fail-open on error", "D": "structural fact",
             "OUT": "out of scope at step 0",
             "FP": "scanner was wrong at step 2"}.get(cls, cls)
    print(f"  {cls:<4} {label:<30} {n}")

groups = defaultdict(list)
for e in adj["entries"]:
    if e["verdict"] == "UPHELD":
        groups[(e["subject"], e["finding"])].append(e)
print("\nUpheld, grouped as distinct findings:")
for (subj, name), es in sorted(groups.items()):
    classes = "/".join(sorted({e["class"] for e in es}))
    prior = "replication" if any("REPLICATION" in (e.get("prior_work") or "")
                                 for e in es) else "new"
    print(f"  {subj:<16} {name:<38} class {classes:<4} "
          f"{len(es)} site(s)  [{prior}]")
print(f"\ndistinct findings: {len(groups)} across {len(subj_with)} subjects, "
      f"{tot['upheld']} sites")

sys.exit(1 if (missing or extra) else 0)
