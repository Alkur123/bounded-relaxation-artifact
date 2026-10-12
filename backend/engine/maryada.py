"""Maryādā — build-time *bounded-relaxation* certification (R14), the twelfth
rung of the certification family: ``pramana`` (R1/R2), ``saksin``,
``anupalabdhi`` (R3), ``rtvij`` (R4), ``vikalpa`` (R5/R6), ``upadha`` (R7),
``prayascitta`` (R8), ``sadlinga`` (R9), ``samaharta`` (R10), ``pratigraha``
(R11).

WHY R14 AND NOT R12. The family's numbering has reached R11 and the next two
integers are already spoken for elsewhere in this system: Ring 12 is the runtime
trajectory verifier and Ring 13 is Jayadratha's egress gate. Reusing either
would produce two different things called R12 in one codebase, which is the kind
of ambiguity this family exists to remove. R12 and R13 are therefore left as
deliberate gaps in the certification numbering, not as omissions.

STATUS: FIRST CUT (2026-08-17). Built from a measured defect rather than from a
principle looking for an application, which is the order this project's own
scoping doctrine prefers and rarely achieves.

WHAT IT CHECKS
--------------
Every rung above asks a question about evidence or structure. None asks what
happens when a stage decides to make the system MORE PERMISSIVE than its own
classifier just said it should be.

  R1/R2  what kind of evidence each arm is
  R3     whether an arm is alive
  R4     whether an evidence-only arm can act
  R5/R6  whether the combinator over the arms is licensed, and mass preserved
  R7     where a component is placed
  R8     whether its recorded failures are reversible
  R9     whether a gate treats its arms as peers
  R10    whether an audit channel is sourced from the party it audits
  R11    whether a declared fallback exists and is not co-located

A relaxation is none of those. It is a stage that takes a verdict and weakens
it: a category demoted to SAFE, a signal zeroed, a block downgraded. Such stages
are legitimate and necessary, because classifiers produce false positives and
something has to fix them. What makes one dangerous is being UNCONDITIONAL.

Three predicates, each from a floor that ``engine/apavada.py`` already states
for regulatory exceptions and that nothing enforced for anything else:

  R14-a  BOUNDED. A relaxation must consult the strength of the evidence it
         overrides. A stage that fires on a pattern match alone releases a
         maximally confident verdict exactly as readily as a marginal one, so it
         is not correcting an error, it is removing a control.
  R14-b  AUDITED. A relaxation must record that it happened, granted or refused.
         apavada's own sentence is the argument: "an unaudited relaxation is
         indistinguishable from a hole." A relaxation that leaves no trace
         cannot be measured, and the defect this rung was built from survived
         precisely because nothing counted it.
  R14-c  FLOORED. A relaxation that can reach a hard-block category must be
         bounded SEPARATELY and more strictly there. The same bound for both is
         not a floor, it is one bound with a second name.

And the discipline every rung in this family shares:

  R14-d  ENACTED. Each declared bound and audit field must actually appear in
         the named module. A declaration is a claim about code, and a claim
         about code that nobody checks against the code is the failure mode the
         whole family exists to close.

WHAT MOTIVATED IT, AND IT IS OURS
---------------------------------
Not a principle from the literature. A measured defect in this system, found on
2026-08-17 and recorded in ``docs/FINDING_2026-08-17_UNBOUNDED_RELAXATION.md``.

``engine/classifier_overrides.py`` is default ON and runs on the live request
path. Forty of its rules demoted a category to SAFE on a substring match and a
category equality, with no confidence term at all, so the verdict was SAFE at
every confidence including 1.00. Fifteen of those rules target ``SELF_HARM`` or
``SEXUAL``, which ``engine/rta.py`` declares hard-block and describes with the
words "admin authority does not reach them". It was an undocumented path that
did reach them, and no admin was involved.

The route to it is worth recording because it was not code review. Anthropic's
August 2026 Risk Report publishes, in Table 2.23.1.2.B, the recall of a
production monitoring pipeline at two stages but never computes the second
stage's conditional retention. Computing it (``eval/stage_retention.py``)
exposes a matched pair: the same SHADE-Arena attempts, the same 100% first-stage
recall, and retention of 45% when the chain of thought discusses the side goal
against 97% when that discussion is ablated. The full-CoT row is strictly the
lowest of every attack row in the table on both monitors. Whatever mechanism
produces that, the shape is a filter whose behaviour is not monotone in the
strength of the evidence it is filtering, and asking whether OUR filters had the
same shape is what found the defect above.

WHAT THIS RUNG IS NOT
---------------------
  * Not a claim about Anthropic's pipeline. Their table supplied the question.
    The benign reading of their result, that the second stage filters
    eval-shaped traffic, is available and likely, and this module asserts
    nothing about which reading is right.
  * Not a runtime check. Zero execution, like every rung here. It reads
    declarations and module source at build time and calls nothing it certifies.
  * Not a substitute for measuring the bound. R14-a asks whether a bound EXISTS
    and is enacted. It cannot tell you whether the number is correct, and in
    this system it currently is not known to be: the ceilings in
    classifier_overrides are declared constants chosen to preserve observed
    behaviour, not fitted to a measured false-positive distribution. A rung that
    passed while the constant was wrong would be exactly the false assurance
    this family keeps warning about, so it is said here rather than in a
    footnote.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

VIOLATION = "VIOLATION"
ADVISORY = "ADVISORY"
OK = "OK"

_REPO_BACKEND = pathlib.Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RelaxationSite:
    """One declared place where the system weakens its own verdict.

    ``bound_by`` and ``hard_block_bound`` name a symbol (a function or constant)
    in ``module``; ``audit_field`` names a dict key written there. All three are
    checked against the module's source by R14-d, so a declaration cannot drift
    from the code it describes without the rung saying so.

    ``None`` means UNDECLARED and is a distinct legal state that the rung
    reports, never a default that quietly passes.

    ``source_root`` is appended last and defaults to ``None``, which resolves
    ``module`` against this repository exactly as before. It exists so the same
    unmodified predicates can be run against a tree we did not write, which is
    what ``engine/maryada_discover.py`` does. No predicate reads it; only the
    source lookup does, so a site declared without it behaves identically.
    """

    name: str
    module: str                       # repo-relative, e.g. "engine/foo.py"
    function: str                     # the callable that performs the relaxation
    relaxes: str                      # "category" | "signal" | "verdict"
    bound_by: Optional[str] = None
    audit_field: Optional[str] = None
    reaches_hard_block: bool = False
    hard_block_bound: Optional[str] = None
    note: str = ""
    source_root: Optional[str] = None

    #: Extensions a site's module may carry. Widened 2026-08-18 from ``.py``
    #: alone, when a second front end (`contrib/external-r14/ts_propose.mjs`)
    #: began proposing sites in TypeScript and JavaScript. This is an
    #: input-shape guard, NOT a predicate: no rule here reads the extension,
    #: and ``_source_of`` reads the module as text and never parses it as
    #: Python. The change is recorded as a dated amendment in
    #: `contrib/external-r14/ADJUDICATION.md` because the cross-language
    #: pre-registration froze this file, and a change made during a frozen
    #: run is declared rather than folded in.
    SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".mts", ".cts",
                       ".js", ".mjs", ".cjs", ".jsx")

    def __post_init__(self) -> None:
        if not self.name or not self.module or not self.function:
            raise ValueError("RelaxationSite needs name, module and function")
        if not self.module.endswith(RelaxationSite.SOURCE_SUFFIXES):
            raise ValueError(
                f"module must be a source path ending in one of "
                f"{RelaxationSite.SOURCE_SUFFIXES}, got {self.module!r}")


@dataclass
class MaryadaFinding:
    rule: str
    severity: str
    reason: str

    def as_dict(self) -> dict:
        return {"rule": self.rule, "severity": self.severity, "reason": self.reason}


@dataclass
class MaryadaResult:
    subject: str
    findings: List[MaryadaFinding] = field(default_factory=list)

    @property
    def violations(self) -> List[MaryadaFinding]:
        return [f for f in self.findings if f.severity == VIOLATION]

    @property
    def advisories(self) -> List[MaryadaFinding]:
        return [f for f in self.findings if f.severity == ADVISORY]

    @property
    def passed(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict:
        return {
            "subject": self.subject,
            "passed": self.passed,
            "findings": [f.as_dict() for f in self.findings],
            "violations": [f.as_dict() for f in self.violations],
        }


def _source_of(site: RelaxationSite) -> Optional[str]:
    root = pathlib.Path(site.source_root) if site.source_root else _REPO_BACKEND
    p = root / site.module
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def check_bounded(site: RelaxationSite) -> MaryadaFinding:
    """R14-a. The relaxation must consult the evidence it overrides."""
    if site.bound_by is None:
        return MaryadaFinding(
            "R14-a", VIOLATION,
            f"unbounded relaxation: {site.name} weakens {site.relaxes} in "
            f"{site.module}::{site.function} and declares no bound, so it fires "
            f"on its trigger alone and releases a maximally confident verdict as "
            f"readily as a marginal one. That is not correcting a false positive, "
            f"it is removing a control.")
    return MaryadaFinding(
        "R14-a", OK,
        f"{site.name} is bounded by {site.bound_by!r}, so the strength of the "
        f"evidence it overrides is consulted before the relaxation applies.")


def check_audited(site: RelaxationSite) -> MaryadaFinding:
    """R14-b. Granted or refused, it must leave a trace."""
    if site.audit_field is None:
        return MaryadaFinding(
            "R14-b", VIOLATION,
            f"unaudited relaxation: {site.name} records no outcome, so a "
            f"suppressed verdict is indistinguishable downstream from a verdict "
            f"that was never raised. Nothing can count what does not exist, which "
            f"is how a relaxation survives unnoticed.")
    return MaryadaFinding(
        "R14-b", OK,
        f"{site.name} records every outcome under {site.audit_field!r}.")


def check_floored(site: RelaxationSite) -> MaryadaFinding:
    """R14-c. A hard-block-reaching relaxation needs its own stricter bound."""
    if not site.reaches_hard_block:
        return MaryadaFinding(
            "R14-c", OK,
            f"{site.name} does not reach a hard-block category, so the floor is "
            f"not engaged.")
    if site.hard_block_bound is None:
        return MaryadaFinding(
            "R14-c", VIOLATION,
            f"unfloored relaxation: {site.name} can reach a hard-block category "
            f"and declares no separate bound for it. Those categories are the ones "
            f"every other mechanism refuses to release, so a relaxation that "
            f"treats them like any other is a path around all of them.")
    if site.hard_block_bound == site.bound_by:
        return MaryadaFinding(
            "R14-c", VIOLATION,
            f"nominal floor: {site.name} declares {site.hard_block_bound!r} for "
            f"hard-block categories and the same symbol as its general bound. One "
            f"bound under two names is not a floor; the hard-block case must be "
            f"bounded more strictly than the ordinary one.")
    return MaryadaFinding(
        "R14-c", OK,
        f"{site.name} bounds hard-block categories separately by "
        f"{site.hard_block_bound!r}.")


def check_enacted(site: RelaxationSite) -> List[MaryadaFinding]:
    """R14-d. Every declared symbol must appear in the module it names.

    A substring search, and the weakness is stated rather than hidden: it
    confirms the symbol is PRESENT, not that it is reached on the relaxation's
    own path. That is the same static boundary saksin, rtvij and anupalabdhi
    each state for themselves, and it under-approximates in the same direction:
    what it reports is real, what it misses is a miss.
    """
    out: List[MaryadaFinding] = []
    src = _source_of(site)
    if src is None:
        out.append(MaryadaFinding(
            "R14-d", VIOLATION,
            f"cannot read {site.module} to check {site.name}'s declarations. An "
            f"unverifiable declaration fails rather than passing on trust."))
        return out
    for label, sym in (("bound", site.bound_by),
                       ("hard-block bound", site.hard_block_bound),
                       ("audit field", site.audit_field)):
        if sym is None:
            continue
        if sym not in src:
            out.append(MaryadaFinding(
                "R14-d", VIOLATION,
                f"declaration does not match code: {site.name} declares its "
                f"{label} as {sym!r}, which does not occur in {site.module}."))
        else:
            out.append(MaryadaFinding(
                "R14-d", OK,
                f"{site.name}'s {label} {sym!r} is present in {site.module}."))
    if site.function not in src:
        out.append(MaryadaFinding(
            "R14-d", VIOLATION,
            f"declaration does not match code: {site.name} names function "
            f"{site.function!r}, which does not occur in {site.module}."))
    return out


def certify(sites: Sequence[RelaxationSite], *, subject: str = "system"
            ) -> MaryadaResult:
    """Run R14-a..d over every declared relaxation site.

    Pure function over declarations plus module source. Zero execution: nothing
    it certifies is imported or called.
    """
    findings: List[MaryadaFinding] = []
    if not sites:
        findings.append(MaryadaFinding(
            "R14", ADVISORY,
            "no relaxation sites declared. That is not the same as having none: "
            "an undeclared relaxation is invisible here, exactly as an undeclared "
            "redistribution path is invisible to R6."))
        return MaryadaResult(subject=subject, findings=findings)

    seen: Dict[str, str] = {}
    for s in sites:
        if s.name in seen:
            findings.append(MaryadaFinding(
                "R14", VIOLATION,
                f"duplicate site name {s.name!r} declared twice"))
        seen[s.name] = s.module
        findings.append(check_bounded(s))
        findings.append(check_audited(s))
        findings.append(check_floored(s))
        findings.extend(check_enacted(s))
    return MaryadaResult(subject=subject, findings=findings)


# ═══════════════════════════════════════════════════════════════════════════
# This system's own relaxation sites, declared honestly
# ═══════════════════════════════════════════════════════════════════════════
# Mirrors the pattern pramana, anupalabdhi, rtvij and vikalpa already use: the
# shipped constants live beside the checker and a runner certifies the real
# thing. Anything absent here is invisible to the rung, which is why the empty
# case is an advisory above.

CHAKRAVYUHA_RELAXATIONS: tuple = (
    RelaxationSite(
        name="classifier_override_demotion",
        module="engine/classifier_overrides.py",
        function="_demote_to_safe",
        relaxes="category",
        bound_by="override_ceiling_for",
        audit_field="override_audit",
        reaches_hard_block=True,
        hard_block_bound="_HARD_BLOCK_OVERRIDE_CEILING",
        note="Forty phrase rules demote a category to SAFE. Unbounded and "
             "unaudited until 2026-08-17; fifteen of the rules target SELF_HARM "
             "or SEXUAL. See docs/FINDING_2026-08-17_UNBOUNDED_RELAXATION.md."),
    RelaxationSite(
        name="distress_idiom_exclusion",
        module="engine/classifier_overrides.py",
        function="apply_overrides",
        relaxes="signal",
        bound_by="DISTRESS_EXCLUSION_CEILING",
        audit_field="exclusion_audit",
        reaches_hard_block=True,
        hard_block_bound="DISTRESS_EXCLUSION_CEILING",
        note="Zeroes a passive-self-harm signal, which per "
             "docs/CLASSIFIER_OVERRIDES.md suppresses a HITL escalation. The "
             "hard-block bound is deliberately THE SAME symbol as the general "
             "one, so R14-c convicts this site, and the conviction is correct: "
             "there is no separate stricter floor here. A strength ceiling "
             "cannot supply one, because this detector is tuned aggressive and "
             "a genuine idiom scores 0.85, so the honest position is that this "
             "site is audited but not floored. Recorded, not argued away."),
)


def certify_chakravyuha_relaxations() -> MaryadaResult:
    """Certify this system's own declared relaxation sites."""
    return certify(CHAKRAVYUHA_RELAXATIONS, subject="chakravyuha")
