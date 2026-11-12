import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier/flat";
import boundaries from "eslint-plugin-boundaries";

/*
 * Layers (src/):
 *   app/       routes and layouts: may use features and shared
 *   features/  one folder per domain: may use shared and its own folder; another feature only
 *              through that feature's `keys` (cache invalidation) or `components` (composition)
 *   shared/    api client, ui, layout, lib, charts: may use shared only
 */
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  prettier,
  {
    plugins: { boundaries },
    settings: {
      "boundaries/include": ["src/**/*"],
      "boundaries/elements": [
        { type: "app", pattern: "src/app" },
        { type: "feature", pattern: "src/features/*", capture: ["name"] },
        { type: "shared", pattern: "src/shared" },
      ],
      "boundaries/files": [
        // A feature's public surface: its query hooks, cache keys and components.
        // api.ts and lib/ are private.
        { pattern: "src/features/*/hooks.ts", category: "hooks" },
        { pattern: "src/features/*/keys.ts", category: "keys" },
        { pattern: "src/features/*/components/**/*", category: "components" },
      ],
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          message:
            "{{ from.element.type }} may not import this from {{ to.element.type }}: a feature exposes only hooks, keys and components",
          policies: [
            {
              from: { element: { type: "app" } },
              allow: [
                { to: { element: { type: "shared" } } },
                { to: { element: { type: "feature" }, file: { categories: "components" } } },
              ],
            },
            {
              from: { element: { type: "shared" } },
              allow: { to: { element: { type: "shared" } } },
            },
            {
              from: { element: { type: "feature" } },
              allow: [
                { to: { element: { type: "shared" } } },
                // Inside one feature anything goes (internal). Another feature only through its
                // public surface: hooks, keys and components; never its api.ts or lib/.
                {
                  to: {
                    element: { type: "feature" },
                    file: { categories: { anyOf: ["hooks", "keys", "components"] } },
                  },
                },
              ],
            },
          ],
        },
      ],
    },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "playwright-report/**",
    "test-results/**",
  ]),
]);

export default eslintConfig;
