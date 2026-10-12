"""Tests for Maryādā discovery — proposing R14 sites in code that declared none.

Same non-vacuity discipline as the siblings: the scanner must FIND a relaxation
that is really there, must NOT fire on an initialiser or on a write that moves a
verdict the strict way, and must report bounded/audited in both directions.

The load-bearing pair is the HISTORICAL one at the bottom. Our own defect and
our own repair are both in the git history, both predate this scanner, and
neither was written to be found by it. The scanner must convict the version that
shipped broken and clear the version that shipped fixed. Anything that only
passes one of those halves is a scanner that says what we want.

The first version of this scanner found NEITHER of our two real sites. The
fixtures below pin each of the four defects that caused it, by name, so a
regression is a named failure rather than a silently smaller number.
"""
from __future__ import annotations

import pathlib
import textwrap

import pytest

from engine import maryada as mz
from engine.maryada_discover import (Candidate, declares_hard_block, discover,
                                     iter_python_files)

ENGINE = pathlib.Path(__file__).resolve().parent.parent / "engine"


def _scan(tmp_path: pathlib.Path, source: str, name: str = "m.py"):
    (tmp_path / name).write_text(textwrap.dedent(source), encoding="utf-8")
    cands, _stats = discover(tmp_path, subject="fixture")
    return cands


def _one(cands, target: str) -> Candidate:
    hits = [c for c in cands if c.target == target]
    assert len(hits) == 1, f"expected exactly one {target!r}, got {hits}"
    return hits[0]


# ── the write must actually be a relaxation ─────────────────────────────────

def test_an_unguarded_initialiser_is_not_a_relaxation(tmp_path):
    """`score = 0.0` at the top of a function initialises; it does not weaken."""
    cands = _scan(tmp_path, """
        def check(text):
            score = 0.0
            for rule in RULES:
                if rule in text:
                    score = 1.0
            return score
    """)
    assert cands == []


def test_a_write_that_strengthens_a_verdict_is_not_a_relaxation(tmp_path):
    """Direction is the entire point: 1.0 is not the permissive extreme."""
    cands = _scan(tmp_path, """
        def check(text, score):
            if "bomb" in text:
                score = 1.0
                is_malicious = True
            return score
    """)
    assert cands == []


def test_a_guarded_benign_write_is_found(tmp_path):
    cands = _scan(tmp_path, """
        def check(text, score):
            if "weather" in text:
                score = 0.0
            return score
    """)
    c = _one(cands, "score")
    assert c.written == "0.0" and c.polarity == "risk"
    assert c.guards == ['"weather" in text']


def test_permit_polarity_fires_on_true_not_false(tmp_path):
    """`allowed` arrives as a parameter, so there is a verdict to weaken."""
    cands = _scan(tmp_path, """
        def check(text, allowed):
            if text in ALLOWLIST:
                allowed = True
            else:
                allowed = False
            return allowed
    """)
    c = _one(cands, "allowed")
    assert c.polarity == "permit" and c.written == "True"


# ── the four defects the first version had, pinned by name ──────────────────

def test_defect1_an_early_return_guard_is_seen(tmp_path):
    """`if cond: return` guards everything after it in the same block.

    Missing this made the scanner blind to our own `_demote_to_safe`.
    """
    cands = _scan(tmp_path, """
        def demote(sem):
            if sem["confidence"] > 0.9:
                return
            sem["category"] = "SAFE"
    """)
    c = _one(cands, "category")
    assert c.guards == ['not (sem["confidence"] > 0.9)']
    assert c.bounded is True, "the early-return guard compares a magnitude"


def test_defect2_a_dict_literal_replacement_is_expanded(tmp_path):
    """Our distress site rebinds the whole record; the name carries no polarity."""
    cands = _scan(tmp_path, """
        def apply(dist, phrase, q):
            if phrase in q:
                dist = {"is_passive_self_harm": False, "strength": 0.0}
            return dist
    """)
    assert {c.target for c in cands} == {"is_passive_self_harm", "strength"}
    assert all(c.kind == "dict-key" for c in cands)


