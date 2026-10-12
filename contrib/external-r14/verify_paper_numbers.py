"""Check every scalar claim in paper 14 against the artifacts that produced it.

`verify_paper_table.py` pins the per-subject table. This pins everything else:
the corpus sizes, the domain split, the adjudication outcomes, the two
precisions, the handoff between rungs, and the pre-registered audit-rate result.

    python verify_paper_numbers.py      # exits non-zero on any drift

WHY THIS EXISTS, AND IT IS NOT HYPOTHETICAL
-------------------------------------------
Three times in one session a number in this paper went stale because an artifact
was regenerated underneath it. Twice it was the compiled bundle; once it was the
handoff table, which still reported fifty-two deferred sites after the corpus
grew to seventy-two. Each was caught by hand, and a check caught by hand is a
check that will eventually not be.

Each claim below is COMPUTED from the released artifacts and then required to
appear in the source as written. A claim that moves and is not re-typed fails
here rather than reaching a reader.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
TEX = pathlib.Path(os.environ["R14_PAPER_TEX"]) if os.environ.get("R14_PAPER_TEX") else HERE.parents[1] / "backend" / "paper" / "bounded_relaxation.tex"

res = json.loads((HERE / "external_r14_results.json").read_text(encoding="utf-8"))
adj = json.loads((HERE / "adjudication.json").read_text(encoding="utf-8"))
hand = json.loads((HERE / "r3_handoff.json").read_text(encoding="utf-8"))
rate = json.loads((HERE / "audit_rate.json").read_text(encoding="utf-8"))
SURFACE = re.compile(adj["_surface_regex"], re.I)

tex = TEX.read_text(encoding="utf-8")
verdict_of = {(e["subject"], e["module"], e["line"]): e["verdict"]
              for e in adj["entries"]}
scanned = [s for s in res["subjects"] if s.get("candidates") is not None]
adjudicated = set(adj.get("_adjudicated_subjects") or
                  {e["subject"] for e in adj["entries"]})


def tally(subjects):
    t: Counter = Counter()
    for s in subjects:
        dom = Counter(c.get("domain", "R14") for c in s["candidates"])
        st = s.get("stratum", "A")
        surf = [c for c in s["candidates"]
                if c.get("domain") == "R14"
                and (st == "B" or SURFACE.search(c["module"]))]
        t["files"] += s["scan"]["parsed"]
        t["prop"] += len(s["candidates"])
        t["r14"] += dom.get("R14", 0)
        t["r3"] += dom.get("R3", 0)
        t["struct"] += dom.get("STRUCTURAL", 0)
        if s["key"] in adjudicated:
            t["surf"] += len(surf)
            for c in surf:
                v = verdict_of.get((s["key"], c["module"], c["line"]))
                if v == "UPHELD":
                    t["upheld"] += 1
                elif v == "PASS":
                    t["passes"] += 1
                elif v == "WITHDRAWN":
                    t["withdrawn"] += 1
    return t


ALL = tally(scanned)
ADJ = tally([s for s in scanned if s["key"] in adjudicated])


def latex_int(n: int) -> str:
    """LaTeX writes a thousands separator as {,} in this paper."""
    return f"{n:,}".replace(",", "{,}")


site_prec = 100.0 * (ADJ["upheld"] + ADJ["passes"]) / ADJ["surf"]
viol_prec = 100.0 * ADJ["upheld"] / ADJ["surf"]
viol_all = 100.0 * ADJ["upheld"] / ADJ["prop"]

CLAIMS = [
    # (label, string that must appear verbatim in the source)
    ("adjudicated corpus, files", f"${latex_int(ADJ['files'])}$"),
    ("adjudicated corpus, proposed", f"${ADJ['prop']}$"),
    ("full corpus, files", f"${latex_int(ALL['files'])}$"),
    ("upheld findings", {3: "three findings", 2: "two findings"}.get(
        ADJ["upheld"], f"{ADJ['upheld']} findings")),
    ("site precision", f"${site_prec:.1f}\\%$"),
    ("violation precision", f"${viol_prec:.1f}\\%$"),
    ("violation precision, all proposals", f"${viol_all:.1f}\\%$"),
    ("handoff: both", f"both rungs flag it & {hand['both']} &"),
    ("handoff: ours only", f"ours only & {hand['r14_only']} &"),
    ("handoff: outside interface",
     f"outside its interface & {hand['not_expressible']} &"),
    ("handoff: theirs only", f"theirs only & {hand['r3_only']} &"),
    ("audit rate, stratum A sites", f"& {rate['stratum_A']['sites']} &"),
    ("audit rate, stratum A rate",
     f"${rate['stratum_A']['rate_pct']:.1f}\\%$"),
    ("audit rate, stratum B sites", f"& {rate['stratum_B']['sites']} &"),
    ("audit rate, stratum B rate",
     f"${rate['stratum_B']['rate_pct']:.1f}\\%$"),
    ("audit rate, difference", f"${rate['difference_pp']:.1f}$"),
    ("audit rate, p value", f"p = {rate['fisher_p_two_sided']:.3f}"),
]

# ── the per-subject deferral table, which nothing was checking ──────────
# It went stale once already: it summed to 52 and omitted four subjects after
# the corpus widened. Parsed and summed here rather than eyeballed.
DEFER_NAME = {
    "OpenAI Agents": "openai-agents", "NeMo Guardrails": "nemo-guardrails",
    "mypy": "mypy", "garak": "garak", "ControlArena": "control-arena",
    "Checkov": "checkov", "Inspect AI": "inspect_ai", "Semgrep": "semgrep",
    "Giskard": "giskard", "Guardrails AI": "guardrails",
    "LlamaFirewall": "llama-firewall", "Petri": "petri", "TruLens": "trulens",
    "CrewAI": "crewai", "Pylint": "pylint",
}
deferred_truth = Counter()
for s_ in scanned:
    for c in s_["candidates"]:
        if c.get("domain") == "R3":
            deferred_truth[s_["key"]] += 1

defer_block = tex.split(r"\label{tab:deferred}")[1].split(r"\end{tabular}")[0]
defer_rows, defer_total = {}, None
for raw in defer_block.split(r"\\"):
    line = " ".join(raw.split())
    # \heavyrule and \hline are the boxed-table rules; strip them for the
    # same reason verify_paper_table.py does.
    for tok in ('\\midrule', '\\toprule', '\\bottomrule',
                '\\heavyrule', '\\hline'):
        line = line.replace(tok, " ")
    cells = [c.strip() for c in line.split("&")]
    for j in range(0, len(cells) - 1, 2):
        name = cells[j].replace('\\textbf{', '').replace('}', '').strip()
        val = "".join(ch for ch in cells[j + 1] if ch.isdigit())
        if not name or not val or name == "Subject":
            continue
        if name.lower() == "total":
            defer_total = int(val)
        elif name in DEFER_NAME:
            defer_rows[DEFER_NAME[name]] = int(val)

defer_bad = []
if defer_total != sum(deferred_truth.values()):
    defer_bad.append(f"deferral table total is {defer_total}, artifact says "
                     f"{sum(deferred_truth.values())}")
if sum(defer_rows.values()) != defer_total:
    defer_bad.append(f"deferral rows sum to {sum(defer_rows.values())}, "
                     f"table total says {defer_total}")
for key, n in deferred_truth.items():
    if defer_rows.get(key) != n:
        defer_bad.append(f"deferral row {key}: table {defer_rows.get(key)}, "
                         f"artifact {n}")

bad = list(defer_bad)
for label, needle in CLAIMS:
    if needle not in tex:
        bad.append(f"{label}: expected {needle!r} in the source, not found")

# a claim the paper must NOT make any more, because it was falsified
FORBIDDEN = [
    ("the withdrawn generalisation", "whether anyone asked"),
]
for label, needle in FORBIDDEN:
    if needle in tex:
        bad.append(f"{label}: {needle!r} is present and was withdrawn "
                   f"by the pre-registered test")

if bad:
    print("PAPER 14 DRIFTED FROM ITS ARTIFACTS:")
    for b in bad:
        print("  ", b)
    sys.exit(1)

print(f"paper 14 agrees with its artifacts on all {len(CLAIMS)} scalar claims")
print(f"  adjudicated corpus : {len(adjudicated & {s['key'] for s in scanned})}"
      f" subjects, {ADJ['files']} files, {ADJ['prop']} proposed, "
      f"{ADJ['surf']} on a safety path")
print(f"  full corpus        : {len(scanned)} subjects, {ALL['files']} files")
print(f"  outcomes           : {ADJ['upheld']} upheld, {ADJ['passes']} pass, "
      f"{ADJ['withdrawn']} withdrawn")
print(f"  precision          : site {site_prec:.1f}%, violation "
      f"{viol_prec:.1f}%")
print(f"  handoff            : {hand['both']} both, {hand['r14_only']} ours, "
      f"{hand['not_expressible']} outside, {hand['r3_only']} theirs")
print(f"  audit rate         : A {rate['stratum_A']['rate_pct']}%, "
      f"B {rate['stratum_B']['rate_pct']}%, p={rate['fisher_p_two_sided']:.4g}, "
      f"{rate['verdict']}")
