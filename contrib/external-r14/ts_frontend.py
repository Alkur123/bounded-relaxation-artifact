"""Turn the TypeScript front end's syntax observations into shipped Candidates.

`ts_propose.mjs` walks TypeScript and JavaScript and reports what it saw. It
judges nothing. This module makes every judgement, and makes it by calling the
Python that already ships:

    polarity of a name          maryada_discover._polarity_of
    is this value benign        maryada_discover._is_benign_constant
    does the guard bound it     maryada_discover._GuardInspector
    does the block audit it     maryada_discover.AUDIT_* lexicons
    is this a detection list    maryada_discover.RISK_COLLECTION
    is this a principal waiver  maryada_discover.WAIVER_COLLECTION
    which rung owns the site    maryada_discover.classify_domain
                                (which imports anupalabdhi's own classifiers)

Nothing in this file restates a lexicon. That is the condition the
cross-language pre-registration froze, because two front ends that each decided
what a risk-carrying name is would drift, and the drift would be silent.

WHAT IS GENUINELY DIFFERENT, AND IT IS NOT NOTHING
--------------------------------------------------
Three things cannot be shared, and each is declared here rather than in a
footnote:

1. **Guard text is translated.** The JS side renders each condition as Python
   expression source so `classify_domain` and `_GuardInspector` can parse it. A
   condition it cannot render arrives as ``None`` and is dropped. A dropped
   guard cannot supply a bound, so this UNDER-reports bounds and therefore
   OVER-reports R14-a, which is the same direction the Python front end already
   errs in.
2. **Guard resolution is one level deep, not two.** The Python front end follows
   a guard into same-module helpers twice; the JS side inlines one level.
3. **The audit scan is re-expressed, not reused.** `_branch_audit_symbol` walks
   a Python AST. The JS side reports the calls, assignment targets and object
   keys in the relaxing block, and this module applies the SAME two lexicons to
   them. The traversal is different; the vocabulary is identical.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import subprocess
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from engine import maryada_discover as md            # noqa: E402

PROPOSER = HERE / "ts_propose.mjs"
NODE_MODULES = HERE / "node_modules" / "typescript"


class TsFrontendUnavailable(RuntimeError):
    """Node or the TypeScript package is missing. A reported state, not a crash."""


def available() -> Tuple[bool, str]:
    if not PROPOSER.exists():
        return False, f"missing {PROPOSER.name}"
    if not NODE_MODULES.exists():
        return False, "typescript not installed (run `npm ci` in contrib/external-r14)"
    try:
        out = subprocess.run(["node", "--version"], capture_output=True, text=True,
                             timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"node not runnable: {exc}"
    if out.returncode != 0:
        return False, "node not runnable"
    return True, out.stdout.strip()


# ═══════════════════════════════════════════════════════════════════════════
# The lexicons the JS side needs, exported from the shipped module
# ═══════════════════════════════════════════════════════════════════════════

def lexicon_payload() -> Dict[str, str]:
    """The two patterns the JS side must apply, taken from the shipped module.

    Only the hard-block declaration scan needs a lexicon on the JS side,
    because it has to decide which *declarations* to collect while it has the
    AST. Everything else is decided here.
    """
    return {
        "hard_block_declaration": md.HARD_BLOCK_DECLARATION.pattern,
        "category_token": md._CATEGORY_TOKEN.pattern,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Running the proposer
# ═══════════════════════════════════════════════════════════════════════════

def run_proposer(root: pathlib.Path, subject: str, *, timeout: int = 900) -> Dict:
    ok, why = available()
    if not ok:
        raise TsFrontendUnavailable(why)
    lex = HERE / ".lexicon.json"
    lex.write_text(json.dumps(lexicon_payload()), encoding="utf-8")
    cmd = ["node", str(PROPOSER), str(root), "--subject", subject,
           "--lexicon", str(lex)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                         encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise TsFrontendUnavailable(
            f"proposer exited {res.returncode}: {res.stderr.strip()[:300]}")
    return json.loads(res.stdout)


# ═══════════════════════════════════════════════════════════════════════════
# Judging what it saw, with the shipped lexicons
# ═══════════════════════════════════════════════════════════════════════════

import re                                                    # noqa: E402

# ── identifier normalisation, and why it is not a lexicon change ───────────
# The shipped lexicons anchor on `(?:^|_)` and `(?:$|_)`: snake_case word
# boundaries. TypeScript is camelCase. Measured on the validation fixtures,
# `is_injection` reads as risk-carrying and `isInjection` reads as nothing,
# for no reason other than where the language puts its word breaks. Without
# this the instrument would measure naming convention rather than semantics,
# and it would do so in the direction that makes the second language look
# clean.
#
# So identifiers are tokenised into the convention the lexicons are written
# in, BEFORE lookup. The vocabulary is untouched: not one word is added,
# removed or loosened, and the original spelling is what gets recorded on the
# candidate and reported to a reader. Recorded as a dated amendment in
# ADJUDICATION.md, and both figures -- with and without -- are reported,
# because the amendment was made after seeing a fixture result.
_CAMEL_HEAD = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_TAIL = re.compile(r"([a-z0-9])([A-Z])")

NORMALISE_IDENTIFIERS = True


def _snake(name: str) -> str:
    if not NORMALISE_IDENTIFIERS or not name:
        return name
    s = _CAMEL_HEAD.sub(r"\1_\2", name)
    return _CAMEL_TAIL.sub(r"\1_\2", s).lower()


class _SnakeNames(ast.NodeTransformer):
    """Rewrite identifiers in a parsed guard into the lexicons' convention."""

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = _snake(node.id)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        self.generic_visit(node)
        node.attr = _snake(node.attr)
        return node


