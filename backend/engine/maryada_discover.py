"""Maryādā discovery — finding relaxation sites in code that declared none.

R14 (``engine/maryada.py``) certifies *declared* relaxation sites. That is the
right interface for a system whose authors are willing to declare, and it is
useless for every system that is not, which is all of them except ours.

This module closes that gap. It reads Python source and proposes
``RelaxationSite`` declarations mechanically, so R14 can be run against a
codebase whose authors have never heard of it. The certifier itself is not
modified: what comes out of here goes into ``maryada.certify()`` unchanged.

WHY THE ORDER OF WORK MATTERS, AND IT IS THE WHOLE METHODOLOGY
-------------------------------------------------------------
If the patterns below were written after reading the systems they are run
against, this module would be a machine for confirming whatever we already
believed, and every finding it produced would be worth nothing. So they derive
from exactly two things, both of which predate any foreign subject:

  1. This system's own two relaxation sites, in
     ``engine/classifier_overrides.py``, as they stood on 2026-08-17. The
     bounded one writes a benign constant to a verdict-carrying key
     (``sem["category"] = "SAFE"``) under a guard that compares a magnitude
     (``conf < override_ceiling_for(...)``) and records an outcome
     (``sem["override_audit"] = {...}``). The unfloored one zeroes a signal
     (``dist = {"is_passive_self_harm": False, "strength": 0.0, ...}``).
  2. ``engine/apavada.py``'s two stated floors, which are R14-b and R14-c.

This file is committed BEFORE any third-party code is fetched. The commit order
is the pre-registration, and it is checkable in the log.

THE FIRST VERSION OF THIS FILE FOUND NEITHER OF OUR OWN TWO SITES
-----------------------------------------------------------------
Recorded because it is the most useful thing that happened during the build and
because a reader is entitled to know the detector was calibrated at all. Run
against ``engine/`` it returned twenty-one candidates and **both ground-truth
sites were absent**. Three defects, all of them general rather than peculiar to
us, and all fixed here before any third-party tree was fetched:

  * **Guards are flow-sensitive, not only syntactic.** ``_demote_to_safe``
    bails with ``if not _may_demote(sem): ... return`` and then writes
    ``sem["category"] = "SAFE"`` at function top level. Looking only at
    enclosing ``if`` blocks, that write has no guard at all and reads as an
    initialiser. Early-return guarding is one of the most common shapes in
    Python, so a scanner blind to it is blind to a large fraction of real
    relaxations. Now a preceding ``if <t>: return|raise|continue|break`` in the
    same block contributes ``not (t)`` to everything after it, and ``assert t``
    contributes ``t``.
  * **A weakening write can be a whole-dict replacement.** Our distress site
    does not zero a field; it rebinds the record:
    ``dist = {"is_passive_self_harm": False, "strength": 0.0, ...}``. The name
    ``dist`` carries no polarity and the value is not a constant, so nothing
    matched. Dict literals are now expanded and each key considered as its own
    write.
  * **A bound is usually reached through a helper.** Our guard calls
    ``_may_demote``, whose comparison lives one frame away, so the site read as
    unbounded, which would have been a false accusation against our own fixed
    code. Guards now resolve calls to functions defined in the same module, to
    a bounded depth, before concluding that nothing is consulted.
  * **The weakening and the trigger routinely live in different frames**, and
    this one was found by scanning the DEFECT as it shipped rather than the
    repaired code. Before the fix, ``_demote_to_safe`` wrote
    ``sem["category"] = "SAFE"`` unconditionally at its own top level, and the
    only conditions were at its three call sites. So the write had no guard and
    the calls had no write, and the scanner saw nothing on the exact code the
    rung was built from. A function that unconditionally performs a benign
    write is now itself treated as a weakening operation, and a guarded CALL to
    one is a relaxation site whose trigger is the guard at the call.

WHAT A RELAXATION LOOKS LIKE IN SOURCE
--------------------------------------
Three parts, and all three are required:

  W  a WEAKENING WRITE. A value moves in the permissive direction: a
     risk-polarity name set to a benign constant (``score = 0.0``,
     ``is_malicious = False``, ``category = "SAFE"``), a permit-polarity name
     set to true (``allowed = True``), a benign key inside a dict literal, or a
     return of any of those from a function whose own name carries the polarity.

  T  a TRIGGER. W is dominated by at least one condition, whether by nesting or
     by a preceding bail-out. An unguarded ``score = 0.0`` at the top of a
     function is an initialiser, not a relaxation, and treating the two alike
     would drown every real finding. An ``except`` handler counts as a trigger:
     it is the condition "something broke", and a benign write under it is a
     fail-open relaxation.

  and then R14 asks its questions of T:

  R14-a  does any dominating condition consult a MAGNITUDE of the evidence
         being overridden: a comparison against a score, confidence, strength,
         probability or severity, or a call to a threshold-ish helper, directly
         or one level down?
  R14-b  does the block performing W leave a trace: a log, an audit record, a
         metric, a written reason?

HONEST BOUNDARIES, STATED HERE RATHER THAN IN A FOOTNOTE
--------------------------------------------------------
  * It is SYNTACTIC. Guard resolution is one module deep and follows names, not
    values. A bound reached through an imported helper, a method on an injected
    object, or a config lookup this module cannot see still reads as unbounded.
  * R14-b is evaluated over the innermost enclosing BLOCK, so a log anywhere in
    that block counts even if it is not on the relaxing path. That direction is
    deliberate: it OVER-credits auditing, so the rung under-reports R14-b
    violations rather than accusing a subject of a hole it does not have.
  * R14-a errs the other way and OVER-reports: an unresolvable guard reads as
    unbounded. So every R14-a finding is a CANDIDATE and nothing here is a
    verdict about anybody's code until a human has read the lines it names.
  * R14-d is VACUOUS under discovery. The declared symbols are extracted from
    the module's own source, so the presence check they exist to fail cannot
    fail. It is reported as vacuous rather than counted as a pass.
  * R14-c is engaged only where the subject itself declares a category it
    treats as unreleasable. Most do not. Absent such a declaration the floor is
    NOT ENGAGED, which is a different statement from satisfied, and this module
    never converts one into the other.
  * Polarity is a guess from a name. ``valid`` is permissive in a guardrail and
    means something else in a parser; ``clean`` is benign here and is a verb
    elsewhere. Both directions of that error are real and both were observed.
  * A bare-name assignment counts only where the name is ALREADY BOUND at
    that point, as a parameter or by an earlier binding in scope. A first
    binding of a fresh local establishes a value; it does not weaken one, and
    you cannot relax a verdict that does not exist yet. This was the dominant
    false positive when the scanner was first pointed at code we did not write:
    a function opening with a bail-out puts a guard on the stack, after which
    every ordinary initialiser below it reads as a guarded weakening write.
    Attribute and subscript writes are unaffected, because the object they
    mutate came from somewhere else by construction.
  * KNOWN BLIND SPOT, not fixed: a *multiplicative* relaxation
    (``score *= 0.5``, ``score -= penalty``) weakens a verdict without ever
    writing a benign constant, and nothing here sees it. It is named rather
    than quietly excluded.
"""