def test_defect3_a_bound_reached_through_a_local_helper_is_resolved(tmp_path):
    """Otherwise the scanner falsely accuses correctly bounded code."""
    cands = _scan(tmp_path, """
        def _may_demote(sem):
            return sem.get("confidence", 0.0) < CEILING

        def demote(sem):
            if not _may_demote(sem):
                return
            sem["category"] = "SAFE"
    """)
    c = _one(cands, "category")
    assert c.bounded is True
    assert c.bound_via == "_may_demote", "resolved one frame down, not inline"


def test_defect4_a_guarded_call_to_an_always_weakening_helper_is_a_site(tmp_path):
    """The weakening and the trigger routinely live in different frames."""
    cands = _scan(tmp_path, """
        def _demote(sem):
            sem["category"] = "SAFE"

        def apply(sem, q):
            for rule in RULES:
                if rule in q:
                    _demote(sem)
    """)
    c = _one(cands, "_demote")
    assert c.kind == "call" and c.bounded is False
    assert "category" in c.written


def test_defect4_does_not_fire_when_the_helper_is_itself_guarded(tmp_path):
    """The repaired shape. Reporting the call sites too would double-count, and
    convicting them would re-open a defect that had already been closed."""
    cands = _scan(tmp_path, """
        def _demote(sem):
            if sem["confidence"] >= CEILING:
                return
            sem["category"] = "SAFE"

        def apply(sem, q):
            for rule in RULES:
                if rule in q:
                    _demote(sem)
    """)
    assert [c.target for c in cands] == ["category"]
    assert cands[0].bounded is True


# ── R14-a and R14-b, both directions ────────────────────────────────────────

def test_a_trigger_with_no_magnitude_reads_as_unbounded(tmp_path):
    cands = _scan(tmp_path, """
        def check(text, verdict):
            if "my phone battery is dying" in text:
                verdict = "SAFE"
            return verdict
    """)
    assert _one(cands, "verdict").bounded is False


def test_a_logging_call_in_the_block_satisfies_the_trace_obligation(tmp_path):
    cands = _scan(tmp_path, """
        def check(text, score):
            if "weather" in text:
                logger.info("suppressed %s", text)
                score = 0.0
            return score
    """)
    c = _one(cands, "score")
    assert c.audited is True and c.audit_symbol == "logger.info"


def test_a_silent_relaxation_leaves_no_trace(tmp_path):
    cands = _scan(tmp_path, """
        def check(text, score):
            if "weather" in text:
                score = 0.0
            return score
    """)
    assert _one(cands, "score").audited is False


def test_a_benign_write_in_an_exception_handler_is_marked_fail_open(tmp_path):
    """The detector returns its safe value when it could not decide."""
    cands = _scan(tmp_path, """
        def detect(text):
            try:
                return model.score(text)
            except Exception:
                return 0.0
    """)
    c = _one(cands, "detect")
    assert c.from_handler is True and c.bounded is False
    assert c.kind == "return"


def test_a_fresh_local_below_a_bail_out_is_still_an_initialiser(tmp_path):
    """The dominant false positive when this was first pointed at foreign code.

    A guard clause at the top of a function puts a condition on the stack, and
    every ordinary initialiser below it then looks like a guarded weakening
    write. It is not one: there is no prior verdict for it to weaken. This
    exact shape accounted for eight of ten candidates in one subject, all of
    them plainly correct code.
    """
    cands = _scan(tmp_path, """
        def scan(self, prompt):
            if prompt.strip() == "":
                return prompt, True, -1.0
            highest_score = 0.0
            for result in self._pipeline(prompt):
                if result["score"] > highest_score:
                    highest_score = result["score"]
            return highest_score
    """)
    assert cands == [], [c.as_dict() for c in cands]


def test_but_a_bound_name_written_benign_under_a_guard_still_counts(tmp_path):
    """The other half, so the rule above is a distinction and not an off switch."""
    cands = _scan(tmp_path, """
        def scan(self, prompt):
            score = self._pipeline(prompt)
            if "weather" in prompt:
                score = 0.0
            return score
    """)
    assert _one(cands, "score").written == "0.0"


# ── R14-c is engaged, not assumed ───────────────────────────────────────────

