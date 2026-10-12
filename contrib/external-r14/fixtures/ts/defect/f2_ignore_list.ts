// Fixture F2 — hand translation of the second upheld finding of the Python run:
// llm-guard `transformers_recognizer.py:308`, class B (principal waiver).
//
// SYNTHETIC, as F1. The shape: of the branches that drop a detection, the one
// driven by an operator-supplied ignore list is the only one that leaves no
// trace. The bound obligation is not engaged for a waiver, because a waiver has
// no evidence strength to consult. The audit obligation is.

interface Entity { text: string; score: number; label: string; }

declare const logger: { debug(msg: string, e?: unknown): void };
declare const CONFIDENCE_THRESHOLD: number;

export function filterEntities(entities: Entity[], ignoreList: string[]): Entity[] {
  const kept: Entity[] = [];
  for (const entity of entities) {
    if (ignoreList.includes(entity.text)) {
      continue;
    }
    if (entity.score < CONFIDENCE_THRESHOLD) {
      logger.debug("dropping entity below confidence threshold", entity);
      continue;
    }
    kept.push(entity);
  }
  return kept;
}
