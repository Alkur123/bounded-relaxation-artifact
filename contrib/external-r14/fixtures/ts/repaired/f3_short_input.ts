// Control for F3: the same exemption, recorded.
//
// The length bound was already sound; what was missing was any trace that the
// check had been skipped. With the record in place a caller can tell an
// exempted prompt from a tested one, which is the whole of R14-b.

declare function tokenize(prompt: string): string[];
declare function perplexity(prompt: string): number;
declare const logger: { info(msg: string, ctx?: unknown): void };
declare const MIN_TOKENS: number;
declare const PERPLEXITY_LIMIT: number;

export function jailbreakHeuristics(prompt: string): boolean {
  const tokens = tokenize(prompt);
  let flagged = perplexity(prompt) > PERPLEXITY_LIMIT;
  if (tokens.length < MIN_TOKENS) {
    flagged = false;
    logger.info("perplexity check skipped: prompt below minimum length", {
      tokens: tokens.length,
    });
  }
  return flagged;
}