def test_no_hard_block_declaration_means_not_engaged_not_satisfied(tmp_path):
    (tmp_path / "m.py").write_text("X = 1\n", encoding="utf-8")
    assert declares_hard_block(tmp_path) == []


def test_a_hard_block_declaration_is_found(tmp_path):
    (tmp_path / "m.py").write_text(
        "NEVER_ALLOW = {'csam'}\n# hard_block mentioned in a comment only\n",
        encoding="utf-8")
    hits = declares_hard_block(tmp_path)
    assert [h[2] for h in hits] == ["NEVER_ALLOW"], "comments must not count"


# ── handing discovered sites to the unmodified certifier ────────────────────

def test_a_discovered_site_certifies_through_the_real_r14(tmp_path):
    cands = _scan(tmp_path, """
        def check(text, score):
            if "weather" in text:
                score = 0.0
            return score
    """)
    site = cands[0].to_site(source_root=str(tmp_path))
    res = mz.certify([site], subject="fixture")
    assert res.passed is False
    assert "R14-a" in {f.rule for f in res.violations}
    assert "R14-b" in {f.rule for f in res.violations}


def test_source_root_is_what_lets_r14_read_a_foreign_tree(tmp_path):
    """R14-d must fail closed when it cannot read, not pass on trust."""
    site = mz.RelaxationSite(
        name="s", module="nope.py", function="f", relaxes="verdict",
        bound_by="cap", source_root=str(tmp_path))
    res = mz.certify([site], subject="fixture")
    assert any(f.rule == "R14-d" and f.severity == mz.VIOLATION
               for f in res.findings)


def test_omitting_source_root_resolves_against_this_repo_exactly_as_before(tmp_path):
    """The field is appended last and no predicate reads it, so a site declared
    without it must behave identically. This is the regression guard on the one
    change made to maryada.py."""
    site = mz.RelaxationSite(
        name="s", module="engine/classifier_overrides.py",
        function="_demote_to_safe", relaxes="category",
        bound_by="override_ceiling_for", audit_field="override_audit")
    assert site.source_root is None
    res = mz.certify([site], subject="own")
    assert res.passed is True


# ── tests are excluded, because a test of a relaxation looks like one ───────

def test_test_files_are_not_scanned(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        'def t():\n    if "a" in b:\n        score = 0.0\n', encoding="utf-8")
    cands, _ = discover(tmp_path, subject="fixture")
    assert cands == []
    assert list(iter_python_files(tmp_path)) == []


# ═══════════════════════════════════════════════════════════════════════════
# The historical pair. Both halves are real code that shipped.
# ═══════════════════════════════════════════════════════════════════════════

def test_the_repaired_override_module_is_clean_on_both_predicates():
    """Every site the scanner finds in our live module is bounded AND audited.

    This is the regression guard for the 2026-08-17 fix, stated in the
    scanner's own terms rather than the declaration's.
    """
    cands, _stats = discover(ENGINE, subject="chakravyuha")
    own = [c for c in cands if c.module == "classifier_overrides.py"]
    assert len(own) == 3, f"expected the three known sites, got {own}"
    assert all(c.bounded for c in own), [c.as_dict() for c in own if not c.bounded]
    assert all(c.audited for c in own), [c.as_dict() for c in own if not c.audited]


def test_the_defect_as_it_shipped_is_convicted_on_both_predicates(tmp_path):
    """A faithful reduction of engine/classifier_overrides.py at commit a089ccc.

    Reduced rather than pulled from git so the test does not depend on a repo
    checkout, and kept structurally identical: an always-weakening helper called
    from phrase-guarded sites, plus a signal zeroed inside a phrase loop. Every
    site must come back unbounded and unaudited, which is what the finding of
    2026-08-17 says it was.
    """
    cands = _scan(tmp_path, """
        def _demote_to_safe(sem, reason):
            prior_conf = sem.get("confidence", 0.5)
            sem["category"] = "SAFE"
            sem["confidence"] = max(0.65, 1.0 - prior_conf)
            sem.setdefault("override_reason", reason)

        def apply_overrides(sem, dist, original_query):
            q_lc = (original_query or "").lower()
            for rule in DATA.get("unconditional", {}).get("rules", []):
                if rule["phrase"] in q_lc and sem.get("category") == rule["wrong"]:
                    _demote_to_safe(sem, reason="override")
                    break
            if dist and dist.get("is_passive_self_harm"):
                for phrase in DATA.get("distress", {}).get("phrases", []):
                    if phrase in q_lc:
                        dist = {"is_passive_self_harm": False, "strength": 0.0}
                        break
            return sem, dist
    """)
    assert len(cands) == 3, [c.as_dict() for c in cands]
    assert not any(c.bounded for c in cands), "the defect had no confidence term"
    assert not any(c.audited for c in cands), "and it wrote no audit record"

    res = mz.certify([c.to_site(source_root=str(tmp_path)) for c in cands],
                     subject="a089ccc")
    assert res.passed is False
    rules = {f.rule for f in res.violations}
    assert rules == {"R14-a", "R14-b"}