from __future__ import annotations

import ast
import pathlib
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .maryada import RelaxationSite

# R3's guard classifiers, imported rather than reimplemented. Two rungs that
# disagree about what an unavailability guard looks like would be worse than
# either rung being slightly wrong, and this is the same reuse discipline
# vikalpa follows when it reads substrate_attest's shipped weight mapping.
from .anupalabdhi import (_no_backend_guard_branches,  # noqa: F401
                          _none_guard_branches)

# ═══════════════════════════════════════════════════════════════════════════
# Lexicons. Pre-registered; see the module docstring for what they derive from.
# ═══════════════════════════════════════════════════════════════════════════

#: Names whose LOW/FALSE value is the permissive one. Setting one of these to a
#: benign constant weakens a verdict.
RISK_POLARITY = re.compile(
    r"(?:^|_)(?:"
    r"suspicio\w*|suspect\w*|risk\w*|threat\w*|harm\w*|danger\w*|malicious|"
    r"unsafe|toxic\w*|attack\w*|injection|jailbreak|exploit|abuse|violat\w*|"
    r"severity|score|rating|confidence|probability|prob|likelihood|"
    r"strength\w*|"
    r"block\w*|deny|denied|reject\w*|refus\w*|flag\w*|alert\w*|"
    r"detect\w*|finding\w*|"
    r"verdict|decision|category|label|classification"
    r")(?:$|_)",
    re.IGNORECASE,
)

#: Names whose TRUE value is the permissive one.
PERMIT_POLARITY = re.compile(
    r"(?:^|_)(?:"
    r"allow\w*|permit\w*|safe|ok|okay|valid|passed|benign|"
    r"clean|approved|accept\w*|whitelist\w*|allowlist\w*|exempt\w*|trusted|"
    r"authorized|authorised|granted|skip\w*|ignore\w*|bypass\w*|excluded"
    r")(?:$|_)",
    re.IGNORECASE,
)

#: A magnitude of the evidence. A guard that compares one of these is bounded.
EVIDENCE_LEXICON = re.compile(
    r"(?:^|_|\.)(?:"
    r"score\w*|confidence\w*|conf|strength\w*|probability|prob\w*|likelihood|"
    r"severity|weight\w*|magnitude|certainty|logit\w*|risk_?level|level|"
    r"count|len|ratio|rate|percent\w*|pct|threshold\w*"
    r")(?:$|_|\b)",
    re.IGNORECASE,
)

#: Helpers whose very name is a bound. A guard calling one is bounded.
BOUND_CALL_LEXICON = re.compile(
    r"(?:^|_)(?:"
    r"threshold\w*|ceiling\w*|cap|caps|capped|limit\w*|bound\w*|floor\w*|"
    r"cutoff\w*|tolerance|margin|budget|quota"
    r")(?:$|_)",
    re.IGNORECASE,
)

#: Leaving a trace. Calls matching this inside the relaxing block satisfy R14-b.
AUDIT_CALL_LEXICON = re.compile(
    r"(?:^|_|\.)(?:"
    r"log\w*|logger|logging|debug|info|warn\w*|error|exception|critical|"
    r"audit\w*|record\w*|track\w*|trace\w*|report\w*|emit\w*|publish|"
    r"observe|metric\w*|counter|increment|incr|telemetr\w*|span|"
    r"print|annotate|explain"
    r")(?:$|_|\b)",
    re.IGNORECASE,
)

#: Written into an audit-ish key. Same obligation, different syntax.
AUDIT_KEY_LEXICON = re.compile(
    r"(?:^|_)(?:"
    r"audit\w*|reason\w*|explanation|rationale|justification|"
    r"detail\w*|metadata|provenance|evidence|trace\w*|"
    r"override\w*|suppress\w*|exclusion\w*|waiver"
    r")(?:$|_)",
    re.IGNORECASE,
)

#: Values that read as "nothing to worry about" for a risk-polarity name.
BENIGN_STRINGS = frozenset({
    "safe", "none", "no", "ok", "okay", "clean", "benign", "allow", "allowed",
    "pass", "passed", "accept", "accepted", "low", "info", "informational",
    "negative", "n/a", "na", "skip", "skipped", "ignore",
    "not_applicable", "no_risk", "harmless", "valid",
})

#: Category names a subject may declare unreleasable. R14-c engages only if the
#: subject declares something of this shape somewhere in its own source.
#: Matched against whole LINES, so the anchors are lookarounds rather than the
#: (?:^|_) / (?:$|_) the identifier lexicons use. With those anchors
#: ``NEVER_ALLOW = {...}`` did not match, because the next character is a space,
#: and every subject that does declare an unreleasable category was reported as
#: NOT ENGAGED. That is the fail-open direction, so it is pinned by a test.
HARD_BLOCK_DECLARATION = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"hard_?block\w*|never_?allow\w*|always_?block\w*|unreleasable|"
    r"prohibited|forbidden|non_?overridable|non_?negotiable|"
    r"critical_?categor\w*|blocklist_?always"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

#: Attributes whose comparison tests whether an OPERATION succeeded, rather
#: than what it concluded. A branch taken on one of these is R3's question.
FAILURE_TEST_LEXICON = re.compile(
    r"(?:^|_|\.)(?:"
    r"status_?code|statuscode|status|ok|success\w*|failed|failure|error\w*|"
    r"exception|exc|errno|retcode|returncode|is_?error|has_?error"
    r")(?:$|_|\b)",
    re.IGNORECASE,
)

#: In-band error sentinels. A guard that tests for one of these is testing
#: whether the evidence producer failed, not how strong its evidence was.
#: LlamaFirewall's PII scanner is the reference case: its error response is
#: ``detected_pii_types=["ERROR"]`` and the score conversion tests for it.
ERROR_SENTINEL_LEXICON = re.compile(
    r"^(?:error|errored|failure|failed|unknown|unavailable|timeout|"
    r"exception|n/?a|none)$",
    re.IGNORECASE,
)

#: Emptiness/shape tests. A guard on one of these over a PARAMETER establishes
#: that there is nothing to judge, which is neither R3 nor R14.
EMPTINESS_CALL_LEXICON = re.compile(r"^(?:len|bool|isinstance|hasattr|any|all)$")

