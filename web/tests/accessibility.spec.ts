import { expectNoSeriousViolations } from "./support/axe";
import { expect, test } from "./support/fixtures";
import { LoginPage, NewNotePage, ReviewPage } from "./support/pages";

test.describe("accessibility (axe, WCAG 2.1 AA)", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`login, ward, record, review and patient pages (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/login");
      await expect(page.getByText("Operational")).toBeVisible();
      await expectNoSeriousViolations(page);

      await new LoginPage(page).signInAs(/Nurse.*Nora/, "Ward 3A");
      await expectNoSeriousViolations(page);

      const notes = new NewNotePage(page);
      await notes.goto();
      await page.getByRole("tab", { name: "Type" }).click();
      await expectNoSeriousViolations(page);
      await notes.typeNote("Mrs. Keller, BP 168/96, pulse 380, sats 91% RA.");
      const review = new ReviewPage(page);
      await review.waitForDraft();
      await expect(page.getByText("Needs your attention")).toBeVisible();
      await expectNoSeriousViolations(page);

      await review.candidate(/Keller, Anna/).check();
      await review.confirm().click();
      await review.openPatient().click();
      await expect(page.getByRole("heading", { name: "Keller, Anna" })).toBeVisible();
      await expectNoSeriousViolations(page);
    });
  }

  test("audit log, metrics and quality pages", async ({ as }) => {
    const page = await as("auditor");
    await expectNoSeriousViolations(page);
    await page.getByRole("link", { name: "LLM metrics" }).click();
    await expect(page.getByRole("heading", { name: "LLM metrics" })).toBeVisible();
    await expectNoSeriousViolations(page);
    await page.getByRole("link", { name: "AI quality" }).click();
    await expect(page.getByRole("heading", { name: "Where it fails", exact: false })).toBeVisible();
    await expectNoSeriousViolations(page);
  });
});
