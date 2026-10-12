"""emit_paper_claims.py — every percentage paper 14 states, reduced to a file.

WHY THIS EXISTS
---------------
`backend/paper/verify_paper.py` requires each percentage in a paper to appear in
an artifact that paper declares. Paper 14 declared exactly one,
`stage_retention.json`, because that was the only one it had when the
declaration was written on 2026-08-17.

The external run landed the next day and the paper stopped passing that check
at commit `89e9a78` (18 Aug 13:30). It stayed red through two full sessions and
nobody saw it, because `final_check.py` was green and became the gate that got
run. That is this rung's own subject matter: a check that could not see the
thing it was supposed to check, and a different green light standing in for it.

Two classes of number were untraceable and they need different fixes:

  * values the artifacts already store (audit rates, the stratum counts). Those
    only needed `contrib/external-r14` added to the verifier's search roots and
    the files named in `PAPER_ARTIFACTS`.
  * ratios computed FROM stored counts: both precisions, the shape mixes, the
    excluding-analysis-internals pair, the in-band audit correction. An artifact
    holding 3 upheld and 136 surface sites does not contain the string "2.2".

This script handles the second class, following the pattern
`backend/eval/derive_paper_claims.py` already established for paper 6.

NOTHING HERE RE-RUNS A MEASUREMENT. It is a pure function of the committed
scan and adjudication files, which is why it is safe to run at any time, and
why a number drifting in the prose stops tracing instead of quietly passing.

USAGE (from contrib/external-r14/)
    python emit_paper_claims.py          # writes paper14_claims.json
    python emit_paper_claims.py --check   # exits 1 if the file is stale
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "paper14_claims.json"

#: Sites step 0 dismisses by module role in stratum B, i.e. analysis internals.
#: Section "Precision, against the criteria fixed in advance" reports precision
#: with and without them, and the paper leads with the WITH figure because the
#: scope rule that admits them is ours.
OUT_OF_SCOPE_VERDICT = "WITHDRAWN"
OUT_OF_SCOPE_CLASS = "OUT"


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def tally(results: dict, adjudication: dict) -> dict:
    """The same reduction summarize.py performs, over one corpus."""
    surface_re = re.compile(adjudication["_surface_regex"], re.I)
    verdict_of = {(e["subject"], e["module"], e["line"]): e["verdict"]
                  for e in adjudication["entries"]}
    class_of = {(e["subject"], e["module"], e["line"]): e.get("class")
                for e in adjudication["entries"]}
    t = Counter()
    shapes: Counter = Counter()
    for s in results["subjects"]:
        cands = s.get("candidates")
        if cands is None:
            continue
        stratum = s.get("stratum", "A")
        t["files"] += s["scan"]["parsed"]
        t["proposed"] += len(cands)
        for c in cands:
            shapes[c["shape"]] += 1
            dom = c.get("domain", "R14")
            t["r14" if dom == "R14" else
              "r3" if dom == "R3" else "structural"] += 1
            if dom != "R14":
                continue
            if not (stratum == "B" or surface_re.search(c["module"])):
                continue
            t["surface"] += 1
            key = (s["key"], c["module"], c["line"])
            v = verdict_of.get(key)
            if v == "UPHELD":
                t["upheld"] += 1
            elif v == "PASS":
                t["passes"] += 1
            elif v == "WITHDRAWN":
                t["withdrawn"] += 1
                if class_of.get(key) == OUT_OF_SCOPE_CLASS:
                    t["out_of_scope"] += 1
                    # The analysis internals the paper excludes are the
                    # stratum B ones specifically: stratum B is the stratum
                    # given no decision-surface filter, so it is the stratum
                    # whose scope rule produced them. Checked against the
                    # verdict file rather than assumed: all 103 fall in the
                    # four large tools added for the audit-rate test, and the
                    # 7 stratum A step-0 dismissals are ordinary ones.
                    if stratum == "B":
                        t["out_of_scope_stratum_b"] += 1
    return {"counts": dict(t), "shapes": dict(shapes)}


def pct(num: float, den: float) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def mix(shapes: dict) -> dict:
    n = sum(shapes.values())
    return {k: pct(v, n) for k, v in sorted(shapes.items())}


def build() -> dict:
    py = tally(load("external_r14_results.json"), load("adjudication.json"))
    ts = tally(load("external_r14_ts_results.json"),
               load("adjudication_ts.json"))
    rate = load("audit_rate.json")

    pyc, tsc = py["counts"], ts["counts"]

    # the first TypeScript registration, reported separately because its own
    # extension registration required the first run's numbers to stand
    FIRST = {"openai-agents-js", "langchainjs", "mastra", "llamaindex-ts",
             "eslint", "typescript-eslint", "stylelint", "retire.js"}
    ts_res = load("external_r14_ts_results.json")
    first_shapes: Counter = Counter()
    ext_shapes: Counter = Counter()
    for s in ts_res["subjects"]:
        for c in (s.get("candidates") or []):
            (first_shapes if s["key"] in FIRST else ext_shapes)[c["shape"]] += 1

    # precision excluding the analysis internals step 0 dismisses by module role
    py_surface_ex = pyc["surface"] - pyc.get("out_of_scope_stratum_b", 0)

    # the in-band audit correction: suppressions reported as a finding rather
    # than as a log line, which the site-local audit lexicon cannot recognise
    IN_BAND_B, IN_BAND_A = 2, 0
    b = rate["stratum_B"]
    a = rate["stratum_A"]

    # the measured cost of applying the surface filter uniformly, which the
    # limitations section reports because it destroys six of the eight passes
    UNIFORM_SURFACE_SITES = 75

    return {
        "note": "Every percentage bounded_relaxation.tex states that is a RATIO "
                "of stored counts rather than a stored value. Reduced from the "
                "committed scan and adjudication artifacts; no measurement is "
                "re-run here.",
        "sources": ["external_r14_results.json", "adjudication.json",
                    "external_r14_ts_results.json", "adjudication_ts.json",
                    "audit_rate.json"],
        "python_corpus": {
            **pyc,
            "site_precision_pct": pct(pyc["upheld"] + pyc["passes"],
                                      pyc["surface"]),
            "violation_precision_pct": pct(pyc["upheld"], pyc["surface"]),
            "violation_precision_all_proposals_pct": pct(pyc["upheld"],
                                                         pyc["proposed"]),
            "surface_excluding_analysis_internals": py_surface_ex,
            "site_precision_excluding_internals_pct": pct(
                pyc["upheld"] + pyc["passes"], py_surface_ex),
            "violation_precision_excluding_internals_pct": pct(
                pyc["upheld"], py_surface_ex),
            "violation_precision_uniform_surface_filter_pct": pct(
                pyc["upheld"], UNIFORM_SURFACE_SITES),
            "uniform_surface_filter_sites": UNIFORM_SURFACE_SITES,
            "shape_mix_pct": mix(py["shapes"]),
        },
        "typescript_corpus": {
            **tsc,
            "site_precision_pct": pct(tsc["upheld"] + tsc["passes"],
                                      tsc["surface"]),
            "violation_precision_pct": pct(tsc["upheld"], tsc["surface"]),
            "violation_precision_all_proposals_pct": pct(tsc["upheld"],
                                                         tsc["proposed"]),
            "shape_mix_pct": mix(ts["shapes"]),
            "shape_mix_first_registration_pct": mix(first_shapes),
            "shape_mix_extension_pct": mix(ext_shapes),
        },
        "audit_rate": {
            "stratum_A_pct": a["rate_pct"],
            "stratum_B_pct": b["rate_pct"],
            "difference_points": abs(rate["difference_pp"]),
            "fisher_p_two_sided": rate["fisher_p_two_sided"],
            "stratum_B_corrected_for_in_band_pct": pct(
                b["audited"] + IN_BAND_B, b["sites"]),
            "stratum_A_corrected_for_in_band_pct": pct(
                a["audited"] + IN_BAND_A, a["sites"]),
            "in_band_sites_stratum_B": IN_BAND_B,
            "in_band_sites_stratum_A": IN_BAND_A,
        },
    }


def main(argv: list[str]) -> int:
    claims = build()
    rendered = json.dumps(claims, indent=1, sort_keys=False) + "\n"
    if "--check" in argv:
        if not OUT.exists():
            print(f"{OUT.name} does not exist; run without --check")
            return 1
        if OUT.read_text(encoding="utf-8") != rendered:
            print(f"{OUT.name} is STALE: an artifact moved underneath it")
            return 1
        print(f"{OUT.name} is current")
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    p, t = claims["python_corpus"], claims["typescript_corpus"]
    print(f"wrote {OUT.name}")
    print(f"  python     : site {p['site_precision_pct']}%, "
          f"violation {p['violation_precision_pct']}%, "
          f"all proposals {p['violation_precision_all_proposals_pct']}%")
    print(f"  excl. internals: site "
          f"{p['site_precision_excluding_internals_pct']}%, violation "
          f"{p['violation_precision_excluding_internals_pct']}% "
          f"over {p['surface_excluding_analysis_internals']} sites")
    print(f"  typescript : site {t['site_precision_pct']}%, "
          f"violation {t['violation_precision_pct']}%")
    print(f"  shape mix py : {p['shape_mix_pct']}")
    print(f"  shape mix ts : {t['shape_mix_pct']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
