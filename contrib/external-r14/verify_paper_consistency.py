"""Require every statement of a quantity in paper 14 to agree with the others.

WHY THIS EXISTS, AND IT IS NOT HYPOTHETICAL
-------------------------------------------
`verify_paper_numbers.py` computes each claim from the artifacts and requires the
computed string to APPEAR in the source. That is a presence check, and a presence
check cannot see a second, older statement of the same quantity sitting a few
hundred lines away. On 2026-08-18 the corpus was widened from twenty-two subjects
to twenty-eight, the tables were regenerated, and the abstract, the claim list,
the shapes table and two prose paragraphs were not. The paper then stated its
site precision as $24.1\\%$ in three places and as $8.1\\%$ in one, and BOTH
checkers reported green, because the one value each of them looked for was there.

So this file asks the other question. For each quantity it finds EVERY place the
source states it and requires them all to be the same number, and requires at
least one, so a claim that is silently deleted fails here too.

    python verify_paper_consistency.py            # exits non-zero on any drift
    python verify_paper_consistency.py --selftest # prove every rule can fail

The self-test is not decoration. A rule whose regex stops matching after an
edit would otherwise go quiet and keep reporting success, which is the exact
fail-open shape this rung's sibling exists to certify against. The self-test
mutates one statement of each quantity and requires the rule to catch it.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
TEX = pathlib.Path(os.environ["R14_PAPER_TEX"]) if os.environ.get("R14_PAPER_TEX") else HERE.parents[1] / "backend" / "paper" / "bounded_relaxation.tex"

WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "twenty-two": 22, "twenty-five": 25, "twenty-eight": 28, "twenty-nine": 29,
    "thirty-nine": 39,  # the cross-corpus subject count, 28 + 11
    "thirty-three": 33, "seventy-two": 72,
    "a hundred and three": 103, "a hundred and ten": 110,
    "a hundred and twenty-two": 122, "a hundred and twenty-five": 125, "hundred and twenty-five": 125,
    "a hundred and thirty-six": 136, "hundred and thirty-six": 136,
}


def as_num(tok: str) -> float | None:
    """Read a source token as a number: 470, 7{,}050, 8.1, or twenty-eight."""
    t = tok.strip().lower().replace("{,}", "").replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return float(t)
    return float(WORDS[t]) if t in WORDS else None


def truth(results: str = "external_r14_results.json",
          adjudication: str = "adjudication.json",
          only: set | None = None) -> dict[str, float]:
    """Every expected value is computed from the released artifacts."""
    res = json.loads((HERE / results).read_text(encoding="utf-8"))
    adj = json.loads((HERE / adjudication).read_text(encoding="utf-8"))
    surface = re.compile(adj["_surface_regex"], re.I)
    scanned = [s for s in res["subjects"] if s.get("candidates") is not None
               and (only is None or s["key"] in only)]
    verdict_of = {(e["subject"], e["module"], e["line"]): e["verdict"]
                  for e in adj["entries"]}
    t = {"subjects": len(scanned), "files": 0, "proposed": 0,
         "r14": 0, "r3": 0, "structural": 0, "surface": 0,
         "upheld": 0, "passes": 0, "withdrawn": 0}
    for s in scanned:
        stratum = s.get("stratum", "A")
        t["files"] += s["scan"]["parsed"]
        t["proposed"] += len(s["candidates"])
        for c in s["candidates"]:
            dom = c.get("domain", "R14")
            t["r14" if dom == "R14" else
              "r3" if dom == "R3" else "structural"] += 1
            if dom == "R14" and (stratum == "B" or surface.search(c["module"])):
                t["surface"] += 1
                v = verdict_of.get((s["key"], c["module"], c["line"]))
                if v == "UPHELD":
                    t["upheld"] += 1
                elif v == "PASS":
                    t["passes"] += 1
                elif v == "WITHDRAWN":
                    t["withdrawn"] += 1
    t["site_prec"] = round(100.0 * (t["upheld"] + t["passes"]) / t["surface"], 1)
    t["viol_prec"] = round(100.0 * t["upheld"] / t["surface"], 1)
    t["viol_all"] = round(100.0 * t["upheld"] / t["proposed"], 1)
    return t


# ── (label, key into truth(), patterns whose group 1 states the quantity) ──
# Every pattern here matched a place the paper went stale on 2026-08-18, or a
# place a future edit would have to keep in step with one that did.
RULES: list[tuple[str, str, list[str]]] = [
    ("subject count", "subjects", [
        r"against ([a-z0-9-]+) open-source systems",
        r"([a-z0-9-]+)(?: Python| TypeScript)? systems we did not (?:write|design)",
        r"contact with those ([a-z0-9-]+)",
        r"the ([a-z0-9-]+) subject corpus",
        r"([A-Za-z0-9-]+) subjects scanned of",
        r"([A-Za-z0-9-]+) subjects, \$",
    ]),
    ("files scanned", "files", [
        r"over \$([\d{},]+)\$ files",
        r"selected, \$([\d{},]+)\$ files",
        r"subjects, \$([\d{},]+)\$ files",
    ]),
    ("proposed sites", "proposed", [
        r"Of \$(\d+)\$[ \t]*\r?\n?[ \t]*proposed sites",
        r"\$(\d+)\$\s*\r?\n?proposed sites \(Table",
        r"over all (\d+) proposals",
        r"\$(\d+)\$ proposed sites, of which",
        r"\$(\d+)\$ proposed sites over",
        r"\\textbf\{total\} & \\textbf\{(\d+)\} & \\textbf\{\d+\} &",
    ]),
    ("sites in this rung's domain", "r14", [
        r"\$(\d+)\$ are relaxations of an",
        r"of which \$(\d+)\$ are in[ \t]*\r?\n?[ \t]*this rung's domain",
        r"\\textbf\{total\} & \\textbf\{\d+\} & \\textbf\{(\d+)\} &",
    ]),
    ("sites deferred to the liveness rung", "r3", [
        r"\$(\d+)\$ belong to (?:a|the) sibling",
        r"^([A-Za-z0-9-]+) sites were classified as belonging",
    ]),
    ("structural sites", "structural", [
        r"and \$(\d+)\$ are structural",
    ]),
    ("decision-surface sites", "surface", [
        r"survived on \$(\d+)\$",
        r"Of \$(\d+)\$ \\textsc\{r14\}-domain candidates",
        r"All \$(\d+)\$ are recorded with a class",
        r"((?:A|a) hundred and [a-z-]+|[A-Z][a-z-]+|\d+) sit on a decision surface",
        r"how the ([a-z0-9 -]+?) resolved",
        r"precision is \$\d+/(\d+) = ",
        r"\$(\d+)\$ sit on a decision surface",
        r"and \$(\d+)\$ on a decision surface",
    ]),
    ("upheld findings", "upheld", [
        r"\\textbf\{([A-Za-z0-9]+) upheld,",
        r"\\textbf\{([a-z0-9]+)\s*\r?\n?\s*upheld findings",
    ]),
    ("passes", "passes", [
        r"\b((?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)) passes(?! then in hand)",
        r"Those ([a-z0-9]+) sites are real",
        r"upheld, ([a-z0-9]+) pass,",
    ]),
    ("withdrawn", "withdrawn", [
        r"pass(?:es)?, a\s*\r?\n?\s*([a-z0-9 -]+?) withdrawn\}",
    ]),
    ("site precision", "site_prec", [
        r"[Ss]ite precision(?: is| of)? \$([\d.]+)\\%\$",
        r"identification and precision is \$\d+/\d+ = ([\d.]+)\\%\$",
    ]),
    ("violation precision", "viol_prec", [
        r"violation\s*\r?\n?\s*precision(?: of)? \$([\d.]+)\\%\$",
        r"\\emph\{violation precision\} \$([\d.]+)\\%\$",
        r"rule\}, precision is \$\d+/\d+ = ([\d.]+)\\%\$",
    ]),
    ("violation precision over all proposals", "viol_all", [
        r"or \$([\d.]+)\\%\$ over all",
    ]),
]


def check(text: str, want_all: dict | None = None, *,
          require_stated: bool = True, where: str = "") -> tuple[list[str], dict[str, int]]:
    """Every place `text` states a quantity must state the same number.

    `require_stated` is on for the main corpus, where a rule that matches
    nothing means the paper stopped making a claim it used to make. It is
    off for the second-language section, which states only some of these.
    """
    problems: list[str] = []
    fired: dict[str, int] = {}
    truths = want_all if want_all is not None else TRUTH
    for label, key, pats in RULES:
        want = truths[key]
        seen = []
        for pat in pats:
            for m in re.finditer(pat, text, re.M):
                seen.append((m.group(1), m.start(1)))
        if not seen:
            if require_stated:
                problems.append(f"{label}: the source states this nowhere the "
                                f"rule can see, so the rule is vacuous")
            continue
        fired[label] = len(seen)
        for tok, pos in seen:
            # A claim the prose marks as spanning both corpora is checked
            # against the sum rather than against whichever corpus owns the
            # surrounding section.
            window = text[max(0, pos - 220):pos + 220]
            want_here = (TRUTH_BOTH[key] if COMBINED_MARKER in window else want)
            got = as_num(tok)
            line = text.count("\n", 0, pos) + 1
            if got is None:
                problems.append(f"{label}{where}: line {line} says {tok!r}, which this "
                                f"rule cannot read as a number")
            elif abs(got - want_here) > 1e-9:
                problems.append(f"{label}{where}: line {line} says {tok!r}, artifacts "
                                f"say {want_here:g}")
    return problems, fired


def selftest(text: str) -> int:
    """Every rule must be able to fail. Mutate one statement and require a catch."""
    bad = []
    for label, key, pats in RULES:
        span = None
        for pat in pats:
            m = re.search(pat, text, re.M)
            if m:
                span = m.span(1)
                break
        if span is None:
            bad.append(f"{label}: no statement to mutate")
            continue
        mutated = text[:span[0]] + "9999" + text[span[1]:]
        problems, _ = check(mutated)
        if not any(p.startswith(label + ":") for p in problems):
            bad.append(f"{label}: mutating its first statement to 9999 did not "
                       f"trip the rule")
    if bad:
        print("SELF-TEST FAILED, these rules cannot fail and so prove nothing:")
        for b in bad:
            print("  ", b)
        return 1
    print(f"self-test: all {len(RULES)} rules trip when their statement is "
          f"mutated")
    return 0


TRUTH = truth()
TRUTH_TS = truth("external_r14_ts_results.json", "adjudication_ts.json")
#: The second-language section reports the first registration's eight
#: subjects separately from the pooled eleven, because its own extension
#: registration required the first run's numbers to stand as reported. So
#: that subsection is checked against the eight, not against the pooled set.
TRUTH_TS_FIRST = truth("external_r14_ts_results.json",
                       "adjudication_ts.json",
                       only={"openai-agents-js", "langchainjs", "mastra",
                             "llamaindex-ts", "eslint", "typescript-eslint",
                             "stylelint", "retire.js"})
FIRST_RUN_SUBSECTION = r"\subsection{The first registration, and the defect in it}"

#: Some claims are deliberately about BOTH corpora at once. They are checked
#: against the sum, and the prose has to say "both corpora" within the same
#: sentence to be read that way -- a marker a reader needs regardless.
TRUTH_BOTH = {k: (TRUTH[k] + TRUTH_TS[k]) for k in
              ("subjects", "files", "proposed", "r14", "r3", "structural",
               "surface", "upheld", "passes", "withdrawn")}
TRUTH_BOTH["site_prec"] = round(
    100.0 * (TRUTH_BOTH["upheld"] + TRUTH_BOTH["passes"]) / TRUTH_BOTH["surface"], 1)
TRUTH_BOTH["viol_prec"] = round(
    100.0 * TRUTH_BOTH["upheld"] / TRUTH_BOTH["surface"], 1)
TRUTH_BOTH["viol_all"] = round(
    100.0 * TRUTH_BOTH["upheld"] / TRUTH_BOTH["proposed"], 1)
COMBINED_MARKER = "both corpora"

#: The paper describes two corpora. Everything from this heading to the end of
#: its section states the SECOND one's numbers, and checking those against the
#: first corpus's artifacts would report a disagreement that is not one.
CROSSLANG = r"\section{A second language}"


def split_corpora(text: str) -> tuple[str, str]:
    """(everything about the Python corpus, the second-language section)."""
    if CROSSLANG not in text:
        return text, ""
    head, tail = text.split(CROSSLANG, 1)
    nxt = tail.find("\n" + "\\section{")
    section, rest = (tail[:nxt], tail[nxt:]) if nxt != -1 else (tail, "")
    return head + rest, section


if __name__ == "__main__":
    tex = TEX.read_text(encoding="utf-8")
    if "--selftest" in sys.argv:
        sys.exit(selftest(split_corpora(tex)[0]))
    main_text, ts_text = split_corpora(tex)
    first_text = ""
    if FIRST_RUN_SUBSECTION in ts_text:
        head, tail = ts_text.split(FIRST_RUN_SUBSECTION, 1)
        nxt = tail.find("\n" + "\\subsection{")
        first_text, rest = (tail[:nxt], tail[nxt:]) if nxt != -1 else (tail, "")
        ts_text = head + rest
    problems, fired = check(main_text)
    ts_problems, ts_fired = check(ts_text, TRUTH_TS, require_stated=False,
                                  where=" [second language]")
    first_problems, first_fired = check(first_text, TRUTH_TS_FIRST,
                                        require_stated=False,
                                        where=" [first registration]")
    problems += ts_problems + first_problems
    if problems:
        print("PAPER 14 DISAGREES WITH ITSELF OR WITH ITS ARTIFACTS:")
        for p in problems:
            print("  ", p)
        sys.exit(1)
    total = sum(fired.values())
    print(f"paper 14 states {len(RULES)} quantities in {total} places and every "
          f"place agrees")
    for label, _key, _pats in RULES:
        print(f"  {label:42s} {fired[label]:2d} statement(s)")
    if ts_text:
        print(f"second-language section: {sum(ts_fired.values())} statement(s) "
              f"in {len(ts_fired)} quantities, all agreeing with the pooled "
              f"TypeScript artifacts")
    if first_text:
        print(f"  its first-registration subsection: "
              f"{sum(first_fired.values())} statement(s) checked against the "
              f"eight subjects that run covered")
