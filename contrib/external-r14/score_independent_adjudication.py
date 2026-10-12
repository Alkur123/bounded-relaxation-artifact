#!/usr/bin/env python3
"""Score the second adjudication against the first, per the pre-registration.

Outcomes O1-O5 of PREREGISTRATION_independent_adjudication.md, computed from
independent_adjudication.json (the model's verdicts) and the committed first
verdicts (adjudication.json, adjudication_ts.json). Nothing is adjudicated
here; disagreements are listed for the author to read (O4).

    python score_independent_adjudication.py  -> independent_adjudication_score.json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LABELS = ("UPHELD", "PASS", "WITHDRAWN")


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def first_verdicts():
    out = {}
    for lang, f in (("py", "adjudication.json"), ("ts", "adjudication_ts.json")):
        for n, e in enumerate(json.loads((HERE / f).read_text(encoding="utf-8"))["entries"]):
            out[f"{lang}-{n:03d}"] = e
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="independent_adjudication.json")
    ap.add_argument("--out", default="independent_adjudication_score.json")
    ap.add_argument("--vs", default=None,
                    help="a second model run: report model-to-model agreement")
    args = ap.parse_args()
    first = first_verdicts()
    run = json.loads((HERE / args.run).read_text(encoding="utf-8"))
    second = run["verdicts"]
    done = [k for k in first if k in second]
    unsure = [k for k in done if second[k]["verdict"] not in LABELS]
    scored = [k for k in done if second[k]["verdict"] in LABELS]

    def block(keys):
        pairs = [(first[k]["verdict"], second[k]["verdict"]) for k in keys]
        agree = sum(1 for a, b in pairs if a == b)
        return {"n": len(pairs), "agree": agree,
                "agreement_pct": round(100 * agree / max(1, len(pairs)), 1),
                "kappa": None if kappa(pairs) is None else round(kappa(pairs), 3),
                "confusion": {f"{a}->{b}": c for (a, b), c in
                              sorted(collections.Counter(pairs).items())}}

    o1 = {"all": block(scored),
          "python": block([k for k in scored if k.startswith("py")]),
          "typescript": block([k for k in scored if k.startswith("ts")]),
          "first_non_withdrawn": block([k for k in scored
                                        if first[k]["verdict"] != "WITHDRAWN"])}

    o2 = []
    for k, e in first.items():
        if e["verdict"] == "WITHDRAWN":
            continue
        s = second.get(k, {})
        o2.append({"id": k, "subject": e["subject"], "module": e["module"],
                   "line": e["line"], "first": e["verdict"],
                   "finding": e.get("finding"),
                   "second": s.get("verdict", "NOT RUN"),
                   "second_class": s.get("class"),
                   "second_reason": s.get("reason"),
                   "survives": s.get("verdict") == e["verdict"]})

    up = [r for r in o2 if r["first"] == "UPHELD"]
    ps = [r for r in o2 if r["first"] == "PASS"]
    o3 = {"upheld_by_both": sum(r["survives"] for r in up), "upheld_first": len(up),
          "pass_by_both": sum(r["survives"] for r in ps), "pass_first": len(ps)}

    o4 = [{"id": k, "subject": first[k]["subject"], "module": first[k]["module"],
           "line": first[k]["line"], "first_class": first[k].get("class"),
           "first_reason": first[k].get("why"),
           "second_class": second[k].get("class"),
           "second_reason": second[k].get("reason")}
          for k in scored
          if first[k]["verdict"] == "WITHDRAWN" and second[k]["verdict"] == "UPHELD"]

    mech = collections.defaultdict(list)
    for r in ps:
        mech[r["finding"]].append(r["survives"])
    o5 = {m: any(v) for m, v in mech.items()}

    out = {"sites_total": len(first), "sites_run": len(done),
           "missing": run.get("missing", []), "unsure": len(unsure),
           "unsure_ids": unsure, "served_models": sorted({u["served"] for u in run["usage"]}),
           "tokens_in": sum(u["usage"].get("input_tokens", 0) for u in run["usage"]),
           "tokens_out": sum(u["usage"].get("output_tokens", 0) for u in run["usage"]),
           "O1": o1, "O2": o2, "O3": o3, "O4_withdrawn_to_upheld": o4,
           "O5_pass_mechanisms_recognised_by_both": o5}
    if args.vs:
        other = json.loads((HERE / args.vs).read_text(encoding="utf-8"))["verdicts"]
        both = [k for k in first if k in second and k in other
                and second[k]["verdict"] in LABELS and other[k]["verdict"] in LABELS]
        mm = [(second[k]["verdict"], other[k]["verdict"]) for k in both]
        out["model_vs_model"] = {
            "other_run": args.vs, "n": len(mm),
            "agree": sum(a == b for a, b in mm),
            "agreement_pct": round(100 * sum(a == b for a, b in mm) / max(1, len(mm)), 1),
            "kappa": None if kappa(mm) is None else round(kappa(mm), 3),
            "both_disagree_with_first_same_way": sum(
                1 for k in both if second[k]["verdict"] == other[k]["verdict"]
                != first[k]["verdict"])}
        print("model vs model:", out["model_vs_model"])
    (HERE / args.out).write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("sites_total", "sites_run", "unsure",
                                          "O1", "O3", "O5_pass_mechanisms_recognised_by_both")},
                     indent=1))
    print(f"O4: {len(o4)} sites the second adjudicator upholds that the first withdrew")
    for r in o2:
        print(f"  O2 {r['first']:6s} {r['subject']:16s} {r['finding']:38s} -> {r['second']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
