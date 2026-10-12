// Fixture F3 — hand translation of the third upheld finding of the Python run:
// nemo-guardrails `library/jailbreak_detection/heuristics/checks.py:89`, class A.
//
// SYNTHETIC, as F1 and F2. The shape the rung was built to separate: the BOUND
// obligation is satisfied and the reasoning is sound, because the attack class
// is not meaningful below the length threshold. The AUDIT obligation is not,
// so a caller cannot tell an exempted prompt from a tested one.

declare function tokenize(prompt: string): string[];
declare function perplexity(prompt: string): number;
declare const MIN_TOKENS: number;
declare const PERPLEXITY_LIMIT: number;

export function jailbreakHeuristics(prompt: string): boolean {
  const tokens = tokenize(prompt);
  let flagged = perplexity(prompt) > PERPLEXITY_LIMIT;
  if (tokens.length < MIN_TOKENS) {
    flagged = false;
  }
  return flagged;
}
