"""Anupalabdhi — build-time *attested-liveness* certification (R3), plus a static
fail-open AST scan, as a sibling to ``engine.pramana`` (same relationship
``saksin.py`` has to ``pramana.py``).

Anupalabdhi (qualified non-perception) is the sixth pramāṇa in Bhāṭṭa-Mīmāṃsā /
Advaita: valid knowledge of an *absence* from non-perception — but only under
*yogyānupalabdhi*, the qualifier that non-perception counts as knowledge of an
absence ONLY when the object would have been perceived were it present (the
perceiver's capacity to perceive must itself be established). The control-code
reading: silence from a dead monitor must never count as a clean signal — a
no-alarm result is admissible evidence only if the arm's liveness at decision
time was itself attested.

This module implements the **two-part check** the Stage-A scoping specifies:

  * **R3 (composition-level, decidable).**  ``certify_r3()`` reads each
    ``EvidenceSource.on_unavailable`` (declared on the source in ``pramana.py``)
    and enforces, over a caller-supplied *safety-critical* subset, that no
    safety-critical arm effectively fails OPEN.  ``eff(s)`` fail-safe-defaults an
    *undeclared* arm (``on_unavailable=None``) to FAIL_OPEN — unattested liveness
    cannot be credited as clean.  Undeclared arms are ALWAYS reported as an
    unattested-liveness advisory; under ``strict_r3=True`` an undeclared arm in
    the safety-critical set additionally becomes a hard R3 failure (treated
    exactly as harshly as a declared FAIL_OPEN — "nobody said" and "somebody said
    FAIL_OPEN" produce identical risk at decision time).  Decidable in O(|S|) by
    direct inspection of the finite declared labelling — no arm is executed, no
    statistical estimate anywhere.  Sound and complete *relative to the
    declaration*: a declared FAIL_CLOSED whose implementation silently returns a
    safe sentinel on an unhandled branch is not something R3 can learn — which is
    exactly why the AST scanner below is the orthogonal, complementary check.

  * **Implementation-level AST rule.**  ``scan_fail_open()`` flags the concrete
    *code shape* of a silent fail-open: a "safe / permissive" sentinel returned
    or assigned on an except / no-backend / is-None fallback branch, plus three
    additional idioms Stage A found in real external systems that a bare
    ``ast.Constant`` visitor cannot catch (see COVERAGE below). Static, no
    execution, no import of the scanned module.

COVERAGE of the AST rule (stated honestly, exactly as ``saksin.py`` states its
own getattr/eval dynamic-dispatch limitation, and R1/R2 state theirs):
  Shapes this scanner CATCHES:
    1. ``bare_constant``       — ``return False`` / ``x = False`` / ``x: bool = False``
       (a safe-sentinel ``ast.Constant``) inside an except / none-guard /
       no-backend-guard branch. Guard branches are polarity-aware: for
       ``if x is None:`` the fallback branch is the ``body``; for
       ``if x is not None:`` / ``if x != None:`` it is the ``orelse``; for a
       truthy config guard (``if server_endpoint:``) it is likewise the
       ``orelse`` (all three inversions were false negatives before the
       senior-review pass).
    2. ``tuple_first_constant``— ``return False, []`` (first tuple element is a
       safe sentinel) inside those same guard branches.
    3. ``safe_constructor_call``— ``result = PassResult()`` (a call to a declared
       "safe result" class) inside those same guard branches.
    4. ``dict_get_default``    — ``d.get(key, True)`` (a dict ``.get`` whose
       default is a safe sentinel — the default IS the silent fallback, so this
       is matched wherever it appears, not only in a guard branch).
    5. ``ctor_kwarg_sentinel`` — ``ScanResult(decision=ScanDecision.ALLOW, ...)``
       / ``InjectionDetectionResult(is_injection=False, ...)`` (a constructor
       whose keyword argument is a safe sentinel — a Constant, or a declared
       safe enum member). Matched wherever it appears (fall-through defaults and
       seed initialisers are the real external shape, not only guard branches).
    6. ``enum_member_default`` — a declared safe enum member (e.g.
       ``ScanDecision.ALLOW``) as a bare return/assign value, or as the ``orelse``
       of a conditional expression (``max(...) if decisions else ScanDecision.ALLOW``).
  Shapes 4/5/6 are the three extensions Stage A §3.1/§3.5 identified as needed to
  catch NeMo's mapping functions (dict ``.get`` default) and PurpleLlama's
  aggregator/scanners (enum-member and constructor-keyword ALLOW defaults) — the
  two strongest external findings.

  Shapes this scanner does NOT catch (STATED LIMITATION, symmetric to Sakṣin's
  dynamic-dispatch caveat):
    * A fallback assembled through **dynamic dispatch** the AST walk cannot
      resolve — a ``getattr(mod, name)()`` fallback branch, an ``eval``-built
      call, or a runtime-config-selected code path — is invisible to a static
      walk by construction.
    * A safe-sentinel returned from a **helper the scanner does not follow**
      (interprocedural fail-open): the rule is intraprocedural/syntactic, so a
      guard that calls ``return _safe_default()`` where ``_safe_default`` itself
      returns the sentinel is not flagged here.
    * A **guarded fall-through** bare constant: ``if rules is not None: return
      check(rules)`` followed by a bare ``return False`` *after* the ``if``
      (reachable only when the guard failed, but lexically outside any branch).
      Branch-scoping shapes 1–3 to guard branches is what keeps the rule's
      false-positive rate usable — flagging every bare ``return False`` in a
      module would be noise — so the fall-through form of a *bare-constant*
      fallback is invisible by construction (the enum/ctor fall-through forms,
      shapes 5–6, ARE caught because their sentinels are distinctive).
    * Polarity is caller-declared, not inferred: which constant/enum member
      counts as the "permissive / safe" sentinel is supplied per scan
      (``safe_sentinels`` / ``safe_enum_members`` / ``safe_constructors``),
      exactly as ``saksin.scan_source`` takes a per-system ``read_surface``. The
      scanner reports the *syntactic shape*; whether a given hit is a genuine
      "couldn't-evaluate" fail-open versus a legitimately-decided permissive
      verdict is a semantic judgement made by reading the source, not by the AST.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from engine import pramana
from engine.pramana import EvidenceSource, GateComposition, OnUnavailable


# ═══════════════════════════════════════════════════════════════════════════
# Part A — R3: attested liveness on the safety-critical subset
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class R3CertificationResult:
    """Structured R3 verdict — mirrors ``pramana.CertificationResult``'s
    honest-report style (hard ``failures`` vs. non-fatal ``advisories``,
    ``as_dict()`` for machine-readable output)."""

    gate_name: str
    r3_passed: bool
    r1r2_passed: bool                                    # from the reused pramana.certify()
    strict_r3: bool
    safety_critical: List[str] = field(default_factory=list)
    # arm name -> eff(s).value  (declared label, or FAIL_OPEN if undeclared)
    effective_availability: Dict[str, str] = field(default_factory=dict)
    unattested_arms: List[str] = field(default_factory=list)   # on_unavailable=None
    failures: List[str] = field(default_factory=list)          # hard R3 violations
    advisories: List[str] = field(default_factory=list)        # non-fatal residuals

    def as_dict(self) -> dict:
        return {
            "gate": self.gate_name,
            "r3_passed": self.r3_passed,
            "r1r2_passed": self.r1r2_passed,
            "strict_r3": self.strict_r3,
            "safety_critical": sorted(self.safety_critical),
            "effective_availability": dict(self.effective_availability),
            "unattested_arms": list(self.unattested_arms),
            "failures": list(self.failures),
            "advisories": list(self.advisories),
        }


def _eff(source: EvidenceSource) -> OnUnavailable:
    """eff(s): the arm's declared absence-semantics, fail-safe-defaulting an
    *undeclared* arm to FAIL_OPEN — silence about liveness is not admissible as
    clean (yogyānupalabdhi)."""
    return source.on_unavailable if source.on_unavailable is not None else OnUnavailable.FAIL_OPEN


def certify_r3(
    composition: GateComposition,
    *,
    safety_critical: Optional[Set[str]] = None,
    strict_r3: bool = False,
) -> R3CertificationResult:
    """Certify attested liveness (R3) over a gate composition.

    R3 invariant (hard): ``for all s in crit(S): eff(s) != FAIL_OPEN``, where
    ``crit(S)`` is ``safety_critical`` (caller-supplied; defaults to every arm).
    ``eff(s)`` fail-safe-defaults an undeclared arm to FAIL_OPEN.

    Advisory (always reported): every arm with ``on_unavailable=None`` is an
    unattested-liveness advisory, regardless of criticality or ``strict_r3``.
    Under ``strict_r3=True`` an undeclared arm that is also safety-critical
    additionally becomes a hard failure.

    Hard failure (regardless of ``strict_r3``): any ``safety_critical`` name
    that matches no declared arm — a typo'd critical set must never silently
    un-protect the gate (senior-review fix).

    Reuses the SHIPPED, unmodified ``pramana.certify()`` for R1/R2 — R3 is layered
    on top and reads only the new ``on_unavailable`` field; the R1/R2 verdict is
    reported alongside so a caller sees both axes at once.
    """
    crit: Set[str] = set(safety_critical) if safety_critical is not None else {
        s.name for s in composition.sources
    }

    base = pramana.certify(composition)   # shipped R1/R2, unmodified

    failures: List[str] = []
    advisories: List[str] = []

    # A safety_critical name that matches NO declared arm must fail loudly:
    # a misspelled critical set would otherwise silently un-protect the gate
    # (crit ∩ arms = ∅ -> vacuous R3 PASS over a declared FAIL_OPEN arm).
    declared_names = {s.name for s in composition.sources}
    unknown_crit = sorted(crit - declared_names)
    if unknown_crit:
        failures.append(
            f"R3 unknown-arm FAILURE: safety_critical name(s) {unknown_crit} match no "
            f"declared arm of gate {composition.gate_name!r} (declared arms: "
            f"{sorted(declared_names)}). A critical set that names a non-existent arm "
            f"cannot be attested — fail loudly rather than certify a gate the caller "
            f"did not actually protect."
        )
    effective_availability: Dict[str, str] = {}
    unattested: List[str] = []

    for s in composition.sources:
        eff = _eff(s)
        effective_availability[s.name] = eff.value
        is_crit = s.name in crit

        if s.on_unavailable is None:
            unattested.append(s.name)
            advisories.append(
                f"R3 advisory (unattested liveness): arm {s.name!r} did not declare "
                f"on_unavailable — its liveness at decision time is unattested; a "
                f"no-alarm result from it cannot be scored clean (yogyānupalabdhi: "
                f"knowledge of an absence requires the capacity to perceive it be "
                f"established first)."
            )
            if strict_r3 and is_crit:
                failures.append(
                    f"R3 undeclared-absence FAILURE: safety-critical arm {s.name!r} "
                    f"did not declare on_unavailable; under strict_r3 an undeclared "
                    f"critical arm is treated exactly as harshly as a declared "
                    f"FAIL_OPEN — 'nobody said' and 'somebody said FAIL_OPEN' produce "
                    f"the identical risk at decision time."
                )
            continue

        # Declared absence-semantics.
        if is_crit and s.on_unavailable is OnUnavailable.FAIL_OPEN:
            failures.append(
                f"R3 fail-open FAILURE: safety-critical arm {s.name!r} declares "
                f"on_unavailable=FAIL_OPEN — a dead monitor's silence would be scored "
                f"as a clean signal (yogyānupalabdhi violated: liveness not attested)."
            )

    r3_passed = len(failures) == 0
    return R3CertificationResult(
        gate_name=composition.gate_name,
        r3_passed=r3_passed,
        r1r2_passed=base.passed,
        strict_r3=strict_r3,
        safety_critical=sorted(crit),
        effective_availability=effective_availability,
        unattested_arms=unattested,
        failures=failures,
        advisories=advisories,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Part B — static AST scan: safe-sentinel fail-open code shapes
# ═══════════════════════════════════════════════════════════════════════════

_CONFIG_HINT = ("url", "endpoint", "backend", "config", "api", "server", "nim",
                "model", "client", "rules")


def _dotted_name(node: ast.expr) -> Optional[str]:
    """Return the dotted name of an attribute/name chain (e.g. ``ScanDecision.ALLOW``)
    or ``None`` if it is not a pure attribute-of-name chain."""
    parts: List[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _none_guard_branches(test: ast.expr) -> Set[str]:
    """Which branch(es) of an ``if`` are the *absence* (x-is-None) branch.

    ``x is None`` / ``x == None``      -> the absence branch is ``body``.
    ``x is not None`` / ``x != None``  -> the absence branch is ``orelse``:
        the fallback lives in the ``else``. Scanning only ``body`` for BOTH
        polarities was a real false negative (an
        ``if rules is not None: ... else: return False`` fallback was invisible,
        and the happy path was scanned instead) — fixed in the senior-review
        pass; boolean combinations are handled conservatively (each positive
        none-comparison votes ``body``, each negated one votes ``orelse``,
        ``not (...)`` flips the inner vote).
    """
    branches: Set[str] = set()
    if isinstance(test, ast.Compare):
        if any(isinstance(c, ast.Constant) and c.value is None for c in test.comparators):
            negated = any(isinstance(op, (ast.IsNot, ast.NotEq)) for op in test.ops)
            branches.add("orelse" if negated else "body")
    elif isinstance(test, ast.BoolOp):
        for v in test.values:
            branches |= _none_guard_branches(v)
    elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        branches |= {"orelse" if b == "body" else "body"
                     for b in _none_guard_branches(test.operand)}
    return branches


def _name_is_configish(node: ast.expr) -> bool:
    txt = ""
    if isinstance(node, ast.Name):
        txt = node.id.lower()
    elif isinstance(node, ast.Attribute):
        txt = node.attr.lower()
    return bool(txt) and any(h in txt for h in _CONFIG_HINT)


def _no_backend_guard_branches(test: ast.expr) -> Set[str]:
    """Which branch(es) of an ``if`` are the *no-backend* branch.

    ``not <configish>``    -> ``body`` (the original shape).
    ``if <configish>:``    -> ``orelse``: a truthy-config guard's fallback lives
        in the ``else`` (``if server_endpoint: result = call(...) else:
        result = False``) — the inverse polarity was a false negative fixed in
        the senior-review pass. Boolean combinations vote per operand.
    """
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        if _name_is_configish(test.operand):
            return {"body"}
        return {"orelse" if b == "body" else "body"
                for b in _no_backend_guard_branches(test.operand)}
    if _name_is_configish(test):
        return {"orelse"}
    if isinstance(test, ast.BoolOp):
        out: Set[str] = set()
        for v in test.values:
            out |= _no_backend_guard_branches(v)
        return out
    return set()


@dataclass
class FailOpenHit:
    lineno: int
    shape: str            # bare_constant | tuple_first_constant | safe_constructor_call
                          # | dict_get_default | ctor_kwarg_sentinel | enum_member_default
    branch_kind: str      # except | none-guard | no-backend-guard | <inline>
    stmt_kind: str        # return | assign | expr
    target: str           # variable assigned / "<return>" / the sentinel expression
    source_line: str

    def as_dict(self) -> dict:
        return {
            "lineno": self.lineno,
            "shape": self.shape,
            "branch_kind": self.branch_kind,
            "stmt_kind": self.stmt_kind,
            "target": self.target,
            "source_line": self.source_line,
        }


class _FailOpenVisitor(ast.NodeVisitor):
    """Flags the six fail-open code shapes documented in the module docstring.

    Shapes 1–3 (bare constant / tuple-first / safe-constructor call) are
    *branch-scoped*: only flagged lexically inside an except / none-guard /
    no-backend-guard branch, because outside such a branch a bare ``return False``
    is ordinary control flow, not a fallback.  Shapes 4–6 (dict ``.get`` default /
    constructor-keyword sentinel / enum-member default) are *inline*: the safe
    default is intrinsic to the expression, so they are flagged wherever they
    appear (the real external instances are fall-through defaults and seed
    initialisers, not guard branches)."""

    def __init__(
        self,
        source: str,
        *,
        safe_sentinels=(False,),
        safe_enum_members: FrozenSet[str] = frozenset(),
        safe_constructors: FrozenSet[str] = frozenset(),
        safe_dict_items: FrozenSet[Tuple[str, object]] = frozenset(),
        safe_default_names: FrozenSet[str] = frozenset(),
    ):
        self._lines = source.splitlines()
        self._safe = safe_sentinels
        self._enum = safe_enum_members
        self._ctors = safe_constructors
        self._dict_items = safe_dict_items
        self._safe_default_names = safe_default_names
        # Names assigned a declared-safe constant anywhere in this module — the
        # precondition for shape 8. Collected once up front so the handler check
        # stays a cheap set intersection.
        self._permissive_defaults: Set[str] = set()
        if safe_default_names:
            for n in ast.walk(ast.parse(source)):
                tgt = None
                if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name):
                    tgt = n.targets[0].id
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                    tgt = n.target.id
                if tgt and self._is_safe_constant(getattr(n, "value", None)):
                    self._permissive_defaults.add(tgt)
        self.hits: List[FailOpenHit] = []

    # -- helpers ----------------------------------------------------------

    def _src(self, lineno: int) -> str:
        return self._lines[lineno - 1].strip() if 0 < lineno <= len(self._lines) else ""

    def _is_safe_constant(self, node: Optional[ast.expr]) -> bool:
        # Type-strict membership: Python treats ``True == 1`` and ``False == 0``,
        # so a plain ``in`` would flag ``k=1`` / ``count=0`` as a bool sentinel.
        # Match value AND exact type so a bool sentinel only matches a bool const.
        if not isinstance(node, ast.Constant):
            return False
        return any(type(node.value) is type(s) and node.value == s for s in self._safe)

    def _is_safe_enum(self, node: Optional[ast.expr]) -> bool:
        name = _dotted_name(node) if node is not None else None
        return name is not None and name in self._enum

    def _safe_dict_hit(self, node: Optional[ast.expr]) -> Optional[str]:
        """Shape 7: a returned/assigned DICT LITERAL carrying a permissive item.

        The shipped fail-open shape in this codebase is not a bare sentinel — it
        is a dict:

            except Exception:
                return {"ran": False, "stable": True, ...}
            except Exception:
                return {"category": "SAFE", "confidence": 0.0}

        Shapes 1-3 cannot see either, because the returned VALUE is an
        ``ast.Dict``, not a constant. Polarity stays CALLER-DECLARED (which
        key/value pairs mean "permissive"), exactly as with ``safe_sentinels`` /
        ``safe_constructors`` — this module never infers which outcome is the
        safe one. Returns the matched ``key=value`` label, or None.

        Opt-in: ``safe_dict_items`` defaults to empty, so every existing call
        site keeps byte-identical six-shape behaviour.
        """
        if not self._dict_items or not isinstance(node, ast.Dict):
            return None
        for k, v in zip(node.keys, node.values):
            if not isinstance(k, ast.Constant) or not isinstance(v, ast.Constant):
                continue
            for want_k, want_v in self._dict_items:
                # Same type-strict match as _is_safe_constant: Python's
                # True == 1 would otherwise let confidence=1 match stable=True.
                if (k.value == want_k
                        and type(v.value) is type(want_v)
                        and v.value == want_v):
                    return f"{want_k}={want_v!r}"
        return None

    def _is_safe_ctor_call(self, node: Optional[ast.expr]) -> bool:
        if not isinstance(node, ast.Call):
            return False
        fname = _dotted_name(node.func)
        if fname is None:
            return False
        # match on the trailing class name too (e.g. `mod.PassResult()`)
        return fname in self._ctors or fname.split(".")[-1] in self._ctors

    def _add(self, lineno, shape, branch_kind, stmt_kind, target):
        self.hits.append(FailOpenHit(lineno, shape, branch_kind, stmt_kind, target, self._src(lineno)))

    # -- branch-scoped shapes (1–3) --------------------------------------

    def _scan_branch(self, body: List[ast.stmt], branch_kind: str) -> None:
        for node in body:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    self._flag_branch_value(sub.value, branch_kind, "return", "<return>", sub.lineno)
                elif isinstance(sub, ast.Assign):
                    tgt = ""
                    if sub.targets and isinstance(sub.targets[0], ast.Name):
                        tgt = sub.targets[0].id
                    self._flag_branch_value(sub.value, branch_kind, "assign", tgt, sub.lineno)
                elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                    # `result: bool = False` in a guard branch — an annotated
                    # assignment is the same fallback, and was a false negative
                    # before the senior-review pass.
                    tgt = sub.target.id if isinstance(sub.target, ast.Name) else ""
                    self._flag_branch_value(sub.value, branch_kind, "assign", tgt, sub.lineno)

    def _flag_branch_value(self, value, branch_kind, stmt_kind, target, lineno):
        if self._is_safe_constant(value):
            self._add(lineno, "bare_constant", branch_kind, stmt_kind, target)
        elif isinstance(value, ast.Tuple) and value.elts and self._is_safe_constant(value.elts[0]):
            self._add(lineno, "tuple_first_constant", branch_kind, stmt_kind, target)
        elif self._is_safe_ctor_call(value):
            self._add(lineno, "safe_constructor_call", branch_kind, stmt_kind, target)
        else:
            item = self._safe_dict_hit(value)      # shape 7 (opt-in)
            if item is not None:
                self._add(lineno, "safe_dict_item", branch_kind, stmt_kind,
                          target if target != "<return>" else item)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._scan_branch(node.body, "except")
        self._flag_swallowing_handler(node)
        self.generic_visit(node)

    # -- shape 8: log-only handler over a pre-assigned permissive default ----

    def _flag_swallowing_handler(self, node: ast.ExceptHandler) -> None:
        """Shape 8: an except handler that SWALLOWS, leaving a permissive default
        that was assigned before the ``try``.

        This is Ring 7's actual fail-open shape and it is invisible to shapes 1-7,
        because the handler returns and assigns nothing at all::

            force_hitl = False          # permissive default, assigned earlier
            try:
                ...                     # the check that would set it True
            except Exception as e:
                logger.warning(...)     # swallowed — default silently stands

        Downstream cannot distinguish "the check ran and found nothing" from
        "the check died", which is precisely the yogyānupalabdhi violation R3
        exists to name.

        Deliberately conservative, because a swallowing handler is an extremely
        common and usually-harmless idiom:
          * opt-in — fires only for names the caller declares in
            ``safe_default_names``;
          * the handler body must be log/pass ONLY (no Return, Raise, Assign,
            AnnAssign, AugAssign, Continue, Break anywhere inside it), so a
            handler that actually does something is never flagged;
          * the declared name must be assigned a declared-safe constant
            somewhere in the enclosing module before being left to stand.
        """
        if not self._safe_default_names:
            return
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Return, ast.Raise, ast.Assign, ast.AnnAssign,
                                ast.AugAssign, ast.Continue, ast.Break)):
                return                       # handler does something — not a swallow
        names = sorted(self._safe_default_names & self._permissive_defaults)
        if not names:
            return
        self._add(node.lineno, "swallowed_permissive_default", "except",
                  "swallow", ",".join(names))

    def visit_If(self, node: ast.If) -> None:
        branches = _none_guard_branches(node.test)
        kind = "none-guard"
        if not branches:
            branches = _no_backend_guard_branches(node.test)
            kind = "no-backend-guard"
        if "body" in branches:
            self._scan_branch(node.body, kind)
        if "orelse" in branches:
            self._scan_branch(node.orelse, kind)
        self.generic_visit(node)

    # -- inline shapes (4–6) ---------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # Shape 4: dict `.get(key, <safe default>)`.
        if isinstance(func, ast.Attribute) and func.attr == "get" and len(node.args) >= 2:
            if self._is_safe_constant(node.args[1]):
                default_repr = getattr(node.args[1], "value", "safe")
                self._add(node.lineno, "dict_get_default", "<inline>", "call",
                          f".get(..., {default_repr!r})")
        # Shape 5: constructor keyword arg that is a safe sentinel.
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if self._is_safe_constant(kw.value) or self._is_safe_enum(kw.value):
                self._add(node.lineno, "ctor_kwarg_sentinel", "<inline>", "call",
                          f"{kw.arg}=safe_sentinel")
                break
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self._flag_inline_enum(node.value, "return", "<return>", node.lineno)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        tgt = ""
        if node.targets and isinstance(node.targets[0], ast.Name):
            tgt = node.targets[0].id
        self._flag_inline_enum(node.value, "assign", tgt, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # `result: ScanDecision = ScanDecision.ALLOW` — annotated seed default.
        if node.value is not None:
            tgt = node.target.id if isinstance(node.target, ast.Name) else ""
            self._flag_inline_enum(node.value, "assign", tgt, node.lineno)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        # Shape 6 in ternary form: `... if cond else ScanDecision.ALLOW`.
        if self._is_safe_enum(node.orelse):
            self._add(node.orelse.lineno, "enum_member_default", "<inline>", "ternary-else",
                      _dotted_name(node.orelse) or "<enum>")
        self.generic_visit(node)

    def _flag_inline_enum(self, value, stmt_kind, target, lineno):
        # Shape 6: a bare declared-safe enum member as a return/assign value.
        if self._is_safe_enum(value):
            self._add(lineno, "enum_member_default", "<inline>", stmt_kind,
                      _dotted_name(value) or "<enum>")


def scan_fail_open(
    source: str,
    *,
    safe_sentinels=(False,),
    safe_enum_members: FrozenSet[str] = frozenset(),
    safe_constructors: FrozenSet[str] = frozenset(),
    safe_dict_items: FrozenSet[Tuple[str, object]] = frozenset(),
    safe_default_names: FrozenSet[str] = frozenset(),
) -> List[FailOpenHit]:
    """Scan module source for the fail-open code shapes. Pure AST, no execution.

    ``safe_sentinels`` / ``safe_enum_members`` / ``safe_constructors`` /
    ``safe_dict_items`` declare, per scan, which constants / enum-members /
    classes / dict entries count as the "permissive / safe" outcome — the
    polarity is caller-declared, never inferred (see the module docstring's
    stated limitation).

    ``safe_dict_items`` (shape 7, added 2026-07-26) defaults to EMPTY, so every
    pre-existing call site keeps byte-identical six-shape behaviour and every
    already-published anupalabdhi number remains valid. It exists because the
    shipped fail-open sites in this codebase return a dict literal
    (``{"stable": True, ...}``) rather than a bare sentinel, which the original
    six shapes structurally could not see — see
    tests/test_anupalabdhi_implementation.py.
    """
    visitor = _FailOpenVisitor(
        source,
        safe_sentinels=safe_sentinels,
        safe_enum_members=safe_enum_members,
        safe_constructors=safe_constructors,
        safe_dict_items=safe_dict_items,
        safe_default_names=safe_default_names,
    )
    visitor.visit(ast.parse(source))
    # de-dup: a line can be reached by both the branch walk and the inline walk.
    seen: Set[Tuple[int, str]] = set()
    uniq: List[FailOpenHit] = []
    for h in sorted(visitor.hits, key=lambda h: (h.lineno, h.shape)):
        key = (h.lineno, h.shape)
        if key not in seen:
            seen.add(key)
            uniq.append(h)
    return uniq


def scan_file_fail_open(
    path,
    *,
    safe_sentinels=(False,),
    safe_enum_members: FrozenSet[str] = frozenset(),
    safe_constructors: FrozenSet[str] = frozenset(),
    safe_dict_items: FrozenSet[Tuple[str, object]] = frozenset(),
    safe_default_names: FrozenSet[str] = frozenset(),
) -> List[FailOpenHit]:
    import pathlib
    p = pathlib.Path(path)
    source = p.read_text(encoding="utf-8", errors="replace")
    return scan_fail_open(
        source,
        safe_sentinels=safe_sentinels,
        safe_enum_members=safe_enum_members,
        safe_constructors=safe_constructors,
        safe_dict_items=safe_dict_items,
        safe_default_names=safe_default_names,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Chakravyuha's own Ring 8 gate, re-declared with measured liveness semantics
# ═══════════════════════════════════════════════════════════════════════════
# Absence-semantics below are MEASURED by static reading of the shipped arms
# (Stage A §4), NOT changed here — this module only *declares and measures* the
# existing behavior; it does not modify ring5_stability.py / ring7.py / ring8.py.
#
#   Ring 4 (policy)  -> pure in-process rule chain: cannot become "unavailable"
#       in the on_unavailable sense (no external dependency). An internal fault
#       propagates as an uncaught exception (fail-STOP: a 5xx, no decision object
#       at all) rather than a silent ALLOW. Modeled as FAIL_CLOSED because
#       fail-stop and fail-closed both DENY the request (they differ only in
#       mechanism — fail-stop kills the request, fail-closed emits an explicit
#       BLOCK/abstain); the 3-value enum has no dedicated fail-stop slot, so
#       fail-stop is documented here as a FAIL_CLOSED subtype (Stage A §4's own
#       suggested resolution), stated explicitly rather than left implicit.
#   Ring 5 (paraphrase stability) -> depends on semantic_engine.get_engine()
#       (ONNX+FAISS). On a _classify_variant exception a variant is silently
#       scored SAFE, and a paraphrase-generation error returns {"stable": True,
#       "ran": False}; both feed "stable": True into the Ring 8 gate. CONFIRMED
#       FAIL_OPEN (ring5_stability.py: the except at 255 returning
#       {"category": "SAFE", ...} at 257, and the except at 315 returning
#       "stable": True at 317-319).
#   Ring 7 (post-gen) -> same ONNX/FAISS engine for 2 of its 4 sub-checks
#       (semantic re-classification, except at ring7.py:126; Ashwatthama-hatah,
#       except at ring7.py:165): on exception each leaves its not-failing default
#       in place and contributes nothing — a silent no-op indistinguishable from
#       "ran and found nothing". Modeled FAIL_OPEN for its dependency-bearing
#       sub-checks (the other two passes are pure regex with no failure mode of
#       this kind).
#
# LINE-NUMBER DRIFT, and why these are now MACHINE-CHECKED (2026-07-26):
# the citations above were hand-read and went stale — the 2026-07-19 R4
# remediation refactored ring5_stability.py and shifted every one of the
# originally-cited ranges (the old "lines 206-215" now points at `_s5_use_llm`,
# an unrelated env predicate). A hand-maintained line citation is exactly the
# kind of claim this family says should not be trusted, so `scan_fail_open` is
# now RUN against these real files by tests/test_anupalabdhi_implementation.py
# rather than only against synthetic sources. See that module for the shape the
# scanner had to learn to see (a permissive key inside a returned dict literal),
# which is the shape the shipped code actually uses.

RING4_POLICY_LIVENESS = EvidenceSource(
    name=pramana.RING4_POLICY.name,
    pramana=pramana.RING4_POLICY.pramana,
    substrate=pramana.RING4_POLICY.substrate,
    on_unavailable=OnUnavailable.FAIL_CLOSED,   # fail-stop, modeled as FAIL_CLOSED subtype
    description=pramana.RING4_POLICY.description,
)
RING5_PARAPHRASE_LIVENESS = EvidenceSource(
    name=pramana.RING5_PARAPHRASE.name,
    pramana=pramana.RING5_PARAPHRASE.pramana,
    substrate=pramana.RING5_PARAPHRASE.substrate,
    on_unavailable=OnUnavailable.FAIL_OPEN,     # MEASURED (Stage A §4)
    description=pramana.RING5_PARAPHRASE.description,
)
RING7_POSTGEN_LIVENESS = EvidenceSource(
    name=pramana.RING7_POSTGEN.name,
    pramana=pramana.RING7_POSTGEN.pramana,
    substrate=pramana.RING7_POSTGEN.substrate,
    on_unavailable=OnUnavailable.FAIL_OPEN,     # MEASURED for 2 of 4 sub-checks (Stage A §4)
    description=pramana.RING7_POSTGEN.description,
)

RING8_GATE_WITH_LIVENESS = GateComposition(
    gate_name="ring8_commit_gate",
    sources=(RING4_POLICY_LIVENESS, RING5_PARAPHRASE_LIVENESS, RING7_POSTGEN_LIVENESS),
)


# The permissive shapes the shipped arms actually use. Caller-declared polarity,
# same discipline as safe_sentinels — this module never infers which outcome is
# "safe". Derived by reading the two arms' exception handlers (see the MEASURED
# block above); the point of R3_IMPL_* is that the reading is now MACHINE-CHECKED
# instead of resting on a hand-maintained line citation that silently went stale.
R3_IMPL_SAFE_DICT_ITEMS: FrozenSet[Tuple[str, object]] = frozenset({
    ("stable", True),        # ring5: paraphrase check reports "all variants agree"
    ("ran", False),          # ring5: check did not run, still feeds the gate
    ("category", "SAFE"),    # ring5: a variant that failed to classify scores SAFE
})
R3_IMPL_SAFE_DEFAULT_NAMES: FrozenSet[str] = frozenset({
    "force_hitl",            # ring7: stays False when the check dies
    "ashwatthama_gap",       # ring7: stays 0.0 when the entailment check dies
})

# arm name -> implementation files whose fail-open shape backs its declaration.
import pathlib as _pathlib

R3_IMPL_FILES: Dict[str, Tuple[str, ...]] = {
    "ring5_paraphrase_stability": ("engine/ring5_stability.py",),
    "ring7_postgen": ("engine/ring7.py",),
}

#: These are relative to backend/, and they used to be resolved against the
#: CWD. That made the certifier's ANSWER depend on where it was invoked:
#: from backend/ it read the files and reported corroborates=True with two
#: sites per arm; from the repository root the open failed, the handler
#: below wrote an entry with no implementation_corroborates key at all, and
#: any caller using .get() read None -- falsy, indistinguishable from "the
#: implementation does not corroborate fail_open". A check that could not
#: run, wearing the face of a check that ran and found nothing, which is the
#: precise shape this module exists to name. Anchoring to the module means
#: the cwd cannot change a verdict.
_BACKEND_ROOT = _pathlib.Path(__file__).resolve().parents[1]


def _impl_path(rel: str):
    return _BACKEND_ROOT / rel


def resolve_declared_path(rel: str):
    """Resolve a path recorded in an anupalabdhi report.

    The reports record paths RELATIVE TO backend/ on purpose: an absolute
    path would bake one machine into a committed artifact and would leak an
    author's directory tree into an anonymised submission. But until this
    existed nothing said what they were relative to, so each consumer
    resolved them against the cwd and inherited the very defect the
    certifier itself had -- a verdict that changed with the working
    directory. Consumers call this instead of guessing.
    """
    return _impl_path(rel)


def verify_r3_declaration_against_implementation() -> dict:
    """The other half of R3's two-part check, run on the REAL arms.

    ``certify_r3()`` reads declared ``on_unavailable`` labels. This function asks
    the orthogonal question the module docstring promises: does the CODE actually
    exhibit the fail-open shape the declaration claims? Until 2026-07-26
    ``scan_fail_open`` had only ever been exercised on synthetic source strings in
    tests, and returned ZERO hits on both real files — because the shipped shapes
    are a returned dict literal (ring5) and a log-only swallowing handler leaving
    a pre-assigned default (ring7), neither of which the original six shapes could
    see. Shapes 7 and 8 close that; both are opt-in, so the six-shape default and
    every published number are unchanged.

    Returns a per-arm report: declared label, whether the code corroborates it,
    and the exact sites found.
    """
    out: Dict[str, dict] = {}
    for arm, files in R3_IMPL_FILES.items():
        declared = next(
            (s.on_unavailable.value for s in RING8_GATE_WITH_LIVENESS.sources
             if s.name == arm and s.on_unavailable is not None), None)
        sites: List[dict] = []
        for rel in files:
            try:
                hits = scan_file_fail_open(
                    _impl_path(rel),
                    safe_sentinels=(True, False),
                    safe_dict_items=R3_IMPL_SAFE_DICT_ITEMS,
                    safe_default_names=R3_IMPL_SAFE_DEFAULT_NAMES,
                )
            except OSError as e:
                # FAIL CLOSED. Previously this recorded {"error": ...} and
                # moved on, leaving the arm with no corroboration key for a
                # caller to read as False. A certifier that cannot read the
                # code it certifies must refuse to answer, not answer quietly.
                raise FileNotFoundError(
                    "anupalabdhi cannot certify %s: declared implementation "
                    "file %r is unreadable (%s). Refusing to report a "
                    "corroboration verdict from a file that was never read."
                    % (arm, str(_impl_path(rel)), e)) from e
            sites.extend({"file": rel, **h.as_dict()} for h in hits)
        else:
            out[arm] = {
                "declared_on_unavailable": declared,
                "implementation_corroborates": bool(sites) and declared == "fail_open",
                "fail_open_sites": sites,
            }
    return {
        "gate": RING8_GATE_WITH_LIVENESS.gate_name,
        "arms": out,
        "note": (
            "Shapes 7 (returned dict literal carrying a permissive item) and 8 "
            "(log-only handler leaving a pre-assigned permissive default) are "
            "opt-in; the six-shape default behaviour is unchanged."
        ),
    }


def certify_chakravyuha_gate_r3() -> R3CertificationResult:
    """Run R3 against Chakravyuha's own Ring 8 commit gate with all three arms
    declared safety-critical and ``strict_r3=True``.

    Expected (and, per Stage A §4, self-critically so): R3 FAILS — both
    ``ring5_paraphrase_stability`` and ``ring7_postgen`` declare FAIL_OPEN and are
    safety-critical, so a silently-down embedder is indistinguishable at the gate
    from an embedder that ran and found every check clean. This is a genuinely
    self-critical result about the real shipped system, reported exactly as
    measured."""
    return certify_r3(
        RING8_GATE_WITH_LIVENESS,
        safety_critical={s.name for s in RING8_GATE_WITH_LIVENESS.sources},
        strict_r3=True,
    )
