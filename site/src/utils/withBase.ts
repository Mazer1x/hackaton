/**
 * Ссылки под Astro `base` и `trailingSlash: 'always'`.
 * Используйте import.meta.env.BASE_URL — не хардкодьте slug репозитория.
 */
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const root = base.endsWith("/") ? base : `${base}/`;
  const clean = path.replace(/^\/+/, "").replace(/\/+$/, "");
  if (!clean) {
    return root;
  }
  return `${root}${clean}/`;
}
