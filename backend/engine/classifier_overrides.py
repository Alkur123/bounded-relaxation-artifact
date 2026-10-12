"""Classifier overrides — loaded from data/known_misclassifications.json.

Documented in docs/CLASSIFIER_OVERRIDES.md. Honors AEGIS_DISABLE_OVERRIDES=1
to bypass entirely (used for benchmark runs). One-time JSON load at import time.

Public API:
    apply_overrides(query, semantic, framing, distress, original_query)
        → (semantic, distress)   # mutated copies, override path applied

The pipeline calls this once between classification and decision. Without
overrides the pipeline still works — accuracy drops by the +8.2pp delta
documented in CLASSIFIER_OVERRIDES.md.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "data" / "known_misclassifications.json"

# ── Bounded relaxation (added 2026-08-17) ────────────────────────────────────
# Finding: docs/FINDING_2026-08-17_UNBOUNDED_RELAXATION.md, probe at
# eval/override_monotonicity_probe.py.
#
# Every demotion below used to be guarded by a substring match and a category
# equality and nothing else, so a phrase match released a classification at ANY
# confidence, including 1.00, and fifteen of the rules target SELF_HARM or
# SEXUAL, which engine/rta.py declares hard-block and describes as categories
# "admin authority does not reach". This module was an undocumented path that
# did reach them.
#
# CLASSIFIER_OVERRIDES.md states the security argument for the unconditional
# table as "phrase-specific enough that adversarial rewording cannot collide
# with the override". That argument is about REWORDING. The guard is `in`, so
# APPENDING a trap phrase to an unrelated request also collides, and appending
# is not rewording. The doc's argument does not cover the mechanism it defends.
#
# The fix is a ceiling, not a refusal, because the table is legitimate: these
# are real misclassifications and "my phone battery is dying" genuinely was a
# SELF_HARM false positive. An idiom collision is a LOW-confidence artifact of
# surface-vocabulary overlap. A high-confidence harmful classification is not
# something an idiom should be able to excuse, whatever phrase is present.
#
# Structure mirrors calibration.benign_ceiling_for, which solved the same
# problem for the Trikala gate: one ceiling for ordinary categories, a stricter
# one for the always-block set. Note the QUANTITY DIFFERS and the constants are
# therefore not shared: calibration ceilings bound p_harm, where LOW means
# benign; these bound the classifier's confidence IN THE HARMFUL LABEL, where
# HIGH means confidently harmful. Do not copy 0.35/0.05 across.
#
# THE DEFAULTS ARE DECLARED, NOT FITTED, and are deliberately generous so this
# change alters no behaviour anyone has observed: every existing test in
# tests/test_classifier_overrides.py exercises confidences between 0.3 and 0.6,
# and the uplift table's own "high but not certain" constant is 0.88. Tightening
# them needs the real false-positive confidence distribution, which is measured
# by running the demo corpus, and is recorded as owed in the finding.
_DEFAULT_OVERRIDE_CEILING = 0.95
_HARD_BLOCK_OVERRIDE_CEILING = 0.70

#: Kept in sync with engine/rta.py HARD_BLOCK_CATEGORIES and
#: semantic_engine._HARD_BLOCK_CATEGORIES. Duplicated rather than imported
#: because engine/__init__ eagerly loads FAISS and ONNX, and this module is
#: deliberately importable on its own; test_classifier_overrides asserts the
#: two agree so a drift is caught rather than assumed away.
HARD_BLOCK_CATEGORIES = frozenset({"SELF_HARM", "SEXUAL"})


def override_ceiling_for(category: Optional[str]) -> float:
    """Confidence at or above which no override may demote `category`."""
    if category in HARD_BLOCK_CATEGORIES:
        try:
            return float(os.environ.get("OVERRIDE_HARD_BLOCK_CEILING",
                                        _HARD_BLOCK_OVERRIDE_CEILING))
        except ValueError:
            return _HARD_BLOCK_OVERRIDE_CEILING
    try:
        return float(os.environ.get("OVERRIDE_CEILING", _DEFAULT_OVERRIDE_CEILING))
    except ValueError:
        return _DEFAULT_OVERRIDE_CEILING


def _may_demote(sem: dict) -> bool:
    """False when the evidence is too strong for a phrase match to excuse."""
    try:
        conf = float(sem.get("confidence", 0.0))
    except (TypeError, ValueError):
        # An unreadable confidence is not evidence of weakness. Fail closed:
        # refuse the relaxation rather than granting it on a parse error.
        return False
    return conf < override_ceiling_for(sem.get("category"))


@lru_cache(maxsize=1)
def _load_overrides() -> dict:
    """Read the override table from disk. Cached for the process lifetime."""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(
            "classifier_overrides loaded (version=%s, rules=%d)",
            data.get("version", "?"),
            sum(
                len(s.get("rules", []) or s.get("phrases", []))
                for s in data.values() if isinstance(s, dict)
            ),
        )
        return data
    except Exception as e:
        logger.warning("classifier_overrides load failed (%s) — running ungated", e)
        return {}


def overrides_disabled() -> bool:
    """True if benchmark / production mode should skip overrides."""
    return os.environ.get("AEGIS_DISABLE_OVERRIDES", "").strip().lower() in {
        "1", "true", "yes"
    }


def apply_overrides(
    *,
    original_query: str,
    semantic: dict,
    framing: Optional[dict] = None,
    distress: Optional[dict] = None,
) -> tuple[dict, Optional[dict]]:
    """Apply demo-mode classifier overrides. No-op if disabled.

    Returns (semantic, distress) — both are new dicts (input not mutated).
    """
    if overrides_disabled():
        return dict(semantic), (dict(distress) if distress else distress)

    data = _load_overrides()
    if not data:
        return dict(semantic), (dict(distress) if distress else distress)

    sem = dict(semantic)
    dist = dict(distress) if distress else distress
    q_lc = (original_query or "").lower()
    is_protective = bool(framing and framing.get("is_protective"))

    # 1. protective_framing_required — gated by intent_guard
    if is_protective:
        for rule in data.get("protective_framing_required", {}).get("rules", []):
            if rule["phrase"] in q_lc and sem.get("category") == rule["wrong_category"]:
                _demote_to_safe(sem, reason=f"override:framed:{rule['domain']}")
                break

    # 2. unconditional — phrase-specific enough to be safe without gating
    for rule in data.get("unconditional", {}).get("rules", []):
        if rule["phrase"] in q_lc and sem.get("category") == rule["wrong_category"]:
            _demote_to_safe(sem, reason=f"override:unconditional:{rule['domain']}")
            break

    # 3. vocabulary_traps — idiom collisions
    for rule in data.get("vocabulary_traps", {}).get("rules", []):
        if rule["phrase"] in q_lc and sem.get("category") == rule["wrong_category"]:
            _demote_to_safe(sem, reason=f"override:idiom:{rule['idiom_for']}")
            break
    # The ceiling is enforced inside _demote_to_safe rather than at each of the
    # three call sites above. Deliberate: a fourth table added later inherits
    # the bound automatically, where three copies of an `if` would not. The
    # `break` still fires on a refused match, so a refusal does not fall through
    # to a later rule and demote by a different name.

    # 4. sexual_targeting_uplifts — UP-classify under-classified harmful content
    if sem.get("category") == "SAFE":
        uplift = data.get("sexual_targeting_uplifts", {})
        for phrase in uplift.get("phrases", []):
            if phrase in q_lc:
                sem["category"] = uplift.get("target_category", "SEXUAL")
                sem["confidence"] = uplift.get("confidence_assigned", 0.88)
                sem.setdefault("override_reason", f"uplift:{phrase}")
                break

    # 5. distress_idiom_exclusions — zero out passive distress on idioms
    #
    # SAME SHAPE AS THE DEMOTIONS ABOVE, AND DELIBERATELY BOUNDED DIFFERENTLY.
    # Found 2026-08-17 while re-reading after fixing the category path, which
    # had missed this: an idiom phrase erases a passive-self-harm signal at ANY
    # strength, and per CLASSIFIER_OVERRIDES.md the effect is to prevent a HITL
    # escalation. So this suppresses a human review, on the highest-stakes
    # signal in the system.
    #
    # A strength ceiling like the one on the categories would be WRONG here and
    # the difference is worth stating, because copying it across looked obvious.
    # The classifier's confidence and this detector's strength are not the same
    # quantity. CLASSIFIER_OVERRIDES.md records that first-person distress is
    # "tuned aggressive" and that "idiom matches [are] inevitable", and the
    # shipped regression test pins a GENUINE idiom, "my phone battery is dying",
    # at strength 0.85. High strength is therefore not evidence of real distress
    # the way high classifier confidence is evidence of real harm, and a 0.70
    # ceiling would delete a true false-positive fix.
    #
    # So the load-bearing change here is OBSERVABILITY, not the bound. A
    # suppression is recorded rather than vanishing, which is apavada's second
    # floor and the thing that let the category defect survive unnoticed. The
    # ceiling below is near-inert by construction and is NOT presented as the
    # safety property: it closes only the degenerate case. The real bound needs
    # the strength distribution of genuine idiom collisions, which has not been
    # measured, and that measurement is owed.
    if dist and dist.get("is_passive_self_harm"):
        for phrase in data.get("distress_idiom_exclusions", {}).get("phrases", []):
            if phrase in q_lc:
                try:
                    strength = float(dist.get("strength", 0.0))
                except (TypeError, ValueError):
                    strength = 1.0        # unreadable: fail closed, keep the signal
                try:
                    ceiling = float(os.environ.get("DISTRESS_EXCLUSION_CEILING", "0.99"))
                except ValueError:
                    ceiling = 0.99
                if strength >= ceiling:
                    dist = dict(dist)
                    dist["exclusion_audit"] = {
                        "outcome": "refused", "phrase": phrase,
                        "strength": strength, "ceiling": ceiling,
                    }
                    logger.warning(
                        "distress idiom exclusion refused: strength %.3f at or "
                        "above ceiling %.3f (phrase %r)", strength, ceiling, phrase)
                    break
                dist = {
                    "is_passive_self_harm": False, "strength": 0.0, "signals": {},
                    "exclusion_audit": {
                        "outcome": "granted", "phrase": phrase,
                        "strength_was": strength, "ceiling": ceiling,
                    },
                }
                break

    return sem, dist


def _demote_to_safe(sem: dict, *, reason: str) -> None:
    """Demote a category to SAFE in-place, IF the evidence is weak enough.

    Two obligations, both from engine/apavada.py's account of when an exception
    may defeat a rule. That module states them and is imported by nothing but
    its own test, so they are enforced here directly:

      * a relaxation may not cross a hard-block floor unexamined. Enforced by
        the stricter ceiling `override_ceiling_for` returns for those
        categories.
      * "an unaudited relaxation is indistinguishable from a hole." So every
        outcome, granted or refused, is recorded on the dict under
        `override_audit`, and a refusal on a hard-block category is also
        logged at WARNING. Silence is what made this reachable for as long as
        it was.

    A refusal leaves the classification exactly as it was. It does not escalate,
    because a phrase match is not evidence of harm and inventing severity from a
    refused excuse would be its own defect.
    """
    prior_conf = sem.get("confidence", 0.5)
    prior_cat = sem.get("category")

    if not _may_demote(sem):
        ceiling = override_ceiling_for(prior_cat)
        sem["override_audit"] = {
            "outcome": "refused",
            "reason": reason,
            "category_held": prior_cat,
            "confidence": prior_conf,
            "ceiling": ceiling,
            "hard_block": prior_cat in HARD_BLOCK_CATEGORIES,
        }
        if prior_cat in HARD_BLOCK_CATEGORIES:
            logger.warning(
                "override refused on hard-block category %s: confidence %.3f "
                "at or above ceiling %.3f (rule %s)",
                prior_cat, prior_conf, ceiling, reason,
            )
        return

    sem["category"] = "SAFE"
    sem["confidence"] = max(0.65, 1.0 - prior_conf)
    sem.setdefault("override_reason", reason)
    sem["override_audit"] = {
        "outcome": "granted",
        "reason": reason,
        "category_was": prior_cat,
        "confidence": prior_conf,
        "ceiling": override_ceiling_for(prior_cat),
        "hard_block": prior_cat in HARD_BLOCK_CATEGORIES,
    }


def stats() -> dict:
    """Telemetry for /api/stats — shows whether overrides are active."""
    data = _load_overrides()
    return {
        "loaded": bool(data),
        "version": data.get("version"),
        "disabled": overrides_disabled(),
        "rule_counts": {
            "protective_framing_required": len(data.get("protective_framing_required", {}).get("rules", [])),
            "unconditional":               len(data.get("unconditional", {}).get("rules", [])),
            "vocabulary_traps":            len(data.get("vocabulary_traps", {}).get("rules", [])),
            "sexual_targeting_uplifts":    len(data.get("sexual_targeting_uplifts", {}).get("phrases", [])),
            "distress_idiom_exclusions":   len(data.get("distress_idiom_exclusions", {}).get("phrases", [])),
        },
    }
