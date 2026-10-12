"""Pramāṇa — build-time epistemic-independence certification for the commit gate.

Nyāya epistemology recognises four *pramāṇa* (valid means of knowledge):
Pratyakṣa (direct perception), Anumāna (inference), Upamāna (analogy/comparison),
Śabda (testimony from a reliable authority). Its rule: a claim is strong when
corroborated by *independent* pramāṇa — not by repeating the same means twice.

Ring 8 is a 3-way AND gate (policy + paraphrase-stability + post-gen reclassify).
Nothing in the codebase certified that those arms fail *independently*. Ring 5
and Ring 7 both bottom out in the same ONNX embedder, so a single embedder failure
can silently defeat two of the "three" arms at once — the exact "all monitors
share a single base model" failure the ensemble-monitoring literature
(arXiv:2605.15377 §6.3) flags but only measures post-hoc (pairwise Pearson ρ).

This module makes independence a **build-time, CI-checkable invariant** instead:

  * Each evidence source declares (a) its pramāṇa category and (b) the concrete
    *substrate* it reduces to (e.g. ``onnx_embedder``, ``policy_rules``).
  * ``certify(composition)`` enforces two hard rules over a gate:
      R1  distinct-pramāṇa floor  — ≥ ``min_distinct_pramana`` distinct categories.
      R2  no single-substrate gate — the arms must not ALL reduce to one substrate.
    and REPORTS (advisory, non-fatal) every pair of arms that share a substrate —
    the honest residual correlation.

The check runs at build/test time (and CI), never on the request hot path. It is
deliberately not faked into a clean pass: R1/R2 genuinely hold for the real gate,
while the residual Ring5≡Ring7 substrate correlation is surfaced, not hidden.

Design note: this is the productionised, statically-certified form of the
independence lever that arXiv:2605.15377 ("Diverse Signals Outweigh More Compute")
establishes empirically. No published AI-control system certifies monitor
independence as a design-time invariant; most assume it or measure it via
post-hoc ablation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple


class Pramana(enum.Enum):
    """The four Nyāya means of knowledge, as evidence-source categories."""

    PRATYAKSA = "pratyaksa"   # direct perception: a classifier / embedder score
    ANUMANA = "anumana"       # inference: a deterministic rule-chain
    UPAMANA = "upamana"       # analogy: nearest-labelled precedent / retrieval
    SABDA = "sabda"           # testimony: a cited external authority (a clause)
    # Added 2026-08-12. Caraka (Carakasaṃhitā, Vimānasthāna) adds a FIFTH means
    # beyond Nyāya's four: *yukti*, reasoning about an effect with several
    # co-operating causes, where no single pramāṇa is sufficient on its own and
    # the judgement comes from how the causes combine. Nyāya rejects it as
    # reducible to anumāna; the medical tradition keeps it precisely because
    # multi-causal judgement is its daily work.
    #
    # It earns a place here for the same reason: an arm that scores a
    # *composition* — an aggregate over other signals, a trajectory verdict over
    # many steps — is not making a direct observation (pratyakṣa), nor a
    # rule-chain inference (anumāna), nor citing testimony (śabda). Declaring
    # such an arm as one of those overstates what it is.
    #
    # Additive and safe: no shipped arm declares YUKTI, so R1's distinct-pramāṇa
    # count and every existing verdict are unchanged. Flagged "small, not
    # promoted" by the 2026-08-11 research session, and it is exactly that.
    YUKTI = "yukti"           # multi-causal judgement: a composition of causes

    def __repr__(self) -> str:  # nicer test output
        return f"Pramana.{self.name}"


class OnUnavailable(enum.Enum):
    """An arm's declared *absence-semantics*: what a gate does with this arm's
    verdict when the arm itself is unavailable (dependency down, model erroring,
    endpoint unreachable). This is the R3 (Anupalabdhi) axis — orthogonal to the
    R1/R2 independence axis ``certify()`` checks. Nothing in ``certify()`` reads
    this field; it is consumed only by ``engine.anupalabdhi.certify_r3()``.

    ``None`` (the field default) is a distinct, legal state meaning the arm never
    declared its absence-semantics at all — R3 tells "declared FAIL_CLOSED" apart
    from "never declared", because the two get different treatment (a hard
    failure vs. an advisory) depending on ``strict_r3``.
    """

    FAIL_CLOSED = "fail_closed"          # arm down -> treat as BLOCK/abstain (safe)
    FAIL_OPEN = "fail_open"              # arm down -> treat as ALLOW (silent pass)
    DEGRADE_TO_HITL = "degrade_to_hitl"  # arm down -> route to human review

    def __repr__(self) -> str:  # nicer test output
        return f"OnUnavailable.{self.name}"


class EnactmentRole(enum.Enum):
    """An arm's declared *enactment role*: whether it is evidence-only (may
    score and report, but must be structurally incapable of acting) or enacting.
    This is the R4 (Ṛtvij) axis — orthogonal to R1/R2 independence and to R3
    liveness. Nothing in ``certify()`` reads this field; it is consumed only by
    ``engine.rtvij.certify_r4()``, which statically verifies that a declared
    EVIDENCE_ONLY arm has no reachable call path to the action surface.

    ``None`` (the field default) is a distinct, legal state meaning the arm
    never declared its role — R4 reports undeclared arms as advisories, exactly
    as R3 does for undeclared absence-semantics.
    """

    EVIDENCE_ONLY = "evidence_only"   # may observe/score/report; must not act
    ENACTING = "enacting"             # legitimately acts (e.g. Ring 6 generation)

    def __repr__(self) -> str:  # nicer test output
        return f"EnactmentRole.{self.name}"


@dataclass(frozen=True)
class EvidenceSource:
    """One arm of a gate: what means of knowledge it is, and what it reduces to.

    ``substrate`` is the load-bearing field for independence: two sources with the
    same substrate share a single point of correlated failure *regardless* of
    their pramāṇa label. A paraphrase-stability check and a post-gen reclassifier
    are, on paper, two arms — but if both call the same ONNX embedder, one model
    failure defeats both, so they count as one independent arm.
    """

    name: str
    pramana: Pramana
    substrate: str
    on_unavailable: Optional[OnUnavailable] = None   # absence-semantics (R3); see OnUnavailable
    description: str = ""
    # Enactment role (R4); see EnactmentRole. Appended last (after description)
    # so no positional construction anywhere can silently shift — consumed only
    # by engine.rtvij.certify_r4(), never by certify().
    enactment_role: Optional[EnactmentRole] = None
    # ── R5 (vikalpa) axis: aggregation licence. Appended last again, for the
    # same reason enactment_role was — every existing positional construction
    # keeps its meaning. Consumed ONLY by engine.vikalpa.certify_r5(); certify()
    # below does not read either field, exactly as it does not read
    # on_unavailable (R3) or enactment_role (R4).
    #
    #   substrate_class — the DEPENDENCE PARTITION this arm belongs to. Coarser
    #     than ``substrate``: two arms may name different substrates and still
    #     fail together if both reduce to the same class of mechanism. R5-a
    #     licenses a weighted sum only ACROSS classes; within a class arms must
    #     combine by min/AND. ``None`` = undeclared, a distinct legal state that
    #     R5 reports rather than guesses at.
    #   alternate — the name of a declared stand-in for this arm. Admissible
    #     only as a substitute for the IMPLEMENTATION (guṇa) — which embedder
    #     computes s1 — never for the KIND of evidence (jāti): another arm may
    #     not stand in for a missing one. Correlation with the original is not a
    #     licence (VP 3.1.80, the *sāmyena* view Bhartṛhari rejects), so no
    #     correlation input exists on this dataclass by design.
    #   replicate_group — arms sharing this label are REPEATED DRAWS OF ONE
    #     MECHANISM, not distinct evidence. Appended 2026-08-17 after R5-a was
    #     run against a published ensemble of ten same-model monitors and
    #     returned a violation that is arguably wrong: pooling repeated draws is
    #     *estimation* of a single reading, not *composition* of independent
    #     ones, and R5-a as written could not tell the two apart. A group is
    #     NOT an escape hatch from R5-a: engine.vikalpa.check_r5e requires every
    #     member to sit in one substrate_class, so declaring two mechanisms
    #     replicates of each other is itself a violation. ``None`` = this arm is
    #     its own reading, which is the common case.
    substrate_class: Optional[str] = None
    alternate: Optional[str] = None
    replicate_group: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("EvidenceSource.name must be non-empty")
        if not isinstance(self.pramana, Pramana):
            raise TypeError("pramana must be a Pramana enum member")
        if not self.substrate:
            raise ValueError("EvidenceSource.substrate must be non-empty")
        if self.on_unavailable is not None and not isinstance(self.on_unavailable, OnUnavailable):
            raise TypeError("on_unavailable must be an OnUnavailable enum member or None")
        if self.enactment_role is not None and not isinstance(self.enactment_role, EnactmentRole):
            raise TypeError("enactment_role must be an EnactmentRole enum member or None")
        if self.substrate_class is not None and not isinstance(self.substrate_class, str):
            raise TypeError("substrate_class must be a str or None")
        if self.substrate_class is not None and not self.substrate_class:
            raise ValueError("substrate_class must be non-empty when declared")
        if self.alternate is not None and not isinstance(self.alternate, str):
            raise TypeError("alternate must be a str or None")
        if self.alternate is not None and not self.alternate:
            raise ValueError("alternate must be non-empty when declared")
        if self.alternate is not None and self.alternate == self.name:
            raise ValueError(
                f"EvidenceSource {self.name!r} declares itself as its own alternate; "
                f"an arm cannot stand in for itself"
            )
        if self.replicate_group is not None and not isinstance(self.replicate_group, str):
            raise TypeError("replicate_group must be a str or None")
        if self.replicate_group is not None and not self.replicate_group:
            raise ValueError("replicate_group must be non-empty when declared")


@dataclass(frozen=True)
class GateComposition:
    """The set of evidence sources feeding one gate (e.g. Ring 8)."""

    gate_name: str
    sources: Tuple[EvidenceSource, ...]

    def __post_init__(self) -> None:
        names = [s.name for s in self.sources]
        if len(names) != len(set(names)):
            dup = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"duplicate evidence-source name(s) in "
                             f"{self.gate_name!r}: {dup}")


@dataclass
class CertificationResult:
    """Structured verdict — the promote_gate.py-style honest report."""

    gate_name: str
    passed: bool
    distinct_pramana: Set[Pramana] = field(default_factory=set)
    substrates: Set[str] = field(default_factory=set)
    # (arm_a, arm_b, shared_substrate) — the advisory residual.
    shared_substrate_pairs: List[Tuple[str, str, str]] = field(default_factory=list)
    # How many arms remain if you collapse every shared-substrate group to one.
    effective_independent_arms: int = 0
    failures: List[str] = field(default_factory=list)   # hard-rule violations
    advisories: List[str] = field(default_factory=list)  # non-fatal residuals

    def as_dict(self) -> dict:
        return {
            "gate": self.gate_name,
            "passed": self.passed,
            "distinct_pramana": sorted(p.value for p in self.distinct_pramana),
            "substrates": sorted(self.substrates),
            "shared_substrate_pairs": [list(t) for t in self.shared_substrate_pairs],
            "effective_independent_arms": self.effective_independent_arms,
            "failures": list(self.failures),
            "advisories": list(self.advisories),
        }


def certify(
    composition: GateComposition,
    *,
    min_distinct_pramana: int = 2,
    forbid_single_substrate: bool = True,
) -> CertificationResult:
    """Certify a gate's evidence composition. Pure function — fully testable.

    Hard rules (a violation sets ``passed=False``):
      R1  the gate draws from ≥ ``min_distinct_pramana`` distinct pramāṇa.
      R2  (if ``forbid_single_substrate``) the arms do not ALL reduce to one
          substrate — otherwise a single dependency failure defeats the whole gate.

    Advisory (never fails the build, always reported):
      every pair of arms that share a substrate, and the resulting effective
      independent-arm count (shared-substrate arms collapse to one).
    """
    sources = composition.sources
    distinct_pramana: Set[Pramana] = {s.pramana for s in sources}
    substrates: Set[str] = {s.substrate for s in sources}

    failures: List[str] = []
    advisories: List[str] = []

    # R1 — distinct-pramāṇa floor.
    if len(distinct_pramana) < min_distinct_pramana:
        failures.append(
            f"R1 distinct-pramana floor: gate {composition.gate_name!r} draws from "
            f"{len(distinct_pramana)} distinct pramana "
            f"({sorted(p.value for p in distinct_pramana)}); "
            f"requires >= {min_distinct_pramana}. Corroboration by the same means "
            f"twice is not corroboration."
        )

    # R2 — no single-substrate gate.
    if forbid_single_substrate and len(sources) >= 2 and len(substrates) < 2:
        only = next(iter(substrates)) if substrates else "<none>"
        failures.append(
            f"R2 single-substrate gate: every arm of {composition.gate_name!r} "
            f"reduces to substrate {only!r}. A single dependency failure defeats "
            f"the entire gate (arXiv:2605.15377 shared-base-model failure)."
        )

    # Advisory residual — shared-substrate pairs + effective independence.
    by_substrate: Dict[str, List[str]] = {}
    for s in sources:
        by_substrate.setdefault(s.substrate, []).append(s.name)
    shared_pairs: List[Tuple[str, str, str]] = []
    for sub, names in by_substrate.items():
        if len(names) >= 2:
            for a, b in combinations(sorted(names), 2):
                shared_pairs.append((a, b, sub))
    for a, b, sub in shared_pairs:
        advisories.append(
            f"advisory: arms {a!r} and {b!r} share substrate {sub!r} — correlated "
            f"failure; they count as ONE independent arm, not two."
        )
    # Effective independence: distinct substrates (each substrate group is one arm).
    effective = len(substrates)

    passed = len(failures) == 0
    return CertificationResult(
        gate_name=composition.gate_name,
        passed=passed,
        distinct_pramana=distinct_pramana,
        substrates=substrates,
        shared_substrate_pairs=shared_pairs,
        effective_independent_arms=effective,
        failures=failures,
        advisories=advisories,
    )


# ── The real Ring 8 gate, declared from the actual codebase ────────────────────
# Substrates were confirmed by reading each arm's imports on 2026-07-03:
#   * Ring 4  -> engine/decision_engine.py + engine/policy.py  (rule-chain)   ANUMANA / policy_rules
#   * Ring 5  -> engine/ring5_stability.py -> semantic_engine.get_engine()    PRATYAKSA / onnx_embedder
#   * Ring 7  -> engine/ring7.py           -> semantic_engine.get_engine()    PRATYAKSA / onnx_embedder
# Keep this in sync with pipeline_rings.ring8_commit_gate_ring; the registry hook
# (RingRegistry.certify_gate) cross-checks the live declarations against it.

RING4_POLICY = EvidenceSource(
    name="ring4_policy",
    pramana=Pramana.ANUMANA,
    substrate="policy_rules",
    description="decision_engine + policy.py deterministic hierarchical rule chain",
)
RING5_PARAPHRASE = EvidenceSource(
    name="ring5_paraphrase_stability",
    pramana=Pramana.PRATYAKSA,
    substrate="onnx_embedder",
    description="ring5_stability re-classifies paraphrases via semantic_engine.get_engine()",
)
RING7_POSTGEN = EvidenceSource(
    name="ring7_postgen",
    pramana=Pramana.PRATYAKSA,
    substrate="onnx_embedder",
    description="ring7 re-classifies the LLM output via semantic_engine.get_engine()",
)

RING8_GATE = GateComposition(
    gate_name="ring8_commit_gate",
    sources=(RING4_POLICY, RING5_PARAPHRASE, RING7_POSTGEN),
)


def certify_ring8_gate() -> CertificationResult:
    """Certify the real Ring 8 commit gate as it exists in this repo.

    Expected (and CI-asserted) result today:
      * R1 PASSES  — 2 distinct pramana (ANUMANA + PRATYAKSA).
      * R2 PASSES  — not single-substrate (policy_rules != onnx_embedder).
      * advisory   — ring5 & ring7 share onnx_embedder; effective independence = 2.
    Adding a genuinely independent third arm (a UPAMANA faiss-precedent arm or a
    SABDA regulation-clause arm on a different substrate) would raise effective
    independence to 3 and clear the advisory.
    """
    return certify(RING8_GATE)
