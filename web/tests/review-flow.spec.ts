import { expect, test } from "./support/fixtures";
import { NewNotePage, ReviewPage } from "./support/pages";

test("nurse uploads a voice note, reviews the draft and confirms it", async ({ as }) => {
  const page = await as("nurse");
  await page
    .getByRole("link", { name: /Record note/ })
    .first()
    .click();
  await new NewNotePage(page).uploadFixture();

  // The fixture says "Mrs. Anna Keller, blood pressure 150 over 90, pulse 88."
  const review = new ReviewPage(page);
  await review.waitForDraft();
  await expect(page.getByText("Ready for review")).toBeVisible();
  await expect(page.locator("mark", { hasText: /blood pressure 150 over 90/i })).toBeVisible();
  await expect(review.candidate(/Keller, Anna/)).toBeChecked();
  await expect(review.vital("Systolic BP")).toHaveValue("150");
  await expect(page.getByText("Warning").first()).toBeVisible();

  // Correct the pulse, then confirm (saves the edit as a new version first).
  await review.vital("Heart rate").fill("92");
  await review.confirm().click();
  await expect(review.confirmed()).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Note confirmed" })).toBeVisible();
  await expect(page.getByText("Edited by nurse v2")).toBeVisible();
});

test("typed note with an ambiguous name requires choosing the patient", async ({ as }) => {
  const page = await as("nurse");
  const notes = new NewNotePage(page);
  await notes.goto();
  await notes.typeNote("Mrs. Keller, temperature 38.6, sats 93 percent. Feeling dizzy.");

  const review = new ReviewPage(page);
  await expect(page.getByText("Several patients could match. Choose the right one.")).toBeVisible();
  await expect(review.confirm()).toBeDisabled();
  await review.candidate(/Keller, Hanna/).check();
  await expect(review.confirm()).toBeEnabled();
  await review.confirm().click();
  await expect(review.confirmed()).toBeVisible();
});

test("a ward 3B nurse cannot open a ward 3A patient", async ({ as }) => {
  const page = await as("nurse_b");
  const patients = await page.request.get("/api/patients?ward=3A");
  expect(patients.status()).toBe(403);
  expect((await patients.json()).code).toBe("forbidden");
});

test("a spoken self-correction is extracted and pointed out for review", async ({ as }) => {
  const page = await as("nurse");
  const notes = new NewNotePage(page);
  await notes.goto();
  await page.getByRole("tab", { name: "Type" }).click();
  await page.getByRole("button", { name: "Self-correction" }).click();
  await page.getByRole("button", { name: "Create draft" }).click();
  const review = new ReviewPage(page);
  await review.waitForDraft();
  const systolic = review.vital("Systolic BP");
  await expect(systolic).toHaveValue("145");
  await expect(systolic).toHaveAccessibleDescription("Corrected while dictating: 140 → 145");
  await expect(review.vital("Diastolic BP")).toHaveValue("85");
});
