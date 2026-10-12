#!/usr/bin/env python3
"""Corrected first-adjudication figures after amendment A4 (ADJUDICATION.md).

The pre-registered first-round record (adjudication.json, adjudication_ts.json)
is not edited. This script overlays the 21 confirmed reversals from
O4_author_reading.json and reports, BESIDE the original figures:

  * upheld sites and distinct findings, per corpus, original and corrected;
  * violation precision over the decision-surface sites, original and corrected;
  * agreement and Cohen's kappa of each model rater against the original and
    against the corrected verdicts (post hoc, labelled as such).

    python score_corrected.py  -> corrected_figures.json
"""
from __future__ import annotations

import json
import pathlib

import score_independent_adjudication as S

HERE = pathlib.Path(__file__).resolve().parent
RATERS = {"gpt-5": "independent_adjudication.json",
          "gemini-3-flash-preview": "independent_adjudication_gemini.json",
          "qwen3.8-27b": "independent_adjudication_qwen.json"}


def main() -> int:
    first = S.first_verdicts()
    o4 = json.loads((HERE / "O4_author_reading.json").read_text(encoding="utf-8"))
    assert o4["status"].startswith("CONFIRMED"), "O4 rulings not confirmed"
    flips = {r["id"]: r for r in o4["rows"] if r["confirmed_verdict"] == "UPHELD"}
    orig = {k: e["verdict"] for k, e in first.items()}
    corr = {k: ("UPHELD" if k in flips else v) for k, v in orig.items()}

    def tally(ver, lang):
        keys = [k for k in ver if k.startswith(lang)]
        up = [k for k in keys if ver[k] == "UPHELD"]
        return {"surface_sites": len(keys), "upheld_sites": len(up),
                "pass_sites": sum(1 for k in keys if ver[k] == "PASS"),
                "subjects_with_upheld": len({first[k]["subject"] for k in up}),
                "violation_precision_pct": round(100 * len(up) / max(1, len(keys)), 1)}

    out = {"_about": __doc__.split("\n\n")[0], "flipped": sorted(flips),
           "original": {"python": tally(orig, "py"), "typescript": tally(orig, "ts")},
           "corrected": {"python": tally(corr, "py"), "typescript": tally(corr, "ts")},
           "agreement": {}}
    for name, f in RATERS.items():
        p = HERE / f
        if not p.exists():
            continue
        run = json.loads(p.read_text(encoding="utf-8"))["verdicts"]
        keys = [k for k in first if k in run and run[k]["verdict"] in S.LABELS]
        row = {"sites_run": sum(1 for k in first if k in run), "scored": len(keys)}
        for label, ref in (("vs_original", orig), ("vs_corrected", corr)):
            pairs = [(ref[k], run[k]["verdict"]) for k in keys]
            row[label] = {
                "agreement_pct": round(100 * sum(a == b for a, b in pairs) / max(1, len(pairs)), 1),
                "kappa": None if S.kappa(pairs) is None else round(S.kappa(pairs), 3)}
        out["agreement"][name] = row
    (HERE / "corrected_figures.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