# ── the scan root itself, which is where two fail-open bugs lived ──────────

def test_a_relative_scan_root_works(tmp_path, monkeypatch):
    """Passing a relative path is the ordinary way to call this, and for a
    while it raised ValueError instead of scanning."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text(
        'def f(t, score):\n    if "x" in t:\n        score = 0.0\n',
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cands, stats = discover(pathlib.Path("pkg"), subject="fixture")
    assert stats["parsed"] == 1
    assert [c.target for c in cands] == ["score"]


def test_a_root_under_a_test_named_directory_is_still_scanned(tmp_path):
    """The exclusions apply to the path RELATIVE to the root. Applying them to
    the absolute path skipped whole subjects and returned zero findings, which
    is indistinguishable from a clean result."""
    root = tmp_path / "test_harness" / "build" / "venv_things"
    root.mkdir(parents=True)
    (root / "m.py").write_text(
        'def f(t, score):\n    if "x" in t:\n        score = 0.0\n',
        encoding="utf-8")
    cands, stats = discover(root, subject="fixture")
    assert stats["parsed"] == 1, "the root itself must never be excluded"
    assert [c.target for c in cands] == ["score"]


# ═══════════════════════════════════════════════════════════════════════════
# Which rung owns a site. R14 is measured on its own domain only, so a
# misclassification here silently moves yield between two papers.
# ═══════════════════════════════════════════════════════════════════════════

from engine.maryada_discover import (DOMAIN_R3, DOMAIN_R14,  # noqa: E402
                                     DOMAIN_STRUCTURAL)


def test_an_exception_handler_belongs_to_r3_not_r14(tmp_path):
    """No verdict was produced, so there was nothing for R14 to consult."""
    cands = _scan(tmp_path, """
        def detect(text):
            try:
                return model.score(text)
            except Exception:
                return 0.0
    """)
    assert _one(cands, "detect").domain == DOMAIN_R3


def test_a_none_check_on_a_call_result_belongs_to_r3(tmp_path):
    cands = _scan(tmp_path, """
        def check(prompt, verdict):
            jailbreak = call_endpoint(prompt)
            if jailbreak is None:
                verdict = False
            return verdict
    """)
    assert _one(cands, "verdict").domain == DOMAIN_R3


def test_an_error_status_test_belongs_to_r3(tmp_path):
    cands = _scan(tmp_path, """
        def check(prompt, score):
            response = http_post(prompt)
            if response.status_code != 200:
                score = 0.0
            return score
    """)
    assert _one(cands, "score").domain == DOMAIN_R3


def test_an_in_band_error_sentinel_belongs_to_r3(tmp_path):
    """LlamaFirewall's shape: the error response is a value, not an exception."""
    cands = _scan(tmp_path, """
        def to_score(response, score):
            if response.types == ["ERROR"]:
                score = 0.0
            return score
    """)
    assert _one(cands, "score").domain == DOMAIN_R3


def test_an_emptiness_test_on_a_parameter_is_structural(tmp_path):
    """`if not schema: return True` is a precondition, not a relaxation."""
    cands = _scan(tmp_path, """
        def accepts_nothing(schema, allowed):
            if not schema:
                allowed = True
            return allowed
    """)
    assert _one(cands, "allowed").domain == DOMAIN_STRUCTURAL


