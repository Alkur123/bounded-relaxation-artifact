"""Tests for Maryādā — the R14 bounded-relaxation invariant.

Same non-vacuity discipline as the siblings (test_vikalpa / test_anupalabdhi /
test_rtvij / test_saksin): the check must FAIL on synthetic unbounded sites so
it is not vacuous, PASS on licit ones so it is not a rubber stamp that fires on
everything, and report the REAL system's result exactly as measured.

The measured half is a SPLIT and both halves are pinned, because each is load
bearing in a different direction. `classifier_override_demotion` passes all four
predicates, which is the regression guard for the 2026-08-17 fix. And
`distress_idiom_exclusion` FAILS R14-c, deliberately: it declares the same
symbol as its general and hard-block bound because there is no separate stricter
floor there, and a strength ceiling cannot supply one when the detector is tuned
aggressive enough that a genuine idiom scores 0.85. That conviction is correct
and must not be silenced by widening the rule.
"""
from __future__ import annotations

import pytest

from engine import maryada as mz
from engine.maryada import (ADVISORY, OK, VIOLATION, MaryadaFinding,
                            MaryadaResult, RelaxationSite, certify)

REAL_MODULE = "engine/classifier_overrides.py"


def _site(**kw) -> RelaxationSite:
    """A fully licit site, overridden per test. Points at a real module so
    R14-d has something to read."""
    base = dict(
        name="s", module=REAL_MODULE, function="_demote_to_safe",
        relaxes="category", bound_by="override_ceiling_for",
        audit_field="override_audit", reaches_hard_block=True,
        hard_block_bound="_HARD_BLOCK_OVERRIDE_CEILING")
    base.update(kw)
    return RelaxationSite(**base)


def _rules(res, severity=VIOLATION):
    return sorted(f.rule for f in res.findings if f.severity == severity)


# ── data model ───────────────────────────────────────────────────────────────

def test_site_requires_a_source_module_path():
    with pytest.raises(ValueError, match="must be a source path"):
        _site(module="engine/classifier_overrides")


def test_site_accepts_a_typescript_module_path():
    """Widened 2026-08-18 for the second front end; still a guard, not a pass.

    No predicate reads the extension and ``_source_of`` never parses the module
    as Python, so accepting a TypeScript path changes what can be certified and
    nothing about how. The rejection case above is what stops it becoming a
    field that accepts anything.
    """
    site = _site(module="library/injection_detection/actions.ts")
    assert site.module.endswith(".ts")

    with pytest.raises(ValueError, match="must be a source path"):
        _site(module="README.md")


def test_site_requires_name_module_function():
    with pytest.raises(ValueError, match="needs name, module and function"):
        _site(name="")


def test_result_cannot_pass_while_carrying_a_violation():
    res = MaryadaResult(subject="x", findings=[
        MaryadaFinding("R14-a", OK, "fine"),
        MaryadaFinding("R14-a", VIOLATION, "not fine")])
    assert res.passed is False and len(res.violations) == 1


# ── synthetic FAILURES: the check is not vacuous ─────────────────────────────

def test_unbounded_relaxation_is_a_violation():
    res = certify([_site(bound_by=None)])
    assert "R14-a" in _rules(res)
    assert not res.passed


def test_unaudited_relaxation_is_a_violation():
    res = certify([_site(audit_field=None)])
    assert "R14-b" in _rules(res)


def test_hard_block_without_its_own_bound_is_a_violation():
    res = certify([_site(hard_block_bound=None)])
    assert "R14-c" in _rules(res)


def test_the_same_bound_under_two_names_is_not_a_floor():
    """The defect the real distress site has. One symbol cannot be both the
    general bound and a stricter floor."""
    res = certify([_site(hard_block_bound="override_ceiling_for")])
    v = [f for f in res.violations if f.rule == "R14-c"]
    assert len(v) == 1 and "nominal floor" in v[0].reason


def test_declared_bound_absent_from_the_module_is_a_violation():
    """R14-d, the family's declaration-versus-code discipline."""
    res = certify([_site(bound_by="a_symbol_that_does_not_exist_anywhere")])
    assert "R14-d" in _rules(res)


def test_declared_function_absent_from_the_module_is_a_violation():
    res = certify([_site(function="no_such_function_here")])
    assert "R14-d" in _rules(res)


def test_unreadable_module_fails_rather_than_passing_on_trust():
    res = certify([_site(module="engine/does_not_exist.py")])
    assert "R14-d" in _rules(res)
    assert any("unverifiable" in f.reason for f in res.violations)


def test_duplicate_site_names_are_rejected():
    res = certify([_site(name="dup"), _site(name="dup")])
    assert any("duplicate site name" in f.reason for f in res.violations)


# ── synthetic PASSES: not a rubber stamp ─────────────────────────────────────

def test_a_fully_bounded_site_passes():
    res = certify([_site()])
    assert res.passed
    assert _rules(res) == []


def test_a_site_that_cannot_reach_hard_block_does_not_need_a_floor():
    res = certify([_site(reaches_hard_block=False, hard_block_bound=None)])
    assert res.passed
    assert any(f.rule == "R14-c" and f.severity == OK for f in res.findings)


def test_no_declared_sites_is_an_advisory_not_a_pass_in_silence():
    res = certify([])
    assert res.passed                       # nothing convicted
    assert [f.severity for f in res.findings] == [ADVISORY]
    assert "not the same as having none" in res.findings[0].reason


# ── the real system, asserted exactly as measured (2026-08-17) ───────────────

def test_real_chakravyuha_relaxations_measured_result():
    res = mz.certify_chakravyuha_relaxations()
    assert res.subject == "chakravyuha"
    # Exactly one violation, and it is the distress site's nominal floor.
    assert len(res.violations) == 1, [f.as_dict() for f in res.violations]
    v = res.violations[0]
    assert v.rule == "R14-c"
    assert "distress_idiom_exclusion" in v.reason
    assert res.passed is False


def test_the_fixed_override_site_is_clean_on_all_four_predicates():
    """Regression guard for the 2026-08-17 bounded-relaxation fix. If this
    fails, a ceiling or an audit record has been removed from the live path."""
    res = mz.certify_chakravyuha_relaxations()
    mine = [f for f in res.findings if "classifier_override_demotion" in f.reason]
    assert mine, "the override site is no longer declared"
    assert all(f.severity == OK for f in mine), [f.as_dict() for f in mine]
    assert {f.rule for f in mine} == {"R14-a", "R14-b", "R14-c", "R14-d"}


def test_declared_sites_point_at_modules_that_exist():
    for site in mz.CHAKRAVYUHA_RELAXATIONS:
        assert (mz._REPO_BACKEND / site.module).is_file(), site.module