#: Collections whose ELEMENTS are detections. Shortening one weakens a verdict.
#: Deliberately separate from RISK_POLARITY: these names carry no polarity when
#: assigned a constant, so widening RISK_POLARITY would add noise to the
#: benign-write path to fix the narrowing path.
RISK_COLLECTION = re.compile(
    r"(?:^|_)(?:"
    r"finding\w*|detection\w*|result\w*|match\w*|hit|hits|entit\w*|"
    r"violation\w*|alert\w*|issue\w*|error\w*|warning\w*|flag\w*|"
    r"score\w*|risk\w*|threat\w*|candidate\w*|span\w*|annotation\w*"
    r")(?:$|_)",
    re.IGNORECASE,
)

#: Methods that shorten a collection in place.
NARROWING_METHODS = frozenset({"remove", "pop", "discard", "clear",
                               "difference_update", "filter"})

#: Collections that name an authority to skip. A membership test against one is
#: a principal waiver, which engages the audit and floor obligations but not the
#: bound obligation, because a waiver has no evidence strength to consult.
WAIVER_COLLECTION = re.compile(
    r"(?:^|_)(?:"
    r"allow\w*|allowlist|allow_?list|white\w*|whitelist|safe_?list|"
    r"ignore\w*|ignored|exempt\w*|exclude\w*|excluded|excluding|skip\w*|"
    r"trusted|permitted|approved|benign\w*|known_?good"
    r")(?:$|_)",
    re.IGNORECASE,
)

#: A declared category reads as an identifier-shaped token. Anything longer or
#: punctuated is prose, a message, or a regex, and is not a category name.
_CATEGORY_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9 _.:/-]*$")

#: Domains a proposed site can belong to.
DOMAIN_R14 = "R14"
DOMAIN_R3 = "R3"
DOMAIN_STRUCTURAL = "STRUCTURAL"

#: How far guard resolution follows same-module helper calls.
GUARD_RESOLUTION_DEPTH = 2


# ═══════════════════════════════════════════════════════════════════════════
# Which rung owns this site
# ═══════════════════════════════════════════════════════════════════════════

def _names_in(node: ast.AST) -> Set[str]:
    out: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            out.add(sub.attr)
    return out


def _tests_failure(test: ast.expr) -> bool:
    """Does this condition ask whether an operation failed?"""
    for sub in ast.walk(test):
        if isinstance(sub, ast.Attribute) and FAILURE_TEST_LEXICON.search(sub.attr):
            return True
        if isinstance(sub, ast.Name) and FAILURE_TEST_LEXICON.search(sub.id):
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if ERROR_SENTINEL_LEXICON.match(sub.value.strip()):
                return True
    return False


def _tests_emptiness_of(test: ast.expr, names: Set[str]) -> bool:
    """Does this condition ask whether one of ``names`` is absent or empty?

    ``not x``, ``x is None``, ``x == ""``, ``len(x) == 0``, ``not isinstance(x, T)``.
    """
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = test.operand
        if isinstance(inner, ast.Name) and inner.id in names:
            return True
        if isinstance(inner, ast.Attribute) and inner.attr in names:
            return True
        if isinstance(inner, ast.Call):
            fn = _callee_name(inner)
            if fn and EMPTINESS_CALL_LEXICON.match(fn.split(".")[-1]):
                return bool(_names_in(inner) & names)
        return _tests_emptiness_of(inner, names)
    if isinstance(test, ast.Compare):
        touched = _names_in(test.left) & names
        left_is_len = (isinstance(test.left, ast.Call)
                       and (_callee_name(test.left) or "").split(".")[-1] == "len")
        for c in test.comparators:
            empty_rhs = (isinstance(c, ast.Constant)
                         and (c.value is None or c.value == "" or c.value == 0
                              or c.value == [] or c.value is False))
            if empty_rhs and (touched or (left_is_len and _names_in(test.left) & names)):
                return True
    if isinstance(test, ast.BoolOp):
        return any(_tests_emptiness_of(v, names) for v in test.values)
    return False


def classify_domain(guards: Sequence[str], *, from_handler: bool,
                    params: Set[str], from_call: Set[str]) -> str:
    """R3, STRUCTURAL or R14 — exactly one, decided from the dominating guards.

    Order matters and is argued rather than assumed:

      1. STRUCTURAL first, when the guard says a PARAMETER is absent or empty.
         ``if not schema: return True`` is a precondition, not a verdict being
         weakened, and it is the single largest source of noise in this scan.
      2. R3 next, when the branch was taken because something FAILED: an
         exception handler, a None returned by a call made in this function, an
         error-status test, or an in-band error sentinel. R3 owns these and has
         a shipped scanner for them.
      3. R14 otherwise. A verdict existed and this branch weakened it.

    A site the scanner cannot place lands in R14, which is the reporting
    direction that costs precision rather than recall, and precision is what
    adjudication is for.
    """
    if from_handler:
        return DOMAIN_R3

    parsed = []
    for g in guards:
        try:
            parsed.append((g, ast.parse(g, mode="eval").body))
        except SyntaxError:
            continue        # synthesised for/while/except/match guard text

    for _g, t in parsed:
        if params and _tests_emptiness_of(t, params) and not (_names_in(t) & from_call):
            return DOMAIN_STRUCTURAL

    for _g, t in parsed:
        if _tests_failure(t):
            return DOMAIN_R3
        # R3 own classifiers. Our guard strings are normalised so the text is
        # the condition we took as TRUE, hence "body".
        if "body" in _none_guard_branches(t) and (_names_in(t) & from_call):
            return DOMAIN_R3
        if "body" in _no_backend_guard_branches(t):
            return DOMAIN_R3

    return DOMAIN_R14


