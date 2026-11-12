import { test as base, expect, type Page } from "@playwright/test";

import { stateFile, type ROLES } from "./global-setup";

export type Role = (typeof ROLES)[number];

/**
 * Sign in through the API in this page's own cookie jar. For the rare test that must set up the
 * page before navigating (init scripts); everything else uses the `as` fixture.
 */
export async function signIn(page: Page, role: Role): Promise<void> {
  const response = await page.request.post("/api/auth/demo-login", { data: { username: role } });
  expect(response.ok(), `demo login as ${role}`).toBeTruthy();
}

type Fixtures = {
  /** A page in a context signed in as the given demo user (cookie from global setup), on home. */
  as: (role: Role) => Promise<Page>;
};

export const test = base.extend<Fixtures>({
  as: async ({ browser, contextOptions }, provide) => {
    const contexts: Array<Awaited<ReturnType<typeof browser.newContext>>> = [];
    await provide(async (role) => {
      const context = await browser.newContext({
        ...contextOptions,
        storageState: stateFile(role),
      });
      contexts.push(context);
      const page = await context.newPage();
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      return page;
    });
    await Promise.all(contexts.map((c) => c.close()));
  },
});

export { expect };
