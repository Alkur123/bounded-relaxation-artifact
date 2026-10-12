"""The TypeScript front end must fire on known positives before it is believed.

The Python proposer was validated on two known positives that predate it: our
own shipped defect and its repair, at two real commits. The second front end has
no such history, so the cross-language pre-registration committed it to a weaker
but explicit substitute: hand translations of the three upheld findings from the
Python run, each with a repaired control it must NOT convict.

    contrib/external-r14/PREREGISTRATION_cross_language.md
    contrib/external-r14/fixtures/ts/{defect,repaired}/

These fixtures are SYNTHETIC and that is stated in the paper rather than
glossed. What they establish is narrow and worth having anyway: that the
TypeScript walker recognises the same three shapes, that the shipped lexicons
reach them once identifiers are tokenised into the convention those lexicons are
written in, and that the certifier's verdict flips when the defect is repaired.

The suite skips, rather than fails, where node or the TypeScript package is
absent: a missing toolchain is a fact about the machine, not about the rung.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CONTRIB = REPO / "contrib" / "external-r14"
if str(CONTRIB) not in sys.path:
    sys.path.insert(0, str(CONTRIB))

from engine import maryada as mz                                # noqa: E402

ts_frontend = pytest.importorskip("ts_frontend")
_ok, _why = ts_frontend.available()
pytestmark = pytest.mark.skipif(not _ok, reason=f"TS front end unavailable: {_why}")

DEFECT = CONTRIB / "fixtures" / "ts" / "defect"
REPAIRED = CONTRIB / "fixtures" / "ts" / "repaired"


def _certify(root: pathlib.Path):
    cands, _stats, _decls, _vocab = ts_frontend.discover(root, subject=root.name)
    sites = [c.to_site(source_root=str(root)) for c in cands]
    result = mz.certify(sites, subject=root.name)
    violations = {(f.rule, f.reason.split("::")[0].split(" ")[-1])
                  for f in result.findings
                  if f.severity == mz.VIOLATION and f.rule != "R14-d"}
    return cands, result, violations


def _rules_at(result, module: str, line: int) -> set:
    """Which predicates a specific site violates, addressed by module and line."""
    needle = f"{module}::"
    tail = f"@{line} "
    out = set()
    for f in result.findings:
        if f.severity != mz.VIOLATION or f.rule == "R14-d":
            continue
        if needle in f.reason and (tail in f.reason or f.reason.endswith(f"@{line}")):
            out.add(f.rule)
    return out


# ── the walker sees the shapes at all ────────────────────────────────────────

def test_all_three_translated_findings_are_proposed():
    cands, _r, _v = _certify(DEFECT)
    seen = {(c.module, c.shape) for c in cands}
    assert ("f1_omit_mode.ts", "benign-write") in seen
    assert ("f2_ignore_list.ts", "waiver-skip") in seen
    assert ("f3_short_input.ts", "benign-write") in seen


def test_the_walker_reads_typescript_at_all():
    """Non-vacuity: a scan that parsed nothing would satisfy every test above."""
    payload = ts_frontend.run_proposer(DEFECT, "fx")
    assert payload["stats"]["parsed"] == 3
    assert payload["stats"]["parse_errors"] == 0


# ── each finding convicts, and its repair does not ───────────────────────────

def test_f1_verdict_from_repair_is_unbounded_and_the_repair_is_not():
    """The omit-mode finding: verdict taken from whether the repair changed the
    text rather than from the strength of the detection."""
    _c, defect, _v = _certify(DEFECT)
    assert "R14-a" in _rules_at(defect, "f1_omit_mode.ts", 42)

    _c, repaired, _v = _certify(REPAIRED)
    assert _rules_at(repaired, "f1_omit_mode.ts", 40) == set()


def test_f2_ignore_list_waiver_is_unaudited_and_the_repair_is_not():
    """The waiver finding: the one branch that drops a detection without a trace.

    R14-a fires on both, and that is correct and matches the Python run: a
    principal waiver has no evidence strength to consult, so the bound
    obligation is not engaged, and it is the ADJUDICATION that records that as
    class B rather than the certifier suppressing it.
    """
    _c, defect, _v = _certify(DEFECT)
    assert "R14-b" in _rules_at(defect, "f2_ignore_list.ts", 18)

    _c, repaired, _v = _certify(REPAIRED)
    assert "R14-b" not in _rules_at(repaired, "f2_ignore_list.ts", 18)


def test_f3_short_input_exemption_is_bounded_but_unaudited():
    """The mild finding, and the one that shows the rung separating its two
    obligations: the length bound is sound, the trace is missing."""
    cands, defect, _v = _certify(DEFECT)
    rules = _rules_at(defect, "f3_short_input.ts", 18)
    assert "R14-b" in rules
    assert "R14-a" not in rules, "the length bound should satisfy R14-a"

    site = next(c for c in cands if c.module == "f3_short_input.ts")
    assert site.bounded and site.bound_symbol == "len"

    _c, repaired, _v = _certify(REPAIRED)
    assert _rules_at(repaired, "f3_short_input.ts", 17) == set()


# ── what the front end gets wrong, recorded rather than hidden ───────────────

def test_recorded_false_positive_the_no_match_early_return():
    """A known false positive of the TS front end, pinned so it stays visible.

    `if (matches.length === 0) return { isInjection: false }` is the negative
    path: no detection was ever produced, so there is no prior verdict for this
    to weaken, and a human adjudicator withdraws it at step 0. The scanner
    proposes it in BOTH the defect and the repair. It is pinned here because an
    instrument's errors belong in its test file, and because a future change
    that silently removes it should have to say so.
    """
    _c, defect, _v = _certify(DEFECT)
    _c2, repaired, _v2 = _certify(REPAIRED)
    assert _rules_at(defect, "f1_omit_mode.ts", 26) == {"R14-a", "R14-b"}
    assert _rules_at(repaired, "f1_omit_mode.ts", 23) == {"R14-a", "R14-b"}


# ── the tokeniser, which is an amendment and is measured both ways ───────────

def test_camel_case_tokenisation_is_what_reaches_the_lexicons():
    """Without it the shipped lexicons miss camelCase, and miss it CLEAN.

    `is_injection` reads as risk-carrying and `isInjection` reads as nothing,
    because the lexicons anchor on snake_case word boundaries. Turning the
    tokeniser off must lose the F1 finding entirely -- if it does not, the
    amendment is doing something other than what it claims.
    """
    from engine import maryada_discover as md

    assert md._polarity_of("is_injection") == "risk"
    assert md._polarity_of("isInjection") is None

    _c, with_norm, _v = _certify(DEFECT)
    assert "R14-a" in _rules_at(with_norm, "f1_omit_mode.ts", 42)

    ts_frontend.NORMALISE_IDENTIFIERS = False
    try:
        cands, without, _v = _certify(DEFECT)
        assert _rules_at(without, "f1_omit_mode.ts", 42) == set()
        assert not any(c.module == "f1_omit_mode.ts" for c in cands)
    finally:
        ts_frontend.NORMALISE_IDENTIFIERS = True

    # and back, so the flag is not left flipped for whatever runs next
    _c, again, _v = _certify(DEFECT)
    assert "R14-a" in _rules_at(again, "f1_omit_mode.ts", 42)