# ═══════════════════════════════════════════════════════════════════════════
# What one candidate looks like
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Candidate:
    """One syntactic relaxation site proposed from source.

    ``bounded`` and ``audited`` are what the SCAN concluded. They are inputs to
    an adjudication, not an adjudication.
    """

    subject: str
    module: str                 # path relative to the scan root
    line: int
    function: str
    target: str                 # the name/key/return being written
    kind: str                   # "assign" | "return" | "subscript" | "dict-key"
    polarity: str               # "risk" | "permit"
    written: str                # the benign value, as source text
    guards: List[str] = field(default_factory=list)
    guard_lines: List[int] = field(default_factory=list)
    bounded: bool = False
    bound_symbol: Optional[str] = None
    bound_via: Optional[str] = None   # the helper it was resolved through
    audited: bool = False
    audit_symbol: Optional[str] = None
    from_handler: bool = False  # dominated by an `except`, i.e. fail-open
    domain: str = DOMAIN_R14    # R14 | R3 | STRUCTURAL, see classify_domain
    shape: str = "benign-write"  # which detector proposed it
    reaches_hard_block: bool = False   # subject declares a floor, site ignores it
    hard_block_ref: Optional[str] = None  # the floor symbol the site DOES cite

    @property
    def site_name(self) -> str:
        stem = self.module.replace("/", ".").removesuffix(".py")
        return f"{stem}::{self.function}::{self.target}@{self.line}"

    def note_text(self) -> str:
        g = " AND ".join(self.guards) if self.guards else "(none)"
        return (f"discovered: writes {self.written} to {self.target!r} under "
                f"{g}")[:400]

    def as_dict(self) -> dict:
        return {
            "subject": self.subject, "module": self.module, "line": self.line,
            "function": self.function, "target": self.target, "kind": self.kind,
            "polarity": self.polarity, "written": self.written,
            "guards": self.guards, "guard_lines": self.guard_lines,
            "bounded": self.bounded, "bound_symbol": self.bound_symbol,
            "bound_via": self.bound_via,
            "audited": self.audited, "audit_symbol": self.audit_symbol,
            "from_handler": self.from_handler,
            "domain": self.domain,
            "shape": self.shape,
            "reaches_hard_block": self.reaches_hard_block,
            "hard_block_ref": self.hard_block_ref,
            "site_name": self.site_name,
        }

    def to_site(self, *, source_root: str) -> RelaxationSite:
        """Hand this candidate to the unmodified R14 certifier.

        R14-c is engaged from the scan: the subject declares a floor and this
        site does not reference it. Where the site DOES reference the floor, the
        symbol it cites is passed as the hard-block bound, so a site that guards
        protected categories with the very same bound it uses for everything
        else is convicted as a nominal floor, which is the verdict our own
        distress site carries.
        """
        return RelaxationSite(
            name=self.site_name,
            module=self.module,
            function=self.function,
            relaxes="verdict",
            bound_by=self.bound_symbol if self.bounded else None,
            audit_field=self.audit_symbol if self.audited else None,
            reaches_hard_block=self.reaches_hard_block,
            # NOT self.hard_block_ref: that field means "a separate stricter
            # bound for protected categories", and a mention of the floor is not
            # a bound. We cannot verify one statically, so a site that reaches
            # the floor is reported unfloored and a site that references it is
            # simply NOT ENGAGED, with the reference recorded as evidence.
            hard_block_bound=None,
            note=self.note_text(),
            source_root=source_root,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Recognising a weakening write
# ═══════════════════════════════════════════════════════════════════════════

def _target_name(node: ast.expr) -> Optional[Tuple[str, str]]:
    """Return (name, kind) for an assignment target we can reason about."""
    if isinstance(node, ast.Name):
        return node.id, "assign"
    if isinstance(node, ast.Attribute):
        return node.attr, "assign"
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return key.value, "subscript"
    return None


def _is_benign_constant(node: ast.expr, polarity: str) -> Optional[str]:
    """The permissive extreme, or None if this value is not one.

    Direction is the entire point. For a risk-polarity name the permissive
    extreme is low/false/empty; for a permit-polarity name it is true.
    """
    if isinstance(node, ast.Constant):
        v = node.value
        if polarity == "risk":
            if v is False or v is None:
                return repr(v)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
                return repr(v)
            if isinstance(v, str) and v.strip().lower() in BENIGN_STRINGS:
                return repr(v)
        else:
            if v is True:
                return repr(v)
    if polarity == "risk":
        # empty container: no findings, no flags, nothing to report
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
            return "empty container"
        if isinstance(node, ast.Dict) and not node.keys:
            return "empty dict"
    return None


def _polarity_of(name: str) -> Optional[str]:
    """Which direction is permissive for this name, if we can tell.

    Permit polarity is tested FIRST and wins ties on purpose: ``is_safe`` and
    ``allowed_score`` both match the risk lexicon through a generic component,
    and the permit reading is the correct one for both.
    """
    if PERMIT_POLARITY.search(name):
        return "permit"
    if RISK_POLARITY.search(name):
        return "risk"
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Recognising a bound and a trace
# ═══════════════════════════════════════════════════════════════════════════

def _callee_name(node: ast.Call) -> Optional[str]:
    parts: List[str] = []
    f = node.func
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    elif not parts:
        return None
    return ".".join(reversed(parts))


def _magnitude_symbol(node: ast.expr) -> Optional[str]:
    """The evidence-magnitude name in an expression, if there is one."""
    if isinstance(node, ast.Name) and EVIDENCE_LEXICON.search(node.id):
        return node.id
    if isinstance(node, ast.Attribute) and EVIDENCE_LEXICON.search(node.attr):
        return node.attr
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            if EVIDENCE_LEXICON.search(key.value):
                return key.value
        return _magnitude_symbol(node.value)
    if isinstance(node, ast.Call):
        fname = _callee_name(node)
        if fname and (EVIDENCE_LEXICON.search(fname.split(".")[-1])
                      or BOUND_CALL_LEXICON.search(fname.split(".")[-1])):
            return fname
        for arg in node.args:
            # `sem.get("confidence", 0.0)` reads a magnitude and the name of it
            # is a string argument, not an identifier. This is at least as
            # common as attribute access in the code this scanner is aimed at.
            if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    and EVIDENCE_LEXICON.search(arg.value)):
                return arg.value
            sym = _magnitude_symbol(arg)
            if sym:
                return sym
    if isinstance(node, ast.BinOp):
        return _magnitude_symbol(node.left) or _magnitude_symbol(node.right)
    return None