def _parse(expr: Optional[str], *, normalise: bool = False) -> Optional[ast.expr]:
    if not expr:
        return None
    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None
    if normalise and NORMALISE_IDENTIFIERS:
        node = _SnakeNames().visit(node)
        ast.fix_missing_locations(node)
    return node


def _snake_text(expr: Optional[str]) -> Optional[str]:
    """The same guard, spelled in the lexicons' convention, for classify_domain."""
    node = _parse(expr, normalise=True)
    if node is None:
        return expr
    try:
        return ast.unparse(node)
    except Exception:                        # pragma: no cover - defensive
        return expr


def _bound_of(guards_py: Sequence[Optional[str]],
              helper_exprs: Sequence[Dict]) -> Tuple[Optional[str], Optional[str]]:
    """Run the shipped guard inspector over the translated conditions."""
    insp = md._GuardInspector({})
    for text in guards_py:
        node = _parse(text, normalise=True)
        if node is not None:
            insp.visit(node)
    if insp.bound_symbol is not None:
        return insp.bound_symbol, insp.bound_via
    # one level into a same-file helper, which is where a bound usually lives
    for helper in helper_exprs:
        node = _parse(helper.get("py"), normalise=True)
        if node is None:
            continue
        inner = md._GuardInspector({})
        inner.visit(node)
        if inner.bound_symbol is not None:
            return inner.bound_symbol, helper.get("via")
    return None, None


def _audit_of(raw: Dict) -> Optional[str]:
    """`_branch_audit_symbol`'s three rules, over the JS side's block report."""
    for call in raw.get("block_calls", []):
        leaf = _snake(call.split(".")[-1])
        if md.AUDIT_CALL_LEXICON.search(leaf):
            return call
    for name in raw.get("block_targets", []):
        if md.AUDIT_KEY_LEXICON.search(_snake(name)):
            return name
    for key in raw.get("block_keys", []):
        if md.AUDIT_KEY_LEXICON.search(_snake(key)):
            return key
    return None


