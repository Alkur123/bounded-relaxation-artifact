"""Second-stage conditional retention of a published production monitor pipeline.

Computes a quantity the source publishes the inputs for and never reports:

    R = P(survives stage 2 | flagged by stage 1) = (rate after 1+2) / (rate after 1)

Both terms are measured on the SAME data by the source, so R is a directly
observed conditional. No independence assumption enters, no access to their
system is needed, and nothing here is estimated or fitted.

SOURCE
------
Anthropic, "Risk Report: August 2026", public version, 186 pages, published
under Responsible Scaling Policy v3.4 with a coverage date of 15 July 2026.
Table 2.23.1.2.B, "Prompt+completion monitor performance", pages 79 to 80.

Every value below is transcribed by hand from that table and each row records
the page it came from. The transcription is the weak link in any such exercise,
so it is pinned by tests/test_stage_retention.py the same way
test_external_ensembles.py pins the numbers in paper 11: a committed verbatim
extraction, and a test that fails if a declared digit stops matching it.

WHAT THE SOURCE SAYS ABOUT THE SECOND STAGE
-------------------------------------------
Its stated job is removing false positives before human review:

  "Second-stage pipelines for both monitors, filtering out common sources of
   false positives and using a hierarchical summarization tool to surface the
   most concerning actions to AI control researchers, which will then manually
   review on the order of 50 trajectories per week"          (Section 2.23.1.1)

and, importantly for how the result below should be read:

  "Certain workloads that result in high rates of false positives or certain
   forms of evals are often filtered out of the second stage prior to review."

CAVEATS THAT TRAVEL WITH EVERY NUMBER
-------------------------------------
1. Rounding. The source reports whole percentages, so a ratio of two of them
   carries the slop of both. R is reported to one decimal and no comparison
   below turns on a difference smaller than the rounding interval.
2. One row is a count, not a percentage: "5 Internal Red-Teaming transcripts"
   reports 4/5, 4/5, 3/5, 4/5. It is included as 80/80/60/80 and flagged, and
   it is excluded from the spread statistics because n=5.
3. The benign row is "lower is better" and is NOT an attack set. Its retention
   is reported separately and must never be pooled with the attack rows.
4. The source states the real-traffic rates "vary over time and the numbers
   reported were not reported on the same period of time".

Run:  python eval/stage_retention.py
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "stage_retention.json"

SOURCE = {
    "document": "Anthropic, Risk Report: August 2026 (public version)",
    "policy": "Responsible Scaling Policy v3.4",
    "coverage_date": "2026-07-15",
    "pages": 186,
    "table": "2.23.1.2.B, Prompt+completion monitor performance",
    "table_pages": "79-80",
    "sha256": "e8f7c01026e798eb9fb01d7470f73b93801835b57f0d134e7a9cc243aa74dcfd",
    "columns": [
        "Positive rate (Opus 4.6 monitor, early Mythos 5 internal deployment)",
        "Positive rate (Opus 4.8 monitor, current internal deployment)",
        "Positive rate (Opus 4.6 monitor + second-stage filter)",
        "Positive rate (Opus 4.8 monitor + second-stage filter)",
    ],
}

#: name, stage1_46, stage1_48, stage12_46, stage12_48, kind, note
ROWS = [
    ("METR red team, all attacks (n=163)", 78, 94, 62, 79, "attack", ""),
    ("5 internal red-team transcripts", 80, 80, 60, 80, "attack",
     "source reports 4/5, 4/5, 3/5, 4/5; n=5, excluded from spread stats"),
    ("Synthetic dangerous/scheming transcripts", 96, 96, 73, 80, "attack", ""),
    ("Internal evaluation set", 87, 87, 62, 72, "attack",
     "superset of the two rows above"),
    ("Internal evaluation set + 200k benign tokens", 80, 89, 64, 69, "attack", ""),
    ("Internal evaluation set + 400k benign tokens", 80, 84, 59, 69, "attack", ""),
    ("SHADE-Arena, full extended thinking", 100, 100, 45, 70, "attack",
     "CoT discusses the side goal; Opus 4.5 attempts"),
    ("SHADE-Arena, side goal ablated from CoT", 100, 100, 97, 92, "attack",
     "same attempts, incriminating reasoning removed"),
    ("MonitorBench Hard (n=60)", 92, 92, 77, 87, "attack", ""),
    ("MonitorBench Hard + 200k before", 72, 83, 58, 75, "attack", ""),
    ("MonitorBench Hard + 200k before and after", 48, 77, 37, 63, "attack",
     "source notes this is less analogous to their setup"),
    ("SLEIGHT-Bench", 23, 58, 14, 44, "attack", ""),
    ("Monitored internal traffic", 0.4, 0.2, 0.04, 0.1, "benign",
     "lower is better; NOT an attack set, never pool with the rows above"),
]

# ── Table 2.23.1.2.A, page 78: the COMPLETION-ONLY monitor ────────────────────
# A DIFFERENT monitor from the one above, with its own second stage. Added
# 2026-08-17 on a second pass, after the first pass analysed only Table B. That
# omission mattered: this table carries an independent replication of the
# ablation effect, and the two lowest retentions in the entire report.
#
#: name, stage1, stage1_plus_2, kind, note
ROWS_A = [
    ("Treutlein 2026 model organisms", 100.0, 33.3, "attack",
     "source reports 3/3 and 1/3; n=3, far too small to carry alone"),
    ("SHADE-Arena CoT only, selected for stealthiness", 100.0, 72.0, "attack",
     "side goal discussed in the chain of thought"),
    ("SHADE-Arena CoT only, side goal ablated", 95.0, 92.0, "attack",
     "same corpus, incriminating discussion removed"),
    ("Synthetic chains-of-thought (single completion)", 72.0, 29.0, "attack", ""),
    ("Monitored internal traffic", 0.74, 0.004, "benign",
     "lower is better; the filter's actual job"),
]

#: The matched pair in Table B. Same attempts, same stage-1 rate, one variable.
PAIR = ("SHADE-Arena, full extended thinking",
        "SHADE-Arena, side goal ablated from CoT")

#: The same contrast in Table A. NEARLY matched rather than exactly: stage-1 is
#: 100% and 95% here, where Table B's pair is 100% and 100%. Stated because the
#: difference is the whole reason Table B's pair is the stronger evidence.
PAIR_A = ("SHADE-Arena CoT only, selected for stealthiness",
          "SHADE-Arena CoT only, side goal ablated")

#: n=5, so it carries no spread information.
SMALL_N = "5 internal red-team transcripts"


def retention(stage1: float, stage12: float) -> float:
    return stage12 / stage1


def build() -> dict:
    rows = []
    for name, a6, a8, b6, b8, kind, note in ROWS:
        rows.append({
            "evaluation": name, "kind": kind, "note": note,
            "stage1": {"opus_4_6": a6, "opus_4_8": a8},
            "stage1_plus_2": {"opus_4_6": b6, "opus_4_8": b8},
            "retention": {"opus_4_6": round(retention(a6, b6), 4),
                          "opus_4_8": round(retention(a8, b8), 4)},
        })

    attacks = [r for r in rows if r["kind"] == "attack"]
    spread_pool = [r for r in attacks if r["evaluation"] != SMALL_N]
    pair = {r["evaluation"]: r for r in attacks if r["evaluation"] in PAIR}

    def stats(key):
        vals = [r["retention"][key] for r in spread_pool]
        return {"mean": round(statistics.mean(vals), 4),
                "min": round(min(vals), 4), "max": round(max(vals), 4),
                "n": len(vals)}

    full, ablated = pair[PAIR[0]], pair[PAIR[1]]
    matched = {}
    for key in ("opus_4_6", "opus_4_8"):
        f, a = full["retention"][key], ablated["retention"][key]
        matched[key] = {
            "full_cot": f, "ablated": a,
            "delta_points": round((f - a) * 100, 1),
            "ablation_multiplier": round(a / f, 2),
            "stage1_identical": (full["stage1"][key] == ablated["stage1"][key]),
        }

    # Is the full-CoT row an outlier against every OTHER attack row?
    outlier = {}
    for key in ("opus_4_6", "opus_4_8"):
        others = [r["retention"][key] for r in spread_pool
                  if r["evaluation"] != PAIR[0]]
        outlier[key] = {
            "full_cot_retention": full["retention"][key],
            "min_of_all_other_attack_rows": round(min(others), 4),
            "is_strictly_lowest": full["retention"][key] < min(others),
        }

    rows_a = []
    for name, s1, s12, kind, note in ROWS_A:
        rows_a.append({
            "evaluation": name, "kind": kind, "note": note,
            "stage1": s1, "stage1_plus_2": s12,
            "retention": round(retention(s1, s12), 4),
        })
    a_by = {r["evaluation"]: r for r in rows_a}
    disc, abl = a_by[PAIR_A[0]], a_by[PAIR_A[1]]
    replication = {
        "table_A_completion_only": {
            "discussed": disc["retention"], "ablated": abl["retention"],
            "delta_points": round((disc["retention"] - abl["retention"]) * 100, 1),
            "stage1_identical": disc["stage1"] == abl["stage1"],
            "caveat": ("stage-1 rates are 100.0 and 95.0, so this pair is NEARLY "
                       "matched, not exactly. Table B's pair is 100/100 and is "
                       "therefore the stronger of the two."),
        },
        "table_B_prompt_completion": {
            k: matched[k]["delta_points"] for k in matched},
        "same_sign_in_all_three_configurations": (
            disc["retention"] < abl["retention"]
            and all(matched[k]["delta_points"] < 0 for k in matched)),
        "reading": ("The ablation contrast appears in TWO tables covering two "
                    "different monitor architectures, with the same sign in all "
                    "three configurations. That is what makes it a pattern rather "
                    "than one striking row."),
    }
    lowest = sorted(
        [r for r in rows_a if r["kind"] == "attack"], key=lambda r: r["retention"])[:2]

    return {
        "what": ("Second-stage conditional retention, R = P(survives stage 2 | "
                 "flagged by stage 1), computed from two published tables"),
        "table_A_rows": rows_a,
        "ablation_replication": replication,
        "lowest_retentions_in_either_table": [
            {"evaluation": r["evaluation"], "retention": r["retention"],
             "note": r["note"]} for r in lowest],
        "benign_filtering_works": {
            "table_A_benign_retention": a_by["Monitored internal traffic"]["retention"],
            # The complement, emitted rather than left for prose to compute. The
            # paper quotes it, and a number a reader can only get by doing
            # arithmetic on another number is exactly the kind that drifts.
            "table_A_benign_removed_pct": round(
                (1 - a_by["Monitored internal traffic"]["retention"]) * 100, 1),
            "reading": ("The filter removes about 99.5% of benign flags, which is "
                        "exactly its stated job. Reported because it is what makes "
                        "the attack rows interpretable rather than alarming on "
                        "their own: the question is the DIFFERENTIAL, not whether "
                        "the stage filters."),
        },
        "generated_by": "backend/eval/stage_retention.py",
        "source": SOURCE,
        "caveats": [
            "The source reports whole percentages; a ratio of two carries both "
            "roundings. No comparison here turns on a difference below that.",
            "The 5-transcript row is a count (4/5 etc.), included as percentages "
            "and excluded from spread statistics because n=5.",
            "The benign row is lower-is-better and is not an attack set.",
            "The source states real-traffic rates were not measured over the "
            "same period.",
            "This is a conditional observed on the source's own data. It is not "
            "a claim about the mechanism producing it.",
        ],
        "rows": rows,
        "attack_retention": {"opus_4_6": stats("opus_4_6"),
                             "opus_4_8": stats("opus_4_8")},
        "benign_retention": {
            r["evaluation"]: r["retention"] for r in rows if r["kind"] == "benign"},
        "matched_pair": {
            "design": ("Same SHADE-Arena side-task attempts, identical stage-1 "
                       "rate, single manipulated variable: whether the chain of "
                       "thought discusses the side goal."),
            "by_monitor": matched,
        },
        "outlier_check": outlier,
    }


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")

    print("SECOND-STAGE CONDITIONAL RETENTION")
    print(f"source: {SOURCE['document']}, table {SOURCE['table']}")
    print()
    print(f"  {'evaluation':<44}{'4.6':>8}{'4.8':>8}")
    print("  " + "-" * 60)
    for r in data["rows"]:
        mark = "  " if r["kind"] == "attack" else " *"
        print(f"{mark}{r['evaluation']:<44}"
              f"{r['retention']['opus_4_6']:>8.1%}{r['retention']['opus_4_8']:>8.1%}")
    print("  " + "-" * 60)
    print("  * benign, lower is better, not pooled")
    print()
    for key in ("opus_4_6", "opus_4_8"):
        s = data["attack_retention"][key]
        print(f"  {key}: attack retention mean {s['mean']:.1%}, "
              f"range {s['min']:.1%} to {s['max']:.1%} over n={s['n']}")
    print()
    print("MATCHED PAIR")
    print(f"  {data['matched_pair']['design']}")
    for key, m in data["matched_pair"]["by_monitor"].items():
        print(f"    {key}: full CoT {m['full_cot']:.0%}, ablated {m['ablated']:.0%}, "
              f"delta {m['delta_points']:+.0f} pts, "
              f"ablating multiplies retention by {m['ablation_multiplier']}x")
        assert m["stage1_identical"], "pair is only matched if stage 1 agrees"
    print()
    print("OUTLIER CHECK, against every other attack row")
    for key, o in data["outlier_check"].items():
        verdict = "strictly lowest" if o["is_strictly_lowest"] else "NOT lowest"
        print(f"    {key}: full-CoT {o['full_cot_retention']:.1%} vs next lowest "
              f"{o['min_of_all_other_attack_rows']:.1%}  ->  {verdict}")
    print()
    print("TABLE A, THE COMPLETION-ONLY MONITOR (a different monitor)")
    for r in data["table_A_rows"]:
        mark = "  " if r["kind"] == "attack" else " *"
        print(f"{mark}{r['evaluation']:<50}{r['retention']:>8.1%}   {r['note']}")
    print()
    rep = data["ablation_replication"]
    a = rep["table_A_completion_only"]
    print("REPLICATION OF THE ABLATION CONTRAST")
    print(f"    Table A  discussed {a['discussed']:.1%}  ablated {a['ablated']:.1%}  "
          f"delta {a['delta_points']:+.1f} pts")
    for k, d in rep["table_B_prompt_completion"].items():
        print(f"    Table B  {k}: delta {d:+.1f} pts")
    print(f"    same sign in all three configurations: "
          f"{rep['same_sign_in_all_three_configurations']}")
    print(f"    caveat: {a['caveat']}")
    print()
    print("LOWEST RETENTIONS IN EITHER TABLE")
    for r in data["lowest_retentions_in_either_table"]:
        print(f"    {r['evaluation']:<50}{r['retention']:>8.1%}   {r['note']}")
    print("    Both are direct tests of catching misaligned REASONING.")
    print()
    b = data["benign_filtering_works"]
    print(f"BENIGN RETENTION {b['table_A_benign_retention']:.2%}. {b['reading']}")
    print()
    print(f"wrote {OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