class _GuardInspector(ast.NodeVisitor):
    """Does this condition consult a magnitude of the evidence?

    ``local_fns`` maps same-module function names to their definitions. A guard
    that calls one is resolved into it, to ``depth`` levels, because the bound
    in real code is almost always one frame away: ours is.
    """

    def __init__(self, local_fns: Dict[str, ast.AST], *,
                 depth: int = GUARD_RESOLUTION_DEPTH,
                 seen: Optional[Set[str]] = None) -> None:
        self.local_fns = local_fns
        self.depth = depth
        self.seen: Set[str] = seen if seen is not None else set()
        self.bound_symbol: Optional[str] = None
        self.bound_via: Optional[str] = None

    def _take(self, sym: Optional[str], via: Optional[str] = None) -> None:
        if sym and self.bound_symbol is None:
            self.bound_symbol = sym
            self.bound_via = via

    def visit_Compare(self, node: ast.Compare) -> None:
        if any(isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE))
               for op in node.ops):
            for side in [node.left, *node.comparators]:
                self._take(_magnitude_symbol(side))
                # the other half of a comparison is often the bound itself,
                # named rather than literal: `score < CEILING`, `n > MAX_HITS`.
                if isinstance(side, ast.Name) and BOUND_CALL_LEXICON.search(side.id):
                    self._take(side.id)
                elif (isinstance(side, ast.Attribute)
                        and BOUND_CALL_LEXICON.search(side.attr)):
                    self._take(side.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        fname = _callee_name(node)
        if fname:
            leaf = fname.split(".")[-1]
            if BOUND_CALL_LEXICON.search(leaf):
                self._take(fname)
            elif self.depth > 0 and leaf in self.local_fns and leaf not in self.seen:
                self.seen.add(leaf)
                inner = _GuardInspector(self.local_fns, depth=self.depth - 1,
                                        seen=self.seen)
                inner.visit(self.local_fns[leaf])
                self._take(inner.bound_symbol, via=leaf)
        self.generic_visit(node)


def _branch_audit_symbol(stmts: Sequence[ast.stmt]) -> Optional[str]:
    """A logging call or an audit-ish write anywhere in the relaxing block."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                fname = _callee_name(node)
                if fname and AUDIT_CALL_LEXICON.search(fname.split(".")[-1]):
                    return fname
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (node.targets if isinstance(node, ast.Assign)
                           else [node.target])
                for t in targets:
                    named = _target_name(t)
                    if named and AUDIT_KEY_LEXICON.search(named[0]):
                        return named[0]
            if isinstance(node, ast.Dict):
                for k in node.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        if AUDIT_KEY_LEXICON.search(k.value):
                            return k.value
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Flow: which conditions dominate a statement
# ═══════════════════════════════════════════════════════════════════════════

def _always_exits(stmts: Sequence[ast.stmt]) -> bool:
    """Does control always leave this block, so the code after it is guarded?"""
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    if isinstance(last, ast.If):
        return (bool(last.orelse) and _always_exits(last.body)
                and _always_exits(last.orelse))
    if isinstance(last, (ast.With, ast.AsyncWith)):
        return _always_exits(last.body)
    if isinstance(last, ast.Try):
        return _always_exits(last.body) and all(
            _always_exits(h.body) for h in last.handlers)
    return False


def _src(source: str, node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.get_source_segment(source, node) or ""
    except Exception:                    # pragma: no cover - defensive
        return ""


class _RelaxationWalker:
    """Walk one module, carrying the conditions that dominate each write.

    Explicitly recursive rather than an ``ast.NodeVisitor`` because domination
    depends on statement ORDER inside a block, which a generic visit does not
    preserve: a bail-out ``if`` guards what follows it and nothing before it.
    """

    def __init__(self, subject: str, module: str, source: str,
                 local_fns: Dict[str, ast.AST],
                 weakening_fns: Optional[Dict[str, str]] = None,
                 hard_block_vocab: Optional[Set[str]] = None) -> None:
        self.subject = subject
        self.module = module
        self.source = source
        self.local_fns = local_fns
        self.weakening_fns = weakening_fns or {}
        self.hard_block_vocab = hard_block_vocab or set()
        # names and string constants used anywhere in the enclosing function
        self._fn_vocab: List[Set[str]] = [set()]
        self.out: List[Candidate] = []
        self._guards: List[Tuple[str, int]] = []
        self._in_handler = 0
        self._fn: List[str] = ["<module>"]
        self._block: List[Sequence[ast.stmt]] = []
        # names bound so far, innermost scope last. A relaxation weakens a
        # value that already exists, so a bare name must be in here already.
        self._bound: List[Set[str]] = [set()]
        # parameters of the enclosing function, and names bound from a CALL.
        # classify_domain needs both: an absence test on a parameter is a
        # precondition, the same test on a call result is an unavailability
        # check, and telling them apart is what separates STRUCTURAL from R3.
        self._params: List[Set[str]] = [set()]
        self._from_call: List[Set[str]] = [set()]

    # -- blocks ------------------------------------------------------------
    def walk_block(self, stmts: Sequence[ast.stmt]) -> None:
        """Walk a statement list, accumulating bail-out guards as we go."""
        depth = len(self._guards)
        self._block.append(stmts)
        for st in stmts:
            self._stmt(st)
            self._absorb_flow_guard(st)
        self._block.pop()
        del self._guards[depth:]

    def _absorb_flow_guard(self, st: ast.stmt) -> None:
        """A statement that bails guards everything after it in this block."""
        if isinstance(st, ast.Assert):
            self._guards.append((_src(self.source, st.test), st.lineno))
            return
        if not isinstance(st, ast.If):
            return
        text = _src(self.source, st.test)
        line = getattr(st.test, "lineno", st.lineno)
        if _always_exits(st.body):
            self._guards.append((f"not ({text})", line))
        if st.orelse and _always_exits(st.orelse):
            self._guards.append((text, line))

    def _guard_vocab(self) -> Set[str]:
        """Names and string constants appearing in the dominating guards.

        Resolved one level into same-module helpers, because a guard that
        distinguishes protected categories usually does so through a helper:
        ours calls ``_may_demote``, which calls ``override_ceiling_for``, which
        is where the protected set is actually named.
        """
        out: Set[str] = set()

        def harvest(node: ast.AST, depth: int) -> None:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    out.add(sub.attr)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    tok = sub.value.strip()
                    if tok:
                        out.add(tok)
                if depth > 0 and isinstance(sub, ast.Call):
                    fname = _callee_name(sub)
                    leaf = fname.split(".")[-1] if fname else None
                    if leaf and leaf in self.local_fns:
                        harvest(self.local_fns[leaf], depth - 1)

        for text, _ln in self._guards:
            if not text:
                continue
            try:
                harvest(ast.parse(text, mode="eval").body, 2)
            except SyntaxError:
                continue
        return out

    def _is_bound(self, name: str) -> bool:
        return any(name in scope for scope in self._bound)

    def _bind(self, node: Optional[ast.AST]) -> None:
        """Record every name a statement or target binds."""
        if node is None:
            return
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                self._bound[-1].add(sub.id)
            elif isinstance(sub, ast.alias):
                self._bound[-1].add((sub.asname or sub.name).split(".")[0])
            elif isinstance(sub, ast.ExceptHandler) and sub.name:
                self._bound[-1].add(sub.name)

    def _under(self, guard: Tuple[str, int], stmts: Sequence[ast.stmt]) -> None:
        self._guards.append(guard)
        self.walk_block(stmts)
        self._guards.pop()

    # -- statements --------------------------------------------------------
    def _stmt(self, node: ast.stmt) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._bound[-1].add(node.name)
            self._fn.append(node.name)
            a = node.args
            params = {p.arg for p in
                      [*a.posonlyargs, *a.args, *a.kwonlyargs]}
            if a.vararg:
                params.add(a.vararg.arg)
            if a.kwarg:
                params.add(a.kwarg.arg)
            self._bound.append(params)
            self._params.append(params)
            self._from_call.append(set())
            self._fn_vocab.append(set())
            saved_guards, self._guards = self._guards, []
            self.walk_block(node.body)
            self._guards = saved_guards
            self._fn_vocab.pop()
            self._from_call.pop()
            self._params.pop()
            self._bound.pop()
            self._fn.pop()
            return
        if isinstance(node, ast.ClassDef):
            self.walk_block(node.body)
            return
        if isinstance(node, ast.If):
            text = _src(self.source, node.test)
            line = getattr(node.test, "lineno", node.lineno)
            self._under((text, line), node.body)
            if node.orelse:
                self._under((f"not ({text})", line), node.orelse)
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self._bind(node.target)
            text = (f"for {_src(self.source, node.target)} "
                    f"in {_src(self.source, node.iter)}")
            self._under((text, node.lineno), node.body)
            self.walk_block(node.orelse)
            return
        if isinstance(node, ast.While):
            self._under((f"while {_src(self.source, node.test)}", node.lineno),
                        node.body)
            self.walk_block(node.orelse)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                self._bind(item.optional_vars)
            self.walk_block(node.body)
            return
        if isinstance(node, ast.Try):
            self.walk_block(node.body)
            for h in node.handlers:
                if h.name:
                    self._bound[-1].add(h.name)
                typ = _src(self.source, h.type) if h.type else "Exception"
                self._in_handler += 1
                self._under((f"except {typ}", h.lineno), h.body)
                self._in_handler -= 1
            self.walk_block(node.orelse)
            self.walk_block(node.finalbody)
            return
        if hasattr(ast, "Match") and isinstance(node, ast.Match):
            subj = _src(self.source, node.subject)
            for case in node.cases:
                pat = _src(self.source, case.pattern)
                self._under((f"match {subj} case {pat}", case.pattern.lineno),
                            case.body)
            return
        if isinstance(node, ast.Assign):
            for t in node.targets:
                named = _target_name(t)
                if named and self._weakens_existing(t, named[0]):
                    self._consider(named[0], named[1], node.value, node.lineno)
            self._expand_dict(node.value, node.lineno)
            self._scan_calls(node)
            self._scan_narrowing(node)
            self._scan_discount(node)
            for t in node.targets:
                self._bind(t)
                self._note_call_binding(t, node.value)
            return
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            named = _target_name(node.target)
            if named and self._weakens_existing(node.target, named[0]):
                self._consider(named[0], named[1], node.value, node.lineno)
            self._expand_dict(node.value, node.lineno)
            self._scan_calls(node)
            self._bind(node.target)
            return
        if isinstance(node, (ast.AugAssign, ast.Import, ast.ImportFrom)):
            self._scan_discount(node)
            self._bind(getattr(node, "target", None) or node)
            self._scan_calls(node)
            return
        if isinstance(node, ast.Return) and node.value is not None:
            self._consider(self._fn[-1], "return", node.value, node.lineno)
            self._expand_dict(node.value, node.lineno)
            self._scan_calls(node)
            return
        self._scan_calls(node)
        self._scan_narrowing(node)
        self._scan_discount(node)
        self._scan_waiver_skip(node)

    def _scan_calls(self, node: ast.stmt) -> None:
        """A guarded call to an always-weakening helper is a relaxation site."""
        if not self.weakening_fns or not self._guards:
            return
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            fname = _callee_name(sub)
            if not fname:
                continue
            leaf = fname.split(".")[-1]
            if leaf in self.weakening_fns and leaf != self._fn[-1]:
                self._emit(target=leaf, kind="call", polarity="risk",
                           written=("calls " + leaf + "() which writes "
                                    + self.weakening_fns[leaf]),
                           lineno=getattr(sub, "lineno", node.lineno))

    def _note_call_binding(self, target: ast.expr, value: ast.expr) -> None:
        """Remember that a name holds the result of a call.

        ``x = model.score(t)`` then ``if x is None`` is an unavailability check
        on that call. The same test on a parameter is a precondition. Awaits
        and comprehensions over a call count too.
        """
        if isinstance(value, ast.Await):
            value = value.value
        is_call = isinstance(value, ast.Call) or any(
            isinstance(s, ast.Call) for s in ast.walk(value))
        if not is_call:
            return
        named = _target_name(target)
        if named:
            self._from_call[-1].add(named[0])

    def _weakens_existing(self, target: ast.expr, name: str) -> bool:
        """Is there a prior verdict here for the write to weaken?

        Attribute and subscript targets always qualify: the object being
        mutated was constructed somewhere else. A bare local qualifies only if
        it is already bound, which is what separates a relaxation from an
        ordinary initialiser sitting below a bail-out.
        """
        if not isinstance(target, ast.Name):
            return True
        return self._is_bound(name)

    # -- shape 2: narrowing a collection of detections --------------------
    def _scan_narrowing(self, node: ast.stmt) -> None:
        """A shorter findings list is a weaker verdict."""
        if not self._guards:
            return
        # xs = [x for x in xs if COND]   /   xs = list(filter(...))
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            named = _target_name(node.targets[0])
            if named and RISK_COLLECTION.search(named[0]) and self._is_bound(named[0]):
                v = node.value
                if isinstance(v, (ast.ListComp, ast.SetComp, ast.DictComp)):
                    gens = getattr(v, "generators", [])
                    if any(g.ifs for g in gens) and named[0] in _names_in(v):
                        self._emit(target=named[0], kind="comprehension",
                                   polarity="risk",
                                   written="rebound to a filtered subset of itself",
                                   lineno=node.lineno, shape="narrowing")
                        return
                if isinstance(v, ast.Call):
                    fn = (_callee_name(v) or "").split(".")[-1]
                    if fn in ("filter", "list", "set") and named[0] in _names_in(v):
                        if fn != "filter" and not any(
                                isinstance(a, ast.Call)
                                and (_callee_name(a) or "").split(".")[-1] == "filter"
                                for a in v.args):
                            return
                        self._emit(target=named[0], kind="filter",
                                   polarity="risk",
                                   written="rebound to a filtered subset of itself",
                                   lineno=node.lineno, shape="narrowing")
                        return
        # xs.remove(y) / xs.pop(i) / del xs[i]
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            fn = _callee_name(node.value)
            if fn and "." in fn:
                base, meth = fn.rsplit(".", 1)
                if meth in NARROWING_METHODS and RISK_COLLECTION.search(
                        base.rsplit(".", 1)[-1]):
                    self._emit(target=base, kind="mutation", polarity="risk",
                               written=f"{meth}() removes a detection",
                               lineno=node.lineno, shape="narrowing")
        if isinstance(node, ast.Delete):
            for t in node.targets:
                named = _target_name(t)
                if named and RISK_COLLECTION.search(named[0]):
                    self._emit(target=named[0], kind="mutation", polarity="risk",
                               written="del removes a detection",
                               lineno=node.lineno, shape="narrowing")

    # -- shape 3: arithmetic that moves a score toward benign --------------
    def _scan_discount(self, node: ast.stmt) -> None:
        """``score *= 0.5`` weakens a verdict without writing a constant."""
        if not self._guards:
            return
        if isinstance(node, ast.AugAssign):
            named = _target_name(node.target)
            if not named or _polarity_of(named[0]) != "risk":
                return
            op = node.op
            down = isinstance(op, (ast.Sub, ast.Div, ast.FloorDiv))
            if isinstance(op, ast.Mult) and isinstance(node.value, ast.Constant):
                v = node.value.value
                down = isinstance(v, (int, float)) and not isinstance(v, bool) and v < 1
            if down:
                self._emit(target=named[0], kind="augassign", polarity="risk",
                           written=f"discounted by {_src(self.source, node.value)}",
                           lineno=node.lineno, shape="discount")
            return
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            named = _target_name(node.targets[0])
            if not named or _polarity_of(named[0]) != "risk":
                return
            if not self._is_bound(named[0]) and isinstance(node.targets[0], ast.Name):
                return
            v = node.value
            # score = min(score, cap)
            if isinstance(v, ast.Call) and (_callee_name(v) or "") == "min":
                if named[0] in _names_in(v):
                    self._emit(target=named[0], kind="clamp", polarity="risk",
                               written="clamped down by min()",
                               lineno=node.lineno, shape="discount")
                    return
            # score = score * 0.5   /   score - penalty
            if isinstance(v, ast.BinOp) and named[0] in _names_in(v):
                down = isinstance(v.op, (ast.Sub, ast.Div, ast.FloorDiv))
                if isinstance(v.op, ast.Mult):
                    for side in (v.left, v.right):
                        if (isinstance(side, ast.Constant)
                                and isinstance(side.value, (int, float))
                                and not isinstance(side.value, bool)
                                and side.value < 1):
                            down = True
                if down:
                    self._emit(target=named[0], kind="assign", polarity="risk",
                               written=f"discounted: {_src(self.source, v)}"[:60],
                               lineno=node.lineno, shape="discount")

    # -- shape 4: a waiver that skips the check entirely -------------------
    def _scan_waiver_skip(self, node: ast.stmt) -> None:
        """``if x in ALLOWLIST: continue`` does not weaken a verdict, it
        prevents one. The audit obligation applies with full force."""
        if not self._guards:
            return
        bare_exit = (isinstance(node, (ast.Continue, ast.Break))
                     or (isinstance(node, ast.Return) and node.value is None)
                     or (isinstance(node, ast.Pass)))
        if not bare_exit:
            return
        for text, _ln in self._guards:
            # A NEGATED membership guard is the opposite of a waiver: reaching
            # the branch means the subject was NOT on the list. Walking the
            # whole guard stack without this check reported the exclusion list
            # again at the next `continue` below it, which is a double count.
            if text.startswith("not ("):
                continue
            try:
                t = ast.parse(text, mode="eval").body
            except SyntaxError:
                continue
            for sub in ast.walk(t):
                if isinstance(sub, ast.UnaryOp) and isinstance(sub.op, ast.Not):
                    continue
                if isinstance(sub, ast.Compare) and any(
                        isinstance(o, ast.In) for o in sub.ops):
                    for c in sub.comparators:
                        nm = None
                        if isinstance(c, ast.Name):
                            nm = c.id
                        elif isinstance(c, ast.Attribute):
                            nm = c.attr
                        if nm and WAIVER_COLLECTION.search(nm):
                            self._emit(
                                target=nm, kind="skip", polarity="permit",
                                written="check skipped for a listed subject",
                                lineno=node.lineno, shape="waiver-skip")
                            return

    def _expand_dict(self, value: ast.expr, lineno: int) -> None:
        """A dict literal is a bundle of writes; consider each key its own.

        This is how our own distress site relaxes: it rebinds the whole record
        with ``{"is_passive_self_harm": False, "strength": 0.0}`` rather than
        touching a field, and the bound name carries no polarity at all.
        """
        if not isinstance(value, ast.Dict) or not value.keys:
            return
        for k, v in zip(value.keys, value.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                self._consider(k.value, "dict-key", v, getattr(k, "lineno", lineno))

    # -- the test ----------------------------------------------------------
    def _consider(self, name: str, kind: str, value: ast.expr,
                  lineno: int) -> None:
        if not self._guards:
            return               # unguarded: an initialiser, not a relaxation
        polarity = _polarity_of(name)
        if polarity is None:
            return
        written = _is_benign_constant(value, polarity)
        if written is None:
            return
        self._emit(target=name, kind=kind, polarity=polarity, written=written,
                   lineno=lineno)

    def _emit(self, *, target: str, kind: str, polarity: str, written: str,
              lineno: int, shape: str = "benign-write") -> None:
        _floor_ref = next(
            iter(sorted(self._guard_vocab() & self.hard_block_vocab)), None)
        insp = _GuardInspector(self.local_fns)
        for text, _ln in self._guards:
            if not text:
                continue
            try:
                insp.visit(ast.parse(text, mode="eval"))
            except SyntaxError:
                continue         # synthesised `for`/`except`/`match` guard text
        audit = _branch_audit_symbol(self._block[-1]) if self._block else None

        self.out.append(Candidate(
            subject=self.subject,
            module=self.module,
            line=lineno,
            function=self._fn[-1],
            target=target,
            kind=kind,
            polarity=polarity,
            written=written,
            guards=[g for g, _ in self._guards],
            guard_lines=[ln for _, ln in self._guards],
            bounded=insp.bound_symbol is not None,
            bound_symbol=insp.bound_symbol,
            bound_via=insp.bound_via,
            audited=audit is not None,
            audit_symbol=audit,
            from_handler=self._in_handler > 0,
            reaches_hard_block=bool(self.hard_block_vocab) and not _floor_ref,
            hard_block_ref=_floor_ref,
            domain=classify_domain(
                [g for g, _ in self._guards],
                from_handler=self._in_handler > 0,
                params=set(self._params[-1]),
                from_call=set(self._from_call[-1]),
            ),
            shape=shape,
        ))


def _unconditional_weakening_writes(fn: ast.AST) -> List[Tuple[str, str]]:
    """Benign writes at the OWN top level of a function, under no condition.

    Top level only, deliberately. A benign write already guarded inside the
    helper is a relaxation in its own right and is reported at its own line;
    counting the calls to it as well would report one site twice. What this
    finds is the other factoring: a helper that always weakens, whose only
    condition sits at the caller.
    """
    body = getattr(fn, "body", [])
    out: List[Tuple[str, str]] = []

    def consider(name: str, value: ast.expr) -> None:
        polarity = _polarity_of(name)
        if polarity is None:
            return
        written = _is_benign_constant(value, polarity)
        if written is not None:
            out.append((name, written))

    # Flow-aware for the same reason the main walker is, and getting this wrong
    # produced a false positive on our own REPAIRED code: after the fix,
    # _demote_to_safe still writes SAFE at its top level, but a preceding
    # `if not _may_demote(sem): ... return` guards it. Reading top-level
    # position as "unconditional" would keep convicting the three call sites of
    # a defect that had already been closed.
    # A bare name must already exist for a write to it to WEAKEN anything,
    # exactly as in the main walker. Without this, a helper that opens with
    # `max_score = 0.0` before a loop that raises it counts as a function that
    # always weakens, and every guarded call to it becomes a candidate.
    a = getattr(fn, "args", None)
    bound: set = set()
    if a is not None:
        bound = {p.arg for p in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        if a.vararg:
            bound.add(a.vararg.arg)
        if a.kwarg:
            bound.add(a.kwarg.arg)

    guarded = False
    for st in body:
        if guarded:
            break
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            targets = (st.targets if isinstance(st, ast.Assign) else [st.target])
            for t in targets:
                named = _target_name(t)
                if named and st.value is not None:
                    if not isinstance(t, ast.Name) or named[0] in bound:
                        consider(named[0], st.value)
            if isinstance(st.value, ast.Dict):
                for k, v in zip(st.value.keys, st.value.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        consider(k.value, v)
            for t in targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name):
                        bound.add(sub.id)
        elif isinstance(st, ast.Assert):
            guarded = True
        elif isinstance(st, ast.If) and (
                _always_exits(st.body)
                or (st.orelse and _always_exits(st.orelse))):
            guarded = True
    return out


def _collect_weakening_functions(tree: ast.AST) -> Dict[str, str]:
    """Same-module helpers that always weaken. Name -> what they write."""
    out: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            writes = _unconditional_weakening_writes(node)
            if writes:
                out[node.name] = ", ".join(f"{n}={w}" for n, w in writes[:4])
    return out


def _collect_local_functions(tree: ast.AST) -> Dict[str, ast.AST]:
    """Every function defined in this module, by bare name.

    Bare name, so a method and a module function of the same name collide. The
    collision costs precision on the bound question only, never soundness of
    the write detection, and resolving it properly needs the type information a
    static scan does not have.
    """
    out: Dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, node)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Driving it over a tree
# ═══════════════════════════════════════════════════════════════════════════

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
              ".mypy_cache", ".pytest_cache", "build", "dist", ".eggs",
              "site-packages"}


def iter_python_files(root: pathlib.Path, *,
                      skip_tests: bool = True) -> Iterable[pathlib.Path]:
    """Every .py under root, tests excluded by default.

    Tests are excluded because a test that asserts a relaxation is refused
    contains the same syntax as the relaxation itself, and counting those would
    inflate every number here with code that ships to nobody.

    Every exclusion is applied to the path RELATIVE to the scan root. Matching
    on the absolute path instead is a fail-open bug and this function had it:
    a subject cloned under any directory whose name begins with ``test_``, or
    under a path containing ``build`` or ``venv``, was skipped in its entirety
    and the scan returned zero findings that read exactly like a clean result.
    Found by pytest, whose ``tmp_path`` is named after the test using it.
    """
    root = root.resolve()
    for p in sorted(root.rglob("*.py")):
        try:
            rel_parts = p.resolve().relative_to(root).parts
        except ValueError:               # pragma: no cover - symlink escape
            continue
        if set(rel_parts) & _SKIP_DIRS:
            continue
        if skip_tests and any(
            part in ("tests", "test", "testing", "conftest.py")
            or part.startswith("test_") or part.endswith("_test.py")
            for part in rel_parts
        ):
            continue
        yield p


def declares_hard_block(root: pathlib.Path) -> List[Tuple[str, int, str]]:
    """Does this subject declare a category it treats as unreleasable?

    R14-c is engaged only if it does. An empty list means NOT ENGAGED, which
    this module is careful never to render as a pass.
    """
    root = root.resolve()
    hits: List[Tuple[str, int, str]] = []
    for path in iter_python_files(root):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            m = HARD_BLOCK_DECLARATION.search(line)
            if m:
                rel = str(path.relative_to(root)).replace("\\", "/")
                hits.append((rel, i, m.group(0)))
    return hits


def hard_block_vocabulary(root: pathlib.Path) -> Set[str]:
    """Symbols that declare an unreleasable category, plus the categories in them.

    ``NEVER_ALLOW = frozenset({"csam", "self_harm"})`` contributes the symbol and
    both strings, so a relaxing function can be checked for any reference to the
    floor by name or by value.
    """
    vocab: Set[str] = set()
    for path in iter_python_files(root):
        # A scanner that scans itself must exclude itself: this module's own
        # HARD_BLOCK_DECLARATION pattern and field names would otherwise become
        # vocabulary and match anything that mentions them.
        if path.name in ("maryada_discover.py", "maryada.py"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            names += [t.attr for t in targets if isinstance(t, ast.Attribute)]
            if not any(HARD_BLOCK_DECLARATION.search(n) for n in names):
                continue
            vocab.update(names)
            if node.value is not None:
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        tok = sub.value.strip()
                        # a category is an identifier-shaped token, not prose and
                        # not a regex; without this the pattern source of a
                        # compiled declaration lands in the vocabulary
                        if tok and len(tok) <= 48 and _CATEGORY_TOKEN.match(tok):
                            vocab.add(tok)
    return vocab


def discover(root: pathlib.Path, *, subject: str, skip_tests: bool = True
             ) -> Tuple[List[Candidate], Dict[str, int]]:
    """Scan a tree and propose relaxation sites. Pure read; nothing imported."""
    root = root.resolve()
    found: List[Candidate] = []
    vocab = hard_block_vocabulary(root)
    stats = {"files": 0, "parsed": 0, "parse_errors": 0}
    for path in iter_python_files(root, skip_tests=skip_tests):
        stats["files"] += 1
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            stats["parse_errors"] += 1
            continue
        stats["parsed"] += 1
        rel = str(path.relative_to(root)).replace("\\", "/")
        w = _RelaxationWalker(subject, rel, src,
                              _collect_local_functions(tree),
                              _collect_weakening_functions(tree),
                              hard_block_vocab=vocab)
        w.walk_block(tree.body)          # type: ignore[attr-defined]
        found.extend(w.out)
    return found, stats
