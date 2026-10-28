/**
 * Detector Playground samples.
 *
 * The bundled samples are neutral business texts only. Teams that want labelled evaluation
 * texts in the playground put them in `/assets/playground-samples.json` (shipped empty; see
 * docs/web-ui.md). That file is data provided by the deployment, parsed defensively here.
 */

export type SampleLang = 'en' | 'ar' | 'mixed';

export interface PlaygroundSample {
  id: string;
  label_en: string;
  label_ar: string;
  lang: SampleLang;
  text: string;
}

export const SAMPLES_URL = '/assets/playground-samples.json';
export const MAX_SAMPLES = 24;
export const MAX_SAMPLE_CHARS = 100_000;
const MAX_LABEL_CHARS = 60;

/** Fictional Najd Trading Co. texts; none of them contains instructions aimed at an AI model. */
export const BUILTIN_SAMPLES: PlaygroundSample[] = [
  {
    id: 'builtin-en',
    label_en: 'Business e-mail (English)',
    label_ar: 'بريد عمل (إنجليزي)',
    lang: 'en',
    text:
      'Hi team,\n\nThe Q3 invoice from our Riyadh supplier is attached. Please check the quantities against ' +
      'purchase order PO-2291 and confirm by Thursday. The quarterly sales report is due next week.\n\nThanks,\nNoura',
  },
  {
    id: 'builtin-ar',
    label_en: 'Business e-mail (Arabic)',
    label_ar: 'بريد عمل (عربي)',
    lang: 'ar',
    text:
      'مرحباً فريق المشتريات،\n\nنرجو مراجعة عرض السعر المرفق لشركة نجد للتجارة ومطابقة الكميات مع أمر الشراء ' +
      'رقم ٢٢٩١، وتزويدنا بتقرير المبيعات الشهري قبل يوم الخميس.\n\nمع الشكر والتقدير',
  },
  {
    id: 'builtin-mixed',
    label_en: 'Customer note (mixed)',
    label_ar: 'ملاحظة عميل (مختلط)',
    lang: 'mixed',
    text: 'Dear Najd team, شكراً على تعاونكم في الطلب الأخير. Please send the updated price list يوم الأحد إن أمكن.',
  },
];

const str = (v: unknown, max: number): string | null => (typeof v === 'string' && v.trim() ? v.trim().slice(0, max) : null);

/**
 * Accepts `{samples: [...]}` or a bare list. Each entry needs `text`; labels fall back to
 * each other and then to "Sample N". Invalid entries are skipped, never thrown on.
 */
export function parseSampleFile(raw: unknown): PlaygroundSample[] {
  const list = Array.isArray(raw)
    ? raw
    : raw && typeof raw === 'object' && Array.isArray((raw as { samples?: unknown }).samples)
      ? (raw as { samples: unknown[] }).samples
      : [];
  const out: PlaygroundSample[] = [];
  for (const entry of list) {
    if (out.length >= MAX_SAMPLES) break;
    if (!entry || typeof entry !== 'object') continue;
    const e = entry as Record<string, unknown>;
    const text = typeof e.text === 'string' ? e.text.slice(0, MAX_SAMPLE_CHARS) : '';
    if (!text.trim()) continue;
    const n = out.length + 1;
    const labelEn = str(e.label_en, MAX_LABEL_CHARS) ?? str(e.label, MAX_LABEL_CHARS) ?? str(e.label_ar, MAX_LABEL_CHARS) ?? `Sample ${n}`;
    const labelAr = str(e.label_ar, MAX_LABEL_CHARS) ?? labelEn;
    const lang: SampleLang = e.lang === 'ar' || e.lang === 'mixed' ? e.lang : 'en';
    out.push({ id: str(e.id, 64) ?? `team-${n}`, label_en: labelEn, label_ar: labelAr, lang, text });
  }
  return out;
}

export function sampleLabel(sample: PlaygroundSample, lang: 'en' | 'ar'): string {
  return lang === 'ar' ? sample.label_ar : sample.label_en;
}