def test_a_phrase_match_belongs_to_r14(tmp_path):
    """The shape the rung exists for: a verdict existed and a heuristic sank it."""
    cands = _scan(tmp_path, """
        def apply(sem, q):
            if "my phone battery is dying" in q:
                sem["category"] = "SAFE"
    """)
    assert _one(cands, "category").domain == DOMAIN_R14


def test_the_historical_defect_is_in_the_r14_domain(tmp_path):
    """If our own defect were classified R3 the rung would have no subject."""
    cands = _scan(tmp_path, """
        def _demote_to_safe(sem, reason):
            sem["category"] = "SAFE"

        def apply_overrides(sem, q):
            for rule in RULES:
                if rule["phrase"] in q:
                    _demote_to_safe(sem, reason="override")
    """)
    assert [c.domain for c in cands] == [DOMAIN_R14]


# ═══════════════════════════════════════════════════════════════════════════
# The three shapes a benign-constant detector cannot see
# ═══════════════════════════════════════════════════════════════════════════

def test_narrowing_a_findings_list_is_a_relaxation(tmp_path):
    """The verdict IS the list; dropping an element weakens it."""
    cands = _scan(tmp_path, """
        def post_process(findings, policy):
            findings = analyse(policy)
            if policy.lenient:
                findings = [f for f in findings if f.severity > 3]
            return findings
    """)
    c = _one(cands, "findings")
    assert c.shape == "narrowing" and c.domain == DOMAIN_R14


def test_removing_a_detection_in_place_is_a_relaxation(tmp_path):
    cands = _scan(tmp_path, """
        def prune(detections, entity):
            if entity in IGNORED:
                detections.remove(entity)
    """)
    c = _one(cands, "detections")
    assert c.shape == "narrowing"


def test_an_unguarded_comprehension_is_not_a_relaxation(tmp_path):
    """Building a list is not narrowing one."""
    cands = _scan(tmp_path, """
        def build(raw):
            findings = [f for f in raw if f.hit]
            return findings
    """)
    assert cands == []


def test_a_multiplicative_discount_is_a_relaxation(tmp_path):
    """Named as a blind spot in the first version, closed here."""
    cands = _scan(tmp_path, """
        def adjust(score, ctx):
            if ctx.trusted_source:
                score *= 0.5
            return score
    """)
    c = _one(cands, "score")
    assert c.shape == "discount" and c.domain == DOMAIN_R14


def test_scaling_a_score_up_is_not_a_relaxation(tmp_path):
    cands = _scan(tmp_path, """
        def adjust(score, ctx):
            if ctx.suspicious:
                score *= 2.0
            return score
    """)
    assert cands == []


def test_a_downward_clamp_is_a_bounded_relaxation(tmp_path):
    cands = _scan(tmp_path, """
        def adjust(score, ctx):
            if ctx.capped:
                score = min(score, CEILING)
            return score
    """)
    c = _one(cands, "score")
    assert c.shape == "discount"


def test_a_waiver_that_skips_the_check_is_a_relaxation(tmp_path):
    """Not a weakened verdict. No verdict, for a listed subject."""
    cands = _scan(tmp_path, """
        def scan(urls, allowlist):
            for url in urls:
                if url in allowlist:
                    continue
                inspect(url)
    """)
    c = _one(cands, "allowlist")
    assert c.shape == "waiver-skip" and c.polarity == "permit"


def test_a_membership_test_against_a_non_waiver_list_does_not_fire(tmp_path):
    cands = _scan(tmp_path, """
        def scan(urls, seen):
            for url in urls:
                if url in seen:
                    continue
                inspect(url)
    """)
    assert cands == []


# ═══════════════════════════════════════════════════════════════════════════
# R14-c, the category floor. The review named four things a run against foreign
# code should look for and this is the fourth; it was hardcoded NOT ENGAGED for
# every external site until 2026-08-18, so these pin that it is really running.
# ═══════════════════════════════════════════════════════════════════════════

from engine.maryada_discover import hard_block_vocabulary  # noqa: E402


