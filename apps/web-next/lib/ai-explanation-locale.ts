import type { AppLocale } from "./locale-context";

export type LocalizableAiExplanation = {
  summary?: unknown;
  summary_en?: unknown;
  summary_bn?: unknown;
  language?: unknown;
  advantages?: unknown;
  risks?: unknown;
  missing_information?: unknown;
  recommended_checks?: unknown;
};

const BANGLA_SCRIPT = /[\u0980-\u09ff]/;

function cleanText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function declaredLanguage(value: unknown): AppLocale | null {
  return value === "en" || value === "bn" ? value : null;
}

function textMatchesLocale(value: string, locale: AppLocale) {
  return locale === "bn" ? BANGLA_SCRIPT.test(value) : !BANGLA_SCRIPT.test(value);
}

/**
 * Selects the requested-language summary while remaining compatible with the
 * legacy `summary_bn` contract, which historically contained both languages.
 */
export function localizedAiSummary(
  explanation: LocalizableAiExplanation | null | undefined,
  locale: AppLocale,
  fallback: string,
) {
  if (!explanation) return fallback;

  const language = declaredLanguage(explanation.language);
  const candidates = locale === "bn"
    ? [explanation.summary_bn, explanation.summary, explanation.summary_en]
    : [explanation.summary_en, explanation.summary, explanation.summary_bn];

  for (const candidate of candidates) {
    const text = cleanText(candidate);
    if (!text) continue;
    if (textMatchesLocale(text, locale)) return text;
    if (language === locale && candidate === explanation.summary) return text;
  }

  return fallback;
}

/**
 * Prevents list content generated for one language from leaking into the
 * other language when old quote snapshots do not have locale metadata.
 */
export function localizedAiItems(
  value: unknown,
  locale: AppLocale,
  fallback: string,
  explanationLanguage?: unknown,
) {
  const items = Array.isArray(value)
    ? value.map(cleanText).filter((item): item is string => Boolean(item))
    : [];
  const language = declaredLanguage(explanationLanguage);

  if (language === locale && items.length) return items;
  if (language && language !== locale) return [fallback];

  const matching = items.filter((item) => textMatchesLocale(item, locale));
  return matching.length ? matching : [fallback];
}
