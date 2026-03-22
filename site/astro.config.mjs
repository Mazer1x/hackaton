// @ts-check
// Auto-updated by init_project_node (repo_name → base). Safe to edit.
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
// trailingSlash: static hosts (nginx) map /repo/history/ → history/index.html; /repo/history often 404.
export default defineConfig({
  base: '/site',
  trailingSlash: "always",
  vite: {
    plugins: [tailwindcss()]
  }
});