def test_a_declared_unreleasable_set_becomes_vocabulary(tmp_path):
    (tmp_path / "policy.py").write_text(
        'NEVER_ALLOW = frozenset({"csam", "self_harm"})\n', encoding="utf-8")
    assert hard_block_vocabulary(tmp_path) == {"NEVER_ALLOW", "csam", "self_harm"}


def test_prose_and_patterns_do_not_become_categories(tmp_path):
    """Without this the module's own regex source entered the vocabulary."""
    (tmp_path / "policy.py").write_text(
        'HARD_BLOCK_MESSAGE = "This category is blocked and cannot be '
        'released by any operator, ever."\n'
        'PROHIBITED = ["weapons"]\n', encoding="utf-8")
    assert hard_block_vocabulary(tmp_path) == {
        "HARD_BLOCK_MESSAGE", "PROHIBITED", "weapons"}


def test_no_declared_floor_means_r14c_never_engages(tmp_path):
    cands = _scan(tmp_path, """
        def apply(sem, q):
            if "battery is dying" in q:
                sem["category"] = "SAFE"
    """)
    assert _one(cands, "category").reaches_hard_block is False


def test_a_relaxation_blind_to_the_floor_reaches_it(tmp_path):
    """The shipped-defect shape: the guards never mention the protected set."""
    (tmp_path / "policy.py").write_text(
        'HARD_BLOCK_CATEGORIES = frozenset({"SELF_HARM", "SEXUAL"})\n',
        encoding="utf-8")
    cands = _scan(tmp_path, """
        def apply(sem, q):
            if "battery is dying" in q:
                sem["category"] = "SAFE"
    """, name="overrides.py")
    c = _one(cands, "category")
    assert c.reaches_hard_block is True and c.hard_block_ref is None
    res = mz.certify([c.to_site(source_root=str(tmp_path))], subject="t")
    assert "R14-c" in {f.rule for f in res.violations}


def test_a_guard_that_consults_the_floor_does_not_reach_it(tmp_path):
    (tmp_path / "policy.py").write_text(
        'HARD_BLOCK_CATEGORIES = frozenset({"SELF_HARM", "SEXUAL"})\n',
        encoding="utf-8")
    cands = _scan(tmp_path, """
        def apply(sem, q):
            if "battery is dying" in q and sem["category"] not in HARD_BLOCK_CATEGORIES:
                sem["category"] = "SAFE"
    """, name="overrides.py")
    c = _one(cands, "category")
    assert c.reaches_hard_block is False
    assert c.hard_block_ref == "HARD_BLOCK_CATEGORIES"


def test_the_floor_check_resolves_one_frame_down(tmp_path):
    """Ours consults the protected set inside a helper, not inline. Testing the
    guard text alone would convict the repaired code."""
    (tmp_path / "policy.py").write_text(
        'HARD_BLOCK_CATEGORIES = frozenset({"SELF_HARM", "SEXUAL"})\n',
        encoding="utf-8")
    cands = _scan(tmp_path, """
        def _ceiling_for(cat):
            if cat in HARD_BLOCK_CATEGORIES:
                return 0.70
            return 0.95

        def _may_demote(sem):
            return sem.get("confidence", 0.0) < _ceiling_for(sem.get("category"))

        def demote(sem):
            if not _may_demote(sem):
                return
            sem["category"] = "SAFE"
    """, name="overrides.py")
    c = _one(cands, "category")
    assert c.reaches_hard_block is False, "the floor is consulted two frames down"


def test_a_mention_elsewhere_in_the_function_does_not_count(tmp_path):
    """The correction that ground truth forced: our own apply_overrides names a
    protected category in an unrelated up-classification branch, which read as
    floor-aware and hid the real defect."""
    (tmp_path / "policy.py").write_text(
        'HARD_BLOCK_CATEGORIES = frozenset({"SELF_HARM", "SEXUAL"})\n',
        encoding="utf-8")
    cands = _scan(tmp_path, """
        def apply(sem, q):
            if "battery is dying" in q:
                sem["category"] = "SAFE"
            if sem.get("category") == "SAFE" and "explicit" in q:
                sem["category"] = "SEXUAL"
    """, name="overrides.py")
    c = _one(cands, "category")
    assert c.reaches_hard_block is True
