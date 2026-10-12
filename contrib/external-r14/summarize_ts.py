"""Join the TypeScript scan to its adjudication, and refuse to print if they disagree.

The twin of `summarize.py`. Every number in the cross-language write-up comes
from here, so a re-scan that moves a site out from under a verdict fails loudly
instead of producing a quietly different figure.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
RES = json.loads((HERE / "external_r14_ts_results.json").read_text(encoding="utf-8"))
ADJ = json.loads((HERE / "adjudication_ts.json").read_text(encoding="utf-8"))
PY = json.loads((HERE / "external_r14_results.json").read_text(encoding="utf-8"))
PY_ADJ = json.loads((HERE / "adjudication.json").read_text(encoding="utf-8"))

SURF = re.compile(ADJ["_surface_regex"], re.I)
verdict_of = {(e["subject"], e["module"], e["line"]): e for e in ADJ["entries"]}


def surface(sub) -> list:
    stratum = sub.get("stratum", "A")
    return [c for c in sub["candidates"]
            if c.get("domain") == "R14"
            and (stratum == "B" or SURF.search(c["module"]))]


def main() -> int:
    scanned = [s for s in RES["subjects"] if s.get("candidates") is not None]

    # ── the join has to be exact in both directions ─────────────────────────
    scan_keys = {(s["key"], c["module"], c["line"])
                 for s in scanned for c in surface(s)}
    adj_keys = set(verdict_of)
    missing = scan_keys - adj_keys
    extra = adj_keys - scan_keys
    if missing or extra:
        print("SCAN AND ADJUDICATION DISAGREE, refusing to print numbers:")
        for k in sorted(missing)[:10]:
            print("   scanned but not adjudicated:", k)
        for k in sorted(extra)[:10]:
            print("   adjudicated but not scanned:", k)
        return 1

    tot = Counter()
    print(f"{'subject':20s} {'st':2s} {'files':>6s} {'prop':>5s} {'R14':>4s} "
          f"{'R3':>4s} {'struct':>6s} {'surf':>5s} {'up':>3s} {'pass':>4s} {'w/dn':>5s}")
    print("-" * 78)
    for s in scanned:
        dom = Counter(c.get("domain") for c in s["candidates"])
        surf = surface(s)
        v = Counter(verdict_of[(s["key"], c["module"], c["line"])]["verdict"]
                    for c in surf)
        print(f"{s['key']:20s} {s.get('stratum', 'A'):2s} "
              f"{s['scan']['parsed']:6d} {len(s['candidates']):5d} "
              f"{dom['R14']:4d} {dom['R3']:4d} {dom['STRUCTURAL']:6d} "
              f"{len(surf):5d} {v['UPHELD']:3d} {v['PASS']:4d} {v['WITHDRAWN']:5d}")
        tot["files"] += s["scan"]["parsed"]
        tot["prop"] += len(s["candidates"])
        tot["r14"] += dom["R14"]
        tot["r3"] += dom["R3"]
        tot["struct"] += dom["STRUCTURAL"]
        tot["surf"] += len(surf)
        for key in ("UPHELD", "PASS", "WITHDRAWN"):
            tot[key] += v[key]
    print("-" * 78)
    print(f"{'TOTAL':20s} {'':2s} {tot['files']:6d} {tot['prop']:5d} "
          f"{tot['r14']:4d} {tot['r3']:4d} {tot['struct']:6d} {tot['surf']:5d} "
          f"{tot['UPHELD']:3d} {tot['PASS']:4d} {tot['WITHDRAWN']:5d}")

    site = 100.0 * (tot["UPHELD"] + tot["PASS"]) / tot["surf"]
    viol = 100.0 * tot["UPHELD"] / tot["surf"]
    allp = 100.0 * tot["UPHELD"] / tot["prop"]
    print(f"\nsite precision      : {tot['UPHELD'] + tot['PASS']}/{tot['surf']} "
          f"= {site:.1f}%")
    print(f"violation precision : {tot['UPHELD']}/{tot['surf']} = {viol:.1f}%")
    print(f"                      {tot['UPHELD']}/{tot['prop']} = {allp:.1f}% "
          f"over every proposal")

    print("\nWithdrawals by cause:")
    for cls, n in sorted(Counter(
            e["class"] for e in ADJ["entries"]
            if e["verdict"] == "WITHDRAWN").items()):
        print(f"  {cls:5s} {n}")

    print("\nUpheld and passed, in full:")
    for e in ADJ["entries"]:
        if e["verdict"] in ("UPHELD", "PASS"):
            print(f"  {e['verdict']:8s} {e['subject']:12s} {e['finding']:34s} "
                  f"class {e['class']}  {e['module']}:{e['line']}")

    # ── shape mix, which the pre-registration named as an outcome ───────────
    def shapes(subjects):
        c = Counter()
        for s in subjects:
            for cand in s["candidates"]:
                c[cand["shape"]] += 1
        return c

    py_scanned = [s for s in PY["subjects"] if s.get("candidates") is not None]
    ts_sh, py_sh = shapes(scanned), shapes(py_scanned)
    ts_n, py_n = sum(ts_sh.values()), sum(py_sh.values())
    print(f"\nShape mix, the two front ends side by side "
          f"(TS n={ts_n}, Python n={py_n}):")
    print(f"  {'shape':14s} {'TS':>8s} {'Python':>8s}")
    for sh in ("benign-write", "narrowing", "waiver-skip", "discount"):
        print(f"  {sh:14s} {100.0 * ts_sh[sh] / ts_n:7.1f}% "
              f"{100.0 * py_sh[sh] / py_n:7.1f}%")

    print(f"\nCorpus side by side:")
    py_files = sum(s["scan"]["parsed"] for s in py_scanned)
    py_prop = sum(len(s["candidates"]) for s in py_scanned)
    print(f"  {'':10s} {'subjects':>9s} {'files':>7s} {'proposed':>9s}")
    print(f"  {'TypeScript':10s} {len(scanned):9d} {tot['files']:7d} {tot['prop']:9d}")
    print(f"  {'Python':10s} {len(py_scanned):9d} {py_files:7d} {py_prop:9d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