def _accept(raw: Dict) -> Optional[Tuple[str, str]]:
    """Does this observation survive the shipped lexicons? -> (polarity, written)."""
    shape = raw.get("shape")
    target = raw.get("target") or ""

    if shape == "benign-write":
        polarity = md._polarity_of(_snake(target))
        if polarity is None:
            return None
        node = _parse(raw.get("written_py"))
        if node is None:
            return None
        written = md._is_benign_constant(node, polarity)
        return (polarity, written) if written is not None else None

    if shape == "narrowing":
        collection = raw.get("collection") or target
        if not md.RISK_COLLECTION.search(_snake(collection)):
            return None
        return "risk", raw.get("written_src") or "narrowed"

    if shape == "waiver-skip":
        containers = raw.get("membership_containers") or [target]
        if not any(md.WAIVER_COLLECTION.search(_snake(c)) for c in containers):
            return None
        return "permit", raw.get("written_src") or "check skipped for a listed subject"

    if shape == "discount":
        if md._polarity_of(_snake(target)) != "risk":
            return None
        return "risk", raw.get("written_src") or "discounted"

    return None


def to_candidates(payload: Dict, *, subject: str,
                  hard_block_vocab: Optional[Set[str]] = None) -> List[md.Candidate]:
    """Every judgement below is the shipped module's, called not copied."""
    vocab = hard_block_vocab or set()
    out: List[md.Candidate] = []
    for raw in payload.get("candidates", []):
        verdict = _accept(raw)
        if verdict is None:
            continue
        polarity, written = verdict

        guards_py = [g for g in raw.get("guards_py", [])]
        guards_src = raw.get("guards_src", [])
        parseable = [t for t in (_snake_text(g) for g in guards_py if g) if t]
        bound_symbol, bound_via = _bound_of(guards_py, raw.get("helper_exprs", []))
        audit_symbol = _audit_of(raw)

        # The floor reference is looked for in the guard text, as the Python
        # front end looks for it in the guard vocabulary.
        guard_words: Set[str] = set()
        for text in guards_py:
            node = _parse(text, normalise=True)
            if node is None:
                continue
            guard_words |= md._names_in(node)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if sub.value.strip():
                        guard_words.add(sub.value.strip())
        floor_ref = next(iter(sorted(guard_words & vocab)), None)

        out.append(md.Candidate(
            subject=subject,
            module=raw["module"],
            line=int(raw["line"]),
            function=raw.get("function") or "<module>",
            target=raw["target"],
            kind=raw.get("kind") or "assign",
            polarity=polarity,
            written=written,
            guards=guards_src,
            guard_lines=raw.get("guard_lines", []),
            bounded=bound_symbol is not None,
            bound_symbol=bound_symbol,
            bound_via=bound_via,
            audited=audit_symbol is not None,
            audit_symbol=audit_symbol,
            from_handler=bool(raw.get("from_handler")),
            reaches_hard_block=bool(vocab) and not floor_ref,
            hard_block_ref=floor_ref,
            domain=md.classify_domain(
                parseable,
                from_handler=bool(raw.get("from_handler")),
                params={_snake(p) for p in raw.get("params", [])},
                from_call={_snake(n) for n in raw.get("from_call", [])},
            ),
            shape=raw.get("shape") or "benign-write",
        ))
    return out


def discover(root: pathlib.Path, *, subject: str
             ) -> Tuple[List[md.Candidate], Dict[str, int], List[Dict], List[str]]:
    """The TS/JS twin of `maryada_discover.discover`, same return shape plus floors."""
    payload = run_proposer(pathlib.Path(root), subject)
    vocab = set(payload.get("hard_block_vocab") or [])
    cands = to_candidates(payload, subject=subject, hard_block_vocab=vocab)
    return (cands, payload.get("stats", {}),
            payload.get("hard_block_decls", []), sorted(vocab))


if __name__ == "__main__":                                  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    ap.add_argument("--subject", default=None)
    args = ap.parse_args()
    r = pathlib.Path(args.root)
    cands, stats, decls, vocab = discover(r, subject=args.subject or r.name)
    print(f"{stats.get('parsed', 0)} files parsed, {len(cands)} candidates")
    for c in cands:
        print(f"  {c.module}:{c.line} {c.shape:13s} {c.domain:10s} "
              f"{c.target:20s} bounded={c.bounded!s:5s} audited={c.audited!s:5s}")
    if vocab:
        print("floor vocabulary:", vocab)
