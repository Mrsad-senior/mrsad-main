/**
 * Settings the Cloudflare deployment must be built with.
 *
 * Vite inlines `VITE_*` variables when it builds, so on Cloudflare they are build variables, not
 * Worker runtime variables. Only the Cloudflare build (`npm run build`, Vite mode `cloudflare`)
 * requires them; the build FastAPI serves (`npm run build:gateway`), dev and tests do not.
 */
export const REQUIRED_ENV = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY'] as const;

export type RequiredEnv = (typeof REQUIRED_ENV)[number];

/** The required variables that are missing or blank, so the page can say so instead of breaking. */
export function missingEnv(
  env: Partial<Record<RequiredEnv | 'MODE', string>> = import.meta.env,
): RequiredEnv[] {
  if (env.MODE !== 'cloudflare') return [];
  return REQUIRED_ENV.filter((name) => !env[name]?.trim());
}
